import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import func, select

from hermes.datamodel.result_tables import EventForecastTable
from hermes.flows.forecast_runner import forecast_runner
from hermes.repositories.project import (ForecastSeriesRepository,
                                         ModelConfigRepository,
                                         ProjectRepository)
from hermes.repositories.results import ModelResultRepository
from hermes.schemas import EInput
from hermes.tests.data_factories import TestDataFactory

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


class TestDefaultModelRun:
    @patch('hermes.io.seismicity.SeismicityDataSource.from_uri')
    def test_full_flow(self, mock_get_catalog, session, prefect):
        # Create project
        project = TestDataFactory.create_project(name='test_project')
        project = ProjectRepository.create(session, project)

        # Create forecastseries with specific configuration for this test
        forecastseries = TestDataFactory.create_forecastseries(
            project_oid=project.oid,
            name='test_forecastseries',
            observation_starttime=datetime(
                2022, 1, 1, 0, 0, 0) - timedelta(days=1),
            forecast_duration=int(timedelta(days=30).total_seconds()),
            fdsnws_url='',
            hydws_url='',
            injectionobservation_required=EInput.NOT_ALLOWED,
            injectionplan_required=EInput.NOT_ALLOWED
        )
        forecastseries = ForecastSeriesRepository.create(
            session, forecastseries)

        # Create model config
        model_config = TestDataFactory.create_model_config(name='test_model')
        model_config = ModelConfigRepository.create(session, model_config)

        with open(MODULE_LOCATION + '/catalog.xml', 'r') as f:
            catalog = f.read()

        mock_get_catalog().get_quakeml.return_value = catalog

        asyncio.run(forecast_runner(forecastseries.oid,
                                    starttime=datetime(2022, 1, 1, 0, 0, 0)))

        # Count ModelResults using repository method
        model_results = ModelResultRepository.get_all(session)
        assert len(model_results) == 100

        # Count EventForecasts using a simple count query
        event_forecast_count = session.execute(
            select(func.count(EventForecastTable.oid))
        ).scalar()
        assert event_forecast_count == 344
