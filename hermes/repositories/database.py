import pandas as pd
from sqlalchemy import Select
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import MetaData
from sqlalchemy.sql import text

from hermes.config import get_settings
from hermes.datamodel.base import ORMBase

EXTENSIONS = ['postgis', 'postgis_topology']

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None
_test_session: Session | None = None


class _TestSessionContext:
    """Prevents test session from being closed on context exit."""

    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, *args) -> bool:
        return False


def set_test_session(session: Session | None) -> None:
    """Set or clear the test session for TESTING mode."""
    global _test_session
    _test_session = session


def create_extensions(engine: Engine) -> None:
    with engine.connect() as conn:
        for extension in EXTENSIONS:
            conn.execute(
                text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"'))
            conn.commit()


def create_engine(url: URL, **kwargs) -> Engine:
    settings = get_settings()
    engine = _create_engine(
        url,
        future=True,
        pool_size=settings.POSTGRES_POOL_SIZE,
        max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        **kwargs,
    )
    create_extensions(engine)
    return engine


def get_engine() -> Engine:
    """
    Get or create the database engine.

    Engine is created lazily on first access, allowing workers to
    load credentials from Prefect Blocks at runtime.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = _create_engine(
            settings.SQLALCHEMY_DATABASE_URL,
            future=True,
            pool_size=settings.POSTGRES_POOL_SIZE,
            max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        )
        create_extensions(_engine)
    return _engine


def reset_engine() -> None:
    """
    Reset the database engine.

    Call this after credential rotation to force reconnection
    with new credentials on next database access.
    """
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def DatabaseSession() -> Session:
    """
    Get a new database session.

    In TESTING mode (TESTING=1 env var), returns the test session
    configured by fixtures with savepoint-based isolation.

    Returns:
        SQLAlchemy Session instance (or test session wrapper in TESTING mode)
    """
    if get_settings().TESTING:
        if _test_session is None:
            raise RuntimeError(
                "TESTING mode enabled but no test session configured. "
                "Ensure your test uses the 'session' fixture."
            )
        return _TestSessionContext(_test_session)

    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(get_engine(), expire_on_commit=True)
    return _SessionFactory()


def _create_tables():
    ORMBase.metadata.create_all(get_engine())


def _drop_tables():
    m = MetaData()
    m.reflect(get_engine(), schema='public')
    tables = [
        table for table in m.sorted_tables if table.name not in
        ['spatial_ref_sys']]
    m.drop_all(get_engine(), tables=tables)


def _check_tables_exist():
    """
    Check if tables exist in the database,
    assuming that if there are more than 5
    tables, the database is initialized.
    """
    m = MetaData()
    m.reflect(get_engine(), schema='public')
    tables = [table for table in m.sorted_tables]
    return len(tables) > 5


def pandas_read_sql(stmt: Select, session: Session):
    df = pd.read_sql_query(stmt, session.connection())
    return df
