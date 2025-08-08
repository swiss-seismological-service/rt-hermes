"""
Shared pytest fixtures for all test layers.

This conftest.py is at the package root and provides fixtures that are
automatically discoverable by all test directories in the hermes package.
"""
import pytest
from prefect.logging import disable_run_logger
from prefect.testing.utilities import prefect_test_harness
from sqlalchemy import Connection, event, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import scoped_session, sessionmaker

from hermes.config import get_settings
from hermes.datamodel.base import ORMBase
from hermes.repositories.database import create_engine, create_extensions
from hermes.tests.data_factories import TestScenarioBuilder

settings = get_settings()


def create_test_engine(db_name: str = None):
    """Create database engine for testing."""
    url = URL.create(
        drivername='postgresql+psycopg2',
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=db_name
    )
    return create_engine(url)


def delete_database(connection: Connection, db_name: str):
    """Helper to clean up test database."""
    try:
        connection.execute(text(f"DROP DATABASE {db_name}"))
    except (ProgrammingError, OperationalError):
        # Database doesn't exist or is in use - ignore silently
        pass


@pytest.fixture(scope="session")
def connection(request: pytest.FixtureRequest) -> Connection:
    """Create a test database connection for all test sessions."""
    test_db_name = f"{settings.POSTGRES_DB}_test"

    # Create/recreate test database
    engine = create_test_engine()
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        delete_database(conn, test_db_name)
        conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    engine.dispose()

    # Connect to test database with extensions
    test_engine = create_test_engine(test_db_name)
    create_extensions(test_engine)
    connection = test_engine.connect()

    def teardown():
        connection.close()
        test_engine.dispose()
        # Clean up test database
        cleanup_engine = create_test_engine()
        with cleanup_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT")
            delete_database(conn, test_db_name)
        cleanup_engine.dispose()

    request.addfinalizer(teardown)
    return connection


@pytest.fixture(scope="session", autouse=True)
def setup_db(connection: Connection, request: pytest.FixtureRequest):
    """Setup test database tables.

    Creates all database tables as declared in SQLAlchemy models,
    then proceeds to drop all the created tables after all tests
    have finished running.
    """
    ORMBase.metadata.create_all(connection.engine)

    def teardown():
        ORMBase.metadata.drop_all(connection.engine)

    request.addfinalizer(teardown)


@pytest.fixture(autouse=True)
def session(connection: Connection, request: pytest.FixtureRequest):
    """Create database session with transaction rollback for test isolation."""
    transaction = connection.begin()
    session = scoped_session(sessionmaker(
        bind=connection, expire_on_commit=False))

    session.begin_nested()

    # Restart savepoint after each commit
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(_, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()

    def teardown():
        session.remove()
        if transaction.is_active:
            transaction.rollback()

    request.addfinalizer(teardown)
    return session


# Scenario Fixtures for Complex Test Scenarios

@pytest.fixture()
def full_scenario(session):
    """Complete test scenario: project → series → forecast → modelrun."""
    return TestScenarioBuilder.create_full_modelrun_scenario(
        session,
        forecastseries={'tags': ['tag1', 'tag2']},
        model_config={'tags': ['tag1', 'tag3']}
    )


@pytest.fixture()
def modelrun_with_dependencies(session):
    """ModelRun with all required dependencies for service testing."""
    return TestScenarioBuilder.create_service_test_scenario(session)


@pytest.fixture(scope="class")
def prefect():
    """Prefect test harness for all tests."""
    with prefect_test_harness():
        with disable_run_logger():
            yield
