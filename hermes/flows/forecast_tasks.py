"""Prefect tasks for forecast execution."""
import asyncio
import json
import logging
from datetime import datetime
from time import sleep
from typing import Literal
from uuid import UUID

from prefect import get_run_logger, task
from prefect.client.orchestration import get_client
from prefect.deployments import run_deployment

from hermes.flows.modelrun_handler import default_model_runner
from hermes.io.hydraulics import HydraulicsDataSource
from hermes.io.injectionplans import InjectionPlanBuilder
from hermes.io.seismicity import SeismicityDataSource
from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)
from hermes.repositories.database import DatabaseSession
from hermes.schemas.base import EInput
from hermes.schemas.data_schemas import InjectionObservation, InjectionPlan


@task(name='FetchSeismicityObservation', cache_policy=None)
def fetch_seismicity_observation(
    forecast_oid: UUID,
    fdsnws_url: str,
    observation_starttime: datetime,
    observation_endtime: datetime,
    required: EInput
) -> UUID | None:
    """
    Fetches seismicity observation data and stores it to the database.

    Args:
        forecast_oid: UUID of the forecast
        fdsnws_url: URL of the FDSNWS service
        observation_starttime: Start time for observation window
        observation_endtime: End time for observation window
        required: Whether seismicity observation is required

    Returns:
        UUID of created seismicity observation, or None if not allowed
    """
    if required == EInput.NOT_ALLOWED:
        return None

    data_source = SeismicityDataSource.from_uri(
        fdsnws_url,
        observation_starttime,
        observation_endtime
    )

    with DatabaseSession() as session:
        seismicity_obs = SeismicityObservationRepository.create_from_quakeml(
            session,
            data_source.get_quakeml(),
            forecast_oid
        )
        return seismicity_obs.oid if seismicity_obs else None


@task(name='FetchInjectionObservation', cache_policy=None)
def fetch_injection_observation(
    forecast_oid: UUID,
    hydws_url: str,
    observation_starttime: datetime,
    observation_endtime: datetime,
    required: EInput
) -> UUID | None:
    """
    Fetches injection observation data and stores it to the database.

    Args:
        forecast_oid: UUID of the forecast
        hydws_url: URL of the hydraulics web service
        observation_starttime: Start time for observation window
        observation_endtime: End time for observation window
        required: Whether injection observation is required

    Returns:
        UUID of created injection observation, or None if not allowed
    """
    if required == EInput.NOT_ALLOWED:
        return None

    data_source = HydraulicsDataSource.from_uri(
        hydws_url,
        observation_starttime,
        observation_endtime
    )

    injection_observation = InjectionObservation(
        forecast_oid=forecast_oid,
        data=data_source.get_json()
    )

    with DatabaseSession() as session:
        injection_obs = InjectionObservationRepository.create(
            session,
            injection_observation
        )
        return injection_obs.oid if injection_obs else None


@task(name='BuildInjectionPlans', cache_policy=None)
def build_injection_plans(
    forecastseries_oid: UUID,
    injection_observation_data: str | None,
    starttime: datetime,
    endtime: datetime,
    required: EInput
) -> list[InjectionPlan]:
    """
    Builds injection plans from templates and observation data.

    Args:
        forecastseries_oid: UUID of the ForecastSeries
        injection_observation_data: JSON string of injection observation data
        starttime: Start time for the injection plan
        endtime: End time for the injection plan
        required: Whether injection plans are required

    Returns:
        List of created InjectionPlan objects

    Raises:
        ValueError: If plans are required but none found
    """
    if required == EInput.NOT_ALLOWED:
        return []

    with DatabaseSession() as session:
        plan_templates = InjectionPlanRepository.get_by_forecastseries(
            session,
            forecastseries_oid
        )

        if not plan_templates:
            if required == EInput.OPTIONAL:
                return []
            else:
                raise ValueError('No injection plans found for the '
                                 'ForecastSeries.')

        created_plans = []
        for template_plan in plan_templates:
            ip_builder = InjectionPlanBuilder(
                json.loads(template_plan.template),
                json.loads(injection_observation_data) if
                injection_observation_data else {}
            )
            plan_data = ip_builder.build(starttime, endtime)

            new_plan = InjectionPlan(
                name=template_plan.name,
                data=json.dumps([plan_data]),
                template=template_plan.template
            )

            created_plan = InjectionPlanRepository.create(session, new_plan)
            created_plans.append(created_plan)

        return created_plans


@task(name='ExecuteForecastModels', cache_policy=None)
def execute_forecast_models(
    model_runs: list,
    forecastseries_name: str,
    mode: Literal['local', 'deploy'] = 'local'
) -> None:
    """
    Executes forecast model runs either locally or as deployed flows.

    Args:
        model_runs: List of (DBModelRunInfo, ModelConfig) tuples
        forecastseries_name: Name of the ForecastSeries (for deployment naming)
        mode: Execution - 'local' runs in-process, 'deploy' submits to Prefect

    Raises:
        Exception: If any model run fails
    """
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    if not model_runs:
        logger.warning('No modelruns to execute.')
        return None

    if mode == 'local':
        for run in model_runs:
            default_model_runner(*run)
    else:
        # Deploy mode: submit model runs as separate flow deployments
        running = []

        for run in model_runs:
            running.append(run_deployment(
                name=f'DefaultModelRunner/{forecastseries_name}',
                parameters={'modelrun_info': run[0],
                            'modelconfig': run[1]},
                timeout=0
            ))

        # Monitor until all runs complete
        is_final = [False] * len(running)
        while not all(is_final):
            is_final = [asyncio.run(_check_flow_run_is_final(r.id))
                        for r in running]
            if not all(is_final):
                sleep(10)


async def _check_flow_run_is_final(flow_run_id: UUID) -> bool:
    """
    Check if a flow run is in a final state.

    Args:
        flow_run_id: UUID of the flow run to check

    Returns:
        True if the flow run is in a final state
    """
    async with get_client() as client:
        flow_run = await client.read_flow_run(flow_run_id=flow_run_id)
        return flow_run.state.is_final()
