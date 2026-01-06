import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from hermes.tests.data_factories import TestScenarioBuilder
from web.main import app
from web.tests.database import (cleanup_test_async_connection,
                                cleanup_test_async_session,
                                create_test_async_connection,
                                create_test_async_engine,
                                create_test_async_session)

pytest_plugins = ['hermes.conftest']


@pytest_asyncio.fixture
async def async_engine(connection):
    """Async engine pointing to the test database.

    Depends on 'connection' fixture (from hermes) to ensure the test database
    is created before we try to connect to it.
    """
    engine = create_test_async_engine()
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_connection(async_engine):
    """Async connection with transaction-based isolation.

    All operations within the test happen in a transaction that is
    rolled back at test end, ensuring complete isolation between tests.
    """
    conn, trans = await create_test_async_connection(async_engine)
    yield conn
    await cleanup_test_async_connection(conn, trans)


@pytest_asyncio.fixture
async def async_session(async_connection):
    """Async session for web tests.

    Bound to the test connection's transaction. Automatically injected
    into the web sessionmanager so all endpoint database operations
    use this isolated session.
    """
    session, listener = create_test_async_session(async_connection)
    yield session
    await cleanup_test_async_session(session, listener)


@pytest_asyncio.fixture
async def sync_session_factory(async_connection):
    """Factory for running sync code within the async transaction.

    Use this to create test data with any sync factory while maintaining
    transaction isolation. The sync code runs in the same transaction as
    async_session, so data is visible to endpoints and rolled back at test end.

    Example:
        async def test_custom_scenario(sync_session_factory, test_client):
            def create_data(session):
                project = ProjectRepository.create(session, project_data)
                return project

            project = await sync_session_factory(create_data)
            response = await test_client.get(f"/v1/projects/{project.oid}")
    """
    async def _run_with_session(func, *args, **kwargs):
        def wrapper(sync_connection):
            session = Session(bind=sync_connection, expire_on_commit=False)
            try:
                result = func(session, *args, **kwargs)
                session.flush()
                return result
            finally:
                session.close()
        return await async_connection.run_sync(wrapper)
    return _run_with_session


@pytest_asyncio.fixture
async def scenario_web(sync_session_factory):
    """Complete test scenario for web tests without events."""
    def create_scenario(session):
        return TestScenarioBuilder.create_full_modelrun_scenario(
            session,
            forecastseries={'tags': ['tag1', 'tag2']},
            model_config={'tags': ['tag1', 'tag3']}
        )

    return await sync_session_factory(create_scenario)


@pytest_asyncio.fixture
async def scenario_with_events(sync_session_factory):
    """Test scenario with event forecasts for query testing."""
    def create_scenario(session):
        return TestScenarioBuilder.create_scenario_with_events(
            session,
            n_catalogs=3,
            forecastseries={'tags': ['tag1', 'tag2']},
            model_config={'tags': ['tag1', 'tag3']}
        )

    return await sync_session_factory(create_scenario)


@pytest_asyncio.fixture
async def test_client(async_session):
    """FastAPI test client with test database session injected.

    The async_session fixture ensures sessionmanager returns the test
    session, so all endpoint DB operations use the isolated transaction.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport,
                           base_url="http://test") as client:
        yield client
