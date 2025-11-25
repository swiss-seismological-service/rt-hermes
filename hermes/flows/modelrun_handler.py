import importlib
import json
import logging
from typing import Any

from hermes_model import ModelInput
from prefect import flow, get_run_logger
from seismostats import ForecastCatalog, ForecastGRRateGrid

from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)
from hermes.repositories.database import DatabaseSession
from hermes.schemas.base import EResultType
from hermes.schemas.model_schemas import DBModelRunInfo, ModelConfig
from hermes.schemas.result_schemas import ModelRun
from hermes.services.result_service import (save_forecast_catalog,
                                            save_forecast_grrategrid)


class ModelRunDataAccess:
    """Handles data I/O for model runs using context-managed sessions."""

    def __init__(self, modelrun_info: DBModelRunInfo):
        self.info = modelrun_info

    def get_seismicity_observation(self):
        if not self.info.seismicity_observation_oid:
            return None
        with DatabaseSession() as session:
            obs = SeismicityObservationRepository.get_by_id(
                session, self.info.seismicity_observation_oid)
            return obs.data

    def get_injection_observation(self):
        if not self.info.injection_observation_oid:
            return None
        with DatabaseSession() as session:
            obs = InjectionObservationRepository.get_by_id(
                session, self.info.injection_observation_oid)
            return json.loads(obs.data)

    def get_injection_plan(self):
        if not self.info.injection_plan_oid:
            return None
        with DatabaseSession() as session:
            plan = InjectionPlanRepository.get_by_id(
                session, self.info.injection_plan_oid)
            return json.loads(plan.data)

    def save_results(self,
                     forecastseries_oid,
                     modelrun_oid,
                     result_type: EResultType,
                     results: Any) -> None:
        save_fn = {
            EResultType.CATALOG: self._save_catalog,
            EResultType.GRID: self._save_grid,
        }
        if result_type not in save_fn:
            raise NotImplementedError(
                f"Result type {result_type} not supported")
        save_fn[result_type](forecastseries_oid, modelrun_oid, results)

    def _save_catalog(self,
                      forecastseries_oid,
                      modelrun_oid,
                      results: list[ForecastCatalog]) -> None:
        with DatabaseSession() as session:
            for catalog in results:
                save_forecast_catalog(
                    session, forecastseries_oid, modelrun_oid, catalog)

    def _save_grid(self,
                   forecastseries_oid,
                   modelrun_oid,
                   results: list[ForecastGRRateGrid]) -> None:
        with DatabaseSession() as session:
            for grid in results:
                save_forecast_grrategrid(
                    session, forecastseries_oid, modelrun_oid, grid)


@flow(name='DefaultModelRunner',
      flow_run_name='ModelRun-{modelconfig.name}')
def default_model_runner(modelrun_info: DBModelRunInfo,
                         modelconfig: ModelConfig,
                         modelrun: ModelRun) -> None:
    try:
        logger = get_run_logger()
    except BaseException:
        logger = logging.getLogger('prefect.hermes')

    data_access = ModelRunDataAccess(modelrun_info)

    # Build model input
    model_input = ModelInput(
        forecast_start=modelrun_info.forecast_start,
        forecast_end=modelrun_info.forecast_end,
        seismicity_observation=data_access.get_seismicity_observation(),
        injection_observation=data_access.get_injection_observation(),
        injection_plan=data_access.get_injection_plan(),
        bounding_polygon=modelrun_info.bounding_polygon,
        depth_min=modelrun_info.depth_min,
        depth_max=modelrun_info.depth_max,
        model_settings=modelrun_info.model_settings,
        model_parameters=modelconfig.model_parameters
    )

    # Import and run model
    logger.info(f"Running model {modelconfig.sfm_module}."
                f"{modelconfig.sfm_function}")
    model_module = importlib.import_module(modelconfig.sfm_module)
    model_function = getattr(model_module, modelconfig.sfm_function)
    results = model_function(model_input.model_dump())

    # Save results
    logger.info(f"Saving results for modelrun {modelrun.oid}")
    data_access.save_results(
        modelrun_info.forecastseries_oid,
        modelrun.oid,
        modelconfig.result_type,
        results
    )
