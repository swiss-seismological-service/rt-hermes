import os
from datetime import datetime
from unittest.mock import MagicMock, patch

from prefect import flow

from hermes.flows.forecast_runner import run_forecast
from hermes.schemas.base import EStatus

CENTRAL_DATA_LOCATION = os.path.join(
    os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))),
    'tests', 'data')
with open(os.path.join(CENTRAL_DATA_LOCATION, 'injection.json')) as f:
    INJECTION = f.read()
with open(os.path.join(CENTRAL_DATA_LOCATION, 'quakeml.xml')) as f:
    SEISMICITY = f.read()


@patch('hermes.flows.forecast_tasks.default_model_runner', autocast=True)
@patch('hermes.io.SeismicityDataSource.from_uri', autocast=True)
@patch('hermes.io.HydraulicsDataSource.from_uri', autocast=True)
@patch('hermes.flows.forecast_runner.DatabaseSession')
@patch('hermes.flows.forecast_tasks.DatabaseSession')
@patch('hermes.services.forecast_service.DatabaseSession')
class TestForecastRunner:
    @flow
    def test_full(self,
                  forecast_service_session: MagicMock,
                  forecast_tasks_session: MagicMock,
                  forecast_runner_session: MagicMock,
                  mock_get_injection: MagicMock,
                  mock_get_catalog: MagicMock,
                  mock_default_model_runner: MagicMock,
                  session,
                  flows_scenario_with_injection,
                  prefect_with_logs
                  ):
        """Test the new flow-centric run_forecast function end-to-end."""
        # Configure all DatabaseSession mocks to use test session
        forecast_service_session.return_value.__enter__.return_value = session
        forecast_tasks_session.return_value.__enter__.return_value = session
        forecast_runner_session.return_value.__enter__.return_value = session

        # Mock external API responses
        mock_get_catalog().get_quakeml.return_value = SEISMICITY
        mock_get_injection().get_json.return_value = INJECTION

        # Execute the new flow
        forecast = run_forecast(
            flows_scenario_with_injection.forecastseries.oid,
            starttime=datetime(2022, 4, 21, 14, 50, 0),
            endtime=datetime(2022, 4, 21, 14, 55, 0),
            mode='local'
        )

        # Verify the flow completed successfully
        assert forecast is not None
        assert forecast.status == EStatus.COMPLETED
        assert forecast.forecastseries_oid == \
            flows_scenario_with_injection.forecastseries.oid

        # Verify model runner was called
        assert mock_default_model_runner.call_count == 1

        # Verify external data sources were called
        assert mock_get_catalog.called
        assert mock_get_injection.called

        # Verify injection plans were created
        assert forecast.injection_observation is not None
        assert forecast.seismicity_observation is not None
