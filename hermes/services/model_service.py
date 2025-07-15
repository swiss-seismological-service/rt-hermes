from uuid import UUID

from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ModelConfigRepository
from hermes.repositories.results import ModelRunRepository
from hermes.repositories.types import DuplicateError
from hermes.schemas import ModelConfig


def get_modelconfig_oid(name_or_id: str):
    try:
        return UUID(name_or_id, version=4)
    except ValueError:
        with DatabaseSession() as session:
            model_config_db = ModelConfigRepository.get_by_name(
                session, name_or_id)

        if not model_config_db:
            raise Exception(f'ModelConfig "{name_or_id}" not found.')

        return model_config_db.oid


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
