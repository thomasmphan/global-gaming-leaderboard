"""Redis leaderboard storage using Sorted Sets.

Redis sorted sets are the industry standard for real-time leaderboards:
  - ZADD with GT flag: O(log N), only updates if new score is greater
  - ZREVRANGE: O(log N + K), retrieves top K in descending order
  - ZREVRANK: O(log N), gets a user's rank instantly
  - ZCARD: O(1), total player count

Key pattern: "leaderboard:{game_id}" — one sorted set per game.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import redis.asyncio as aioredis


class RedisStore:

    def __init__(self, redis_url: str) -> None:
        self._redis: aioredis.Redis = aioredis.from_url(
            redis_url, decode_responses=True
        )

    def _key(self, game_id: str) -> str:
        return f"leaderboard:{game_id}"

    async def add_score(self, game_id: str, user_id: str, score: int) -> int:
        key = self._key(game_id)
        # GT flag: only update if new score > existing score (best-score semantics)
        await self._redis.zadd(key, {user_id: score}, gt=True)
        # ZREVRANK returns 0-based rank in descending order
        rank = await self._redis.zrevrank(key, user_id)
        return rank + 1  # 1-based

    async def get_top(self, game_id: str, limit: int) -> List[Tuple[str, int]]:
        key = self._key(game_id)
        # Returns list of (member, score) tuples in descending order
        results = await self._redis.zrevrange(key, 0, limit - 1, withscores=True)
        return [(user_id, int(score)) for user_id, score in results]

    async def get_rank(self, game_id: str, user_id: str) -> Optional[int]:
        key = self._key(game_id)
        rank = await self._redis.zrevrank(key, user_id)
        return rank  # None if user not found, 0-based if found

    async def get_score(self, game_id: str, user_id: str) -> Optional[int]:
        key = self._key(game_id)
        score = await self._redis.zscore(key, user_id)
        return int(score) if score is not None else None

    async def get_range(self, game_id: str, start: int, stop: int) -> List[Tuple[str, int]]:
        key = self._key(game_id)
        results = await self._redis.zrevrange(key, start, stop, withscores=True)
        return [(user_id, int(score)) for user_id, score in results]

    async def get_total_players(self, game_id: str) -> int:
        key = self._key(game_id)
        return await self._redis.zcard(key)

    async def health_check(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()
