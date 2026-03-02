"""Shared fixtures for integration tests.

Tests run in Redis-only mode (no Postgres). Requires a real Redis at localhost:6379.
Each test gets a unique game_id prefix to avoid collisions, and keys are cleaned up after.
"""
from __future__ import annotations

import uuid

import pytest
import redis.asyncio as aioredis
from httpx import ASGITransport, AsyncClient

from src.config import settings

# Force Redis-only mode for tests
settings.database_url = ""

from src.main import app  # noqa: E402 — must import after patching settings


@pytest.fixture
def game_id():
    """Generate a unique game ID per test to avoid key collisions."""
    return f"test-game-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def client():
    """Async HTTP client wired to the FastAPI app (no real server needed)."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture(autouse=True)
async def cleanup_redis(game_id):
    """Clean up Redis keys created during the test."""
    yield
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    await r.delete(f"leaderboard:{game_id}")
    await r.aclose()
