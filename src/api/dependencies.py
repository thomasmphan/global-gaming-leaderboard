"""FastAPI dependency injection — wires up storage and service singletons."""
from __future__ import annotations

from src.config import settings
from src.services.leaderboard import LeaderboardService
from src.storage.leaderboard_store import LeaderboardStore
from src.storage.postgres_store import PostgresStore
from src.storage.redis_store import RedisStore

_store: LeaderboardStore | None = None
_service: LeaderboardService | None = None


async def init_services() -> None:
    """Called once at app startup to build the object graph."""
    global _store, _service

    redis = RedisStore(settings.redis_url)

    postgres = None
    if settings.database_url:
        postgres = PostgresStore(settings.database_url)

    _store = LeaderboardStore(redis=redis, postgres=postgres)
    await _store.initialize()

    _service = LeaderboardService(_store)


async def shutdown_services() -> None:
    """Called once at app shutdown to clean up connections."""
    if _store:
        await _store.close()


def get_service() -> LeaderboardService:
    """FastAPI dependency — inject into route handlers."""
    return _service
