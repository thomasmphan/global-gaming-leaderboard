# Architecture

## System Overview

```
Client (curl / browser / game server)
       |  HTTP/JSON
       v
+--------------------+
|  FastAPI (ASGI)    |  CORS, error handlers, request validation
+--------------------+
       |
       v
+--------------------+
|  LeaderboardService|  Business logic (ranking, neighbors)
+--------------------+
       |
       v
+--------------------+
|  LeaderboardStore  |  Cache-aside coordinator
+--------------------+
       |
   +---+---+
   |       |
   v       v
+------+ +----------+
|Redis | |PostgreSQL |
|Sorted| |scores tbl |
|Sets  | |(source of |
|(fast | | truth)    |
|reads)| |           |
+------+ +----------+
```

## Data Flow

**Writes:** Client -> API -> Service -> LeaderboardStore -> Postgres (persist) -> Redis (update rank)

**Reads:** Client -> API -> Service -> LeaderboardStore -> Redis (fast lookup). On cache miss, backfill from Postgres into Redis, then retry.

## Why Redis Sorted Sets?

Redis sorted sets are the industry standard for real-time leaderboards. Each operation maps directly to a Redis command:

| Operation | Redis Command | Time Complexity |
|-----------|--------------|-----------------|
| Submit score (keep best) | `ZADD key GT score member` | O(log N) |
| Get top X players | `ZREVRANGE key 0 X withscores` | O(log N + X) |
| Get user rank | `ZREVRANK key member` | O(log N) |
| Get user score | `ZSCORE key member` | O(1) |
| Get total players | `ZCARD key` | O(1) |

One sorted set per game, key pattern: `leaderboard:{game_id}`.

## Why PostgreSQL?

Redis is fast but volatile — data lives in memory. PostgreSQL provides:

- **Durability** — scores survive Redis restarts or crashes
- **Source of truth** — if Redis and Postgres disagree, Postgres wins
- **Bulk recovery** — on-demand `rebuild_redis()` reloads all games from Postgres

The `scores` table uses an upsert with `GREATEST()` to maintain best-score semantics at the database level.

## Cache-Aside Pattern

Every read method in `LeaderboardStore` follows the same pattern:

1. Try Redis first (fast path)
2. If Redis returns empty/null and Postgres is available, backfill that game's scores from Postgres into Redis
3. Retry the Redis read

This means Redis is self-healing — after a restart, it repopulates lazily as games are accessed rather than loading everything at startup.

## Best-Score Semantics

Both storage layers enforce "keep the highest score":

- **Redis:** `ZADD key GT score member` — the `GT` flag only updates if the new score is greater
- **Postgres:** `ON CONFLICT DO UPDATE SET score = GREATEST(scores.score, EXCLUDED.score)`

## Layer Responsibilities

| Layer | File | Responsibility |
|-------|------|----------------|
| API | `routes.py` | HTTP handling, input validation, response formatting |
| Service | `leaderboard.py` | Business logic, neighbor computation, rank formatting |
| Store | `leaderboard_store.py` | Cache-aside coordination between Redis and Postgres |
| Redis | `redis_store.py` | Sorted set operations (all ranked reads) |
| Postgres | `postgres_store.py` | Persistence only (save, bulk load, health check) |
