# IncidentOps - Build Status & How to Proceed

## Current Status ✓

**Running Services (Infrastructure):**
- ✓ Redis (port 6379) - healthy
- ✓ Chroma Vector DB (port 8001) - starting

**Building (First-Time Only):**
- ⏳ API service - building (~5-8 min, installing ML/AI dependencies)
- ⏳ Worker service - building
- ⏳ Frontend service - built (cached)

---

## Why is it taking so long?

The `pip install` step is downloading and compiling large ML dependencies:
- `torch` (PyTorch) - 600MB+
- `transformers` - 100MB+
- `sentence-transformers` - vector embeddings
- `chromadb` - vector DB client
- `langgraph` + `langchain` - agent orchestration
- Plus 80+ transitive dependencies

**This only happens on first build.** Subsequent builds use cache and are instant.

---

## Your Options Now

### Option 1: Wait for Full Stack (Recommended)

Let the build finish in the background. Monitor with:

```bash
docker compose logs -f api    # Watch API build
docker compose logs -f worker # Watch Worker build
```

**Expected time:** 5-10 minutes depending on internet speed and CPU.

Once complete, all services will be healthy and you can:
```bash
curl http://localhost:8000/docs         # Swagger UI
curl http://localhost:8501              # Streamlit UI
curl http://localhost:8000/health       # Health check
```

---

### Option 2: Test Right Now (Partial Stack)

Redis and Chroma are ready. Test their connectivity:

```bash
# Test Redis
docker exec incidentops-redis redis-cli ping
# Response: PONG ✓

# Test Chroma
curl http://localhost:8001/api/v1/heartbeat
# Response: {"status": "healthy"} ✓
```

---

## Checking Build Progress

**Option A: Live Build Logs**
```bash
docker compose up api worker --build
# Shows real-time pip install progress
```

**Option B: Non-blocking Progress**
```bash
docker compose logs -f api --tail=20
# Shows last 20 lines, updates every second
```

**Option C: Just Check Status**
```bash
docker compose ps   # Shows what's running/building
```

---

## When Ready (After Build Completes)

### 1. Verify All Services
```bash
docker compose ps
# All should show either "healthy" or "running"
```

### 2. Quick Health Check
```bash
curl -s http://localhost:8000/health | jq
```

### 3. Submit Test Alert
```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "PostgresReplicationLagHigh",
    "source": "prometheus",
    "fired_at": "2026-10-10T22:30:00Z",
    "metrics": {
      "replication_lag_bytes": 5000000.0,
      "active_connections": 42.0,
      "disk_utilization": 84.5
    },
    "pg_version": "18",
    "severity_hint": "CRITICAL",
    "on_call_note": "Replication slot standby_1 inactive, disk filling with WAL.",
    "tags": {"cluster": "prod-db-primary"}
  }'
```

### 4. Check Result
```bash
# Replace run-xxxxx with the run_id from response above
curl http://localhost:8000/runs/run-xxxxx
```

---

## Troubleshooting

### If Build Hangs
```bash
# Cancel with Ctrl+C, then retry with verbose output
docker compose up --build -d
docker compose logs -f api

# Or force rebuild from scratch
docker compose down -v
docker compose up --build -d
```

### If Out of Disk Space
```bash
# Clean up Docker
docker system prune -a --volumes
# Then restart
docker compose up --build -d
```

### Port Conflicts
```bash
# Check what's using port 8000
lsof -i :8000

# Or just use different ports in docker-compose.yml
# Change: "8000:8000" to "8010:8000"
```

---

## Next Steps

1. **Right now:** Check `docker compose ps` status
2. **In ~5-10 min:** All services will be ready
3. **Then:** Access the UI at http://localhost:8501 or API docs at http://localhost:8000/docs

Check back when ready, or let the build run in the background!
