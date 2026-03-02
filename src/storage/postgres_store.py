"""PostgreSQL leaderboard storage — the durable source of truth.

Uses asyncpg for async database access. Stores all scores in a single
`scores` table with a unique constraint on (user_id, game_id).

Schema:
    CREATE TABLE scores (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(128) NOT NULL,
        game_id VARCHAR(64) NOT NULL,
        score INTEGER NOT NULL CHECK (score >= 0),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, game_id)
    );
    CREATE INDEX idx_scores_game_score ON scores(game_id, score DESC);

Ranking uses a window function: COUNT(*) of players with a higher score + 1.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import asyncpg

from src.storage.interface import LeaderboardStorage

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


class PostgresStore(LeaderboardStorage):

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self) -> None:
        """Create the connection pool and ensure the schema exists."""
        self._pool = await asyncpg.create_pool(self._database_url, min_size=2, max_size=10)
        async with self._pool.acquire() as conn:
            await conn.execute(INIT_SQL)

    async def add_score(self, game_id: str, user_id: str, score: int) -> int:
        async with self._pool.acquire() as conn:
            # Upsert: insert or update only if new score is higher (best-score semantics)
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
            # Calculate rank: count of players with higher score + 1
            rank = await conn.fetchval(
                """
                SELECT COUNT(*) + 1 FROM scores
                WHERE game_id = $1 AND score > (
                    SELECT score FROM scores WHERE game_id = $1 AND user_id = $2
                )
                """,
                game_id,
                user_id,
            )
            return rank

    async def get_top(self, game_id: str, limit: int) -> List[Tuple[str, int]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, score FROM scores
                WHERE game_id = $1
                ORDER BY score DESC, user_id ASC
                LIMIT $2
                """,
                game_id,
                limit,
            )
            return [(row["user_id"], row["score"]) for row in rows]

    async def get_rank(self, game_id: str, user_id: str) -> Optional[int]:
        async with self._pool.acquire() as conn:
            user_score = await conn.fetchval(
                "SELECT score FROM scores WHERE game_id = $1 AND user_id = $2",
                game_id,
                user_id,
            )
            if user_score is None:
                return None
            # 0-based rank
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM scores WHERE game_id = $1 AND score > $2",
                game_id,
                user_score,
            )
            return count

    async def get_score(self, game_id: str, user_id: str) -> Optional[int]:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT score FROM scores WHERE game_id = $1 AND user_id = $2",
                game_id,
                user_id,
            )

    async def get_range(self, game_id: str, start: int, stop: int) -> List[Tuple[str, int]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, score FROM scores
                WHERE game_id = $1
                ORDER BY score DESC, user_id ASC
                LIMIT $2 OFFSET $3
                """,
                game_id,
                stop - start + 1,
                start,
            )
            return [(row["user_id"], row["score"]) for row in rows]

    async def get_total_players(self, game_id: str) -> int:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM scores WHERE game_id = $1", game_id
            )

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

    @property
    def backend_name(self) -> str:
        return "postgres"
