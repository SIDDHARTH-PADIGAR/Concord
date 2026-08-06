"""Environment-driven configuration for infrastructure Concord services connect to.

Each settings class reads from environment variables (or a local .env
file) under its own prefix, so Redis and database config can never be
confused with each other at the env-var level.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONCORD_REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class DatabaseSettings(BaseSettings):
    """user/password have no defaults: a missing credential must fail loudly, not guess."""

    model_config = SettingsConfigDict(env_prefix="CONCORD_DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str
    password: str
    name: str = "concord"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
