import importlib
import json
import logging
from abc import abstractmethod
from typing import Any

from hermes_model import ModelInput
from prefect import flow, get_run_logger, task
from seismostats import ForecastCatalog, ForecastGRRateGrid

from hermes.services.result_service import (
    save_forecast_catalog,
    save_forecast_grrategrid)
from hermes.repositories.data import (InjectionObservationRepository,
                                      InjectionPlanRepository,
                                      SeismicityObservationRepository)
from hermes.repositories.database import DatabaseSession
from hermes.repositories.results import ModelRunRepository
from hermes.schemas.base import EResultType, EStatus
from hermes.schemas.model_schemas import DBModelRunInfo, ModelConfig
from hermes.schemas.result_schemas import ModelRun


class ModelRunHandlerInterface:
    """
    General Interface for a model run handler.
    """

    def __init__(self,
                 modelrun_info: DBModelRunInfo,
                 modelconfig: ModelConfig,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        try:
            self.logger = get_run_logger()
        except BaseException:
            self.logger = logging.getLogger('prefect.hermes')
        self.modelrun_info = modelrun_info
        self.modelconfig = modelconfig

        self.injection_plan = self._fetch_injection_plan()
        self.injection_observation = self._fetch_injection_observation()
        self.seismicity_observation = self._fetch_seismicity_observation()

        self.model_input = self._model_input()

        self.modelrun = self._create_modelrun()

        self.save_results = {EResultType.CATALOG: self._save_catalog,
                             EResultType.BINS: self._save_bins,
                             EResultType.GRID: self._save_grid}

    def _model_input(self) -> ModelInput:
        return ModelInput(
            forecast_start=self.modelrun_info.forecast_start,
            forecast_end=self.modelrun_info.forecast_end,

            injection_observation=self.injection_observation,
            injection_plan=self.injection_plan,
            seismicity_observation=self.seismicity_observation,

            bounding_polygon=self.modelrun_info.bounding_polygon,
            depth_min=self.modelrun_info.depth_min,
            depth_max=self.modelrun_info.depth_max,

            model_settings=self.modelrun_info.model_settings,

            model_parameters=self.modelconfig.model_parameters
        )

    @abstractmethod
    def _create_modelrun(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _fetch_injection_observation(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _fetch_injection_plan(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _fetch_seismicity_observation(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _save_catalog(self, results: list[ForecastCatalog]) -> None:
        raise NotImplementedError

    @abstractmethod
    def _save_bins(self, results: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def _save_grid(self, results: list[ForecastGRRateGrid]) -> None:
        raise NotImplementedError


class DefaultModelRunHandler(ModelRunHandlerInterface):

    def __init__(self, *args, **kwargs) -> None:
        self.session = DatabaseSession()
        super().__init__(*args, **kwargs)

    @task(name='RunModel', cache_policy=None)
    def run(self) -> None:
        try:
            model_module = importlib.import_module(self.modelconfig.sfm_module)
            model_function = getattr(
                model_module, self.modelconfig.sfm_function)
            results = model_function(self.model_input.model_dump())
            self.save_results[self.modelconfig.result_type](results)
        except BaseException as e:
            ModelRunRepository.update_status(
                self.session, self.modelrun.oid, EStatus.FAILED)
            raise e
        else:
            ModelRunRepository.update_status(
                self.session, self.modelrun.oid, EStatus.COMPLETED)

    def __del__(self):
        try:
            self.session.close()
        except BaseException:
            pass

    def _create_modelrun(self) -> None:
        modelrun = ModelRun(
            status=EStatus.SCHEDULED,
            modelconfig_oid=self.modelconfig.oid,
            forecast_oid=self.modelrun_info.forecast_oid,
            injectionplan_oid=self.modelrun_info.injection_plan_oid
        )

        return ModelRunRepository.create(self.session,
                                         modelrun)

    def _fetch_injection_observation(self) -> None:
        if not self.modelrun_info.injection_observation_oid:
            return None
        obs = InjectionObservationRepository.get_by_id(
            self.session, self.modelrun_info.injection_observation_oid)
        return json.loads(obs.data)

    def _fetch_injection_plan(self) -> None:
        if not self.modelrun_info.injection_plan_oid:
            return None
        plan = InjectionPlanRepository.get_by_id(
            self.session, self.modelrun_info.injection_plan_oid)
        return json.loads(plan.data)

    def _fetch_seismicity_observation(self) -> None:
        if not self.modelrun_info.seismicity_observation_oid:
            return None
        return SeismicityObservationRepository.get_by_id(
            self.session, self.modelrun_info.seismicity_observation_oid).data

    def _save_catalog(self, results: list[ForecastCatalog]) -> None:
        for catalog in results:
            save_forecast_catalog(
                self.session,
                self.modelrun_info.forecastseries_oid,
                self.modelrun.oid,
                catalog)

    def _save_bins(self, results: Any) -> None:
        raise NotImplementedError

    def _save_grid(self, results: list[ForecastGRRateGrid]) -> None:
        for grid in results:
            save_forecast_grrategrid(
                self.session,
                self.modelrun_info.forecastseries_oid,
                self.modelrun.oid,
                grid)


@flow(name='DefaultModelRunner',
      flow_run_name='ModelRun-{modelconfig.name}')
def default_model_runner(modelrun_info: DBModelRunInfo,
                         modelconfig: ModelConfig) -> DefaultModelRunHandler:
    runner = DefaultModelRunHandler(modelrun_info, modelconfig)
    runner.run()
    return runner
