"""Prefect tasks for forecast execution."""
import json
from datetime import datetime
from uuid import UUID

from prefect import task

from hermes.io.hydraulics import HydraulicsDataSource
from hermes.io.injectionplans import InjectionPlanBuilder
from hermes.io.seismicity import SeismicityDataSource
from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)
from hermes.repositories.database import DatabaseSession
from hermes.schemas.base import EInput
from hermes.schemas.data_schemas import (InjectionObservation, InjectionPlan,
                                         SeismicityObservation)


@task(name='FetchSeismicityObservation', cache_policy=None)
def fetch_seismicity_observation(
    forecast_oid: UUID,
    fdsnws_url: str,
    observation_starttime: datetime,
    observation_endtime: datetime,
    required: EInput
) -> SeismicityObservation | None:
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
    return seismicity_obs if seismicity_obs else None


@task(name='FetchInjectionObservation', cache_policy=None)
def fetch_injection_observation(
    forecast_oid: UUID,
    hydws_url: str,
    observation_starttime: datetime,
    observation_endtime: datetime,
    required: EInput,
    resample: int | None = None
) -> InjectionObservation | None:
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
        data=data_source.get_json(resample=resample)
    )

    with DatabaseSession() as session:
        injection_obs = InjectionObservationRepository.create(
            session,
            injection_observation
        )
    return injection_obs if injection_obs else None


@task(name='BuildInjectionPlans', cache_policy=None)
def build_injection_plans(
    forecastseries_oid: UUID,
    injection_observation: InjectionObservation | None,
    starttime: datetime,
    endtime: datetime,
    required: EInput
) -> list[InjectionPlan]:
    """
    Builds injection plans from templates and observation data.

    Args:
        forecastseries_oid: UUID of the ForecastSeries
        injection_observation: InjectionObservation object
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
                json.loads(injection_observation.data) if
                injection_observation else {}
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
