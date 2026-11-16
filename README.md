# IncidentOps — Production Incident Triage and Runbook Assistant

An advisory multi-agent SRE assistant for PostgreSQL incidents. It accepts alert payloads and on-call notes, validates and quarantines malformed inputs at the ingestion boundary, retrieves operational guidance from PostgreSQL documentation and runbooks using active tools, determines cause class and severity, verifies all citations against retrieved text, and routes the incident.

> **Advisory Invariant:** The system **never executes remediation commands**. It strictly proposes cause classifications, verified first-response steps, and supporting citations. The on-call engineer decides.

---

## 1. System Architecture & Topology

The system runs as at least 4 interdependent services under Docker Compose (`docker compose up` from a clean clone):

```
[Browser / Streamlit] --:8501--> [frontend]
                                    |
                                    v (HTTP)
[Client / Prometheus]  --:8000--> [api (FastAPI Gateway)]
                                    |
                                    +---> [Quarantine Store (Rejects)]
                                    |
                                    +---> [redis:6379 (Task Queue & Run Cache)]
                                             ^
                                             | (Dequeues run_id)
                                          [worker (Multi-Agent Reasoning)]
                                             |
                                             +---> [chroma:8000 (Vector DB)]
                                             +---> LiteLLM Gateway (Cloud Free-Tier)
```

| Service | Technology | Role & Port |
|---|---|---|
| `api` | FastAPI / Python 3.11 | Ingestion boundary, schema validation, quarantine, async run API (`:8000`). |
| `worker` | Python 3.11 | Background agent worker executing the LangGraph triage $\rightarrow$ investigation $\rightarrow$ verification graph. |
| `redis` | Redis 7 Alpine | FIFO task queue broker and run status store (`:6379`). |
| `chroma` | Chroma DB | Vector database with CPU `sentence-transformers/all-MiniLM-L6-v2` (`:8001` host, `:8000` internal). |
| `frontend` | Streamlit | Thin async web client polling run status and rendering verified guidance (`:8501`). |

---

## 2. Quickstart

### Prerequisites
- Docker & Docker Compose (`docker-compose` or `docker compose`)
- (Optional for local development) Python 3.11

### Step 1: Clone and Configure Environment
```bash
cp .env.example .env
# Edit .env to set your free-tier LLM API key (e.g. GROQ_API_KEY or GEMINI_API_KEY)
```

### Step 2: Launch Full Multi-Service Stack
```bash
docker-compose up --build
```

### Step 3: Access Interfaces
- **Streamlit Web UI:** [http://localhost:8501](http://localhost:8501)
- **FastAPI OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
- **Prometheus Metrics:** [http://localhost:8000/metrics](http://localhost:8000/metrics)

---

## 3. The Section 4.1 Benchmark Demonstration

The authoritative test case from the specification:
> *"Disk usage on the primary is climbing steadily. Table and index sizes are not growing. On-call note: disk filling, cause unknown."*

A single-pass naive keyword search on disk usage fails because it returns table maintenance rather than replication slot WAL retention. IncidentOps's multi-hop investigator retrieves the provision that appears to apply, identifies the modifying replication slot behavior in the PostgreSQL 18 replication chapter, and returns verified citations grounding the advisory steps:

```bash
# Submit Section 4.1 alert via CLI:
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "PostgresWalAccumulationWarning",
    "source": "prometheus",
    "fired_at": "2026-10-10T22:30:00Z",
    "metrics": {
      "disk_utilization": 88.5,
      "replication_lag_bytes": 104857600.0,
      "active_connections": 42.0
    },
    "pg_version": "18.0",
    "severity_hint": "CRITICAL",
    "on_call_note": "Disk usage on primary climbing steadily in /pg_wal. Standby replica standby_1 had network blip earlier.",
    "tags": {"cluster": "prod-db-primary"}
  }'
```

Response:
```json
{
  "run_id": "run-a1b2c3d4e5f6",
  "status": "queued",
  "created_at": "2026-10-10T22:30:00Z",
  "alert_name": "PostgresWalAccumulationWarning",
  "message": "Alert validated successfully and enqueued for multi-agent triage."
}
```

Poll status:
```bash
curl http://localhost:8000/runs/run-a1b2c3d4e5f6
```

---

## 4. Evaluation Suite & Scientific Metrics (L3)

The evaluation suite comprises **20 fixed synthetic scenarios** in `data/eval/scenarios.jsonl` testing normal incidents, Section 4.1 replication slot WAL retention, out-of-corpus degradation, ambiguous multi-cause alerts, and adversarial prompt injections.

To run the scientific evaluation suite:
```bash
python -m app.eval.run --scenarios data/eval/scenarios.jsonl
```

### Metrics Reported:
- **Cause-Class Accuracy:** Percentage of alerts matching ground-truth cause class enum.
- **Route Accuracy:** Accuracy in routing between `self-serve runbook`, `page-secondary`, and `incident-commander`.
- **Escalation Precision & Recall:** Precision and recall for routing to human escalation (F7).
- **Citation-Resolves Rate:** Percentage of citations exactly resolving to retrieved documentation text.

---

## 5. Guardrails & Defensive Boundaries (L4)

1. **Prompt Injection Defense (`src/guardrails/injection.py`):** Intercepts jailbreak strings, system overrides, and prompt leaks in `on_call_note` before reaching model reasoning loops.
2. **Toxicity Detection (`src/guardrails/toxicity.py`):** Real-time scanning for abusive, toxic, or malicious language on inputs and generated outputs.
3. **Output Authorization Filter (`src/guardrails/output.py`):** Ensures `cause_class`, `severity`, and `route` conform strictly to authorized enums, and blocks any destructive executable commands (`rm -rf`, `drop database`, `kill -9`, etc.).

---

## 6. Service Level Objectives & Load Testing (D6)

### Declared Service Level Objective (SLO):
- **Complete End-to-End Run Latency (Submission to Result):** **p95 $\le$ 8.00 seconds**
- **Ingestion Boundary Latency (`POST /runs`):** **p95 $\le$ 0.20 seconds**

### Locust Load Test with LLM Stub:
```bash
locust -f src/eval/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s
```

---

## 7. Operational Documentation & Runbooks
- **Architecture & Boundaries:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Architecture Decision Records (ADRs):** [`docs/DECISIONS.md`](docs/DECISIONS.md)
- **Incident Log & Failure Runbooks (D8):** [`docs/INCIDENT_LOG.md`](docs/INCIDENT_LOG.md)
- **Data Ingestion Contract:** [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)
- **Agent Topology & Transitions:** [`docs/TOPOLOGY.md`](docs/TOPOLOGY.md)
- **Project Progress Tracker:** [`docs/PROGRESS.md`](docs/PROGRESS.md)
