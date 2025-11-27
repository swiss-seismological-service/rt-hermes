import os

import typer
from alembic import command
from rich.console import Console
from sqlalchemy.sql import text

from hermes.config import HermesDatabaseCredentials, get_settings
from hermes.datamodel.alembic.utils import ALEMBIC_CFG, check_current_head
from hermes.repositories.database import (_check_tables_exist, _create_tables,
                                          _drop_tables, get_engine,
                                          reset_engine)

app = typer.Typer()
console = Console()

BLOCK_NAME = "hermes-db"


def _save_credentials_to_block(block_name: str,
                               overwrite: bool = False) -> bool:
    """
    Save current .env credentials to a Prefect Block.

    Returns True if successful, False otherwise.
    """

    settings = get_settings()

    if not settings.POSTGRES_PASSWORD:
        console.print(
            "[red]Error:[/red] POSTGRES_PASSWORD not set in environment")
        return False

    block = HermesDatabaseCredentials(
        host=settings.POSTGRES_HOST_EXTERNAL,
        port=int(settings.POSTGRES_PORT),
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB
    )

    try:
        block.save(block_name, overwrite=overwrite)
        return True
    except ValueError as e:
        if "already exists" in str(e):
            console.print(
                f"[red]Error:[/red] Block '{block_name}' already exists. "
                "Use --overwrite to replace."
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        return False


@app.command("initialize", help="Initialize database tables.")
def initialize(
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

        console.print()
        if _save_credentials_to_block(BLOCK_NAME, overwrite=True):
            settings = get_settings()
            console.print(f"Credentials saved to Prefect Block '{BLOCK_NAME}'")
            console.print(
                f"  Host: {settings.POSTGRES_HOST_EXTERNAL}:"
                f"{settings.POSTGRES_PORT}")
            console.print(f"  Database: {settings.POSTGRES_DB}")
        else:
            console.print(
                "[yellow]Warning:[/yellow] Failed to save credentials")


@app.command("downgrade", help="Downgrade database tables.")
def downgrade(
    revision: str = typer.Argument(
        None,
        help="Target revision (e.g., 'schema@-1', 'utils@base', or revision "
             "id). If not specified, drops all tables (requires -y flag)."
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        help="Confirm dropping all tables when no revision is specified."
    )
):
    if revision:
        command.downgrade(ALEMBIC_CFG, revision)
    elif yes:
        command.downgrade(ALEMBIC_CFG, "utils@base")
        _drop_tables()
        console.print("Database tables dropped.")
    else:
        console.print(
            "This will drop all database tables. "
            "Use -y to confirm, or specify a revision to downgrade to."
        )
        raise typer.Exit(code=1)


@app.command("upgrade", help="Upgrade database tables.")
def upgrade(
    revision: str = typer.Argument(
        None,
        help="Target revision (e.g., 'schema@head', 'utils@+1', or revision "
             "id). If not specified, upgrades both branches to head."
    )
):
    if not _check_tables_exist():
        console.print("Please initialize the database first.")
        return

    if revision:
        command.upgrade(ALEMBIC_CFG, revision)
    elif not check_current_head(ALEMBIC_CFG):
        command.upgrade(ALEMBIC_CFG, "schema@head")
        command.upgrade(ALEMBIC_CFG, "utils@head")
    else:
        console.print("Database is already up to date.")


@app.command("set-credentials",
             help="Save credentials to Prefect Block for distributed workers.")
def set_credentials(
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing block"
    )
):
    """
    Copy current .env database credentials to a Prefect Block.

    Reads POSTGRES_* variables from your current environment/.env file
    and saves them to a Prefect Block for use by remote workers.
    """

    settings = get_settings()

    if _save_credentials_to_block(BLOCK_NAME, overwrite):
        console.print(f"Credentials saved to Prefect Block '{BLOCK_NAME}'")
        console.print(
            f"  Host: {settings.POSTGRES_HOST_EXTERNAL}:"
            f"{settings.POSTGRES_PORT}")
        console.print(f"  Database: {settings.POSTGRES_DB}")
        console.print(f"  User: {settings.POSTGRES_USER}")
        console.print()
        console.print("Workers can now use these credentials with:")
        console.print("  export CREDENTIAL_SOURCE=prefect")
    else:
        raise typer.Exit(code=1)


@app.command("show-credentials",
             help="Display credentials stored in the Prefect Block.")
def show_credentials():

    try:
        block = HermesDatabaseCredentials.load(BLOCK_NAME)
        console.print(f"Block: {BLOCK_NAME}")
        console.print(f"  Host: {block.host}:{block.port}")
        console.print(f"  Database: {block.database}")
        console.print(f"  User: {block.user}")
        console.print("  Password: ********")
    except ValueError:
        console.print(f"[red]Error:[/red] Block '{BLOCK_NAME}' not found")
        console.print("  Run 'hermes db set-credentials' to create it")
        raise typer.Exit(code=1)


@app.command("test-connection",
             help="Test database connection.")
def test_connection(
    source: str = typer.Option(
        None,
        "--source",
        help="Credential source: 'env' or 'prefect' (default: current setting)"
    )
):
    """Test database connection with current or specified credential source."""
    original_source = os.environ.get('CREDENTIAL_SOURCE')
    if source:
        os.environ['CREDENTIAL_SOURCE'] = source

    try:
        settings = get_settings(refresh=True)
        console.print(
            f"Testing connection (source: {settings.CREDENTIAL_SOURCE})...")

        reset_engine()
        engine = get_engine()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()

        console.print("Connection successful")
        console.print(f"  PostgreSQL: {version[:60]}...")

    except Exception as e:
        console.print(f"[red]Connection failed:[/red] {e}")
        raise typer.Exit(code=1)
    finally:
        if original_source is not None:
            os.environ['CREDENTIAL_SOURCE'] = original_source
        elif source:
            os.environ.pop('CREDENTIAL_SOURCE', None)
        reset_engine()
        get_settings(refresh=True)
