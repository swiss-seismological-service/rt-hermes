from hermes.flows.modelrun_builder import ModelRunBuilder


class TestModelRunBuilder:
    def test_build_runs(self,
                        # FIXTURES
                        flows_scenario
                        ):

        builder = ModelRunBuilder(
            flows_scenario.forecast, flows_scenario.forecastseries,
            [flows_scenario.model_config])
        assert len(builder.runs) == 1
        assert builder.runs[0][1] == flows_scenario.model_config

        modelrun_info = builder.runs[0][0]
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
