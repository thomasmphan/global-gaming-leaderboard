#!/bin/bash
# Demo all API endpoints against a live deployment.
# Usage: ./scripts/demo.sh [BASE_URL]

BASE="${1:-https://thomas-leadership-app-5ptvc.ondigitalocean.app}"
API="$BASE/api/v1"

pretty() {
    python3 -m json.tool
}

pause() {
    echo
    echo "--- Press Enter to continue ---"
    read -r
}

echo "========================================"
echo "  Global Gaming Leaderboard — API Demo"
echo "  $BASE"
echo "========================================"
echo

# 1. Health checks
echo "[1] Liveness probe (healthz)"
curl -s "$API/healthz" | pretty
pause

echo "[2] Readiness probe (readyz)"
curl -s "$API/readyz" | pretty
pause

# 2. Submit scores (Un-comment to test scores submission)
# echo "[3] Submit a score (alice, space-invaders, 9500)"
# curl -s -X POST "$API/scores" \
#     -H "Content-Type: application/json" \
#     -d '{"user_id": "alice", "game_id": "space-invaders", "score": 9500}' | pretty
# pause

# echo "[4] Submit a higher score (alice, space-invaders, 9800)"
# curl -s -X POST "$API/scores" \
#     -H "Content-Type: application/json" \
#     -d '{"user_id": "alice", "game_id": "space-invaders", "score": 9800}' | pretty
# pause

# echo "[5] Submit a LOWER score (alice, space-invaders, 5000) — should NOT replace"
# curl -s -X POST "$API/scores" \
#     -H "Content-Type: application/json" \
#     -d '{"user_id": "alice", "game_id": "space-invaders", "score": 5000}' | pretty
# pause

# 3. Leaderboard
echo "[6] Top 5 players for space-invaders"
curl -s "$API/leaderboard/space-invaders/top?limit=5" | pretty
pause

echo "[7] Top 3 players for tetris"
curl -s "$API/leaderboard/tetris/top?limit=3" | pretty
pause

# 4. User context
echo "[8] User context: alice in space-invaders (rank + 2 neighbors)"
curl -s "$API/leaderboard/space-invaders/users/alice?range=2" | pretty
pause

echo "[9] User context: dave in tetris (rank + 2 neighbors)"
curl -s "$API/leaderboard/tetris/users/dave?range=2" | pretty
pause

# 5. Edge cases
echo "[10] User not found (returns 404)"
curl -s -w "\nHTTP status: %{http_code}\n" "$API/leaderboard/space-invaders/users/nobody"
pause

echo "[11] Validation error — negative score (returns 422)"
curl -s -w "\nHTTP status: %{http_code}\n" -X POST "$API/scores" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "alice", "game_id": "space-invaders", "score": -1}'
pause

echo "[12] Validation error — invalid user_id (returns 422)"
curl -s -w "\nHTTP status: %{http_code}\n" -X POST "$API/scores" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "bad user!!", "game_id": "space-invaders", "score": 100}'
pause

# 6. Metrics
echo "[13] Prometheus metrics (first 20 lines)"
curl -s "$BASE/metrics" | head -20
echo "..."
echo

echo "========================================"
echo "  Demo complete!"
echo "========================================"
