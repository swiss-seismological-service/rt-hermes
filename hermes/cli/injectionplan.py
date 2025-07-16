import json
from pathlib import Path

import typer
from rich.console import Console
from typing_extensions import Annotated

from hermes.cli.utils import console_table
from hermes.repositories.data import InjectionPlanRepository
from hermes.repositories.database import DatabaseSession
from hermes.services.forecastseries_service import get_forecastseries_oid
from hermes.services.injection_service import (create_injectionplan_template,
                                               delete_injectionplan)

app = typer.Typer()
console = Console()


@app.command(help="Outputs Injectionplans for a ForecastSeries.")
def list(forecastseries:
         Annotated[str,
                   typer.Argument(
                       help="Name or UUID of the ForecastSeries.")]):

    with DatabaseSession() as session:
        forecastseries_oid = get_forecastseries_oid(forecastseries)
        if not forecastseries_oid:
            console.print("ForecastSeries not found.")
            raise typer.Exit(code=1)

        injectionplan = InjectionPlanRepository.get_by_forecastseries(
            session,
            forecastseries_oid)
        if not injectionplan:
            console.print("No InjectionPlan found.")
            raise typer.Exit(code=1)

    table = console_table(injectionplan, ['oid', 'name'])

    console.print(table)


@app.command(help="Creates a new Injectionplan.")
def create(name: Annotated[str,
                           typer.Argument(
                               help="Name of the Injectionplan.")],
           forecastseries: Annotated[str,
                                     typer.Option(
                                         ...,
                                         help="Name or UUID of the associated"
                                         " Forecast Series.")],
           file: Annotated[Path,
                           typer.Option(
                               ..., resolve_path=True, readable=True,
                               help="Path to IP template file.")]):

    with open(file, "r") as injectionplan_file:
        injectionplan = json.load(injectionplan_file)

    try:
        forecastseries_oid = get_forecastseries_oid(forecastseries)

        forecast_series_out = create_injectionplan_template(
            name, injectionplan, forecastseries_oid)

        console.print('Successfully created new Injectionplan '
                      f'"{forecast_series_out.name}" '
                      f'for ForecastSeries "{forecastseries}".')

    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)


@app.command(help="Delete an Injectionplan.")
def delete(injectionplan: Annotated[str,
                                    typer.Argument(
                                        help="UUID of the Injectionplan.")]):
    try:
        delete_injectionplan(injectionplan)

        console.print(f'Injectionplan "{injectionplan}" deleted.')

    except Exception as e:
        console.print(str(e))
        raise typer.Exit(code=1)
