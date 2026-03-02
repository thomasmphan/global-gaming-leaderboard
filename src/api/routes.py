"""API routes — all under /api/v1."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_service
from src.models.schemas import (
    ApiResponse,
    HealthData,
    ReadyData,
    ScoreResult,
    ScoreSubmission,
    TopLeaderboardData,
    UserContextData,
    error_response,
    success_response,
)
from src.services.leaderboard import LeaderboardService

router = APIRouter(prefix="/api/v1")


@router.post("/scores", response_model=ApiResponse[ScoreResult])
async def submit_score(
    body: ScoreSubmission,
    service: LeaderboardService = Depends(get_service),
):
    """Submit a score. Only updates if new score > existing (best-score semantics)."""
    result = await service.submit_score(body.game_id, body.user_id, body.score)
    return success_response(result)


@router.get("/leaderboard/{game_id}/top", response_model=ApiResponse[TopLeaderboardData])
async def get_top(
    game_id: str,
    limit: int = Query(default=10, ge=1, le=1000, description="Number of top players"),
    service: LeaderboardService = Depends(get_service),
):
    """Return the top players for a game, sorted by score descending."""
    data = await service.get_top(game_id, limit)
    return success_response(data)


@router.get(
    "/leaderboard/{game_id}/users/{user_id}",
    response_model=ApiResponse[UserContextData],
)
async def get_user_context(
    game_id: str,
    user_id: str,
    range: int = Query(
        default=2, ge=0, le=10, alias="range", description="Neighbors above and below"
    ),
    service: LeaderboardService = Depends(get_service),
):
    """Return a user's rank with neighbors above and below."""
    data = await service.get_user_context(game_id, user_id, range)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=error_response("NOT_FOUND", f"User '{user_id}' not found in game '{game_id}'"),
        )
    return success_response(data)


@router.get("/healthz", response_model=ApiResponse[HealthData])
async def healthz(
    service: LeaderboardService = Depends(get_service),
):
    """Liveness probe — returns 200 if the application is running."""
    data = await service.healthz()
    return success_response(data)


@router.get("/readyz", response_model=ApiResponse[ReadyData])
async def readyz(
    service: LeaderboardService = Depends(get_service),
):
    """Readiness probe — pings Redis and Postgres to confirm connectivity."""
    data = await service.readyz()
    return success_response(data)
