from sqlalchemy import URL, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from hermes.config import get_settings
from web.repositories.database import sessionmanager

settings = get_settings()


def create_test_async_engine(test_db_name: str = None):
    """Create async engine pointing to test database."""
    if test_db_name is None:
        test_db_name = f"{settings.POSTGRES_DB}_test"
    url = URL.create(
        drivername='postgresql+asyncpg',
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=test_db_name
    )
    return create_async_engine(url, echo=False)


async def create_test_async_connection(engine):
    """Create async connection with transaction for test isolation.

    Returns:
        tuple: (connection, transaction) for use in fixtures
    """
    conn = await engine.connect()
    trans = await conn.begin()
    await conn.begin_nested()
    return conn, trans


async def cleanup_test_async_connection(conn, trans):
    """Clean up async connection and rollback transaction."""
    await trans.rollback()
    await conn.close()


def create_test_async_session(connection):
    """Create async session bound to connection's transaction.

    Uses explicit savepoint restart pattern (via event listener on the
    underlying sync session) for consistency with sync test sessions.
    This ensures commits only affect the savepoint, not the outer transaction.

    Returns:
        tuple: (session, listener) - listener must be passed to cleanup
    """
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
    )

    def restart_savepoint(session_, transaction_):
        if transaction_.nested and not transaction_.parent.nested:
            session_.expire_all()
            session_.begin_nested()

    event.listen(session.sync_session,
                 "after_transaction_end", restart_savepoint)

    sessionmanager.set_test_session(session)
    return session, restart_savepoint


async def cleanup_test_async_session(session, listener=None):
    """Clean up async session.

    Args:
        session: The async session to clean up
        listener: Event listener to remove
    """
    if listener is not None:
        event.remove(session.sync_session, "after_transaction_end", listener)
    sessionmanager.set_test_session(None)
    await session.close()
