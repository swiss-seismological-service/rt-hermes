from unittest.mock import MagicMock, call, patch

from hermes.flows.modelrun_handler import DefaultModelRunHandler
from hermes.schemas import DBModelRunInfo
from hermes.schemas.base import EStatus
from hermes.schemas.result_schemas import ModelRun


def mock_function(results):
    return MagicMock()


class TestModelRunner:
    @patch('hermes.flows.modelrun_handler.DefaultModelRunHandler'
           '._save_catalog', autocast=True)
    @patch('hermes.flows.tests.test_modelrun_handler.mock_function',
           autocast=True)
    def test_run(self,
                 # MOCKS
                 mock_model_call: MagicMock,
                 mock_handler_catalog_save: MagicMock,
                 # FIXTURES
                 flows_scenario,
                 prefect
                 ):

        modelrun_info = DBModelRunInfo(
            forecast_start=flows_scenario.forecast.starttime,
            forecast_end=flows_scenario.forecast.endtime,
            bounding_polygon=flows_scenario.forecastseries.bounding_polygon,
            depth_min=flows_scenario.forecastseries.depth_min,
            depth_max=flows_scenario.forecastseries.depth_max
        )

        # Create a mock ModelRun object
        mock_modelrun = ModelRun(
            status=EStatus.SCHEDULED,
            modelconfig_oid=flows_scenario.model_config.oid,
            forecast_oid=flows_scenario.forecast.oid,
            injectionplan_oid=None
        )
        mock_modelrun.oid = 1

        mock_model_call.return_value = "teststring"

        handler = DefaultModelRunHandler(
            modelrun_info, flows_scenario.model_config, mock_modelrun)
        handler.run()

        assert call(handler.model_input.model_dump()) == \
            mock_model_call.call_args_list[0]

        mock_handler_catalog_save.assert_called_with("teststring")
