import asyncio
import json
import logging
from datetime import datetime, timedelta
from time import sleep
from typing import Literal
from uuid import UUID

from prefect import flow, get_run_logger, runtime, task
from prefect.client.orchestration import get_client
from prefect.deployments import run_deployment

from hermes.flows.modelrun_builder import ModelRunBuilder
from hermes.flows.modelrun_handler import default_model_runner
from hermes.io.hydraulics import HydraulicsDataSource
from hermes.io.injectionplans import InjectionPlanBuilder
from hermes.io.seismicity import SeismicityDataSource
from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.schemas import Forecast
from hermes.schemas.base import EInput, EStatus
from hermes.schemas.data_schemas import InjectionObservation, InjectionPlan
from hermes.schemas.model_schemas import ModelConfig
from hermes.schemas.project_schemas import ForecastSeries
from hermes.utils.prefect import futures_wait


class ForecastHandler:
    def __init__(self,
                 forecastseries_oid: UUID,
                 starttime: datetime | None = None,
                 endtime: datetime | None = None) -> None:

        try:
            self.logger = get_run_logger()
        except BaseException:
            self.logger = logging.getLogger('prefect.hermes')

        self.starttime: datetime
        self.endtime: datetime
        self.observation_starttime: datetime
        self.observation_endtime: datetime
        self.observation_window: int
        self.forecast: Forecast = None
        self.catalog_data_source: SeismicityDataSource = None
        self.hydraulic_data_source: HydraulicsDataSource = None

        with DatabaseSession() as session:
            self.forecastseries: ForecastSeries = \
                ForecastSeriesRepository.get_by_id(
                    session, forecastseries_oid)
            self.modelconfigs: list[ModelConfig] = \
                ForecastSeriesRepository.get_model_configs(
                session, forecastseries_oid)

        if not self.modelconfigs:
            self.logger.warning('No ModelConfigs associated with the '
                                'ForecastSeries. Exiting.')
            return None

        self._calculate_forecast_timebounds(starttime, endtime)

        self._create_forecast()

        try:
            # Retreive input data from various services
            task_so = self._create_seismicityobservation.submit()
            task_io = self._create_injectionobservation.submit()
            futures_wait([task_so, task_io])
            # necessary to raise exceptions from the tasks if any failed
            [task_so.result(), task_io.result()]

            self._create_injectionplan()

            self.builder = ModelRunBuilder(self.forecast,
                                           self.forecastseries,
                                           self.modelconfigs)
        except BaseException as e:
            with DatabaseSession() as session:
                ForecastRepository.update_status(session, self.forecast.oid,
                                                 EStatus.FAILED)
            raise e

    @task(name='SubmitModelRuns', cache_policy=None)
    def run(self, mode: Literal['local', 'deploy'] = 'local') -> None:
        if not self.builder.runs:
            self.logger.warning('No modelruns to run.')
            with DatabaseSession() as session:
                ForecastRepository.update_status(session, self.forecast.oid,
                                                 EStatus.CANCELLED)
            return None

        try:
            with DatabaseSession() as session:
                ForecastRepository.update_status(session, self.forecast.oid,
                                                 EStatus.RUNNING)
            if mode == 'local':
                for run in self.builder.runs:
                    default_model_runner(*run)
            else:
                running = []
                is_final = [False]

                for run in self.builder.runs:
                    running.append(run_deployment(
                        name=f'DefaultModelRunner/{self.forecastseries.name}',
                        parameters={'modelrun_info': run[0],
                                    'modelconfig': run[1]},
                        timeout=0
                    ))

                while not all(is_final):
                    is_final = [asyncio.run(check_flow_run_is_final(r.id))
                                for r in running]
                    sleep(10)

        except BaseException as e:
            with DatabaseSession() as session:
                ForecastRepository.update_status(session, self.forecast.oid,
                                                 EStatus.FAILED)
            raise e

        with DatabaseSession() as session:
            ForecastRepository.update_status(session, self.forecast.oid,
                                             EStatus.COMPLETED)

    @task(name='CreateForecast', cache_policy=None)
    def _create_forecast(self) -> None:
        """
        Creates the forecast in the database.
        """
        new_forecast = self.forecast or Forecast(
            forecastseries_oid=self.forecastseries.oid,
            status='PENDING',
            starttime=self.starttime,
            endtime=self.endtime,
        )
        with DatabaseSession() as session:
            self.forecast: Forecast = ForecastRepository.create(
                session, new_forecast)

    @task(name='CreateSeismicityObservation', cache_policy=None)
    def _create_seismicityobservation(self) -> None:
        """
        Gets the seismicity observation data and stores it to the database.
        """

        if self.forecastseries.seismicityobservation_required == \
                EInput.NOT_ALLOWED:
            self.forecast.seismicity_observation = None
            return None

        self.catalog_data_source = SeismicityDataSource.from_uri(
            self.forecastseries.fdsnws_url,
            self.observation_starttime,
            self.observation_endtime
        )

        with DatabaseSession() as session:
            self.forecast.seismicity_observation = \
                SeismicityObservationRepository.create_from_quakeml(
                    session,
                    self.catalog_data_source.get_quakeml(),
                    self.forecast.oid
                )

    @task(name='CreateInjectionObservation', cache_policy=None)
    def _create_injectionobservation(self) -> None:
        """
        Gets the injection observation data and stores it to the database.
        """
        if self.forecastseries.injectionobservation_required == \
                EInput.NOT_ALLOWED:
            self.forecast.injection_observation = None
            return None

        self.hydraulic_data_source = HydraulicsDataSource.from_uri(
            self.forecastseries.hydws_url,
            self.observation_starttime,
            self.observation_endtime
        )

        self.injection_observation = InjectionObservation(
            forecast_oid=self.forecast.oid,
            data=self.hydraulic_data_source.get_json()
        )
        with DatabaseSession() as session:
            self.forecast.injection_observation = \
                InjectionObservationRepository.create(
                    session,
                    self.injection_observation
                )

    @task(name='CreateInjectionPlan', cache_policy=None)
    def _create_injectionplan(self) -> None:
        """
        Gets the injection plan data and stores it to the database.
        """
        if self.forecastseries.injectionplan_required == \
                EInput.NOT_ALLOWED:
            self.forecastseries.injection_plans = None
            return None

        with DatabaseSession() as session:
            injection_plans = \
                InjectionPlanRepository.get_by_forecastseries(
                    session,
                    self.forecastseries.oid
                )

            if not injection_plans:
                if self.forecastseries.injectionplan_required == \
                        EInput.OPTIONAL:
                    self.forecastseries.injection_plans = None
                    return None
                else:
                    raise ValueError('No injection plans found for the '
                                     'ForecastSeries.')

            for idx, ip in enumerate(injection_plans):
                ip_builder = InjectionPlanBuilder(
                    json.loads(ip.template),
                    json.loads(self.forecast.injection_observation.data))
                plan = ip_builder.build(self.starttime, self.endtime)

                new_ip = InjectionPlan(
                    name=ip.name,
                    data=json.dumps([plan]),
                    template=ip.template
                )

                injection_plans[idx] = InjectionPlanRepository.create(
                    session, new_ip)

        self.forecastseries.injection_plans = injection_plans

    def _build_injectionplan(self) -> None:
        """
        Builds the injection plan data.
        """
        if self.forecastseries.injection_plans is None:
            return None

        for injection_plan in self.forecastseries.injection_plans:
            InjectionPlanBuilder(injection_plan.template,
                                 self.forecast.injection_observation.data)

    def _calculate_forecast_timebounds(self,
                                       starttime: datetime,
                                       endtime: datetime) -> None:
        """
        Sets the forecast start and end times, and observation times.

        starttime:  When running forecasts manually or catching up on a
                    schedule, the starttime should be passed as an argument.
                    Else, a fixed starttime can be set on the ForecastSeries.
                    If the forecasts are run on a schedule, the starttime
                    will be the scheduled start time of the flow run.
        endtime:    When running forecasts manually or catching up on a
                    schedule, the endtime should be passed as an argument.
                    Else, it is given by the two following fields on
                    the ForecastSeries:
                    forecast_duration, forecast_endtime.
        """
        # set start and endtime
        self.starttime = self.forecastseries.forecast_starttime or \
            starttime or \
            runtime.flow_run.scheduled_start_time

        if self.starttime.tzinfo is not None:
            self.starttime = self.starttime.replace(tzinfo=None)

        if self.forecastseries.forecast_starttime is not None and \
                self.starttime > self.forecastseries.forecast_starttime:
            raise ValueError(
                "Starttime can't be later than forecast_starttime.")

        # set endtime, forecast_duration takes precedence over forecast_endtime
        self.endtime = endtime or \
            (self.starttime
             + timedelta(seconds=self.forecastseries.forecast_duration)
             if self.forecastseries.forecast_duration else None) or \
            self.forecastseries.forecast_endtime
        # endtime can't be later than forecast_endtime
        if self.forecastseries.forecast_endtime is not None and \
                self.forecastseries.forecast_endtime < self.endtime:
            self.endtime = self.forecastseries.forecast_endtime

        if self.endtime.tzinfo is not None:
            self.endtime = self.endtime.replace(tzinfo=None)

        # set observation times from ForecastSeries
        self.observation_starttime = self.forecastseries.observation_starttime
        self.observation_endtime = self.forecastseries.observation_endtime or \
            self.starttime
        self.observation_window = self.forecastseries.observation_window

        if self.observation_starttime is not None and \
                self.observation_starttime.tzinfo is not None:
            self.observation_starttime = self.observation_starttime.replace(
                tzinfo=None)
        if self.observation_endtime.tzinfo is not None:
            self.observation_endtime = self.observation_endtime.replace(
                tzinfo=None)

        # user can't configure both observation times and observation window
        if (self.observation_starttime is not None
            or self.observation_endtime != self.starttime) and \
                self.observation_window is not None:
            raise ValueError("ForecastSeries can't have both observation "
                             "start/end time and observation_window configured.")

        # if observation window is configured, calculate observation start time
        if self.observation_window is not None:
            self.observation_starttime = self.starttime - \
                timedelta(seconds=self.observation_window)

        # Sanity Checks
        if self.observation_starttime == self.observation_endtime:
            raise ValueError("Observation start and end time can't be equal.")
        if self.observation_starttime > self.observation_endtime:
            raise ValueError("Observation start time can't be later than "
                             "observation end time.")

        if self.starttime == self.endtime:
            raise ValueError("Forecast start and end time can't be equal.")

        if self.starttime > self.endtime:
            raise ValueError("Forecast start time can't be later than "
                             "forecast end time.")


def generate_flow_run_name():
    """
    Try to use starttime to generate a name for the flow run.
    """

    parameters = runtime.flow_run.parameters
    start = parameters["starttime"] or \
        runtime.flow_run.scheduled_start_time or None

    if start:
        end = parameters["endtime"] or None
        if end:
            return f"Forecast-{start}-{end}"
        else:
            return f"Forecast-{start}"

    return f"Forecast-{parameters['forecastseries_oid']}"


@flow(name='ForecastRunner', flow_run_name=generate_flow_run_name)
def forecast_runner(forecastseries_oid: UUID,
                    starttime: datetime | None = None,
                    endtime: datetime | None = None,
                    mode: Literal['local', 'deploy'] = 'local') \
        -> ForecastHandler:
    forecasthandler = ForecastHandler(forecastseries_oid, starttime, endtime)
    forecasthandler.run(mode)
    return forecasthandler


async def check_flow_run_is_final(flow_run_id: UUID) -> bool:
    """
    Check if a flow run is in a final state.
    """
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=flow_run_id)
        return flow_run.state.is_final()
