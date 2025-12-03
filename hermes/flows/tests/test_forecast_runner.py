import asyncio
import os
from datetime import datetime
from unittest.mock import ANY, MagicMock, patch

import pytest
from prefect.exceptions import FailedRun

from hermes.flows.forecast_runner import forecast_runner, prepare_model_runs
from hermes.schemas.base import EStatus

CENTRAL_DATA_LOCATION = os.path.join(
    os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))),
    'tests', 'data')
with open(os.path.join(CENTRAL_DATA_LOCATION, 'injection.json')) as f:
    INJECTION = f.read()
with open(os.path.join(CENTRAL_DATA_LOCATION, 'quakeml.xml')) as f:
    SEISMICITY = f.read()


@patch('hermes.flows.forecast_runner.default_model_runner', autospec=True)
@patch('hermes.io.SeismicityDataSource.from_uri', autospec=True)
@patch('hermes.io.HydraulicsDataSource.from_uri', autospec=True)
@patch('hermes.flows.forecast_runner.DatabaseSession')
@patch('hermes.flows.forecast_tasks.DatabaseSession')
@patch('hermes.services.forecast_service.DatabaseSession')
class TestForecastRunner:
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
        """Test the new flow-centric forecast_runner function end-to-end."""
        # Configure all DatabaseSession mocks to use test session
        forecast_service_session.return_value.__enter__.return_value = session
        forecast_tasks_session.return_value.__enter__.return_value = session
        forecast_runner_session.return_value.__enter__.return_value = session

        # Mock external API responses
        mock_get_catalog.return_value.get_quakeml.return_value = SEISMICITY
        mock_get_injection.return_value.get_json.return_value = INJECTION

        # Execute the new flow
        forecast = asyncio.run(forecast_runner(
            flows_scenario_with_injection.forecastseries.oid,
            starttime=datetime(2022, 4, 21, 14, 50, 0),
            endtime=datetime(2022, 4, 21, 14, 55, 0),
            mode='local'
        ))

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

    @patch('hermes.flows.forecast_runner.update_forecast_status',
           autospec=True)
    def test_model_failure_sets_forecast_failed(
            self,
            mock_update_forecast_status: MagicMock,
            forecast_service_session: MagicMock,
            forecast_tasks_session: MagicMock,
            forecast_runner_session: MagicMock,
            mock_get_injection: MagicMock,
            mock_get_catalog: MagicMock,
            mock_default_model_runner: MagicMock,
            session,
            flows_scenario_with_injection,
            prefect_with_logs):
        """Test that forecast status is FAILED when model raises exception."""
        # Configure all DatabaseSession mocks to use test session
        forecast_service_session.return_value.__enter__.return_value = session
        forecast_tasks_session.return_value.__enter__.return_value = session
        forecast_runner_session.return_value.__enter__.return_value = session

        # Mock external API responses
        mock_get_catalog.return_value.get_quakeml.return_value = SEISMICITY
        mock_get_injection.return_value.get_json.return_value = INJECTION

        # Make model runner fail
        mock_default_model_runner.side_effect = Exception("Model crashed")

        # Execute the flow
        with pytest.raises(FailedRun):
            asyncio.run(forecast_runner(
                flows_scenario_with_injection.forecastseries.oid,
                starttime=datetime(2022, 4, 21, 14, 50, 0),
                endtime=datetime(2022, 4, 21, 14, 55, 0),
                mode='local'
            ))

        # called with any id and FAILED status
        mock_update_forecast_status.assert_called_with(ANY, EStatus.FAILED)
        assert mock_default_model_runner.call_count == 1


def test_prepare_model_runs(flows_scenario):
    runs = prepare_model_runs(
        flows_scenario.forecast,
        flows_scenario.forecastseries,
        [flows_scenario.model_config])

    assert len(runs) == 1
    assert runs[0][1] == flows_scenario.model_config

    modelrun_info = runs[0][0]
    assert (modelrun_info.forecastseries_oid
            == flows_scenario.forecastseries.oid)
    assert modelrun_info.forecast_oid == flows_scenario.forecast.oid
    assert (modelrun_info.forecast_start
            == flows_scenario.forecast.starttime)
    assert modelrun_info.forecast_end == flows_scenario.forecast.endtime
    assert (modelrun_info.bounding_polygon
            == flows_scenario.forecastseries.bounding_polygon.wkt)
    assert (modelrun_info.depth_min
            == flows_scenario.forecastseries.depth_min)
    assert (modelrun_info.depth_max
            == flows_scenario.forecastseries.depth_max)
    assert modelrun_info.injection_plan_oid is None
    assert modelrun_info.injection_observation_oid is None
    assert modelrun_info.seismicity_observation_oid is None
