import asyncio
from uuid import UUID

from hermes.flows.forecastseries_deployment import DEPLOYMENT_NAME
from hermes.flows.forecastseries_scheduler import delete_deployment_schedule
from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.repositories.types import DuplicateError
from hermes.schemas import EStatus, ForecastSeriesConfig


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
        except Exception:
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
