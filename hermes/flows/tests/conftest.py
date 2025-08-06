import uuid
from datetime import datetime

import pytest
from shapely import Polygon

from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.project import (ForecastSeriesRepository,
                                         ModelConfigRepository,
                                         ProjectRepository)
# Database fixtures now available from package root conftest.py
from hermes.schemas import (EInput, EResultType, EStatus, Forecast,
                            ForecastSeries, ModelConfig, Project)
from hermes.schemas.data_schemas import InjectionPlan


# Database fixtures auto-discovered from package root hermes/conftest.py
# Prefect fixture is also now available from package root


@pytest.fixture()
def project_db(session) -> Project:
    project = Project(
        name='test_project',
        description='test_description',
        starttime=datetime(2022, 4, 21, 0, 0, 0),
        endtime=datetime(2022, 4, 21, 23, 59, 59)
    )

    project = ProjectRepository.create(session, project)

    return project


@pytest.fixture()
def forecastseries_db(session, project_db):
    forecastseries = ForecastSeries(
        name='test_forecastseries',
        project_oid=project_db.oid,
        observation_starttime=datetime(2022, 4, 21, 14, 45, 0),
        bounding_polygon=Polygon(
            [(-125, 35), (-115, 35), (-115, 40), (-125, 40), (-125, 35)]),
        depth_min=0,
        depth_max=10,
        model_settings={
            "well_section_id": "37801a57-90b9-4fb5-83d7-506ee9166acf",
            "injection_point": [
                8.47449792444771,
                46.5098187019071,
                1271.43402303251
            ],
            "local_proj_string": "epsg:2056",
            "epoch_duration": 600,
            "n_phases": 8
        },
        tags=['test'],
        seismicityobservation_required=EInput.REQUIRED,
        injectionobservation_required=EInput.REQUIRED,
        injectionplan_required=EInput.REQUIRED,
        fdsnws_url='https://',
        hydws_url='https://'
    )

    forecastseries = ForecastSeriesRepository.create(
        session, forecastseries)

    return forecastseries


@pytest.fixture()
def modelconfig_db(session):
    model_config = ModelConfig(
        name='test_model',
        description='test_description',
        tags=['test'],
        result_type=EResultType.CATALOG,
        enabled=True,
        sfm_module='hermes.flows.tests.test_modelrun_handler',
        sfm_function='mock_function',
        model_parameters={
            "b_value": 1,
            "afb": -2,
            "Tau": 60,
            "dM": 0.05,
            "Mc": None,
            "tau_force": False,
            "Nsim": 100,
            "mode": "MLE"
        }
    )
    model_config = ModelConfigRepository.create(session, model_config)
    return model_config


@pytest.fixture()
def injectionplan_db(session, forecastseries_db):
    ip_template = InjectionPlan(
        template="""
        {
            "borehole_name": "16A-32",
            "section_name": "16A-32/section_03",
            "type": "multiply",
            "resolution": 60,
            "config": {
                "plan": {
                    "topflow": {
                        "value": 2
                    }
                },
                "lookback_window": 5,
                "mode": "mean"
            }
        }
        """,
        forecastseries_oid=forecastseries_db.oid,
        name='test_injectionplan',
    )
    ip_template = InjectionPlanRepository.create(session, ip_template)
    return ip_template


@pytest.fixture()
def forecast(forecastseries_db):
    forecast = Forecast(
        oid=uuid.uuid4(),
        forecastseries_oid=forecastseries_db.oid,
        status=EStatus.PENDING,
        starttime=datetime(2021, 1, 2, 0, 30, 0),
        endtime=datetime(2021, 1, 4, 0, 0, 0),
    )
    return forecast
