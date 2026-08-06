"""Tests for environment-driven settings.

_env_file=None disables loading a local .env file -- without it, a
real .env on a developer's machine would leak into test results.
"""

import pytest
from pydantic import ValidationError

from concord_core.config.settings import DatabaseSettings, RedisSettings


class TestRedisSettings:
    def test_defaults(self) -> None:
        settings = RedisSettings(_env_file=None)
        assert settings.url == "redis://localhost:6379/0"

    def test_reads_from_env_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONCORD_REDIS_HOST", "redis.internal")
        monkeypatch.setenv("CONCORD_REDIS_PORT", "6380")
        settings = RedisSettings(_env_file=None)
        assert settings.url == "redis://redis.internal:6380/0"


class TestDatabaseSettings:
    def test_missing_credentials_raise(self) -> None:
        with pytest.raises(ValidationError):
            DatabaseSettings(_env_file=None)

    def test_dsn_built_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONCORD_DB_USER", "concord")
        monkeypatch.setenv("CONCORD_DB_PASSWORD", "secret")
        settings = DatabaseSettings(_env_file=None)
        assert settings.dsn == "postgresql://concord:secret@localhost:5432/concord"
