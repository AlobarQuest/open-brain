# open-brain Operational Runbook

**Production URL:** https://open-brain.devonwatkins.com  
**GHCR image:** `ghcr.io/alobarquest/open-brain`  
**Coolify app UUID:** `e0000okgowcgkw0wosgo8kg8`  
**Coolify API base:** `http://coolify-1.devonwatkins.com/api/v1`

---

## 1. Local Development

### First-time setup

Copy and populate the env file:

```bash
cp .env.example .env
```

Required values to fill in `.env`:

```
POSTGRES_PASSWORD=changeme          # any local password
OPENROUTER_API_KEY=sk-or-v1-...    # your OpenRouter key
MCP_ACCESS_KEY=<64 lowercase hex chars>  # generate with: openssl rand -hex 32
```

Generate a valid `MCP_ACCESS_KEY`:

```bash
openssl rand -hex 32
```

### Start the stack

The local override file maps ports and sets `APP_ENV=development`. Always use both compose files together:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

| Service      | Container port | Host port |
|--------------|---------------|-----------|
| API          | 80            | 8002      |
| Postgres     | 5432          | 5434      |

The API is available at `http://localhost:8002` once the container passes its health check (`/api/health`). The database must be healthy before the API starts — this is enforced by `depends_on: condition: service_healthy`.

### Stop / clean up

```bash
# Stop containers, keep volumes
docker compose -f docker-compose.yml -f docker-compose.local.yml down

# Stop and remove the postgres volume (full reset)
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v
```

### Rebuild after dependency changes

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

---

## 2. Running Tests

Tests require Docker to be running — they use `testcontainers` to spin up a real Postgres instance.

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
```

### Run the full suite

```bash
MCP_ACCESS_KEY=$(openssl rand -hex 32) OPENROUTER_API_KEY=sk-test-dummy pytest -x -v
```

The CI pipeline uses a hardcoded dummy `MCP_ACCESS_KEY` (`aaaa...` × 64) and a dummy `OPENROUTER_API_KEY`. For local runs, any valid 64-char hex value works for `MCP_ACCESS_KEY`.

### Run a specific test file

```bash
MCP_ACCESS_KEY=$(openssl rand -hex 32) OPENROUTER_API_KEY=sk-test-dummy pytest tests/test_health.py -v
```

---

## 3. CI/CD Pipeline

Triggered on every push to `main`. The pipeline has two jobs that run sequentially.

### Job 1: test

1. Checks out the repo and sets up Python 3.12.
2. Installs `requirements-dev.txt`.
3. Validates both compose files with `docker compose config --quiet`.
4. Runs `pytest -x -v` with dummy credentials.

If tests fail, the build-and-push job does not run.

### Job 2: build-and-push (requires test to pass)

1. Logs in to GHCR with `GITHUB_TOKEN`.
2. Builds the Docker image using BuildKit with GHA layer caching.
3. Pushes two tags:
   - `ghcr.io/alobarquest/open-brain:latest`
   - `ghcr.io/alobarquest/open-brain:<git-sha>` (full 40-char SHA)
4. Triggers Coolify redeploy via webhook:
   ```
   GET ${COOLIFY_WEBHOOK_URL}?uuid=${COOLIFY_APP_UUID}&force=false
   Authorization: Bearer ${COOLIFY_API_TOKEN}
   ```
5. Polls `https://open-brain.devonwatkins.com/api/health` every 15 seconds for up to 5 attempts (after an initial 30-second wait). Exits non-zero if health check never passes.

### Required GitHub secrets

| Secret                  | Purpose                              |
|-------------------------|--------------------------------------|
| `COOLIFY_WEBHOOK_URL`   | Coolify deploy webhook endpoint      |
| `COOLIFY_APP_UUID`      | `e0000okgowcgkw0wosgo8kg8`           |
| `COOLIFY_API_TOKEN`     | Coolify API bearer token             |

---

## 4. Database Operations

### Connect to the local dev database

```bash
psql -h localhost -p 5434 -U openbrain -d openbrain
```

### Connect to the production database (via VPS)

The production Postgres container is managed by Coolify and not directly port-exposed. Use `docker exec` through the VPS:

```bash
ssh root@178.156.247.239 \
  "docker exec -it \$(docker ps --filter name=openbrain-db --format '{{.Names}}' | head -1) \
  psql -U openbrain -d openbrain"
```

### Run migrations manually (local)

Migrations run automatically on container start via `scripts/start.sh`. To run them manually against the local stack:

```bash
DATABASE_URL=postgresql+asyncpg://openbrain:changeme@localhost:5434/openbrain \
  alembic upgrade head
```

### Run migrations manually (production — emergency only)

```bash
ssh root@178.156.247.239 \
  "docker exec \$(docker ps --filter name=open-brain-api --format '{{.Names}}' | head -1) \
  sh -c 'alembic upgrade head'"
```

### Check migration status

```bash
# Local
DATABASE_URL=postgresql+asyncpg://openbrain:changeme@localhost:5434/openbrain \
  alembic current

# Show full history with applied status
DATABASE_URL=postgresql+asyncpg://openbrain:changeme@localhost:5434/openbrain \
  alembic history --verbose
```

### Create a new migration

```bash
DATABASE_URL=postgresql+asyncpg://openbrain:changeme@localhost:5434/openbrain \
  alembic revision --autogenerate -m "describe_the_change"
```

Review the generated file in `alembic/versions/` before committing — autogenerate is not always correct, especially for pgvector types.

---

## 5. Deployment

### How Coolify deploys this app

open-brain uses the **dockercompose build pack** (Flavor C equivalent). Coolify pulls `ghcr.io/alobarquest/open-brain:latest`, runs `docker compose up -d` with the production `docker-compose.yml`, and routes traffic through the `coolify` external Docker network via Traefik.

The `coolify` network is declared as external in `docker-compose.yml` — this is required for Traefik routing. The local override (`docker-compose.local.yml`) overrides this to `external: false` so it works without Coolify present.

On container start, `scripts/start.sh` runs `alembic upgrade head` before launching uvicorn. Migrations always run before the app accepts traffic.

### Trigger a manual redeploy via Coolify API

```bash
curl -f -X GET \
  "http://coolify-1.devonwatkins.com/api/v1/deploy?uuid=e0000okgowcgkw0wosgo8kg8&force=false" \
  -H "Authorization: Bearer <COOLIFY_API_TOKEN>"
```

Use `force=true` to force a rebuild even if nothing changed.

### Force-pull latest image and redeploy

```bash
curl -f -X GET \
  "http://coolify-1.devonwatkins.com/api/v1/deploy?uuid=e0000okgowcgkw0wosgo8kg8&force=true" \
  -H "Authorization: Bearer <COOLIFY_API_TOKEN>"
```

---

## 6. Rollback

Every push to `main` produces a SHA-tagged image in GHCR alongside `:latest`. This makes rollback straightforward.

### Step 1: Identify the SHA to roll back to

Check recent GHCR tags or the GitHub Actions run history to find the SHA of the last known-good build. The tag format is the full 40-character git SHA.

### Step 2: Option A — git revert and push (preferred)

This keeps the deployment history clean and re-runs CI validation:

```bash
git revert <bad-commit-sha>
git push origin main
```

CI will test, build a new image, and deploy. If the revert itself is safe this is the lowest-risk path.

### Step 3: Option B — direct image pin via Coolify (faster, skips CI)

If you need to roll back immediately without waiting for CI, update the image tag in Coolify to point at the previous SHA:

1. In the Coolify UI, find the open-brain application.
2. Update the image tag from `latest` to `ghcr.io/alobarquest/open-brain:<previous-sha>`.
3. Trigger a redeploy.

Or via API — update the application config, then redeploy:

```bash
# Redeploy with force to pick up the tag change
curl -f -X GET \
  "http://coolify-1.devonwatkins.com/api/v1/deploy?uuid=e0000okgowcgkw0wosgo8kg8&force=true" \
  -H "Authorization: Bearer <COOLIFY_API_TOKEN>"
```

After rolling back, follow up with a proper fix on `main` to restore forward progress.

---

## 7. Troubleshooting

### Health check returning 503

The `/api/health` endpoint returns 503 with `{"status": "degraded", "db": "error"}` when the API cannot reach Postgres.

**Check:**
- Is the `openbrain-db` container running and healthy?
  ```bash
  ssh root@178.156.247.239 "docker ps --filter name=openbrain"
  ```
- Check container logs for connection errors:
  ```bash
  ssh root@178.156.247.239 "docker logs \$(docker ps --filter name=open-brain-api --format '{{.Names}}' | head -1) --tail 50"
  ```
- Verify `POSTGRES_PASSWORD` env var matches what the DB was initialized with. If the volume was created with a different password, the only fix is to delete the volume and redeploy fresh.

### Health check returning 401 or unreachable

The `/api/health` path is explicitly excluded from auth middleware — it does not require `x-brain-key`. If health checks are returning 401, the middleware path matching may have regressed. Check `src/main.py`.

If the endpoint is unreachable entirely, verify Traefik routing and that the `coolify` external network is attached to the `api` service.

### Migration failures on startup

Migrations run before uvicorn starts. If they fail, the container will exit immediately.

**Check container logs:**
```bash
ssh root@178.156.247.239 "docker logs \$(docker ps -a --filter name=open-brain-api --format '{{.Names}}' | head -1) --tail 100"
```

Common causes:
- Database not yet healthy when migration runs (dependency ordering issue — should not happen with `depends_on: condition: service_healthy`).
- A migration file has a syntax error or references a column that doesn't exist.
- Conflicting migration heads (if two branches each added migrations). Resolve with `alembic merge heads`.

### Auth errors (401) on MCP endpoints

All routes except `/api/health` require authentication.

**Header-based auth:**
```bash
curl -H "x-brain-key: <MCP_ACCESS_KEY>" https://open-brain.devonwatkins.com/mcp
```

**Query param auth:**
```bash
curl "https://open-brain.devonwatkins.com/mcp?key=<MCP_ACCESS_KEY>"
```

`MCP_ACCESS_KEY` must be exactly 64 lowercase hex characters. The validator in `src/config.py` will reject the app at startup if the key is malformed — check Coolify env vars if the container crashes immediately on deploy.

**Verify the key format:**
```bash
echo -n "$MCP_ACCESS_KEY" | wc -c    # must be 64
echo "$MCP_ACCESS_KEY" | grep -E '^[0-9a-f]{64}$'  # must match
```

### Container not starting

1. Check Coolify deployment logs in the UI or via API.
2. Check Docker logs on the VPS:
   ```bash
   ssh root@178.156.247.239 "docker logs \$(docker ps -a --filter name=open-brain-api --format '{{.Names}}' | head -1) --tail 200"
   ```
3. Common causes:
   - Missing required env var (`DATABASE_URL` or `POSTGRES_PASSWORD`, `MCP_ACCESS_KEY`, `OPENROUTER_API_KEY`).
   - `MCP_ACCESS_KEY` fails the 64-char hex validation in `src/config.py` — app raises `ValidationError` and exits.
   - Image failed to pull from GHCR (check GHCR credentials or network connectivity from VPS).

### Coolify build failures

open-brain uses a pre-built GHCR image, not a source build in Coolify. Coolify does not build the image — GitHub Actions builds and pushes to GHCR, then Coolify pulls it.

If Coolify reports a build failure:
- Check that the image `ghcr.io/alobarquest/open-brain:latest` was successfully pushed (check GitHub Actions logs).
- Verify the VPS can reach `ghcr.io` (network/firewall issue).
- Check that Coolify has valid credentials for GHCR if the package visibility is private.

---

## 8. Backup and Restore

The production Postgres data lives in a Docker named volume managed by Coolify on the VPS (`178.156.247.239`).

### Backup — dump to a local file

```bash
# Find the container name
ssh root@178.156.247.239 "docker ps --filter name=openbrain-db --format '{{.Names}}'"

# Run pg_dump and stream to local file
ssh root@178.156.247.239 \
  "docker exec <openbrain-db-container-name> \
  pg_dump -U openbrain -d openbrain --no-password -F c" \
  > openbrain-backup-$(date +%Y%m%d-%H%M%S).dump
```

The `-F c` flag uses custom format (compressed, supports partial restore). Use `-F p` for plain SQL if you need a human-readable dump.

### Backup — plain SQL

```bash
ssh root@178.156.247.239 \
  "docker exec <openbrain-db-container-name> \
  pg_dump -U openbrain -d openbrain --no-password" \
  > openbrain-backup-$(date +%Y%m%d-%H%M%S).sql
```

### Restore from custom-format dump

```bash
# Copy dump to VPS
scp openbrain-backup-<timestamp>.dump root@178.156.247.239:/tmp/

# Restore (will error on conflicts if DB has existing data — drop/recreate first for full restore)
ssh root@178.156.247.239 \
  "docker exec -i <openbrain-db-container-name> \
  pg_restore -U openbrain -d openbrain --no-password -c /dev/stdin" \
  < openbrain-backup-<timestamp>.dump
```

For a clean restore (wipe and reload), stop the API first so there are no active connections:

```bash
# Stop the API container
ssh root@178.156.247.239 "docker stop <open-brain-api-container-name>"

# Drop and recreate the database
ssh root@178.156.247.239 \
  "docker exec <openbrain-db-container-name> \
  psql -U openbrain -c 'DROP DATABASE openbrain; CREATE DATABASE openbrain;'"

# Restore
ssh root@178.156.247.239 \
  "docker exec -i <openbrain-db-container-name> \
  pg_restore -U openbrain -d openbrain --no-password /dev/stdin" \
  < openbrain-backup-<timestamp>.dump

# Restart the API (migrations will re-run on start)
ssh root@178.156.247.239 "docker start <open-brain-api-container-name>"
```

---

## 9. Monitoring

### Health check endpoint

```
GET /api/health
```

No authentication required. Returns HTTP 200 on healthy, HTTP 503 when the database is unreachable.

**Response (healthy):**
```json
{"status": "ok", "app": "open-brain", "db": "connected"}
```

**Response (degraded):**
```json
{"status": "degraded", "app": "open-brain", "db": "error"}
```

The health check executes `SELECT 1` against the database on every request — it is a live connectivity check, not a cached status.

### Check health from outside

```bash
curl -sf https://open-brain.devonwatkins.com/api/health | python3 -m json.tool
```

For a quick pass/fail:
```bash
curl -sf https://open-brain.devonwatkins.com/api/health > /dev/null && echo "OK" || echo "FAILED"
```

### Docker container health

The `api` service has a Docker-level health check that calls `http://127.0.0.1:80/api/health` every 30 seconds (timeout 10s, 3 retries, 40-second start period). Check it with:

```bash
ssh root@178.156.247.239 "docker inspect \$(docker ps --filter name=open-brain-api --format '{{.Names}}' | head -1) --format '{{.State.Health.Status}}'"
```

### View live application logs

```bash
ssh root@178.156.247.239 \
  "docker logs -f \$(docker ps --filter name=open-brain-api --format '{{.Names}}' | head -1)"
```

### View database logs

```bash
ssh root@178.156.247.239 \
  "docker logs -f \$(docker ps --filter name=openbrain-db --format '{{.Names}}' | head -1)"
```
