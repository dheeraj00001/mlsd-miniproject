# IncidentOps Quick Start Guide

## 1. Prerequisites
- Docker & Docker Compose installed
- Free-tier LLM API key (Groq, OpenAI, or Gemini)

## 2. Setup

### Create .env file
```bash
cp .env.example .env
```

Edit `.env` and add your LLM key:
```
GROQ_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here
# OR
GEMINI_API_KEY=your_key_here
```

### Start all services
```bash
docker compose up --build -d
```

### Wait for services to be healthy
```bash
docker compose ps  # Check status
```

Expected output:
```
NAME                IMAGE              STATUS
incidentops-redis   redis:7-alpine     healthy
incidentops-chroma  chromadb/chroma    healthy
incidentops-api     mlsd_mini-api      healthy
incidentops-worker  mlsd_mini-worker   running
incidentops-frontend mlsd_mini-frontend running
```

## 3. Access the System

### Streamlit UI (Simple)
http://localhost:8501

### FastAPI Docs (Technical)
http://localhost:8000/docs

### Health Check
```bash
curl http://localhost:8000/health
```

## 4. Submit a Test Alert

### Via curl:
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
    "on_call_note": "Replication slot standby_1 appears inactive and disk is filling up with WAL.",
    "tags": {"cluster": "prod-db-primary", "region": "us-east-1"}
  }'
```

Response:
```json
{
  "run_id": "run-abc123def456",
  "status": "queued",
  "created_at": "2026-10-10T22:30:00Z",
  "alert_name": "PostgresReplicationLagHigh",
  "message": "Alert validated successfully and enqueued for multi-agent triage."
}
```

### Check result:
```bash
curl http://localhost:8000/runs/run-abc123def456
```

## 5. View Quarantined Requests (Bad Data)

```bash
# List all quarantined requests
curl http://localhost:8000/quarantine

# Get specific quarantine record
curl http://localhost:8000/quarantine/quar-xyz789
```

## 6. Monitor Logs

### API logs
```bash
docker compose logs -f api
```

### Worker logs
```bash
docker compose logs -f worker
```

### All services
```bash
docker compose logs -f
```

## 7. Stop the System

```bash
docker compose down
```

## 8. Troubleshooting

### Services not starting
```bash
# Check logs
docker compose logs api
docker compose logs worker

# Common issues:
# - Port 8000, 8501, 6379 already in use
# - LLM API key missing or invalid
# - Not enough disk space
```

### Worker not processing
```bash
# Check worker logs
docker compose logs worker

# Restart worker
docker compose restart worker
```

### Redis connection errors
```bash
# Test Redis connection
docker exec incidentops-redis redis-cli ping
# Should return: PONG
```

### Chroma not responding
```bash
# Test Chroma health
curl http://localhost:8001/api/v1/heartbeat
```

## 9. Development Tips

### Run locally (without Docker)
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"

# In one terminal:
redis-server

# In another:
python -m src.worker.main

# In another:
uvicorn src.api.main:app --reload
```

### Format code
```bash
ruff check src/ --fix
```

### Run tests
```bash
pytest tests/ -v
```

## 10. Next Steps

- Set up CI/CD (GitHub Actions, GitLab CI)
- Deploy to Kubernetes or cloud platform
- Add custom guardrails and business logic
- Integrate with existing incident management tools
