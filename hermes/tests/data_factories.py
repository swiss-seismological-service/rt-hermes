import os
import pickle
import uuid
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from seismostats import ForecastCatalog
from shapely import Polygon

from hermes.datamodel.result_tables import ModelRunTable
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository,
                                         ModelConfigRepository,
                                         ProjectRepository)
from hermes.schemas import (EInput, EResultType, EStatus, Forecast,
                            ForecastSeries, ModelConfig, Project)


class TestDataFactory:
    """Factory for creating simple domain objects with realistic defaults."""

    @staticmethod
    def create_project(
        name: str = "test_project",
        description: str = "Test project description",
        starttime: Optional[datetime] = None,
        endtime: Optional[datetime] = None
    ) -> Project:
        """Create a test Project with realistic defaults."""
        if starttime is None:
            starttime = datetime(2022, 1, 1, 0, 0, 0)
        if endtime is None:
            endtime = starttime + timedelta(days=365)

        return Project(
            name=name,
            description=description,
            starttime=starttime,
            endtime=endtime
        )

    @staticmethod
    def create_forecastseries(
        project_oid: uuid.UUID,
        name: str = "test_forecastseries",
        bounding_polygon: Optional[Polygon] = None,
        **kwargs
    ) -> ForecastSeries:
        """Create a test ForecastSeries with realistic defaults."""
        if bounding_polygon is None:
            # Default to Switzerland-like coordinates
            bounding_polygon = Polygon([
                (5.95, 45.82), (10.49, 45.82),
                (10.49, 47.81), (5.95, 47.81), (5.95, 45.82)
            ])

        defaults = {
            'name': name,
            'project_oid': project_oid,
            'observation_starttime': datetime(2022, 1, 1, 0, 0, 0),
            'bounding_polygon': bounding_polygon,
            'depth_min': 0,
            'depth_max': 10,
            'model_settings': {
                "well_section_id": str(uuid.uuid4()),
                "injection_point": [8.47, 46.51, 1271.43],
                "local_proj_string": "epsg:2056",
                "epoch_duration": 600,
                "n_phases": 8
            },
            'tags': ['test'],
            'seismicityobservation_required': EInput.REQUIRED,
            'injectionobservation_required': EInput.OPTIONAL,
            'injectionplan_required': EInput.OPTIONAL,
            'fdsnws_url': 'https://test.example.com/fdsnws',
            'hydws_url': 'https://test.example.com/hydws'
        }
        defaults.update(kwargs)

        return ForecastSeries(**defaults)

    @staticmethod
    def create_model_config(
        name: str = "test_model",
        result_type: EResultType = EResultType.CATALOG,
        **kwargs
    ) -> ModelConfig:
        """Create a test ModelConfig with realistic defaults."""
        defaults = {
            'name': name,
            'description': f'Test model configuration for {name}',
            'tags': ['test'],
            'result_type': result_type,
            'enabled': True,
            'sfm_module': 'hermes.tests.model_mock',
            'sfm_function': 'model_mock',
            'model_parameters': {
                "b_value": 1.0,
                "tau": 60,
                "n_simulations": 10
            }
        }
        defaults.update(kwargs)

        return ModelConfig(**defaults)

    @staticmethod
    def create_forecast(
        forecastseries_oid: uuid.UUID,
        starttime: Optional[datetime] = None,
        endtime: Optional[datetime] = None,
        **kwargs
    ) -> Forecast:
        """Create a test Forecast with realistic defaults."""
        if starttime is None:
            starttime = datetime(2022, 1, 1)
        if endtime is None:
            endtime = datetime(2022, 1, 31)

        defaults = {
            'forecastseries_oid': forecastseries_oid,
            'status': EStatus.PENDING,
            'starttime': starttime,
            'endtime': endtime
        }
        defaults.update(kwargs)

        return Forecast(**defaults)


class TestDataGenerator:
    """Utilities for generating complex test data structures."""

    @staticmethod
    def create_forecast_catalog(
        n_catalogs: int = 10,
        **kwargs
    ) -> ForecastCatalog:
        """Load ForecastCatalog from test data file."""

        catalog_path = os.path.join(
            os.path.dirname(__file__),
            '../repositories/tests/data/catalog.parquet.gzip'
        )

        catalog = ForecastCatalog(pd.read_parquet(catalog_path))

        # Set required attributes with defaults
        catalog.starttime = kwargs.get('starttime', datetime(2022, 1, 1))
        catalog.endtime = kwargs.get('endtime', datetime(2022, 1, 31))
        catalog.bounding_polygon = kwargs.get('bounding_polygon', Polygon([
            (5.95, 45.82), (10.49, 45.82),
            (10.49, 47.81), (5.95, 47.81), (5.95, 45.82)
        ]))
        catalog.depth_min = kwargs.get('depth_min', 0)
        catalog.depth_max = kwargs.get('depth_max', 10)
        catalog.n_catalogs = n_catalogs

        # Add catalog_id column if not present (needed by service)
        if 'catalog_id' not in catalog.columns:
            catalog['catalog_id'] = np.random.randint(
                0, n_catalogs, catalog.shape[0])

        return catalog

    @staticmethod
    def create_rate_grid(
        **kwargs
    ) -> pd.DataFrame:
        """Load forecast rate grid from test data file."""
        rategrid_path = os.path.join(
            os.path.dirname(__file__),
            '../repositories/tests/data/forecastgrrategrid.pkl'
        )

        with open(rategrid_path, 'rb') as f:
            data = pickle.load(f)

        # The pickle file contains a list of rate grids, take the last one
        rategrid = data[-1]

        # Apply customizations from kwargs if provided
        if 'starttime' in kwargs:
            rategrid.starttime = kwargs['starttime']
        if 'endtime' in kwargs:
            rategrid.endtime = kwargs['endtime']

        return rategrid


class TestScenarioBuilder:
    """Creates complete test scenarios with all dependencies."""

    @staticmethod
    def create_full_modelrun_scenario(session, **kwargs):
        """Create complete scenario: project → series → forecast → modelrun."""
        # Create project
        project = TestDataFactory.create_project(**kwargs.get('project', {}))
        project = ProjectRepository.create(session, project)

        # Create forecastseries
        forecastseries = TestDataFactory.create_forecastseries(
            project_oid=project.oid,
            **kwargs.get('forecastseries', {})
        )
        forecastseries = ForecastSeriesRepository.create(
            session, forecastseries)

        # Create model config
        model_config = TestDataFactory.create_model_config(
            **kwargs.get('model_config', {})
        )
        model_config = ModelConfigRepository.create(session, model_config)

        # Create forecast
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=forecastseries.oid,
            **kwargs.get('forecast', {})
        )
        forecast = ForecastRepository.create(session, forecast)

        # Create modelrun
        modelrun = ModelRunTable(
            modelconfig_oid=model_config.oid,
            forecast_oid=forecast.oid,
            status=EStatus.PENDING.value
        )
        session.add(modelrun)
        session.commit()

        # Return a simple namespace object with all components
        class Scenario:
            pass

        scenario = Scenario()
        scenario.project = project
        scenario.forecastseries = forecastseries
        scenario.model_config = model_config
        scenario.forecast = forecast
        scenario.modelrun = modelrun

        return scenario

    @staticmethod
    def create_service_test_scenario(session, **kwargs):
        """Create scenario optimized for service layer testing."""
        scenario = TestScenarioBuilder.create_full_modelrun_scenario(
            session, **kwargs)
        return scenario.forecastseries, scenario.modelrun
