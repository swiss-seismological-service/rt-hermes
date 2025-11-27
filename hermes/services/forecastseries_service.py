import asyncio
import logging
from uuid import UUID

from prefect.exceptions import ObjectNotFound
from prefect.runner import Runner

from hermes.flows.forecast_runner import forecast_runner
from hermes.flows.forecastseries_scheduler import (
    DEPLOYMENT_NAME,
    delete_deployment_schedule,
    get_existing_deployment_schedules)
from hermes.flows.modelrun_handler import default_model_runner
from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.repositories.types import DuplicateError
from hermes.schemas import EStatus, ForecastSeriesConfig

logger = logging.getLogger('prefect.hermes')


def get_forecastseries_oid(name_or_id: str):
    """
    Takes the name or ID of a Forecast Series, checks if it exists,
    and returns the ID.
    """
    try:
        return UUID(name_or_id, version=4)
    except ValueError:
        with DatabaseSession() as session:
            forecastseries_db = ForecastSeriesRepository.get_by_name(
                session, name_or_id)

        if not forecastseries_db:
            raise ValueError(f'ForecastSeries "{name_or_id}" not found.')

        return forecastseries_db.oid


def create_forecastseries(name, fseries_config, project_oid):
    forecast_series = ForecastSeriesConfig(name=name,
                                           status=EStatus.PENDING,
                                           project_oid=project_oid,
                                           **fseries_config)
    try:
        with DatabaseSession() as session:
            forecast_series_out = ForecastSeriesRepository.create(
                session, forecast_series)

        return forecast_series_out
    except DuplicateError:
        raise ValueError(f'ForecastSeries with name "{name}" already exists,'
                         ' please choose a different name.')


def update_forecastseries(fseries_config: dict,
                          forecastseries_oid: UUID,
                          force: bool = False):

    new_forecastseries = ForecastSeriesConfig(oid=forecastseries_oid,
                                              **fseries_config)

    # the following fields should generally not be updated,
    # check whether they are being updated and raise an exception
    # if not forced
    if not force:
        with DatabaseSession() as session:
            old_forecastseries = ForecastSeriesRepository.get_by_id(
                session, forecastseries_oid)

        protected_fields = ['project_oid',
                            'status',
                            'observation_starttime',
                            'observation_endtime',
                            'bounding_polygon',
                            'depth_min',
                            'depth_max',
                            'seismicityobservation_required',
                            'injectionobservation_required',
                            'injectionplan_required']

        for field in protected_fields:
            if field in fseries_config.keys():
                if getattr(old_forecastseries, field) != \
                        getattr(new_forecastseries, field):
                    raise Exception(
                        f'Field "{field}" should not be updated. '
                        'Use --force to update anyway.')

    try:
        with DatabaseSession() as session:
            forecast_series_out = ForecastSeriesRepository.update(
                session, new_forecastseries)
    except DuplicateError:
        raise ValueError(f'ForecastSeries with name "{fseries_config["name"]}"'
                         ' already exists, please choose a different name.')

    return forecast_series_out


def delete_forecastseries(forecastseries_oid: UUID):

    with DatabaseSession() as session:
        forecastseries = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)

    if not forecastseries:
        raise Exception(
            f'ForecastSeries with oid "{forecastseries_oid}" not found.')

    # check no forecasts are running
    with DatabaseSession() as session:
        forecasts = ForecastRepository.get_by_forecastseries(
            session, forecastseries_oid)

    if any(f.status == EStatus.RUNNING for f in forecasts):
        raise Exception(
            'ForecastSeries cannot be deleted because it is currently running.'
            ' Stop the forecasts first.')

    # delete schedule if exists
    if forecastseries.schedule_id:
        try:
            asyncio.run(delete_deployment_schedule(
                DEPLOYMENT_NAME.format(forecastseries_oid),
                forecastseries.schedule_id))
        except ObjectNotFound:
            # schedule has already been deleted on prefect side
            pass

    # delete forecastseries
    with DatabaseSession() as session:
        injectionplans = []
        for f in forecasts:
            ips = InjectionPlanRepository.get_ids_by_forecast(session, f.oid)
            injectionplans.extend(ips)

        # the deletion cascade takes care of most of the deletion
        ForecastSeriesRepository.delete(session, forecastseries_oid)

        # injectionplans belonging to modelruns aren't automatically
        # deleted by the cascade
        for ip in injectionplans:
            InjectionPlanRepository.delete(session, ip)


def serve_forecastseries(forecastseries_oid: UUID, concurrency_limit: int = 3):
    """
    Serve a ForecastSeries by creating deployments and starting a runner.

    Preserves existing schedules from the Prefect server across restarts
    and updates the schedule_id in the database if it changes.
    """
    with DatabaseSession() as session:
        forecastseries = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)

    if not forecastseries:
        raise ValueError(
            f'ForecastSeries with oid "{forecastseries_oid}" not found.')

    # Fetch existing schedules from Prefect server to preserve them
    deployment_name = DEPLOYMENT_NAME.format(forecastseries.name)
    existing_schedules = asyncio.run(
        get_existing_deployment_schedules(deployment_name))

    # Extract schedule objects for to_deployment()
    schedules_for_deployment = None
    if existing_schedules:
        logger.info(
            f"Preserving {len(existing_schedules)} existing schedule(s).")
        schedules_for_deployment = [s.schedule for s in existing_schedules]

    forecast_deployment = forecast_runner.to_deployment(
        name=forecastseries.name,
        parameters={"forecastseries_oid": str(forecastseries_oid)},
        concurrency_limit=concurrency_limit,
        schedules=schedules_for_deployment)

    modelrun_deployment = default_model_runner.to_deployment(
        name=forecastseries.name,
        concurrency_limit=concurrency_limit)

    # Use Runner directly to have control over deployment creation
    runner = Runner(pause_on_shutdown=False)
    runner.add_deployment(forecast_deployment)
    runner.add_deployment(modelrun_deployment)

    # Update DB with new schedule ID (if schedules were preserved)
    if existing_schedules:
        new_schedules = asyncio.run(
            get_existing_deployment_schedules(deployment_name))
        if new_schedules:
            with DatabaseSession() as session:
                ForecastSeriesRepository.update_schedule_id(
                    session, forecastseries_oid, new_schedules[0].id)

    # Start the runner (blocking)
    logger.info(f"Starting runner for '{forecastseries.name}'")
    asyncio.run(runner.start())
