#!/bin/bash
# Seed the leaderboard with sample games and scores.
# Usage: ./scripts/seed.sh [BASE_URL]

BASE="${1:-https://thomas-leadership-app-5ptvc.ondigitalocean.app}"
API="$BASE/api/v1"

echo "Seeding leaderboard at $API ..."
echo

submit() {
    local game="$1" user="$2" score="$3"
    curl -s -X POST "$API/scores" \
        -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$user\", \"game_id\": \"$game\", \"score\": $score}" \
        | python3 -m json.tool --compact
}

echo "=== space-invaders (10 players) ==="
submit space-invaders alice   9500
submit space-invaders bob     8200
submit space-invaders charlie 9900
submit space-invaders dave    7100
submit space-invaders eve     8800
submit space-invaders frank   6500
submit space-invaders grace   9200
submit space-invaders hank    7800
submit space-invaders ivy     8500
submit space-invaders jack    7400
echo

echo "=== tetris (8 players) ==="
submit tetris alice   145000
submit tetris bob     230000
submit tetris charlie 189000
submit tetris dave    310000
submit tetris eve     175000
submit tetris frank   265000
submit tetris grace   198000
submit tetris hank    220000
echo

echo "=== mario-kart (6 players) ==="
submit mario-kart alice   4200
submit mario-kart bob     3800
submit mario-kart charlie 4500
submit mario-kart dave    3100
submit mario-kart eve     4800
submit mario-kart frank   3500
echo

echo
echo "Done! Seeded 3 games with 24 total scores."
