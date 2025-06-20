import asyncio
import json
from uuid import UUID

from prefect.exceptions import ObjectNotFound

from hermes.flows.forecastseries_scheduler import (DEPLOYMENT_NAME,
                                                   delete_deployment_schedule)
from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository,
                                         ModelConfigRepository,
                                         ProjectRepository)
from hermes.repositories.results import ModelRunRepository
from hermes.repositories.types import DuplicateError
from hermes.schemas import EStatus, ForecastSeriesConfig, ModelConfig
from hermes.schemas.data_schemas import InjectionPlan, InjectionPlanTemplate
from hermes.schemas.project_schemas import Project


def read_project_oid(name_or_id: str):
    try:
        return UUID(name_or_id, version=4)
    except ValueError:
        with DatabaseSession() as session:
            project_db = ProjectRepository.get_by_name(session, name_or_id)

        if not project_db:
            raise Exception(f'Project "{name_or_id}" not found.')

        return project_db.oid


def update_project(new_config: dict,
                   project_oid: UUID):

    new_data = Project(oid=project_oid, **new_config)

    try:
        with DatabaseSession() as session:
            project_out = ProjectRepository.update(session, new_data)
    except DuplicateError:
        raise ValueError(f'Project with name "{new_config["name"]}"'
                         ' already exists, please choose a different name.')

    return project_out


def delete_project(project_oid: UUID):
    # delete all forecastseries separately to ensure correct deletion
    # of associated forecasts and schedules
    with DatabaseSession() as session:
        forecastseries = ForecastSeriesRepository.get_by_project(
            session, project_oid)

    for fseries in forecastseries:
        delete_forecastseries(fseries.oid)

    # delete project
    with DatabaseSession() as session:
        ProjectRepository.delete(session, project_oid)


def read_forecastseries_oid(name_or_id: str):
    """
    Takes the name or ID of a Forecast Series, checks if it exists,
    and returns the ID.
    """
    try:
        return UUID(name_or_id, version=4)
    except ValueError:
        with DatabaseSession() as session:
            forecastseries_db = ForecastSeriesRepository.get_by_name(
                session, name_or_id)

        if not forecastseries_db:
            raise ValueError(f'ForecastSeries "{name_or_id}" not found.')

        return forecastseries_db.oid


def create_forecastseries(name, fseries_config, project_oid):
    forecast_series = ForecastSeriesConfig(name=name,
                                           status=EStatus.PENDING,
                                           project_oid=project_oid,
                                           **fseries_config)
    try:
        with DatabaseSession() as session:
            forecast_series_out = ForecastSeriesRepository.create(
                session, forecast_series)

        return forecast_series_out
    except DuplicateError:
        raise ValueError(f'ForecastSeries with name "{name}" already exists,'
                         ' please choose a different name.')


def update_forecastseries(fseries_config: dict,
                          forecastseries_oid: UUID,
                          force: bool = False):

    new_forecastseries = ForecastSeriesConfig(oid=forecastseries_oid,
                                              **fseries_config)

    # the following fields should generally not be updated,
    # check whether they are being updated and raise an exception
    # if not forced
    if not force:
        with DatabaseSession() as session:
            old_forecastseries = ForecastSeriesRepository.get_by_id(
                session, forecastseries_oid)

        protected_fields = ['project_oid',
                            'status',
                            'observation_starttime',
                            'observation_endtime',
                            'bounding_polygon',
                            'depth_min',
                            'depth_max',
                            'seismicityobservation_required',
                            'injectionobservation_required',
                            'injectionplan_required']

        for field in protected_fields:
            if field in fseries_config.keys():
                if getattr(old_forecastseries, field) != \
                        getattr(new_forecastseries, field):
                    raise Exception(
                        f'Field "{field}" should not be updated. '
                        'Use --force to update anyway.')

    try:
        with DatabaseSession() as session:
            forecast_series_out = ForecastSeriesRepository.update(
                session, new_forecastseries)
    except DuplicateError:
        raise ValueError(f'ForecastSeries with name "{fseries_config["name"]}"'
                         ' already exists, please choose a different name.')

    return forecast_series_out


def delete_forecastseries(forecastseries_oid: UUID):

    with DatabaseSession() as session:
        forecastseries = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)

    if not forecastseries:
        raise Exception(
            f'ForecastSeries with oid "{forecastseries_oid}" not found.')

    # check no forecasts are running
    with DatabaseSession() as session:
        forecasts = ForecastRepository.get_by_forecastseries(
            session, forecastseries_oid)

    if any(f.status == EStatus.RUNNING for f in forecasts):
        raise Exception(
            'ForecastSeries cannot be deleted because it is currently running.'
            ' Stop the forecasts first.')

    # delete schedule if exists
    if forecastseries.schedule_id:
        try:
            asyncio.run(delete_deployment_schedule(
                DEPLOYMENT_NAME.format(forecastseries_oid),
                forecastseries.schedule_id))
        except ObjectNotFound:
            # schedule has already been deleted on prefect side
            pass

    # delete forecastseries
    with DatabaseSession() as session:
        injectionplans = []
        for f in forecasts:
            ips = InjectionPlanRepository.get_ids_by_forecast(session, f.oid)
            injectionplans.extend(ips)

        # the deletion cascade takes care of most of the deletion
        ForecastSeriesRepository.delete(session, forecastseries_oid)

        # injectionplans belonging to modelruns aren't automatically
        # deleted by the cascade
        for ip in injectionplans:
            InjectionPlanRepository.delete(session, ip)


def create_modelconfig(name, model_config):
    model_config = ModelConfig(name=name, **model_config)
    try:
        with DatabaseSession() as session:
            model_config_out = ModelConfigRepository.create(
                session, model_config)
        return model_config_out
    except DuplicateError:
        raise ValueError(f'ModelConfig with name "{name}" already exists,'
                         ' please choose a different name or archive the'
                         ' existing ModelConfig with the same name.')


def read_modelconfig_oid(name_or_id: str):
    try:
        return UUID(name_or_id, version=4)
    except ValueError:
        with DatabaseSession() as session:
            model_config_db = ModelConfigRepository.get_by_name(
                session, name_or_id)

        if not model_config_db:
            raise Exception(f'ModelConfig "{name_or_id}" not found.')

        return model_config_db.oid


def update_modelconfig(new_config: dict,
                       modelconfig_oid: UUID,
                       force: bool = False):

    if not force:
        with DatabaseSession() as session:
            modelruns = ModelRunRepository.get_by_modelconfig(
                session, modelconfig_oid)
        if len(modelruns) > 0:
            raise Exception(
                'ModelConfig cannot be updated because it is associated with '
                'one or more ModelRuns. Use --force to update anyway.')

    new_data = ModelConfig(oid=modelconfig_oid, **new_config)

    try:
        with DatabaseSession() as session:
            model_config_out = ModelConfigRepository.update(session, new_data)
    except DuplicateError:
        raise ValueError(f'ModelConfig with name "{new_config["name"]}"'
                         ' already exists, please choose a different name.')

    return model_config_out


def delete_modelconfig(modelconfig_oid: UUID):
    with DatabaseSession() as session:
        modelruns = ModelRunRepository.get_by_modelconfig(
            session, modelconfig_oid)
    if len(modelruns) > 0:
        raise Exception(
            'ModelConfig cannot be deleted because it is associated with '
            'one or more ModelRuns. Delete the ModelRuns first.')

    with DatabaseSession() as session:
        ModelConfigRepository.delete(session, modelconfig_oid)


def enable_modelconfig(modelconfig_oid: UUID):
    with DatabaseSession() as session:
        model_config = ModelConfigRepository.get_by_id(
            session, modelconfig_oid)
        model_config.enabled = True
        return ModelConfigRepository.update(session, model_config)


def disable_modelconfig(modelconfig_oid: UUID):
    with DatabaseSession() as session:
        model_config = ModelConfigRepository.get_by_id(
            session, modelconfig_oid)
        model_config.enabled = False
        return ModelConfigRepository.update(session, model_config)


def archive_modelconfig(modelconfig_oid: UUID):
    with DatabaseSession() as session:
        model_config = ModelConfigRepository.get_by_id(
            session, modelconfig_oid)
        model_config.enabled = False
        base_name = model_config.name

    try:
        with DatabaseSession() as session:
            model_config.name = f'{base_name}_archived'
            model_config = ModelConfigRepository.update(session, model_config)
            return model_config
    except DuplicateError:
        for i in range(1, 100):
            with DatabaseSession() as session:
                try:
                    model_config.name = f'{base_name}_archived_{i}'
                    model_config = ModelConfigRepository.update(
                        session, model_config)
                    return model_config
                except DuplicateError:
                    continue


def create_injectionplan_template(name: str,
                                  template: dict,
                                  forecastseries_oid: UUID):
    if not isinstance(template, dict):
        raise ValueError('Injectionplan data must be a single valid '
                         'json object.')

    try:
        InjectionPlanTemplate(**template)  # validate data
    except Exception as e:
        raise ValueError(f'Error parsing injectionplan template: {str(e)}')

    template = json.dumps(template).encode()

    injectionplan = InjectionPlan(name=name,
                                  template=template,
                                  forecastseries_oid=forecastseries_oid)

    try:
        with DatabaseSession() as session:
            injectionplan_out = InjectionPlanRepository.create(
                session, injectionplan)
        return injectionplan_out
    except DuplicateError:
        raise ValueError(
            f'InjectionPlan with name "{name}" already exists'
            ' for this ForecastSeries, please choose a different name.')


def delete_injectionplan(injectionplan_oid: UUID):
    with DatabaseSession() as session:
        modelruns = ModelRunRepository.get_by_injectionplan(
            session, injectionplan_oid)

    if len(modelruns) > 0:
        raise Exception(
            'Injectionplan cannot be deleted because it is associated with '
            'one or more ModelRuns. Delete the ModelRuns first.')

    with DatabaseSession() as session:
        InjectionPlanRepository.delete(session, injectionplan_oid)


def delete_forecast(forecast_oid: UUID):
    with DatabaseSession() as session:

        injectionplans = InjectionPlanRepository.get_ids_by_forecast(
            session, forecast_oid)

        ForecastRepository.delete(session, forecast_oid)

        for ip in injectionplans:
            InjectionPlanRepository.delete(session, ip)

    return f"Forecast {forecast_oid} deleted."
