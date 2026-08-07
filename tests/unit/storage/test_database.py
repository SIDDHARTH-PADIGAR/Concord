"""Tests for create_pool's startup retry behavior (fully mocked, no Docker needed)."""

from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from concord_core.config.settings import DatabaseSettings
from concord_core.storage.database import create_pool


def _settings() -> DatabaseSettings:
    return DatabaseSettings(_env_file=None, user="concord", password="secret")


async def test_create_pool_retries_while_database_is_starting_up() -> None:
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_create_pool = AsyncMock(
        side_effect=[asyncpg.exceptions.CannotConnectNowError("starting up"), mock_pool]
    )
    with (
        patch("concord_core.storage.database.asyncpg.create_pool", new=mock_create_pool),
        patch("concord_core.storage.database.asyncio.sleep", new=AsyncMock()),
    ):
        pool = await create_pool(_settings())
    assert pool is mock_pool


async def test_create_pool_raises_after_max_attempts() -> None:
    mock_create_pool = AsyncMock(
        side_effect=asyncpg.exceptions.CannotConnectNowError("starting up")
    )
    with (
        patch("concord_core.storage.database.asyncpg.create_pool", new=mock_create_pool),
        patch("concord_core.storage.database.asyncio.sleep", new=AsyncMock()),
        pytest.raises(asyncpg.exceptions.CannotConnectNowError),
    ):
        await create_pool(_settings())
