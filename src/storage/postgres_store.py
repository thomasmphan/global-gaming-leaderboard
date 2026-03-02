"""PostgreSQL persistence layer — the durable source of truth.

This is NOT a full LeaderboardStorage implementation. It only handles:
  1. Saving scores (upsert with best-score semantics)
  2. Loading all scores for a game (to rebuild Redis on startup/recovery)
  3. Health checks

All ranked reads (top-N, get rank, neighbors) go through Redis.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import asyncpg

INIT_SQL = """
CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    game_id VARCHAR(64) NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_scores_game_score ON scores(game_id, score DESC);
"""


class PostgresStore:

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Create the connection pool and ensure the schema exists."""
        self._pool = await asyncpg.create_pool(self._database_url, min_size=2, max_size=10)
        async with self._pool.acquire() as conn:
            await conn.execute(INIT_SQL)

    async def save_score(self, game_id: str, user_id: str, score: int) -> None:
        """Persist a score. Only updates if new score > existing (best-score semantics)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO scores (user_id, game_id, score)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, game_id) DO UPDATE
                SET score = GREATEST(scores.score, EXCLUDED.score),
                    updated_at = NOW()
                """,
                user_id,
                game_id,
                score,
            )

    async def get_all_scores(self, game_id: str) -> List[Tuple[str, int]]:
        """Load all scores for a game. Used to rebuild Redis after a restart."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, score FROM scores WHERE game_id = $1",
                game_id,
            )
            return [(row["user_id"], row["score"]) for row in rows]

    async def get_all_game_ids(self) -> List[str]:
        """Return all distinct game IDs. Used during Redis rebuild to know which games to load."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT DISTINCT game_id FROM scores")
            return [row["game_id"] for row in rows]

    async def health_check(self) -> bool:
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
