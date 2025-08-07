import pytest

from hermes.repositories.data import InjectionPlanRepository
from hermes.schemas.data_schemas import InjectionPlan
from hermes.tests.data_factories import TestScenarioBuilder

# Database fixtures auto-discovered from package root hermes/conftest.py
# Prefect fixture is also now available from package root


@pytest.fixture()
def flows_scenario(session):
    """Complete scenario for flows testing using factory defaults."""
    return TestScenarioBuilder.create_full_modelrun_scenario(
        session,
        model_config={
            'sfm_module': 'hermes.flows.tests.test_modelrun_handler',
            'sfm_function': 'mock_function'
        }
    )


@pytest.fixture()
def flows_scenario_with_injection(session):
    """Complete scenario including injection plan."""
    scenario = TestScenarioBuilder.create_full_modelrun_scenario(
        session,
        model_config={
            'sfm_module': 'hermes.flows.tests.test_modelrun_handler',
            'sfm_function': 'mock_function'
        }
    )

    # Add minimal injection plan
    template = ('{"borehole_name": "16A-32", '
                '"section_name": "16A-32/section_01", '
                '"type": "multiply", "resolution": 60, '
                '"config": {"plan": {"topflow": {"value": 2}}}}')
    injection_plan = InjectionPlan(
        template=template,
        forecastseries_oid=scenario.forecastseries.oid,
        name='test_injectionplan'
    )
    scenario.injection_plan = InjectionPlanRepository.create(
        session, injection_plan)

    return scenario
