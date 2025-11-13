from datetime import datetime, timedelta
from uuid import UUID

from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastRepository
from hermes.schemas.base import EStatus
from hermes.schemas.project_schemas import ForecastSeries


def calculate_forecast_timebounds(
    forecastseries: ForecastSeries,
    starttime: datetime | None = None,
    endtime: datetime | None = None,
    scheduled_start_time: datetime | None = None
) -> tuple[datetime, datetime, datetime, datetime]:
    """
    Calculate forecast and observation time boundaries.

    Args:
        forecastseries: The ForecastSeries configuration
        starttime: Manual forecast start time (overrides scheduled/config)
        endtime: Manual forecast end time (overrides config)
        scheduled_start_time: Scheduled start time from flow runtime

    Returns:
        Tuple of (forecast_start, forecast_end,
        observation_start, observation_end)

    Raises:
        ValueError: If time validation fails
    """
    # Calculate forecast start time
    forecast_start = forecastseries.forecast_starttime or \
        starttime or \
        scheduled_start_time

    # Remove timezone info
    if forecast_start.tzinfo is not None:
        forecast_start = forecast_start.replace(tzinfo=None)

    # Validate against configured forecast_starttime
    if forecastseries.forecast_starttime is not None and \
            forecast_start > forecastseries.forecast_starttime:
        raise ValueError(
            "Starttime can't be later than forecast_starttime.")

    # Calculate forecast end time
    # forecast_duration takes precedence over forecast_endtime
    forecast_end = endtime or \
        (forecast_start
         + timedelta(seconds=forecastseries.forecast_duration)
         if forecastseries.forecast_duration else None) or \
        forecastseries.forecast_endtime

    # endtime can't be later than configured forecast_endtime
    if forecastseries.forecast_endtime is not None and \
            forecastseries.forecast_endtime < forecast_end:
        forecast_end = forecastseries.forecast_endtime

    # Remove timezone info
    if forecast_end.tzinfo is not None:
        forecast_end = forecast_end.replace(tzinfo=None)

    # Calculate observation times from ForecastSeries config
    observation_starttime = forecastseries.observation_starttime
    observation_endtime = forecastseries.observation_endtime or forecast_start
    observation_window = forecastseries.observation_window

    if observation_starttime is not None and \
            observation_starttime.tzinfo is not None:
        observation_starttime = observation_starttime.replace(tzinfo=None)
    if observation_endtime.tzinfo is not None:
        observation_endtime = observation_endtime.replace(tzinfo=None)

    # Validate observation config
    if (observation_starttime is not None
        or observation_endtime != forecast_start) and \
            observation_window is not None:
        raise ValueError("ForecastSeries can't have both observation "
                         "start/end time and observation_window configured.")

    # If observation window is configured, calculate observation start time
    if observation_window is not None:
        observation_starttime = forecast_start - \
            timedelta(seconds=observation_window)

    # Sanity checks
    if observation_starttime == observation_endtime:
        raise ValueError("Observation start and end time can't be equal.")
    if observation_starttime > observation_endtime:
        raise ValueError("Observation start time can't be later than "
                         "observation end time.")

    if forecast_start == forecast_end:
        raise ValueError("Forecast start and end time can't be equal.")

    if forecast_start > forecast_end:
        raise ValueError("Forecast start time can't be later than "
                         "forecast end time.")

    return forecast_start, forecast_end, \
        observation_starttime, observation_endtime


def update_forecast_status(forecast_oid: UUID, status: EStatus) -> EStatus:
    """
    Update the status of a forecast.

    Args:
        forecast_oid: UUID of the forecast
        status: New status to set

    Returns:
        Updated Forecast object
    """
    with DatabaseSession() as session:
        forecast = ForecastRepository.update_status(
            session, forecast_oid, status)
    return forecast.status


def delete_forecast(forecast_oid: UUID):
    with DatabaseSession() as session:

        injectionplans = InjectionPlanRepository.get_ids_by_forecast(
            session, forecast_oid)

        ForecastRepository.delete(session, forecast_oid)

        for ip in injectionplans:
            InjectionPlanRepository.delete(session, ip)

    return f"Forecast {forecast_oid} deleted."
