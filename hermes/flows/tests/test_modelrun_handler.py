from unittest.mock import MagicMock, patch
from uuid import uuid4

from prefect.client.schemas.objects import FlowRun

from hermes.flows.modelrun_handler import (ModelRunDataAccess,
                                           _update_modelrun_status,
                                           default_model_runner)
from hermes.repositories.results import ModelRunRepository
from hermes.schemas import DBModelRunInfo
from hermes.schemas.base import EStatus
from hermes.schemas.result_schemas import ModelRun


def mock_function(model_input):
    return "test_results"


class TestModelRunDataAccess:
    def test_get_seismicity_observation_none(self, flows_scenario):
        modelrun_info = DBModelRunInfo(
            forecast_start=flows_scenario.forecast.starttime,
            forecast_end=flows_scenario.forecast.endtime,
            seismicity_observation_oid=None
        )
        data_access = ModelRunDataAccess(modelrun_info)
        assert data_access.get_seismicity_observation() is None

    def test_get_injection_observation_none(self, flows_scenario):
        modelrun_info = DBModelRunInfo(
            forecast_start=flows_scenario.forecast.starttime,
            forecast_end=flows_scenario.forecast.endtime,
            injection_observation_oid=None
        )
        data_access = ModelRunDataAccess(modelrun_info)
        assert data_access.get_injection_observation() is None

    def test_get_injection_plan_none(self, flows_scenario):
        modelrun_info = DBModelRunInfo(
            forecast_start=flows_scenario.forecast.starttime,
            forecast_end=flows_scenario.forecast.endtime,
            injection_plan_oid=None
        )
        data_access = ModelRunDataAccess(modelrun_info)
        assert data_access.get_injection_plan() is None


class TestDefaultModelRunner:
    @patch.object(ModelRunDataAccess, 'save_results')
    @patch('hermes.flows.tests.test_modelrun_handler.mock_function')
    def test_run(self,
                 mock_model_call: MagicMock,
                 mock_save_results: MagicMock,
                 flows_scenario,
                 prefect):

        modelrun_info = DBModelRunInfo(
            forecast_start=flows_scenario.forecast.starttime,
            forecast_end=flows_scenario.forecast.endtime,
            forecastseries_oid=flows_scenario.forecastseries.oid,
            bounding_polygon=flows_scenario.forecastseries.bounding_polygon,
            depth_min=flows_scenario.forecastseries.depth_min,
            depth_max=flows_scenario.forecastseries.depth_max
        )

        mock_modelrun = ModelRun(
            status=EStatus.SCHEDULED,
            modelconfig_oid=flows_scenario.model_config.oid,
            forecast_oid=flows_scenario.forecast.oid,
            injectionplan_oid=None
        )
        mock_modelrun.oid = uuid4()

        mock_model_call.return_value = "test_results"

        default_model_runner(modelrun_info, flows_scenario.model_config,
                             mock_modelrun)

        mock_model_call.assert_called_once()
        mock_save_results.assert_called_once_with(
            flows_scenario.forecastseries.oid,
            mock_modelrun.oid,
            flows_scenario.model_config.result_type,
            "test_results"
        )


class TestUpdateModelrunStatus:
    """Test the _update_modelrun_status helper function."""

    def _make_flow_run(self, modelrun_param):
        """Create a mock FlowRun with given modelrun parameter."""
        flow_run = MagicMock(spec=FlowRun)
        flow_run.parameters = {'modelrun': modelrun_param}
        return flow_run

    @patch('hermes.flows.modelrun_handler.DatabaseSession')
    def test_updates_status_with_dict_parameter(
            self, mock_db_session, session, flows_scenario):
        """Test status update."""
        mock_db_session.return_value.__enter__.return_value = session

        # Simulate Prefect's dict deserialization of modelrun
        modelrun_dict = {'oid': str(flows_scenario.modelrun.oid)}

        flow_run = self._make_flow_run(modelrun_dict)
        _update_modelrun_status(flow_run, EStatus.COMPLETED)

        # Verify the status was updated in the database
        updated = ModelRunRepository.get_by_id(
            session, flows_scenario.modelrun.oid)
        assert updated.status == EStatus.COMPLETED

    @patch('hermes.flows.modelrun_handler.DatabaseSession')
    def test_does_nothing_when_modelrun_is_none(self, mock_db_session):
        """Test graceful handling when modelrun parameter is missing."""
        flow_run = self._make_flow_run(None)

        # Should not raise, should not call DatabaseSession
        _update_modelrun_status(flow_run, EStatus.COMPLETED)

        mock_db_session.assert_not_called()

    @patch('hermes.flows.modelrun_handler.DatabaseSession')
    def test_does_nothing_when_oid_is_none(self, mock_db_session):
        """Test graceful handling when modelrun has no oid."""
        flow_run = self._make_flow_run({'oid': None})

        # Should not raise, should not call DatabaseSession
        _update_modelrun_status(flow_run, EStatus.COMPLETED)

        mock_db_session.assert_not_called()

    @patch('hermes.flows.modelrun_handler.DatabaseSession')
    def test_logs_error_on_db_failure(self, mock_db_session, caplog):
        """Test that database errors are logged but not raised."""
        mock_db_session.return_value.__enter__.side_effect = \
            Exception("DB connection failed")

        modelrun_oid = uuid4()
        flow_run = self._make_flow_run({'oid': str(modelrun_oid)})

        # Should not raise
        _update_modelrun_status(flow_run, EStatus.FAILED)

        # Should log the error
        assert "Failed to update ModelRun" in caplog.text
        assert str(modelrun_oid) in caplog.text
