import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import scoped_session, sessionmaker

from hermes.config import get_settings
from hermes.tests.data_factories import TestScenarioBuilder
from web.main import app
from web.tests.database import (cleanup_test_sessionmanager,
                                configure_test_sessionmanager)

pytest_plugins = ['hermes.conftest']


@pytest.fixture(scope="module")
def module_session(connection):
    """Module-scoped session that commits data to database.

    Unlike function-scoped session, data is visible to async connections.
    Cleans up all data at module end.
    """
    session = scoped_session(sessionmaker(
        bind=connection, expire_on_commit=False))
    yield session
    session.rollback()
    session.remove()


@pytest.fixture(scope="module")
def web_scenario(module_session):
    """Test scenario for web tests using existing TestScenarioBuilder."""
    return TestScenarioBuilder.create_full_modelrun_scenario(module_session)


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def test_client(connection):
    """FastAPI test client with injected test database."""
    test_db_name = f"{get_settings().POSTGRES_DB}_test"
    await configure_test_sessionmanager(test_db_name)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await cleanup_test_sessionmanager()
