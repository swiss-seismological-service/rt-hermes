import os
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import text

from hermes.flows.forecast_handler import forecast_runner

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


class TestDefaultModelRun:
    @patch('hermes.io.seismicity.SeismicityDataSource.from_uri')
    @patch('hermes.flows.forecast_handler.DatabaseSession')
    @patch('hermes.flows.modelrun_handler.DatabaseSession')
    def test_full_flow(self,
                       mock_session_m, mock_session_fc, mock_get_catalog,
                       session, prefect):

        # Create test data specifically configured for this test
        from datetime import timedelta

        from hermes.repositories.project import (ForecastSeriesRepository,
                                                 ModelConfigRepository,
                                                 ProjectRepository)
        from hermes.tests.data_factories import TestDataFactory

        # Create project
        project = TestDataFactory.create_project(name='test_project')
        project = ProjectRepository.create(session, project)

        # Create forecastseries with specific configuration for this test
        from hermes.schemas import EInput

        forecastseries = TestDataFactory.create_forecastseries(
            project_oid=project.oid,
            name='test_forecastseries',
            observation_starttime=datetime(
                2022, 1, 1, 0, 0, 0) - timedelta(days=1),
            forecast_duration=int(timedelta(days=30).total_seconds()),
            fdsnws_url='',  # Empty URLs to avoid actual HTTP requests
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

        mock_session_fc.return_value.__enter__.return_value = session
        mock_session_m.return_value = session
        mock_get_catalog().get_quakeml.return_value = catalog

        forecast_runner(forecastseries.oid,
                        starttime=datetime(2022, 1, 1, 0, 0, 0))

        n_modelresult = session.execute(
            text('SELECT COUNT(*) FROM modelresult'))
        assert n_modelresult.scalar() == 100

        n_eventforecasts = session.execute(
            text('SELECT COUNT(*) FROM eventforecast'))
        assert n_eventforecasts.scalar() == 344
