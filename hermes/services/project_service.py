from uuid import UUID

from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import (ForecastSeriesRepository,
                                         ProjectRepository)
from hermes.repositories.types import DuplicateError
from hermes.schemas.project_schemas import Project


def get_project_oid(name_or_id: str):
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
        from hermes.services.forecastseries_service import \
            delete_forecastseries
        delete_forecastseries(fseries.oid)

    # delete project
    with DatabaseSession() as session:
        ProjectRepository.delete(session, project_oid)
