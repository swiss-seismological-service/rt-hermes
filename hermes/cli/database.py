import typer
from alembic import command
from rich.console import Console

from hermes.datamodel.alembic.utils import ALEMBIC_CFG, check_current_head
from hermes.repositories.database import (_check_tables_exist, _create_tables,
                                          _drop_tables)

app = typer.Typer()
console = Console()


@app.command(help="Initialize Database Tables.")
def init():
    if _check_tables_exist():
        console.print("Tables already exist.")
        return

    _create_tables()

    command.ensure_version(ALEMBIC_CFG)
    command.stamp(ALEMBIC_CFG, "schema@head")
    command.upgrade(ALEMBIC_CFG, "utils@head")


@app.command(help="Drop Database Tables.")
def purge():
    command.downgrade(ALEMBIC_CFG, "utils@base")
    _drop_tables()


@app.command(help="Upgrade Database Tables.")
def upgrade():

    if not _check_tables_exist():
        console.print("Please initialize the database first.")

    if not check_current_head(ALEMBIC_CFG):
        command.upgrade(ALEMBIC_CFG, "schema@head")
        command.upgrade(ALEMBIC_CFG, "utils@head")
    else:
        console.print("Database is already up to date.")
