# PhotoSorter Deployment Commands

## Server Connection Details

| Field | Value |
|-------|-------|
| Host | `sz-verwaltung.ddns.net` |
| User | `aisdata` |
| Project Path | `~/PhotoSorter` |

---

## Redeploy Options

### Option 1: Direct File Copy (Recommended)

Best for quick updates - works around Docker BuildKit caching issues.

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && \
  git pull && \
  docker compose stop celery celery-beat && \
  docker cp backend/apps/uploads/tasks.py photosorter-celery-1:/app/backend/apps/uploads/tasks.py && \
  docker cp backend/apps/uploads/tasks.py photosorter-celery-beat-1:/app/backend/apps/uploads/tasks.py && \
  docker compose start celery celery-beat"
```

### Option 2: Full Rebuild with Legacy Builder

Use when you need to rebuild images but BuildKit caching causes issues.

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && \
  git pull && \
  docker compose down && \
  DOCKER_BUILDKIT=0 docker compose build --no-cache && \
  docker compose up -d"
```

### Option 3: Nuclear Option (Complete Clean Rebuild)

Use when everything else fails - removes all Docker cache and rebuilds from scratch.

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && \
  git pull && \
  docker compose down && \
  docker system prune -af && \
  docker builder prune -af && \
  DOCKER_BUILDKIT=0 docker compose build --no-cache && \
  docker compose up -d"
```

---

## Verification Commands

### Check Container Status

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose ps"
```

### Verify Celery Tasks Registered

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose logs --tail=30 celery | grep -A20 '\[tasks\]'"
```

### Check for Errors

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose logs --tail=50 | grep -i error"
```

### View Recent Logs

```bash
# All services
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose logs --tail=100"

# Specific service
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose logs --tail=50 celery"
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose logs --tail=50 backend"
```

---

## Troubleshooting

### Docker BuildKit Caching Issue

If rebuilds don't pick up code changes, BuildKit may be caching old layers. Solutions:

1. Use `DOCKER_BUILDKIT=0` to disable BuildKit
2. Use `docker cp` to copy files directly into containers
3. Run `docker builder prune -af` before building

### Restart Individual Services

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose restart celery"
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose restart backend"
```

### View Container File Contents

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && docker compose exec celery cat /app/backend/apps/uploads/tasks.py | head -20"
```

### Compare Source vs Container File

```bash
ssh aisdata@sz-verwaltung.ddns.net "cd PhotoSorter && \
  echo 'Source:' && md5sum backend/apps/uploads/tasks.py && \
  echo 'Container:' && docker compose exec celery md5sum /app/backend/apps/uploads/tasks.py"
```
