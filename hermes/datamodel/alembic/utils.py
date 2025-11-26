from importlib.resources import files

import typer
from alembic import script
from alembic.config import Config
from alembic.runtime import migration

import hermes.datamodel.alembic
from hermes.repositories.database import _check_tables_exist, get_engine


def get_alembic_config() -> Config:
    ini_path = files(hermes.datamodel.alembic).joinpath("alembic.ini")
    cfg = Config(str(ini_path))

    cfg.set_main_option("script_location", str(
        files(hermes.datamodel.alembic)))
    return cfg


ALEMBIC_CFG = get_alembic_config()


def check_current_head(alembic_cfg) -> bool:
    directory = script.ScriptDirectory.from_config(alembic_cfg)
    with get_engine().begin() as connection:
        context = migration.MigrationContext.configure(connection)
        return set(context.get_current_heads()) == set(directory.get_heads())


def check_db():
    if not _check_tables_exist():
        typer.echo("Please initialize the database first.")
        raise typer.Abort()
    if not check_current_head(ALEMBIC_CFG):
        typer.echo("Please upgrade the database first.")
        raise typer.Abort()
