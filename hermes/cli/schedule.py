import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from hermes.cli.utils import console_table, console_tree
from hermes.flows.forecastseries_scheduler import ForecastSeriesScheduler
from hermes.repositories.database import DatabaseSession
from hermes.repositories.project import ForecastSeriesRepository
from hermes.services.forecastseries_service import get_forecastseries_oid

app = typer.Typer()
console = Console()


@app.command(help="Lists existing schedules.")
def list():
    with DatabaseSession() as session:
        fseries = ForecastSeriesRepository.get_all(session)

    fs_with_schedule = []

    for fs in fseries:
        scheduler = ForecastSeriesScheduler(fs.oid)
        if asyncio.run(scheduler.check_schedule_exists()):
            fs_with_schedule.append(fs)

    if not fs_with_schedule:
        console.print("No Schedules found.")
        return

    table = console_table(fs_with_schedule, ['name',
                                             'schedule_starttime',
                                             'schedule_endtime',
                                             'schedule_interval',
                                             'schedule_active'])

    console.print(table)


@app.command(help="Show full details of a single schedule.")
def show(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")]):

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        exists = asyncio.run(scheduler.check_schedule_exists())
        fs_config = scheduler.schedule_info
    except ValueError as e:
        console.print(str(e))
        raise typer.Exit(code=1)
    except BaseException as e:
        raise e

    if not exists:
        console.print("No schedule found.")
        raise typer.Exit(code=1)

    tree = console_tree(fs_config, show_none=False)
    console.print(tree)


@app.command(help="Schedules future Forecasts.")
def create(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")],
    config: Annotated[Path,
                      typer.Option(
                          ...,
                          resolve_path=True,
                          readable=True,
                          help="Path to json schedule "
                          "configuration file.")]):

    with open(config, "r") as project_file:
        schedule_config = json.load(project_file)

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        asyncio.run(scheduler.create(schedule_config))

        console.print(
            f'Successfully created schedule for "{forecastseries}".')
    except BaseException as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Deletes existing schedule.")
def delete(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")]):

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)

        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        asyncio.run(scheduler.delete_schedule())
        console.print(
            f'Successfully deleted schedule for "{forecastseries}".')
    except BaseException as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Activate existing schedule.")
def activate(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")]):

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        asyncio.run(scheduler.update_status(active=True))

        console.print(
            f'Successfully activated schedule for "{forecastseries}".')
    except BaseException as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Deactivate existing schedule.")
def deactivate(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")]):

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        asyncio.run(scheduler.update_status(active=False))

        console.print(
            f'Successfully deactivated schedule for "{forecastseries}".')
    except BaseException as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Executes Forecasts for the given schedule which "
             "have scheduled start times in the past.")
def catchup(
    forecastseries: Annotated[str,
                              typer.Argument(
                                  help="Name or UUID of "
                                  "the ForecastSeries.")],
    local: Annotated[
        bool,
        typer.Option(
            help="Flag to run the Forecast in local mode.")] = False
):
    mode = 'local' if local else 'deploy'

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        scheduler = ForecastSeriesScheduler(forecastseries_oid)
        asyncio.run(scheduler.run_past_forecasts(mode))
    except BaseException as e:
        console.print(str(e))
        raise typer.Exit(code=1)
