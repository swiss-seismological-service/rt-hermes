"""New flow-centric forecast runner."""
import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from prefect import flow, get_run_logger, runtime

from hermes.flows.forecast_tasks import (build_injection_plans,
                                         execute_forecast_models,
                                         fetch_injection_observation,
                                         fetch_seismicity_observation)
from hermes.flows.modelrun_builder import ModelRunBuilder
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.schemas import Forecast
from hermes.schemas.base import EStatus
from hermes.services.forecast_service import (calculate_forecast_timebounds,
                                              update_forecast_status)
from hermes.utils.prefect import futures_wait


def generate_flow_run_name():
    """
    Generate a descriptive name for the flow run based on parameters.

    Returns:
        Formatted string with forecast times or forecastseries ID
    """
    parameters = runtime.flow_run.parameters
    start = parameters.get("starttime") or \
        runtime.flow_run.scheduled_start_time or None

    if start:
        end = parameters.get("endtime") or None
        if end:
            return f"Forecast-{start}-{end}"
        else:
            return f"Forecast-{start}"

    return f"Forecast-{parameters.get('forecastseries_oid')}"


@flow(name='RunForecast', flow_run_name=generate_flow_run_name)
def run_forecast(
    forecastseries_oid: UUID,
    starttime: datetime | None = None,
    endtime: datetime | None = None,
    mode: Literal['local', 'deploy'] = 'local'
) -> Forecast:
    """
    Execute a forecast for a given ForecastSeries.

    This flow orchestrates all steps required to run a forecast:
    1. Load configuration and calculate time boundaries
    2. Create forecast record
    3. Fetch observations (seismicity and injection) in parallel
    4. Build injection plans
    5. Create and execute model runs
    6. Update forecast status

    Args:
        forecastseries_oid: UUID of the ForecastSeries
        starttime: Optional manual forecast start time
        endtime: Optional manual forecast end time
        mode: Execution mode - 'local' or 'deploy'

    Returns:
        The completed Forecast object

    Raises:
        ValueError: If validation fails or required data is missing
        Exception: If any step in the forecast execution fails
    """
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    # Step 1: Load ForecastSeries configuration
    logger.info(f"Loading ForecastSeries {forecastseries_oid}")

    with DatabaseSession() as session:
        forecastseries = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)
        modelconfigs = ForecastSeriesRepository.get_model_configs(
            session, forecastseries_oid)

    if not modelconfigs:
        logger.warning('No ModelConfigs associated with the '
                       'ForecastSeries. Exiting.')
        return None

    # Step 2: Calculate time boundaries
    logger.info("Calculating forecast time boundaries")
    f_start, f_end, obs_start, obs_end = calculate_forecast_timebounds(
        forecastseries,
        starttime,
        endtime,
        runtime.flow_run.scheduled_start_time
    )

    logger.info(f"Forecast period: {f_start} to {f_end}")
    logger.info(f"Observation period: {obs_start} to {obs_end}")

    # Step 3: Create forecast record
    with DatabaseSession() as session:
        forecast = ForecastRepository.create(session, Forecast(
            forecastseries_oid=forecastseries_oid,
            status=EStatus.PENDING,
            starttime=starttime,
            endtime=endtime,
        ))

    logger.info(f"Created forecast {forecast.oid}")

    try:
        # Step 4: Fetch observations in parallel
        logger.info("Fetching observations")
        seismicity_task = fetch_seismicity_observation.submit(
            forecast.oid,
            forecastseries.fdsnws_url,
            obs_start,
            obs_end,
            forecastseries.seismicityobservation_required
        )

        injection_task = fetch_injection_observation.submit(
            forecast.oid,
            forecastseries.hydws_url,
            obs_start,
            obs_end,
            forecastseries.injectionobservation_required
        )

        # Wait for both to complete
        futures_wait([seismicity_task, injection_task])
        seismicity_obs_oid = seismicity_task.result()
        injection_obs_oid = injection_task.result()

        logger.info(f"Seismicity observation: {seismicity_obs_oid}")
        logger.info(f"Injection observation: {injection_obs_oid}")

        # Get injection observation data for plan building
        injection_obs_data = None
        if injection_obs_oid:
            with DatabaseSession() as session:
                from hermes.repositories.data import \
                    InjectionObservationRepository
                injection_obs = InjectionObservationRepository.get_by_id(
                    session, injection_obs_oid)
                injection_obs_data = injection_obs.data \
                    if injection_obs else None

        # Step 5: Build injection plans
        logger.info("Building injection plans")
        injection_plans = build_injection_plans(
            forecastseries_oid,
            injection_obs_data,
            f_start,
            f_end,
            forecastseries.injectionplan_required
        )
        logger.info(f"Created {len(injection_plans)} injection plan(s)")

        # Step 6: Create model runs
        logger.info("Creating model runs")
        # Attach injection plans to forecastseries for ModelRunBuilder
        forecastseries.injection_plans = injection_plans

        # Update forecast with observation OIDs for ModelRunBuilder
        with DatabaseSession() as session:
            forecast_with_obs = ForecastRepository.get_by_id(
                session, forecast.oid)

        builder = ModelRunBuilder(
            forecast_with_obs,
            forecastseries,
            modelconfigs
        )

        if not builder.runs:
            logger.warning('No modelruns to execute.')
            forecast = update_forecast_status(forecast.oid, EStatus.CANCELLED)
            return forecast

        logger.info(f"Prepared {len(builder.runs)} model run(s)")

        # Step 7: Execute model runs
        logger.info(f"Executing models in {mode} mode")
        forecast = update_forecast_status(forecast.oid, EStatus.RUNNING)

        execute_forecast_models(
            builder.runs,
            forecastseries.name,
            mode
        )

        # Step 8: Mark as completed
        logger.info("Forecast execution completed successfully")
        forecast = update_forecast_status(forecast.oid, EStatus.COMPLETED)

    except Exception as e:
        logger.error(f"Forecast execution failed: {e}")
        forecast = update_forecast_status(forecast.oid, EStatus.FAILED)
        raise e

    return forecast
