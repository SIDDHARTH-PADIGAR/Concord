"""asyncpg connection pool and migration runner for TimescaleDB."""

import asyncio
from pathlib import Path

import asyncpg

from concord_core.config.settings import DatabaseSettings

_MAX_CONNECT_ATTEMPTS = 10
_RETRY_DELAY_SECONDS = 1.0


async def create_pool(settings: DatabaseSettings) -> asyncpg.Pool:
    """Creates a connection pool, retrying while Postgres is still starting up.

    A fresh container goes through an internal restart (initdb ->
    temporary server -> final server) before it's ready for client
    connections, even after Docker reports the healthcheck passing.
    Retrying here means a client that starts slightly too early
    recovers on its own -- true for tests today, and just as true for
    any real service connecting to this database at startup.
    """
    last_error: Exception | None = None
    for attempt in range(1, _MAX_CONNECT_ATTEMPTS + 1):
        try:
            return await asyncpg.create_pool(dsn=settings.dsn)
        except (asyncpg.exceptions.CannotConnectNowError, ConnectionError, OSError) as exc:
            last_error = exc
            if attempt == _MAX_CONNECT_ATTEMPTS:
                break
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
    assert last_error is not None
    raise last_error


async def apply_migrations(pool: asyncpg.Pool, migrations_dir: Path) -> None:
    """Applies every .sql file in migrations_dir, in filename order.

    Every statement is written as idempotent (IF NOT EXISTS), so
    re-running this on every startup is safe -- no migration-tracking
    table needed yet.
    """
    sql_files = sorted(migrations_dir.glob("*.sql"))
    async with pool.acquire() as conn:
        for sql_file in sql_files:
            await conn.execute(sql_file.read_text())
