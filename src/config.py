from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    # Set to empty string to run Redis-only (no Postgres persistence)
    database_url: str = "postgresql://leaderboard:leaderboard@localhost:5432/leaderboard"
    log_level: str = "INFO"
    api_version: str = "1.0.0"
    allowed_origins: str = "*"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
