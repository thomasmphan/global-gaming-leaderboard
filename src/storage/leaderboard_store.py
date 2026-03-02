"""Leaderboard store — coordinates Redis (reads/ranking) and optional Postgres (persistence).

This is the only storage class the service layer interacts with.
- Reads try Redis first; on a miss, falls back to Postgres and populates Redis (cache-aside)
- Writes go to Postgres first (if available), then Redis
- If Postgres is not configured, operates in Redis-only mode
- Bulk rebuild available on-demand (not automatic at startup)
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from src.storage.redis_store import RedisStore
from src.storage.postgres_store import PostgresStore

logger = logging.getLogger(__name__)


class LeaderboardStore:

    def __init__(self, redis: RedisStore, postgres: Optional[PostgresStore] = None) -> None:
        self._redis = redis
        self._postgres = postgres

    async def initialize(self) -> None:
        """Initialize Postgres connection pool and schema (if configured)."""
        if self._postgres:
            await self._postgres.initialize()

    async def _backfill_game(self, game_id: str) -> None:
        """Load a single game's scores from Postgres into Redis (cache-aside).

        Called when a read misses in Redis and Postgres is available.
        """
        if not self._postgres:
            return
        scores = await self._postgres.get_all_scores(game_id)
        if not scores:
            return
        for user_id, score in scores:
            await self._redis.add_score(game_id, user_id, score)
        logger.info(f"Backfilled Redis for game '{game_id}' with {len(scores)} scores")

    async def rebuild_redis(self) -> dict:
        """Bulk-load all games from Postgres into Redis. Call on-demand (e.g. via admin endpoint).

        Returns a summary of what was rebuilt.
        """
        if not self._postgres:
            return {"error": "Postgres not configured"}
        game_ids = await self._postgres.get_all_game_ids()
        summary = {}
        for game_id in game_ids:
            scores = await self._postgres.get_all_scores(game_id)
            for user_id, score in scores:
                await self._redis.add_score(game_id, user_id, score)
            summary[game_id] = len(scores)
            logger.info(f"Rebuilt Redis for game '{game_id}' with {len(scores)} scores")
        return summary

    async def add_score(self, game_id: str, user_id: str, score: int) -> int:
        """Submit a score. Persists to Postgres (if available), then updates Redis.

        Returns the user's current rank (1-based).
        """
        if self._postgres:
            await self._postgres.save_score(game_id, user_id, score)
        return await self._redis.add_score(game_id, user_id, score)

    async def get_top(self, game_id: str, limit: int) -> List[Tuple[str, int]]:
        """Return the top `limit` users, descending by score.

        Falls back to Postgres on Redis miss.
        """
        results = await self._redis.get_top(game_id, limit)
        if not results and self._postgres:
            await self._backfill_game(game_id)
            results = await self._redis.get_top(game_id, limit)
        return results

    async def get_rank(self, game_id: str, user_id: str) -> Optional[int]:
        """Return the user's 0-based rank, or None if not found.

        Falls back to Postgres on Redis miss.
        """
        rank = await self._redis.get_rank(game_id, user_id)
        if rank is None and self._postgres:
            await self._backfill_game(game_id)
            rank = await self._redis.get_rank(game_id, user_id)
        return rank

    async def get_score(self, game_id: str, user_id: str) -> Optional[int]:
        """Return the user's score, or None if not found."""
        score = await self._redis.get_score(game_id, user_id)
        if score is None and self._postgres:
            await self._backfill_game(game_id)
            score = await self._redis.get_score(game_id, user_id)
        return score

    async def get_range(self, game_id: str, start: int, stop: int) -> List[Tuple[str, int]]:
        """Return users in rank positions [start, stop] (0-based, inclusive).

        Falls back to Postgres on Redis miss.
        """
        results = await self._redis.get_range(game_id, start, stop)
        if not results and self._postgres:
            await self._backfill_game(game_id)
            results = await self._redis.get_range(game_id, start, stop)
        return results

    async def get_total_players(self, game_id: str) -> int:
        """Return total number of players in a game's leaderboard.

        Falls back to Postgres on Redis miss.
        """
        total = await self._redis.get_total_players(game_id)
        if total == 0 and self._postgres:
            await self._backfill_game(game_id)
            total = await self._redis.get_total_players(game_id)
        return total

    async def health_check(self) -> dict:
        """Check health of all backends. Returns status dict."""
        redis_ok = await self._redis.health_check()
        result = {"redis": redis_ok}
        if self._postgres:
            result["postgres"] = await self._postgres.health_check()
        return result

    async def close(self) -> None:
        """Clean up all connections."""
        await self._redis.close()
        if self._postgres:
            await self._postgres.close()
