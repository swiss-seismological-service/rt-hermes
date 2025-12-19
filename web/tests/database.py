from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hermes.config import get_settings
from web.repositories.database import sessionmanager


def get_test_async_engine(test_db_name: str):
    """Create async engine pointing to test database."""
    settings = get_settings()
    url = URL.create(
        drivername='postgresql+asyncpg',
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=test_db_name
    )
    return create_async_engine(url, echo=False)


async def configure_test_sessionmanager(test_db_name: str):
    """Configure web sessionmanager with test database."""
    engine = get_test_async_engine(test_db_name)
    sm = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)
    sessionmanager.configure_for_testing(engine, sm)


async def cleanup_test_sessionmanager():
    """Clean up the test sessionmanager."""
    if sessionmanager._engine:
        await sessionmanager._engine.dispose()
