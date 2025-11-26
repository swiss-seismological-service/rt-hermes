from prefect.blocks.core import Block
from pydantic import SecretStr
from sqlalchemy.engine import URL


class HermesDatabaseCredentials(Block):
    """
    Block for storing HERMES database credentials.

    Credentials are encrypted and stored in Prefect Server.
    Workers retrieve credentials at runtime without needing
    local configuration files.

    Example:
        # On host machine: copy .env credentials to Prefect Block
        hermes config set-credentials

        # On worker: load credentials from block
        block = HermesDatabaseCredentials.load("hermes-db")
        url = block.get_connection_url()
    """
    _block_type_name = "hermes-database-credentials"
    _block_type_slug = "hermes-db-credentials"

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr
    database: str = "postgres"

    def get_connection_url(self, async_driver: bool = False) -> URL:
        """
        Build SQLAlchemy connection URL from stored credentials.

        Args:
            async_driver: If True, use asyncpg driver instead of psycopg2

        Returns:
            SQLAlchemy URL object
        """
        driver = "postgresql+asyncpg" if async_driver \
            else "postgresql+psycopg2"
        return URL.create(
            drivername=driver,
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.database
        )
