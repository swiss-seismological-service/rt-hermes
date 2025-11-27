import json
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from hermes.cli.utils import console_table, console_tree
from hermes.flows.forecastseries_deployment import serve_forecastseries
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastSeriesRepository
from hermes.schemas.project_schemas import ForecastSeriesConfig
from hermes.services.forecastseries_service import (create_forecastseries,
                                                    delete_forecastseries,
                                                    get_forecastseries_oid,
                                                    update_forecastseries)
from hermes.services.project_service import get_project_oid

app = typer.Typer()
console = Console()


@app.command(help="Outputs list of ForecastSeries")
def list():
    with DatabaseSession() as session:
        fseries = ForecastSeriesRepository.get_all(session)
    if not fseries:
        console.print("No ForecastSeries found")
        return

    table = console_table(fseries,
                          ['oid', 'name', 'observation_starttime',
                                  'observation_endtime', 'tags'])

    console.print(table)


@app.command(help="Show full details of a single ForecastSeries.")
def show(forecastseries:
         Annotated[str,
                   typer.Argument(
                       help="Name or UUID of the ForecastSeries.")]):

    with DatabaseSession() as session:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        forecast_series = ForecastSeriesRepository.get_by_id(
            session, forecastseries_oid)

    if not forecast_series:
        console.print("ForecastSeries not found.")
        return

    # don't display all the schedule information
    fs_config = ForecastSeriesConfig(
        **forecast_series.model_dump(
            include=ForecastSeriesConfig.model_fields.keys()))

    tree = console_tree(fs_config)
    console.print(tree)


@app.command(help="Creates a new ForecastSeries.")
def create(name: Annotated[str,
                           typer.Argument(
                               help="Name of the ForecastSeries.")],
           project: Annotated[str,
                              typer.Option(
                                  ...,
                                  help="Name or UUID of the parent Project.")],
           config: Annotated[Path,
                             typer.Option(
                                 ..., resolve_path=True, readable=True,
                                 help="Path to json Forecastseries "
                                 "configuration file.")]):

    with open(config, "r") as project_file:
        fseries_config = json.load(project_file)

    try:
        project_oid = get_project_oid(project)

        forecast_series_out = create_forecastseries(
            name, fseries_config, project_oid)

        console.print('Successfully created new ForecastSeries '
                      f'{forecast_series_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Updates a ForecastSeries.")
def update(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of the ForecastSeries.")],
    config: Annotated[Path,
                      typer.Option(
                          ..., resolve_path=True, readable=True,
                          help="Path to json Forecastseries "
                          "configuration file.")],
    force: Annotated[bool,
                     typer.Option("--force")] = False):

    with open(config, "r") as project_file:
        fseries_config = json.load(project_file)

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)

        forecast_series_out = update_forecastseries(
            fseries_config, forecastseries_oid, force)

        console.print(
            f'Successfully updated ForecastSeries {forecast_series_out.name}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Deletes a ForecastSeries.")
def delete(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of the ForecastSeries.")]
):
    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)

        delete_forecastseries(forecastseries_oid)

        console.print(f'Successfully deleted ForecastSeries {forecastseries}.')
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Serve the forecastseries.")
def serve(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of the ForecastSeries.")],
    concurrency_limit: Annotated[int,
                                 typer.Option()] = 3
):
    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        serve_forecastseries(forecastseries_oid, concurrency_limit)
    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)
