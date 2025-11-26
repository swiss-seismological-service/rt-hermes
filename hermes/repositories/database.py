import pandas as pd
from sqlalchemy import Select
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import MetaData
from sqlalchemy.sql import text

from hermes.datamodel.base import ORMBase

EXTENSIONS = ['postgis', 'postgis_topology']

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def create_extensions(engine: Engine) -> None:
    with engine.connect() as conn:
        for extension in EXTENSIONS:
            conn.execute(
                text(f'CREATE EXTENSION IF NOT EXISTS "{extension}"'))
            conn.commit()


def create_engine(url: URL, **kwargs) -> Engine:
    from hermes.config import get_settings
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
        from hermes.config import get_settings
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

    Returns:
        SQLAlchemy Session instance
    """
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
