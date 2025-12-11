import logging
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from dateutil.rrule import SECONDLY, rrule
from prefect import get_run_logger
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.client.schemas.schedules import RRuleSchedule
from prefect.deployments import run_deployment

from hermes.flows.forecast_runner import forecast_runner
from hermes.flows.forecastseries_deployment import (DEPLOYMENT_NAME,
                                                    deployment_active,
                                                    deployment_exists)
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastSeriesRepository
from hermes.schemas.project_schemas import (ForecastSeries,
                                            ForecastSeriesSchedule)


class ForecastSeriesAttr:
    """
    Given an object, acts as a proxy to the attributes of the object.
    """

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, instance, type=None) -> object:
        return getattr(instance.forecastseries, self._name)

    def __set__(self, instance, value):
        setattr(instance.forecastseries, self._name, value)


class ForecastSeriesScheduler:

    schedule_starttime = ForecastSeriesAttr()
    schedule_interval = ForecastSeriesAttr()
    schedule_endtime = ForecastSeriesAttr()
    schedule_id = ForecastSeriesAttr()
    schedule_active = ForecastSeriesAttr()

    forecast_starttime = ForecastSeriesAttr()
    forecast_endtime = ForecastSeriesAttr()
    forecast_duration = ForecastSeriesAttr()

    def __init__(self, forecastseries_oid: UUID) -> None:
        try:
            self.logger = get_run_logger()
        except BaseException:
            self.logger = logging.getLogger('prefect.hermes')

        self.logger.debug('Initializing ForecastSeriesScheduler')

        self.session = DatabaseSession()
        self.forecastseries: ForecastSeries = \
            ForecastSeriesRepository.get_by_id(
                self.session, forecastseries_oid)

        self.deployment_name = DEPLOYMENT_NAME.format(self.forecastseries.name)

        self.now = datetime.now()

        if self.schedule_active is None:
            self.schedule_active = True

    def __del__(self) -> None:
        try:
            self.session.close()
        except BaseException:
            pass

    @property
    def schedule_info(self) -> ForecastSeriesSchedule:
        '''
        Returns the ForecastSeriesSchedule object of the ForecastSeries.
        '''
        return ForecastSeriesSchedule(
            schedule_starttime=self.schedule_starttime,
            schedule_interval=self.schedule_interval,
            schedule_endtime=self.schedule_endtime,
            schedule_id=self.schedule_id,
            schedule_active=self.schedule_active,
            forecast_starttime=self.forecast_starttime,
            forecast_endtime=self.forecast_endtime,
            forecast_duration=self.forecast_duration
        )

    async def check_deployment_exists(self) -> bool:
        '''
        Returns True if the deployment exists for the ForecastSeries.
        '''
        return await deployment_exists(self.deployment_name)

    async def check_deployment_active(self) -> bool:
        '''
        Returns True if the deployment is active for the ForecastSeries.
        '''
        return await deployment_active(self.deployment_name)

    async def check_prefect_schedule_exists(self) -> bool:
        '''
        Returns True if a prefect schedule exists for the ForecastSeries.
        '''
        if self.schedule_id is None:
            return False

        schedule = await get_deployment_schedule_by_id(
            self.deployment_name, self.schedule_id)
        return schedule is not None

    async def check_schedule_exists(self) -> bool:
        '''
        Returns True if a schedule exists for the ForecastSeries.
        '''
        try:
            self._check_schedule_validity(
                self.schedule_info.model_dump(exclude_unset=True))
            local_schedule = True
        except ValueError:
            local_schedule = False

        past_schedule = self._is_schedule_in_past(
            self.schedule_info.model_dump(exclude_unset=True))

        prefect_schedule = await self.check_prefect_schedule_exists()

        return (prefect_schedule and local_schedule) or \
            (local_schedule and past_schedule)

    async def create(self, schedule_config: dict) -> None:
        '''
        Creates or updates a schedule based on the given configuration.

        args:
            schedule_config: dict
                A dictionary with the configuration to create or update a
                schedule.
        '''
        deployment_exists = await self.check_deployment_exists()
        if not deployment_exists and not self._is_schedule_in_past(
                schedule_config):
            raise ValueError(
                'No deployment exists for this ForecastSeries. Please '
                'create one first with "hermes forecastseries serve".')

        if 'schedule_id' in schedule_config.keys():
            raise ValueError(
                'Schedule ID can not be set manually.'
            )

        self._check_schedule_validity(schedule_config)

        schedule_exists = await self.check_schedule_exists()
        if schedule_exists:
            raise ValueError(
                'Schedule already exists for this ForecastSeries. Use '
                '"delete" to remove the existing schedule before creating '
                'a new one.'
            )

        self._unset_schedule(False)
        self._update(schedule_config)
        if not self._is_schedule_in_past(schedule_config):
            await self._create_prefect_schedule(schedule_config)

            status = await self.check_deployment_active()
            if not status:
                self.logger.warning(
                    'The deployment is not active, to run the '
                    'schedule, activate the deployment with '
                    '"hermes forecastseries serve".')
        else:
            self.logger.info('No future schedule was created, '
                             'all forecasts are in the past.')

        self.logger.info('Schedule successfully created.')

    async def update_status(self, active: bool) -> None:
        """
        Updates the status of the schedule to active or inactive.
        If the schedule is active, it will be created or updated.
        If the schedule is inactive, it will be deleted.
        """
        schedule_exists = await self.check_schedule_exists()
        if not schedule_exists:
            raise ValueError(
                'No schedule exists for this ForecastSeries. '
                'Use `create_schedule` to create a new schedule.')

        prefect_schedule_exists = await self.check_prefect_schedule_exists()
        if prefect_schedule_exists:
            await update_deployment_schedule_status(
                self.deployment_name, self.schedule_id, active)

        self.schedule_active = active
        self._update()

    async def delete_schedule(self) -> None:
        schedule_exists = await self.check_schedule_exists()
        if not schedule_exists:
            raise ValueError(
                'No schedule exists for this ForecastSeries. ')

        prefect_schedule_exists = await self.check_prefect_schedule_exists()
        if prefect_schedule_exists:
            await delete_deployment_schedule(self.deployment_name,
                                             self.schedule_id)

        self._unset_schedule()

    async def run_past_forecasts(
            self, mode: Literal['local', 'deploy'] = 'local'):
        """
        If the forecast has a start time in the past, calculate the past
        forecast start and endtimes.
        """
        if self.schedule_active is False:
            self.logger.info('Schedule is deactivated, no past forecasts '
                             'will be executed.')
            return None

        if self.schedule_starttime > self.now:
            self.logger.info('No past forecasts to execute.')
            return None

        past_dates = list(self._build_rrule('past'))

        if mode == 'local':
            for d in past_dates:
                await forecast_runner(self.forecastseries.oid,
                                      starttime=d,
                                      mode=mode)
        elif mode == 'deploy':
            for d in past_dates:
                await run_deployment(
                    name=f'ForecastRunner/{self.forecastseries.name}',
                    parameters={'forecastseries_oid': self.forecastseries.oid,
                                'starttime': d,
                                'mode': mode},
                    timeout=0
                )

    def _update(self, config: dict | None = None, update_db: bool = True) \
            -> None:
        '''
        Updates the ForecastSeries object with the given configuration.

        args:
            config: dict
                A dictionary with the configuration to update.
            update_db: bool
                If True, the changes will be saved to the database.
        '''
        if config is not None:
            schedule = ForecastSeriesSchedule(**config)
            for key, value in schedule.model_dump(exclude_unset=True).items():
                setattr(self, key, value)

        if update_db:
            self.forecastseries = ForecastSeriesRepository.update(
                self.session, self.forecastseries)

    def _check_schedule_validity(self, schedule_config: dict) -> None:
        schedule = ForecastSeriesSchedule(**schedule_config)

        if schedule.schedule_starttime is None \
                or schedule.schedule_interval is None:
            raise ValueError(
                'Creating a schedule always requires a '
                'schedule_starttime, schedule_interval')

        if schedule.forecast_endtime is None \
                and schedule.forecast_duration is None:
            raise ValueError(
                'Creating a schedule always requires a '
                'forecast_endtime or/and a forecast_duration')

        if schedule.schedule_endtime is not None and \
            schedule.forecast_endtime is not None and \
                schedule.schedule_endtime >= schedule.forecast_endtime:
            raise ValueError(
                'Cannot create a schedule with a schedule endtime which is '
                'after the forecast endtime.')

        if schedule.forecast_starttime is not None and \
                schedule.schedule_endtime is not None and \
                schedule.forecast_starttime < schedule.schedule_endtime:
            raise ValueError(
                'Cannot create a schedule with a schedule endtime which is '
                'after the forecast starttime.')

        # if no schedule endtime is specified, check whether it is constrained
        # by the forecast starttime or forecast endtime and set explicitly
        if schedule.schedule_endtime is None and \
                schedule.forecast_starttime is not None:
            # no schedules should be created after the forecast starttime
            schedule.schedule_endtime = schedule.forecast_starttime
        elif schedule.schedule_endtime is None and \
                schedule.forecast_endtime is not None:
            # no schedules should be created after the forecast endtime
            schedule.schedule_endtime = schedule.forecast_endtime - \
                timedelta(seconds=schedule.schedule_interval - 1)

    def _is_schedule_in_past(self, schedule_config: dict) -> bool:
        """
        Check if the schedule is already fully in the past.

        I.e. returns False if forecasts will be created in the future.
        """
        schedule = ForecastSeriesSchedule(**schedule_config)

        if schedule.schedule_endtime is not None and \
                schedule.schedule_endtime < self.now:
            return True

        if schedule.schedule_endtime is None and \
                schedule.forecast_endtime is not None and \
                schedule.forecast_endtime < self.now:
            return True

        return False

    def _build_rrule(
            self,
            timeframe: Literal['all', 'past', 'future'] = 'all') -> rrule:
        '''
        Builds a rrule object based on the ForecastSeries attributes.

        args:
            timeframe:
                If `future`, the rrule will start at the next schedule
                interval after the current time.
                If `past`, the rrule will end at the current time.
        '''
        # create a schedule which starts at schedule_starttime
        rule = rrule(
            freq=SECONDLY,
            interval=self.schedule_interval,
            dtstart=self.schedule_starttime,
            until=self.schedule_endtime)

        if timeframe == 'future':
            if self.schedule_endtime and \
                    self.schedule_endtime < self.now:
                raise ValueError('No future schedule can be created, '
                                 'the schedule endtime is in the past.')

            rule = rrule(
                freq=SECONDLY,
                interval=self.schedule_interval,
                dtstart=rule.after(self.now, inc=False),
                until=self.schedule_endtime)

        elif timeframe == 'past':
            if self.schedule_starttime > self.now:
                raise ValueError('No past schedule can be created, '
                                 'the schedule startime is in the future.')

            if self.schedule_endtime is None or \
                    self.schedule_endtime > self.now:
                rule = rrule(
                    freq=SECONDLY,
                    interval=self.schedule_interval,
                    dtstart=self.schedule_starttime,
                    until=self.now)

        return rule

    def _unset_schedule(self, update_db: bool = True) -> None:
        '''
        Clears all schedule attributes and resets active to True.

        args:
            update_db: bool
                If True, the changes will be saved to the database.
        '''
        clear = {k: None for k in ForecastSeriesSchedule.__annotations__}
        clear['schedule_active'] = True
        self._update(clear, update_db)

    async def _create_prefect_schedule(self, schedule_config: dict) -> None:
        self._unset_schedule(False)
        self._update(schedule_config, update_db=False)
        rule = self._build_rrule()

        prefect_schedule = await add_deployment_schedule(
            self.deployment_name, rule, self.schedule_active)

        self.schedule_id = prefect_schedule.id

        # update data locally and on the database
        self._update()


async def add_deployment_schedule(
        deployment_name: str,
        schedule: rrule,
        active: bool = True) -> DeploymentSchedule:

    async with get_client() as client:
        schedule = RRuleSchedule(rrule=str(schedule))
        deployment = await client.read_deployment_by_name(deployment_name)

        # Add the new schedule to the deployment
        [schedule] = await client.create_deployment_schedules(
            deployment_id=deployment.id,
            schedules=[(schedule, active)]
        )
        return schedule


async def get_deployment_schedule_by_id(
        deployment_name: str,
        schedule_id: UUID) -> DeploymentSchedule:

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)
        schedules = await client.read_deployment_schedules(deployment.id)

    return next((s for s in schedules if s.id == schedule_id), None)


async def update_deployment_schedule_status(
        deployment_name: str,
        schedule_id: UUID,
        active: bool) -> None:

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)

        await client.update_deployment_schedule(
            deployment_id=deployment.id,
            schedule_id=schedule_id,
            active=active
        )


async def delete_deployment_schedule(
        deployment_name: str,
        schedule_id: UUID) -> None:

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)
        await client.delete_deployment_schedule(
            deployment_id=deployment.id,
            schedule_id=schedule_id
        )
