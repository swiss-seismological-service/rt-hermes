import pytest
from prefect.logging import disable_run_logger
from prefect.testing.fixtures import \
    add_prefect_loggers_to_caplog  # noqa: F401
from prefect.testing.utilities import prefect_test_harness
from sqlalchemy import Connection

from hermes.repositories.tests.database import (cleanup_test_environment,
                                                cleanup_test_session,
                                                create_test_environment,
                                                create_test_session)
from hermes.tests.data_factories import TestScenarioBuilder


@pytest.fixture(scope="session")
def connection(request: pytest.FixtureRequest) -> Connection:
    """Create test database connection using repository package utilities.
    """
    # Use repository package to create complete test environment
    connection, test_db_name = create_test_environment()

    def teardown():
        cleanup_test_environment(connection, test_db_name)

    request.addfinalizer(teardown)
    return connection


@pytest.fixture
def session(connection: Connection, request: pytest.FixtureRequest):
    """Create database session with transaction rollback for test isolation.

    Uses repository package utilities to maintain the repository pattern.
    """
    session, transaction = create_test_session(connection)

    def teardown():
        cleanup_test_session(session, transaction)

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
    """Prefect test harness for all tests with logging disabled."""
    with prefect_test_harness():
        with disable_run_logger():
            yield


@pytest.fixture(scope="function")
def prefect_with_logs(add_prefect_loggers_to_caplog):  # noqa
    """Prefect test harness with logging enabled.

    Use this instead of 'prefect' when you want to see logs.
    Automatically configures caplog to capture Prefect logs.
    """
    with prefect_test_harness():
        yield
