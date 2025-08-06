"""
Test data helpers for creating realistic test scenarios.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from seismostats import ForecastCatalog
from shapely import Polygon

from hermes.schemas import (EInput, EResultType, ForecastSeries,
                            ModelConfig, Project)


class TestDataFactory:
    """Factory for creating realistic test data objects."""

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


class TestDataGenerator:
    """Utilities for generating test data for services."""

    @staticmethod
    def create_forecast_catalog(
        n_catalogs: int = 10,
        n_events_per_catalog: int = 50,
        **kwargs
    ) -> ForecastCatalog:
        """Create a ForecastCatalog for testing model results."""
        # Create events for all catalogs combined, with catalog_id
        catalog_data = []
        for catalog_id in range(n_catalogs):
            for event_id in range(n_events_per_catalog):
                starttime = kwargs.get('starttime', datetime(2022, 1, 1))
                endtime = kwargs.get('endtime', starttime + timedelta(days=30))
                bounding_polygon = kwargs.get('bounding_polygon', Polygon([
                    (5.95, 45.82), (10.49, 45.82),
                    (10.49, 47.81), (5.95, 47.81), (5.95, 45.82)
                ]))

                bounds = bounding_polygon.bounds
                total_events = n_catalogs * n_events_per_catalog
                event_index = catalog_id * n_events_per_catalog + event_id
                time_fraction = event_index / total_events
                event_time = starttime + (endtime - starttime) * time_fraction

                catalog_data.append({
                    'time': event_time,
                    'longitude': np.random.uniform(bounds[0], bounds[2]),
                    'latitude': np.random.uniform(bounds[1], bounds[3]),
                    'depth': np.random.uniform(
                        kwargs.get('depth_min', 0),
                        kwargs.get('depth_max', 10)
                    ),
                    'magnitude': np.random.uniform(1.0, 4.0),
                    'magnitude_type': 'ML',
                    'event_id': f'catalog_{catalog_id}_event_{event_id}',
                    'catalog_id': catalog_id
                })

        combined_df = pd.DataFrame(catalog_data)
        forecast_catalog = ForecastCatalog(combined_df, n_catalogs=n_catalogs)

        # Set required attributes
        forecast_catalog.starttime = kwargs.get(
            'starttime', datetime(2022, 1, 1))
        default_endtime = forecast_catalog.starttime + timedelta(days=30)
        forecast_catalog.endtime = kwargs.get('endtime', default_endtime)
        forecast_catalog.bounding_polygon = kwargs.get(
            'bounding_polygon', Polygon([
                (5.95, 45.82), (10.49, 45.82),
                (10.49, 47.81), (5.95, 47.81), (5.95, 45.82)
            ]))
        forecast_catalog.depth_min = kwargs.get('depth_min', 0)
        forecast_catalog.depth_max = kwargs.get('depth_max', 10)

        return forecast_catalog
