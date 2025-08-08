from sqlalchemy import Connection, event, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import scoped_session, sessionmaker

from hermes.config import get_settings
from hermes.datamodel.base import ORMBase
from hermes.repositories.database import create_engine, create_extensions

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


def create_test_database(test_db_name: str) -> Connection:
    """Create and setup a test database, returning connection to it."""
    # Create/recreate test database
    engine = create_test_engine()
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        delete_database(conn, test_db_name)
        try:
            conn.execute(text(f"CREATE DATABASE {test_db_name}"))
        except (ProgrammingError, OperationalError):
            # Database might still exist from previous failed tests
            # - try to delete again
            delete_database(conn, test_db_name)
            conn.execute(text(f"CREATE DATABASE {test_db_name}"))
    engine.dispose()

    # Connect to test database with extensions
    test_engine = create_test_engine(test_db_name)
    create_extensions(test_engine)
    connection = test_engine.connect()
    return connection


def cleanup_test_database(connection: Connection, test_db_name: str):
    """Clean up test database and connection."""
    test_engine = connection.engine
    connection.close()
    test_engine.dispose()

    # Clean up test database
    cleanup_engine = create_test_engine()
    with cleanup_engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        delete_database(conn, test_db_name)
    cleanup_engine.dispose()


def setup_test_tables(connection: Connection):
    """Setup test database tables."""
    ORMBase.metadata.create_all(connection.engine)


def teardown_test_tables(connection: Connection):
    """Teardown test database tables."""
    ORMBase.metadata.drop_all(connection.engine)


def create_test_session(connection: Connection):
    """Create a test session with transaction isolation."""
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

    return session, transaction


def cleanup_test_session(session, transaction):
    """Clean up test session and transaction."""
    session.remove()
    if transaction.is_active:
        transaction.rollback()


def create_test_environment():
    """Create complete test environment: database + tables + connection.

    Returns:
        tuple: (connection, test_db_name) for use in fixtures
    """
    test_db_name = f"{settings.POSTGRES_DB}_test"

    # Create test database and get connection
    connection = create_test_database(test_db_name)

    # Setup database tables
    setup_test_tables(connection)

    return connection, test_db_name


def cleanup_test_environment(connection: Connection,
                             test_db_name: str):
    """Clean up complete test environment: tables + database.

    Args:
        connection: Database connection to clean up
        test_db_name: Name of test database to drop
    """
    # Teardown tables first, then database
    teardown_test_tables(connection)
    cleanup_test_database(connection, test_db_name)
