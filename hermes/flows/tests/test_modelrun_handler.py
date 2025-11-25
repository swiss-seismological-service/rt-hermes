from unittest.mock import MagicMock, patch
from uuid import uuid4

from hermes.flows.modelrun_handler import (ModelRunDataAccess,
                                           default_model_runner)
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
