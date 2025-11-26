import typer

from hermes.cli.database import app as database
from hermes.cli.forecast import app as forecast
from hermes.cli.forecastseries import app as forecastseries
from hermes.cli.injectionplan import app as injectionplan
from hermes.cli.model import app as model
from hermes.cli.project import app as project
from hermes.cli.schedule import app as schedule
from hermes.datamodel.alembic.utils import check_db

app = typer.Typer(pretty_exceptions_enable=False)


@app.callback()
def main(ctx: typer.Context):
    # make sure that the database is initialized and up to date
    if ctx.invoked_subcommand != "db":
        check_db()


app.add_typer(project, name="projects")
app.add_typer(forecastseries, name="forecastseries")
app.add_typer(model, name="models")
app.add_typer(forecast, name="forecasts")
app.add_typer(schedule, name="schedules")
app.add_typer(injectionplan, name="injectionplans")
app.add_typer(database, name="db")
