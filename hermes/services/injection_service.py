import json
from uuid import UUID

from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.repositories.results import ModelRunRepository
from hermes.repositories.types import DuplicateError
from hermes.schemas.data_schemas import InjectionPlan, InjectionPlanTemplate


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
