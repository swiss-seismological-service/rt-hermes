import asyncio
import logging
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.runner import Runner

from hermes.flows.forecast_runner import forecast_runner
from hermes.flows.modelrun_handler import default_model_runner
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastSeriesRepository

logger = logging.getLogger('prefect.hermes')

DEPLOYMENT_NAME = 'ForecastRunner/{}'


async def deployment_exists(deployment_name: str) -> bool:
    """
    Check if a deployment exists by its name.
    """
    async with get_client() as client:
        try:
            await client.read_deployment_by_name(deployment_name)
            return True
        except Exception:
            return False


async def deployment_active(deployment_name: str) -> bool:
    """
    Check if a deployment is active by its name.
    """
    async with get_client() as client:
        deployment = await client.read_deployment_by_name(deployment_name)
        if deployment.status.value == 'NOT_READY' or deployment.paused is True:
            return False
        return True


async def get_existing_deployment_schedules(
        deployment_name: str) -> list[DeploymentSchedule] | None:
    """
    Fetch existing schedules from a Prefect deployment.

    Returns full DeploymentSchedule objects, or None if the deployment
    doesn't exist or has no schedules.
    """
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
            schedules = await client.read_deployment_schedules(deployment.id)
            return schedules if schedules else None
        except Exception:
            return None


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
        parameters={"forecastseries_oid": str(forecastseries_oid),
                    "mode": "deploy"},
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
