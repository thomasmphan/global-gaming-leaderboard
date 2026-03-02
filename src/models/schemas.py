from __future__ import annotations

import re
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")

# --- Validation constants ---
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_SCORE = 1_000_000_000


# --- Request models ---


class ScoreSubmission(BaseModel):
    """Request body for submitting a score. Validates format and range constraints."""

    user_id: str = Field(..., min_length=1, max_length=128, description="Unique player identifier")
    game_id: str = Field(..., min_length=1, max_length=64, description="Game identifier")
    score: int = Field(..., ge=0, le=MAX_SCORE, description="Player score (non-negative)")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError("user_id must be alphanumeric with hyphens and underscores only")
        return v

    @field_validator("game_id")
    @classmethod
    def validate_game_id(cls, v: str) -> str:
        if not ID_PATTERN.match(v):
            raise ValueError("game_id must be alphanumeric with hyphens and underscores only")
        return v


# --- Response models ---
# All API responses use the ApiResponse envelope: {success, data, error}


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    score: int


class ScoreResult(BaseModel):
    user_id: str
    game_id: str
    score: int
    rank: int


class TopLeaderboardData(BaseModel):
    game_id: str
    entries: List[LeaderboardEntry]
    total_players: int


class NeighborSet(BaseModel):
    above: List[LeaderboardEntry]
    below: List[LeaderboardEntry]


class UserContextData(BaseModel):
    game_id: str
    user: LeaderboardEntry
    neighbors: NeighborSet
    total_players: int


class GameSummary(BaseModel):
    game_id: str
    total_players: int


class GameListData(BaseModel):
    games: List[GameSummary]
    total_games: int


class HealthData(BaseModel):
    status: str


class ReadyData(BaseModel):
    status: str
    storage: dict
    version: str


# --- Convenience constructors for consistent response format ---


def success_response(data) -> dict:
    return {"success": True, "data": data, "error": None}


def error_response(code: str, message: str) -> dict:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}
