"""New flow-centric forecast runner."""
import asyncio
import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from prefect import flow, get_run_logger, runtime
from prefect.client.orchestration import get_client
from prefect.flow_runs import wait_for_flow_run
from prefect.futures import wait
from prefect.states import Completed, Failed

from hermes.flows.forecast_tasks import (build_injection_plans,
                                         fetch_injection_observation,
                                         fetch_seismicity_observation)
from hermes.flows.modelrun_handler import default_model_runner
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.repositories.results import ModelRunRepository
from hermes.schemas import (DBModelRunInfo, Forecast, ForecastSeries,
                            InjectionPlan, ModelConfig)
from hermes.schemas.base import EStatus
from hermes.schemas.result_schemas import ModelRun
from hermes.services.forecast_service import (calculate_forecast_timebounds,
                                              update_forecast_status)


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
            forecastseries.injectionobservation_required,
            forecastseries.model_settings.get('hydraulics_resample', None)
        )

        # Wait for both to complete
        wait([seismicity_task, injection_task])
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
        model_runs = prepare_model_runs(forecast, forecastseries, modelconfigs)

        if not model_runs:
            logger.warning('No modelruns to execute.')
            forecast.status = update_forecast_status(forecast.oid,
                                                     EStatus.CANCELLED)
            return forecast

        logger.info(f"Prepared {len(model_runs)} model run(s)")

        # Execute model runs
        logger.info(f"Executing models in {mode} mode")
        forecast.status = update_forecast_status(forecast.oid,
                                                 EStatus.RUNNING)

        if mode == 'local':
            failed_count = _execute_local_models(model_runs)
        else:
            failed_count = await _execute_deployed_models(
                forecastseries.name, model_runs)

        # Set final status based on model run results
        if failed_count == 0:
            logger.info("Forecast execution completed successfully")
            forecast.status = update_forecast_status(
                forecast.oid, EStatus.COMPLETED)
            return Completed(message="Forecast completed successfully",
                             data=forecast)
        else:
            logger.warning(f"Forecast completed with {failed_count} "
                           f"failed model run(s)")
            forecast.status = update_forecast_status(
                forecast.oid, EStatus.FAILED)
            return Failed(
                message=f"{failed_count}/{len(model_runs)} "
                "model run(s) failed")

    except Exception as e:
        logger.error(f"Forecast execution failed: {e}")
        forecast.status = update_forecast_status(forecast.oid, EStatus.FAILED)
        raise


def prepare_model_runs(
    forecast: Forecast,
    forecastseries: ForecastSeries,
    modelconfigs: list[ModelConfig]
) -> list[tuple[DBModelRunInfo, ModelConfig]]:
    """
    Build (run_info, config) tuples for all enabled model/plan combinations.
    """
    enabled = [c for c in modelconfigs if c.enabled]
    plans = forecastseries.injection_plans or [None]

    return [
        (_make_run_info(forecast, forecastseries, plan), config)
        for config in enabled
        for plan in plans
    ]


def _make_run_info(
    forecast: Forecast,
    forecastseries: ForecastSeries,
    injection_plan: InjectionPlan | None
) -> DBModelRunInfo:
    return DBModelRunInfo(
        forecastseries_oid=forecastseries.oid,
        forecast_oid=forecast.oid,
        forecast_start=forecast.starttime,
        forecast_end=forecast.endtime,
        injection_observation_oid=getattr(
            forecast.injection_observation, 'oid', None),
        seismicity_observation_oid=getattr(
            forecast.seismicity_observation, 'oid', None),
        bounding_polygon=forecastseries.bounding_polygon,
        depth_min=forecastseries.depth_min,
        depth_max=forecastseries.depth_max,
        model_settings=forecastseries.model_settings,
        injection_plan_oid=getattr(injection_plan, 'oid', None)
    )


def _execute_local_models(
    model_runs: list
) -> int:
    """
    Execute model runs locally in sequence.

    Args:
        model_runs: List of (DBModelRunInfo, ModelConfig) tuples

    Returns:
        Number of failed model runs
    """
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    failed_count = 0
    with DatabaseSession() as session:
        for modelrun_info, modelconfig in model_runs:
            modelrun = ModelRun(
                status=EStatus.SCHEDULED,
                modelconfig_oid=modelconfig.oid,
                forecast_oid=modelrun_info.forecast_oid,
                injectionplan_oid=modelrun_info.injection_plan_oid
            )
            modelrun = ModelRunRepository.create(session, modelrun)

            try:
                ModelRunRepository.update_status(
                    session, modelrun.oid, EStatus.RUNNING)
                default_model_runner(modelrun_info, modelconfig, modelrun)
            except Exception as e:
                logger.error(f"ModelRun {modelrun.oid} failed: {e}")
                failed_count += 1

    return failed_count


async def _execute_deployed_models(
    forecastseries_name: str,
    model_runs: list
) -> int:
    """
    Execute model runs as deployed flows and wait for completion.

    Args:
        forecastseries_name: Name of the ForecastSeries for deployment lookup
        model_runs: List of (DBModelRunInfo, ModelConfig) tuples

    Returns:
        Number of failed model runs
    """
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    with DatabaseSession() as session:
        modelruns = []
        for modelrun_info, modelconfig in model_runs:
            modelrun = ModelRun(
                status=EStatus.SCHEDULED,
                modelconfig_oid=modelconfig.oid,
                forecast_oid=modelrun_info.forecast_oid,
                injectionplan_oid=modelrun_info.injection_plan_oid
            )
            modelrun = ModelRunRepository.create(session, modelrun)
            modelruns.append(modelrun)

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(
            f'DefaultModelRunner/{forecastseries_name}'
        )

        # Create all flow runs
        flow_runs = []
        for (modelrun_info, modelconfig), \
                modelrun in zip(model_runs, modelruns):
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters={'modelrun_info': modelrun_info,
                            'modelconfig': modelconfig,
                            'modelrun': modelrun}
            )
            flow_runs.append((flow_run, modelrun))

        with DatabaseSession() as session:
            for _, modelrun in flow_runs:
                ModelRunRepository.update_status(
                    session, modelrun.oid, EStatus.RUNNING)

        # Wait for all flow runs to complete
        finished_runs = await asyncio.gather(*[
            wait_for_flow_run(flow_run_id=fr.id) for fr, _ in flow_runs
        ])

        # Count failures (including crashed and cancelled)
        failed_count = 0
        for finished_run, (_, modelrun) in zip(finished_runs, flow_runs):
            state = finished_run.state
            if state.is_failed() or state.is_crashed() or state.is_cancelled():
                logger.error(f"ModelRun {modelrun.oid} {state.name}")
                failed_count += 1

    return failed_count
