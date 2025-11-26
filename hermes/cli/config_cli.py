import typer
from rich.console import Console
from sqlalchemy.sql import text

app = typer.Typer(help="Configuration management commands")
console = Console()

BLOCK_NAME = "hermes-db"


def _save_credentials_to_block(block_name: str,
                               overwrite: bool = False) -> bool:
    """
    Save current .env credentials to a Prefect Block.

    Returns True if successful, False otherwise.
    """
    from hermes.config import HermesDatabaseCredentials, get_settings

    settings = get_settings()

    if not settings.POSTGRES_PASSWORD:
        console.print(
            "[red]Error:[/red] POSTGRES_PASSWORD not set in environment")
        return False

    block = HermesDatabaseCredentials(
        host=settings.POSTGRES_HOST,
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


@app.command("set-credentials")
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
    from hermes.config import get_settings

    settings = get_settings()

    if _save_credentials_to_block(BLOCK_NAME, overwrite):
        console.print(f"Credentials saved to Prefect Block '{BLOCK_NAME}'")
        console.print(
            f"  Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        console.print(f"  Database: {settings.POSTGRES_DB}")
        console.print(f"  User: {settings.POSTGRES_USER}")
        console.print()
        console.print("Workers can now use these credentials with:")
        console.print("  export CREDENTIAL_SOURCE=prefect")
    else:
        raise typer.Exit(code=1)


@app.command("show-credentials")
def show_credentials():
    """Display credentials stored in the Prefect Block."""
    from hermes.config import HermesDatabaseCredentials

    try:
        block = HermesDatabaseCredentials.load(BLOCK_NAME)
        console.print(f"Block: {BLOCK_NAME}")
        console.print(f"  Host: {block.host}:{block.port}")
        console.print(f"  Database: {block.database}")
        console.print(f"  User: {block.user}")
        console.print("  Password: ********")
    except ValueError:
        console.print(f"[red]Error:[/red] Block '{BLOCK_NAME}' not found")
        console.print("  Run 'hermes config set-credentials' to create it")
        raise typer.Exit(code=1)


@app.command("test-connection")
def test_connection(
    source: str = typer.Option(
        None,
        "--source",
        help="Credential source: 'env' or 'prefect' (default: current setting)"
    )
):
    """Test database connection with current or specified credential source."""
    import os

    from hermes.config import get_settings
    from hermes.repositories.database import get_engine, reset_engine

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
