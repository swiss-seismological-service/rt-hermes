import typer
from alembic import command
from rich.console import Console

from hermes.datamodel.alembic.utils import ALEMBIC_CFG, check_current_head
from hermes.repositories.database import (_check_tables_exist, _create_tables,
                                          _drop_tables)

app = typer.Typer()
console = Console()


@app.command(help="Initialize Database Tables.")
def init(
    set_credentials: bool = typer.Option(
        True,
        "--set-credentials/--no-set-credentials",
        help="Save credentials to Prefect Block for distributed workers"
    )
):
    if _check_tables_exist():
        console.print("Tables already exist.")
        return

    _create_tables()

    command.ensure_version(ALEMBIC_CFG)
    command.stamp(ALEMBIC_CFG, "schema@head")
    command.upgrade(ALEMBIC_CFG, "utils@head")

    console.print("Database initialized.")

    if set_credentials:
        from hermes.cli.config_cli import _save_credentials_to_block
        from hermes.config import get_settings

        console.print()
        if _save_credentials_to_block("hermes-db", overwrite=True):
            settings = get_settings()
            console.print("Credentials saved to Prefect Block 'hermes-db'")
            console.print(
                f"  Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            console.print(f"  Database: {settings.POSTGRES_DB}")
        else:
            console.print(
                "[yellow]Warning:[/yellow] Failed to save credentials")


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
