import contextlib
from typing import Annotated, Any, AsyncIterator

import pandas as pd
from fastapi import Depends
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import (AsyncConnection, AsyncSession,
                                    async_sessionmaker, create_async_engine)

from hermes.config import get_settings


class DatabaseSessionManager:
    def __init__(self, host: str | None = None, engine_kwargs: dict[str, Any] = {}):
        self._engine = None
        self._sessionmaker = None

        if host is not None:
            settings = get_settings()
            self._engine = create_async_engine(
                host,
                pool_size=settings.POSTGRES_POOL_SIZE,
                max_overflow=settings.POSTGRES_MAX_OVERFLOW,
                **engine_kwargs)
            self._sessionmaker = async_sessionmaker(
                autocommit=False, autoflush=False, bind=self._engine)

    def configure_for_testing(self, engine, sessionmaker):
        """Configure sessionmanager with test database connection."""
        self._engine = engine
        self._sessionmaker = sessionmaker

    async def close(self):
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")
        await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise Exception("DatabaseSessionManager is not initialized")

        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise Exception("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


_settings = get_settings()
sessionmanager = DatabaseSessionManager(
    None if _settings.TESTING else _settings.ASYNC_SQLALCHEMY_DATABASE_URL,
    {"echo": False}
)


async def get_db():
    async with sessionmanager.session() as session:
        yield session

DBSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def pandas_read_sql_async(stmt: Select, session: AsyncSession):
    """
    Get a pandas dataframe from a SQL statement.
    """
    result = await session.execute(stmt)
    rows = result.fetchall()
    columns = result.keys()
    return pd.DataFrame(rows, columns=columns)
