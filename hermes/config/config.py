import inspect
from typing import Literal

from prefect.utilities.asyncutils import run_coro_as_sync
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from hermes.config.blocks import HermesDatabaseCredentials


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    # Credential source: 'env' (default) or 'prefect' (for distributed workers)
    CREDENTIAL_SOURCE: Literal['env', 'prefect'] = 'env'

    # Local database credentials (used when CREDENTIAL_SOURCE='env')
    POSTGRES_HOST: str = 'localhost'
    POSTGRES_HOST_EXTERNAL: str = 'localhost'
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = 'postgres'
    POSTGRES_PASSWORD: str | None = None
    POSTGRES_DB: str = 'postgres'

    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10

    # Timezone of the DATA, eg. if 'UTC', all datetime which are passed
    # via CLI and configuration files will be converted from the operators
    # system timezone to UTC before querying data and running forecasts.
    TIMEZONE: str | None = None

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> URL:
        if self.CREDENTIAL_SOURCE == 'prefect':
            return self._get_url_from_block()
        return self._get_url_from_env()

    @property
    def ASYNC_SQLALCHEMY_DATABASE_URL(self) -> URL:
        if self.CREDENTIAL_SOURCE == 'prefect':
            return self._get_url_from_block(async_driver=True)
        return self._get_url_from_env(async_driver=True)

    def _get_url_from_env(self, async_driver: bool = False) -> URL:
        driver = "postgresql+asyncpg" if async_driver \
            else "postgresql+psycopg2"
        return URL.create(
            drivername=driver,
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB
        )

    def _get_url_from_block(self, async_driver: bool = False) -> URL:
        result = HermesDatabaseCredentials.load("hermes-db")
        block = run_coro_as_sync(result) if \
            inspect.iscoroutine(result) else result
        return block.get_connection_url(async_driver=async_driver)


_settings_instance: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    """
    Get application settings.

    Args:
        refresh: If True, reload settings (useful after credential rotation)

    Returns:
        Settings instance
    """
    global _settings_instance
    if _settings_instance is None or refresh:
        _settings_instance = Settings()
    return _settings_instance
