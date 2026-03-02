# Global Gaming Leaderboard

A production-ready REST API for managing real-time gaming leaderboards across multiple games. Built with FastAPI, Redis Sorted Sets, and PostgreSQL.

## Features

- **Submit scores** with best-score semantics (only keeps the highest)
- **Top X leaderboard** per game (configurable limit up to 1000)
- **User context** — a player's rank with configurable neighbors above and below
- **Multi-game support** — separate leaderboard per game via `game_id`
- **Cache-aside pattern** — Redis for fast reads, Postgres for durability, automatic backfill on cache miss

## Quick Start

### With Docker (recommended)

```bash
docker compose up
```

This starts the API on `http://localhost:8000` with Redis and Postgres.

### Without Docker

Prerequisites: Python 3.9+, Redis running on localhost:6379, PostgreSQL running on localhost:5432

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your connection details
uvicorn src.main:app --reload
```

## API Endpoints

All endpoints are under `/api/v1`. Interactive docs available at `http://localhost:8000/docs`.

### Submit Score

```bash
curl -X POST http://localhost:8000/api/v1/scores \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "game_id": "space-invaders", "score": 9500}'
```

```json
{
  "success": true,
  "data": {
    "user_id": "alice",
    "game_id": "space-invaders",
    "score": 9500,
    "rank": 1
  }
}
```

### Get Top Players

```bash
curl http://localhost:8000/api/v1/leaderboard/space-invaders/top?limit=10
```

```json
{
  "success": true,
  "data": {
    "game_id": "space-invaders",
    "entries": [
      {"rank": 1, "user_id": "alice", "score": 9500},
      {"rank": 2, "user_id": "bob", "score": 8200}
    ],
    "total_players": 2
  }
}
```

### Get User Context (rank + neighbors)

```bash
curl http://localhost:8000/api/v1/leaderboard/space-invaders/users/alice?range=2
```

```json
{
  "success": true,
  "data": {
    "game_id": "space-invaders",
    "user": {"rank": 3, "user_id": "alice", "score": 9500},
    "neighbors": {
      "above": [
        {"rank": 1, "user_id": "charlie", "score": 9900},
        {"rank": 2, "user_id": "bob", "score": 9700}
      ],
      "below": [
        {"rank": 4, "user_id": "dave", "score": 9200},
        {"rank": 5, "user_id": "eve", "score": 8800}
      ]
    },
    "total_players": 50
  }
}
```

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Testing

Tests run against a real Redis instance (no mocks). Postgres is not required for tests.

```bash
pip install -r requirements-dev.txt

# Start Redis if not already running
docker run -d --name test-redis -p 6379:6379 redis:7-alpine

# Run tests
DATABASE_URL="" pytest -v
```

## Project Structure

```
src/
  main.py              — FastAPI app factory, CORS, lifespan
  config.py            — Settings via pydantic-settings (.env support)
  api/
    routes.py          — REST endpoints
    dependencies.py    — Dependency injection (store + service wiring)
  models/
    schemas.py         — Pydantic request/response models
  services/
    leaderboard.py     — Business logic (ranking, neighbors)
  storage/
    redis_store.py     — Redis sorted set operations
    postgres_store.py  — PostgreSQL persistence (upsert, bulk load)
    leaderboard_store.py — Coordinates Redis + Postgres (cache-aside)
tests/
  conftest.py          — Fixtures (test client, Redis cleanup)
  test_api.py          — 14 integration tests against real Redis
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection URL |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins (comma-separated). Set to your domain(s) in production |
