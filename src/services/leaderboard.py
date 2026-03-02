"""Business logic for leaderboard operations.

This layer sits between the API routes and storage. It handles:
  - Formatting raw storage results into response-ready data
  - Neighbor computation (users above/below a given player)
  - Edge cases (user not found, rank boundaries)

It does NOT know about HTTP, FastAPI, or request/response objects.
"""
from __future__ import annotations

from typing import Optional

from src.config import settings
from src.models.schemas import (
    HealthData,
    LeaderboardEntry,
    NeighborSet,
    ScoreResult,
    TopLeaderboardData,
    UserContextData,
)
from src.storage.leaderboard_store import LeaderboardStore


class LeaderboardService:

    def __init__(self, store: LeaderboardStore) -> None:
        self._store = store

    async def submit_score(self, game_id: str, user_id: str, score: int) -> ScoreResult:
        """Submit a score and return the user's current rank."""
        rank = await self._store.add_score(game_id, user_id, score)
        return ScoreResult(user_id=user_id, game_id=game_id, score=score, rank=rank)

    async def get_top(self, game_id: str, limit: int) -> TopLeaderboardData:
        """Return the top `limit` players for a game."""
        results = await self._store.get_top(game_id, limit)
        total = await self._store.get_total_players(game_id)
        entries = [
            LeaderboardEntry(rank=idx + 1, user_id=uid, score=sc)
            for idx, (uid, sc) in enumerate(results)
        ]
        return TopLeaderboardData(game_id=game_id, entries=entries, total_players=total)

    async def get_user_context(
        self, game_id: str, user_id: str, neighbor_range: int
    ) -> Optional[UserContextData]:
        """Return a user's rank plus neighbors above and below.

        `neighbor_range` controls how many neighbors on each side (e.g. 2 = 2 above + 2 below).
        Returns None if the user is not on the leaderboard.
        """
        rank = await self._store.get_rank(game_id, user_id)
        if rank is None:
            return None

        score = await self._store.get_score(game_id, user_id)
        total = await self._store.get_total_players(game_id)

        # rank is 0-based from storage
        user_entry = LeaderboardEntry(rank=rank + 1, user_id=user_id, score=score)

        # Neighbors above: positions [rank - neighbor_range, rank - 1]
        above_start = max(0, rank - neighbor_range)
        above = []
        if above_start < rank:
            raw_above = await self._store.get_range(game_id, above_start, rank - 1)
            above = [
                LeaderboardEntry(rank=above_start + i + 1, user_id=uid, score=sc)
                for i, (uid, sc) in enumerate(raw_above)
            ]

        # Neighbors below: positions [rank + 1, rank + neighbor_range]
        below = []
        if rank + 1 < total:
            below_stop = min(total - 1, rank + neighbor_range)
            raw_below = await self._store.get_range(game_id, rank + 1, below_stop)
            below = [
                LeaderboardEntry(rank=rank + 1 + i + 1, user_id=uid, score=sc)
                for i, (uid, sc) in enumerate(raw_below)
            ]

        return UserContextData(
            game_id=game_id,
            user=user_entry,
            neighbors=NeighborSet(above=above, below=below),
            total_players=total,
        )

    async def health_check(self) -> HealthData:
        """Check storage health and return status."""
        storage_health = await self._store.health_check()
        all_healthy = all(storage_health.values())
        return HealthData(
            status="healthy" if all_healthy else "degraded",
            storage=str(storage_health),
            version=settings.api_version,
        )
