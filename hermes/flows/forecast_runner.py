"""New flow-centric forecast runner."""
import asyncio
import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from prefect import flow, get_run_logger, runtime
from prefect.client.orchestration import get_client
from prefect.flow_runs import wait_for_flow_run

from hermes.flows.forecast_tasks import (build_injection_plans,
                                         fetch_injection_observation,
                                         fetch_seismicity_observation)
from hermes.flows.modelrun_builder import ModelRunBuilder
from hermes.flows.modelrun_handler import default_model_runner
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.schemas import Forecast, ForecastSeries
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


@flow(name='ForecastRunner', flow_run_name=generate_flow_run_name)
async def forecast_runner(
    forecastseries_oid: UUID,
    starttime: datetime | None = None,
    endtime: datetime | None = None,
    mode: Literal['local', 'deploy'] = 'local'
) -> Forecast:
    """
    Execute a forecast for a given ForecastSeries.

    This flow orchestrates all steps required to run a forecast.

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

    # Load ForecastSeries configuration
    logger.info(f"Loading ForecastSeries {forecastseries_oid}")

    with DatabaseSession() as session:
        modelconfigs = ForecastSeriesRepository.get_model_configs(
            session, forecastseries_oid)

        if not modelconfigs:
            logger.warning('No ModelConfigs associated with the '
                           'ForecastSeries. Exiting.')
            return None

        forecastseries: ForecastSeries = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)

    # Calculate time boundaries
    starttime, endtime, obs_start, obs_end = \
        calculate_forecast_timebounds(forecastseries,
                                      starttime,
                                      endtime,
                                      runtime.flow_run.scheduled_start_time)

    logger.info(f"Forecast period: {starttime} to {endtime}")
    logger.info(f"Observation period: {obs_start} to {obs_end}")

    # Create Forecast entry
    with DatabaseSession() as session:
        forecast: Forecast = ForecastRepository.create(
            session,
            Forecast(forecastseries_oid=forecastseries_oid,
                     status=EStatus.PENDING,
                     starttime=starttime,
                     endtime=endtime,
                     ))
    logger.info(f"Created forecast {forecast.oid}")

    try:
        # Fetch observations in parallel
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
        forecast.seismicity_observation = seismicity_task.result()
        forecast.injection_observation = injection_task.result()

        if forecast.seismicity_observation:
            logger.info("Seismicity observation: "
                        f"{forecast.seismicity_observation.oid}")
        if forecast.injection_observation:
            logger.info("Injection observation: "
                        f"{forecast.injection_observation.oid}")

        # Build injection plans
        forecastseries.injection_plans = build_injection_plans(
            forecastseries_oid,
            forecast.injection_observation,
            forecast.starttime,
            forecast.endtime,
            forecastseries.injectionplan_required
        )
        if forecastseries.injection_plans:
            logger.info(f"Created {len(forecastseries.injection_plans)} "
                        "injection plan(s)")

        # Create model runs
        builder = ModelRunBuilder(
            forecast,
            forecastseries,
            modelconfigs
        )

        if not builder.runs:
            logger.warning('No modelruns to execute.')
            forecast.status = update_forecast_status(forecast.oid,
                                                     EStatus.CANCELLED)
            return forecast

        logger.info(f"Prepared {len(builder.runs)} model run(s)")

        # Execute model runs
        logger.info(f"Executing models in {mode} mode")
        forecast.status = update_forecast_status(forecast.oid,
                                                 EStatus.RUNNING)

        if mode == 'local':
            for run in builder.runs:
                default_model_runner(*run)
        else:
            await _execute_deployed_models(forecastseries.name, builder.runs)

        # Mark as completed
        logger.info("Forecast execution completed successfully")
        forecast.status = update_forecast_status(
            forecast.oid, EStatus.COMPLETED)

    except Exception as e:
        logger.error(f"Forecast execution failed: {e}")
        forecast.status = update_forecast_status(forecast.oid, EStatus.FAILED)
        raise e

    return forecast


async def _execute_deployed_models(
    forecastseries_name: str,
    model_runs: list
) -> None:
    """
    Execute model runs as deployed flows and wait for completion.

    Args:
        forecastseries_name: Name of the ForecastSeries for deployment lookup
        model_runs: List of (DBModelRunInfo, ModelConfig) tuples

    Raises:
        Exception: If any model runs fail
    """
    async with get_client() as client:
        # Get deployment by name
        deployment = await client.read_deployment_by_name(
            f'DefaultModelRunner/{forecastseries_name}'
        )

        # Create all flow runs
        flow_runs = []
        for run in model_runs:
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters={'modelrun_info': run[0],
                            'modelconfig': run[1]}
            )
            flow_runs.append(flow_run)

        # Wait for all flow runs to complete
        finished_runs = await asyncio.gather(*[
            wait_for_flow_run(flow_run_id=fr.id) for fr in flow_runs
        ])

        # Check for failures
        failed = [fr for fr in finished_runs if fr.state.is_failed()]
        if failed:
            raise Exception(f"{len(failed)} model run(s) failed")
