import json
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from hermes.cli.utils import console_table, console_tree
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ModelConfigRepository
from hermes.services.model_service import (archive_modelconfig,
                                           create_modelconfig,
                                           delete_modelconfig,
                                           disable_modelconfig,
                                           enable_modelconfig,
                                           get_modelconfig_oid,
                                           update_modelconfig)

app = typer.Typer()
console = Console()


@app.command(help="List all ModelConfigs.")
def list():
    with DatabaseSession() as session:
        model_config = ModelConfigRepository.get_all(session)
    if not model_config:
        console.print("No ModelConfigs found")
        return

    table = console_table(
        model_config, ['oid', 'name', 'tags', 'enabled'])

    console.print(table)


@app.command(help="Show full details of a single ModelConfig.")
def show(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")]):
    with DatabaseSession() as session:
        modelconfig_oid = get_modelconfig_oid(modelconfig)
        model_config = ModelConfigRepository.get_by_id(
            session, modelconfig_oid)

    if not model_config:
        console.print("ModelConfig not found.")
        return

    tree = console_tree(model_config)
    console.print(tree)


@app.command(help="Create a new ModelConfig.")
def create(
    name: Annotated[str, typer.Argument(help="Name of the ModelConfig.")],
    config: Annotated[Path, typer.Option(
        ..., resolve_path=True, readable=True,
        help="Path to json ModelConfig configuration file.")]
):
    try:
        with open(config, "r") as model_config_file:
            model_config_dict = json.load(model_config_file)

        model_config = create_modelconfig(name, model_config_dict)

        console.print(f"Successfully created ModelConfig {model_config.name}.")

    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Update an existing ModelConfig.")
def update(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")],
    config: Annotated[Path,
                      typer.Option(
                          ..., resolve_path=True, readable=True,
                          help="Path to json ModelConfig "
                          "configuration file.")],
    force: Annotated[bool,
                     typer.Option("--force")] = False):
    """
    Only possible if no ModelRun exists for the ModelConfig.
    """

    with open(config, "r") as project_file:
        new_config = json.load(project_file)

    try:
        modelconfig_oid = get_modelconfig_oid(modelconfig)

        model_config_out = update_modelconfig(
            new_config, modelconfig_oid, force)

        console.print(
            f'Successfully updated ForecastSeries {model_config_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Delete a ModelConfig.")
def delete(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")]):
    """
    Only possible if no ModelRun exists for the ModelConfig.
    """
    try:
        modelconfig_oid = get_modelconfig_oid(modelconfig)

        delete_modelconfig(modelconfig_oid)

        console.print(f'Successfully deleted ModelConfig {modelconfig}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Disable a ModelConfig.")
def disable(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")]):
    try:
        modelconfig_oid = get_modelconfig_oid(modelconfig)

        model_config_out = disable_modelconfig(modelconfig_oid)

        console.print(
            f'Successfully disabled ModelConfig {model_config_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Enable a ModelConfig.")
def enable(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")]):
    try:
        modelconfig_oid = get_modelconfig_oid(modelconfig)

        model_config_out = enable_modelconfig(modelconfig_oid)

        console.print(
            f'Successfully enabled ModelConfig {model_config_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Archive a ModelConfig.")
def archive(
    modelconfig: Annotated[str,
                           typer.Argument(
                               help="Name or UUID of the ModelConfig.")]):

    try:
        modelconfig_oid = get_modelconfig_oid(modelconfig)

        model_config_out = archive_modelconfig(modelconfig_oid)

        console.print(
            f'Successfully archived ModelConfig {model_config_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)
