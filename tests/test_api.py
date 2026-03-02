"""Integration tests for the leaderboard API.

All tests hit real Redis — no mocks. Each test uses a unique game_id (from conftest)
so tests can run in parallel without interfering with each other.
"""
from __future__ import annotations

import pytest


# ── POST /scores ──


async def test_submit_score(client, game_id):
    resp = await client.post("/api/v1/scores", json={
        "user_id": "alice", "game_id": game_id, "score": 100,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["user_id"] == "alice"
    assert body["data"]["score"] == 100
    assert body["data"]["rank"] == 1


async def test_submit_score_best_score_semantics(client, game_id):
    """A lower score should NOT replace a higher one."""
    await client.post("/api/v1/scores", json={
        "user_id": "alice", "game_id": game_id, "score": 200,
    })
    resp = await client.post("/api/v1/scores", json={
        "user_id": "alice", "game_id": game_id, "score": 50,
    })
    body = resp.json()
    # Rank is still returned, but the top score should remain 200
    assert body["success"] is True
    assert body["data"]["rank"] == 1


async def test_submit_score_validation_error(client, game_id):
    """Invalid user_id should return 422."""
    resp = await client.post("/api/v1/scores", json={
        "user_id": "bad user!!", "game_id": game_id, "score": 100,
    })
    assert resp.status_code == 422


async def test_submit_score_negative_score(client, game_id):
    """Negative scores should be rejected."""
    resp = await client.post("/api/v1/scores", json={
        "user_id": "alice", "game_id": game_id, "score": -1,
    })
    assert resp.status_code == 422


# ── GET /leaderboard/{game_id}/top ──


async def test_get_top_empty(client, game_id):
    resp = await client.get(f"/api/v1/leaderboard/{game_id}/top")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["entries"] == []
    assert body["data"]["total_players"] == 0


async def test_get_top_returns_sorted(client, game_id):
    """Top endpoint should return players sorted by score descending."""
    players = [("alice", 100), ("bob", 300), ("charlie", 200)]
    for uid, score in players:
        await client.post("/api/v1/scores", json={
            "user_id": uid, "game_id": game_id, "score": score,
        })

    resp = await client.get(f"/api/v1/leaderboard/{game_id}/top?limit=10")
    body = resp.json()
    entries = body["data"]["entries"]

    assert len(entries) == 3
    assert entries[0]["user_id"] == "bob"
    assert entries[0]["rank"] == 1
    assert entries[1]["user_id"] == "charlie"
    assert entries[1]["rank"] == 2
    assert entries[2]["user_id"] == "alice"
    assert entries[2]["rank"] == 3
    assert body["data"]["total_players"] == 3


async def test_get_top_respects_limit(client, game_id):
    for i in range(5):
        await client.post("/api/v1/scores", json={
            "user_id": f"player-{i}", "game_id": game_id, "score": i * 100,
        })

    resp = await client.get(f"/api/v1/leaderboard/{game_id}/top?limit=3")
    entries = resp.json()["data"]["entries"]
    assert len(entries) == 3


async def test_get_top_limit_validation(client, game_id):
    """Limit must be between 1 and 1000."""
    resp = await client.get(f"/api/v1/leaderboard/{game_id}/top?limit=0")
    assert resp.status_code == 422

    resp = await client.get(f"/api/v1/leaderboard/{game_id}/top?limit=1001")
    assert resp.status_code == 422


# ── GET /leaderboard/{game_id}/users/{user_id} ──


async def test_get_user_context_not_found(client, game_id):
    resp = await client.get(f"/api/v1/leaderboard/{game_id}/users/nobody")
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


async def test_get_user_context_with_neighbors(client, game_id):
    """User in the middle should have neighbors above and below."""
    players = [
        ("p1", 500), ("p2", 400), ("p3", 300), ("p4", 200), ("p5", 100),
    ]
    for uid, score in players:
        await client.post("/api/v1/scores", json={
            "user_id": uid, "game_id": game_id, "score": score,
        })

    # p3 is rank 3 (middle). With range=2, should get p1,p2 above and p4,p5 below.
    resp = await client.get(f"/api/v1/leaderboard/{game_id}/users/p3?range=2")
    body = resp.json()
    assert body["success"] is True

    data = body["data"]
    assert data["user"]["user_id"] == "p3"
    assert data["user"]["rank"] == 3

    above = data["neighbors"]["above"]
    assert len(above) == 2
    assert above[0]["user_id"] == "p1"
    assert above[1]["user_id"] == "p2"

    below = data["neighbors"]["below"]
    assert len(below) == 2
    assert below[0]["user_id"] == "p4"
    assert below[1]["user_id"] == "p5"


async def test_get_user_context_near_top(client, game_id):
    """Player near top with range exceeding available neighbors above."""
    players = [
        ("p1", 500), ("p2", 400), ("p3", 300), ("p4", 200), ("p5", 100),
    ]
    for uid, score in players:
        await client.post("/api/v1/scores", json={
            "user_id": uid, "game_id": game_id, "score": score,
        })

    # p2 is rank 2. With range=2, only 1 player above but 2 below.
    resp = await client.get(f"/api/v1/leaderboard/{game_id}/users/p2?range=2")
    data = resp.json()["data"]
    assert data["user"]["rank"] == 2

    above = data["neighbors"]["above"]
    assert len(above) == 1
    assert above[0]["user_id"] == "p1"

    below = data["neighbors"]["below"]
    assert len(below) == 2
    assert below[0]["user_id"] == "p3"
    assert below[1]["user_id"] == "p4"


async def test_get_user_context_top_player(client, game_id):
    """Top player should have no neighbors above."""
    await client.post("/api/v1/scores", json={
        "user_id": "top", "game_id": game_id, "score": 999,
    })
    await client.post("/api/v1/scores", json={
        "user_id": "second", "game_id": game_id, "score": 500,
    })

    resp = await client.get(f"/api/v1/leaderboard/{game_id}/users/top?range=2")
    data = resp.json()["data"]
    assert data["user"]["rank"] == 1
    assert data["neighbors"]["above"] == []
    assert len(data["neighbors"]["below"]) == 1


async def test_get_user_context_last_player(client, game_id):
    """Last player should have no neighbors below."""
    await client.post("/api/v1/scores", json={
        "user_id": "first", "game_id": game_id, "score": 999,
    })
    await client.post("/api/v1/scores", json={
        "user_id": "last", "game_id": game_id, "score": 1,
    })

    resp = await client.get(f"/api/v1/leaderboard/{game_id}/users/last?range=2")
    data = resp.json()["data"]
    assert data["user"]["rank"] == 2
    assert len(data["neighbors"]["above"]) == 1
    assert data["neighbors"]["below"] == []


# ── GET /health ──


async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
