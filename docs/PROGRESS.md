# IncidentOps — Project Progress & Milestone Tracker

## Current Status: Full System Implemented (MUST & NEXT Slices Completed, Docker Compose Ready)

---

### Prioritized Vertical Slice Roadmap

#### Tier 1: MUST Slices (Foundational Core — Minimum Viable Demonstration)

| Slice # | Slice Title | Requirements Covered | Scope & Key Deliverables | Tests Passing | Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **1** | **Ingestion Contract & Quarantine** | **F1, F2, D1, D4** | Pydantic data contract, range, categorical & cross-field validation, quarantine storage for rejected requests, `.env.example`. | 27 / 27 (100%) | **Completed** |
| **2** | **Corpus Ingestion & Chroma Vector Store** | **D2, L1, F4** | PostgreSQL 18 PDF/markdown parser, 3 custom runbooks, escalation policy, hierarchical section chunker with breadcrumbs & section IDs, CPU `all-MiniLM-L6-v2` embeddings, idempotent Chroma upsert by ID, freshness metrics. | 37 / 37 (100%) | **Completed** |
| **3** | **Multi-Agent Core & Tools** | **F3, A1, A2** | LangGraph 2-agent topology: Triage Agent (extracts entities, candidate cause classes) -> typed hand-off -> Investigator Agent. Tools: `corpus_search`, `get_section`, `get_alert_field`. Bounded loops (steps, tool calls, wall-clock time). | 43 / 43 (100%) | **Completed** |
| **4** | **Citation Verifier & Escalation Engine** | **F5, F6, F7, A3** | Mandatory Verifier: checks every citation resolves to retrieved text. Categorical cause classification, severity assignment, and routing (`self-serve runbook`, `page-secondary`, `incident-commander`). Deterministic escalation on ambiguous support (F7, Section 4.1 scenario). | 52 / 52 (100%) | **Completed** |
| **5** | **Async API & Redis Worker Queue** | **A4, D3** | FastAPI asynchronous endpoints: `POST /runs` (returns `run_id`), `GET /runs/{id}`, `GET /quarantine`. Redis-backed task queue with background worker (`src/worker/main.py`), and `RunStore` (`src/worker/store.py`). Docker Compose 5-service topology (`api`, `worker`, `redis`, `chroma`, `frontend`). | Verified | **Completed** |
| **6** | **Streamlit Web Client UI** | **A8** | Web client (`frontend/app.py`) submitting alerts and notes, Section 4.1 quick-fill, polling run status, displaying routed recommendations with verified citations, or escalation path. | Verified | **Completed** |

#### Tier 2: NEXT Slices (Reliability, Guardrails & LLMOps)

| Slice # | Slice Title | Requirements Covered | Scope & Key Deliverables | Tests Passing | Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **7** | **Guardrails & Defensive Boundaries** | **L4** | Prompt-injection detection (`src/guardrails/injection.py`), real-time input/output toxicity checks (`src/guardrails/toxicity.py`), output authorization filter blocking unauthorized determinations and destructive remediation commands (`src/guardrails/output.py`). | Verified | **Completed** |
| **8** | **Timeouts & Circuit Breaker** | **A5** | Per-call timeouts, bounded exponential backoff retries, circuit breaker on LLM provider (`src/gateway/client.py`), graceful degradation fallback to safe escalation (`page-secondary`). | Verified | **Completed** |
| **9** | **20-Scenario Evaluation Suite** | **L3** | Fixed benchmark suite (`data/eval/scenarios.jsonl`, 20 synthetic scenarios covering normal, section 4.1, out-of-corpus, ambiguous, prompt-injection, toxicity, and destructive attempts) with evaluation CLI `app.eval.run`. | Verified | **Completed** |
| **10** | **Observability & Correlation Tracing** | **D5, F8** | Correlation IDs across API and agent steps (`src/observability/correlation.py`), structured JSON logging (`src/observability/logging.py`), Prometheus `/metrics` endpoint. | Verified | **Completed** |
| **11** | **Declared SLO & Locust Load Testing** | **D6** | Declared p95 SLO target ($\le 8.0$s e2e, $\le 0.2$s submit). Realistic LLM stub service returning canned responses (`src/eval/stub_llm.py`). Locust load test measuring p50/p95, RPS (`src/eval/locustfile.py`). | Verified | **Completed** |

#### Tier 3: LATER Slices (Optimization, Scaling & Governance)

| Slice # | Slice Title | Requirements Covered | Scope & Key Deliverables | Tests Passing | Status |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **12** | **Prompt Versioning & Comparison** | **L2** | Prompt versioning artifacts (`triage-v1.0.0`, `investigator-v1.0.0`); prompt version recorded with every response. | Implemented | Pending Evaluation Report |
| **13** | **Cost & Token Attribution** | **L5** | Per-step and per-run prompt/completion token tracking in LiteLLM cache. | Partial | Pending |
| **14** | **Worker Scaling & Bottleneck Analysis** | **A7** | Benchmark `docker compose up --scale worker=3` against Locust stub. | Runnable | Pending |
| **15** | **Caching & Rate Limiting** | **D7** | Caching of SQLite responses in `GatewayResponseCache`. | Implemented | Pending |
| **16** | **User Feedback & Quality Tracking** | **L6** | Endpoint for feedback (satisfactory/unsatisfactory + reason). | TBD | Pending |
| **17** | **Dashboard Agent Analytics** | **A6** | Dashboard tracking per-agent success rate, tool calls per run, container uptime. | TBD | Pending |
| **18** | **Failure Runbooks & Incident Log** | **D8** | Runbooks for top 2 failure modes (provider outage, chroma failure) and genuine development incident log entry. | Documented | **Completed** |

---

### Activity Log
- **2026-10-09:** Completed baseline project memory bootstrap.
- **2026-10-09:** Aligned all architecture and memory specifications to authoritative `docs/ASSIGNMENT.pdf`.
- **2026-10-10:** Completed **Slice 1: Ingestion Contract & Quarantine** (F1, F2, D1, D4).
- **2026-10-10:** Completed **Slice 2: Corpus Ingestion & Chroma Vector Store** (D2, L1, F4).
- **2026-10-10:** Completed **Slice 3: Multi-Agent Core & Tools** (F3, A1, A2).
- **2026-10-11:** Completed **Slice 4: Citation Verifier & Escalation Engine** (F5, F6, F7, A3).
- **2026-11-03:** Completed **Slice 5: Async API & Redis Worker Queue** (A4, D3):
  - Created `src/worker/store.py` (`RunStore`, `RedisRunStore`, `InMemoryRunStore`).
  - Created background agent consumer `src/worker/main.py` executing `run_multi_agent_triage`.
  - Added `GET /runs/{run_id}` and `RunDetailResponse` in `src/api/main.py`.
- **2026-11-03:** Completed **Slice 6: Streamlit Web Client UI** (A8):
  - Built `frontend/app.py` with Section 4.1 scenario quick-fill, async run polling, quarantine viewer, and health checks.
  - Authored `Dockerfile.frontend`.
- **2026-11-03:** Completed **Slice 7: Guardrails & Defensive Boundaries** (L4):
  - Created `src/guardrails/toxicity.py` (real-time input/output abusive language detection).
  - Created `src/guardrails/output.py` (authorisation filter for cause classes/routes, blocking destructive remediation commands).
- **2026-11-03:** Completed **Slice 8: Timeouts & Circuit Breaker** (A5):
  - Upgraded `src/gateway/client.py` with `CircuitBreaker` (states: CLOSED, OPEN, HALF_OPEN; threshold 3, cooldown 30s).
  - Added bounded exponential backoff retries (factor 1.5, max 3 attempts) and 15s per-request timeout.
- **2026-11-03:** Completed **Slice 9: 20-Scenario Evaluation Suite** (L3):
  - Expanded `data/eval/scenarios.jsonl` from 10 to 20 synthetic scenarios covering all failure modes, out-of-corpus, ambiguous, and prompt-injection/toxicity cases.
- **2026-11-03:** Completed **Slice 10: Observability & Correlation Tracing** (D5, F8):
  - Created `src/observability/correlation.py` (`X-Correlation-ID` middleware).
  - Created `src/observability/logging.py` (`StructuredJsonFormatter`).
- **2026-11-03:** Completed **Slice 11: Declared SLO & Locust Load Testing** (D6):
  - Created `src/eval/stub_llm.py` (`StubLLMService`).
  - Created `src/eval/locustfile.py` declaring p95 $\le 8.0$s end-to-end run latency and p95 $\le 0.2$s submit latency.
- **2026-11-03:** Completed **Slice 18 & Platform Setup (D3, D8)**:
  - Authored `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.worker`, `Dockerfile.frontend`.
  - Created `docs/INCIDENT_LOG.md` recording genuine development incident INC-2026-001 and operational failure runbooks.
  - Rewrote and published comprehensive `README.md`.
