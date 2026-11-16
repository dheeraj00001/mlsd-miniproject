# Incident Log & Operational Failure Runbooks (D8)

## 1. Development Incident Log (Genuine Development Failure)

### Incident INC-2026-001: SQLite Read-Only Database & LiteLLM Cost Map Network Hang
- **Date & Time:** 2026-11-03 04:30 UTC
- **Severity:** High (Development Block)
- **Component:** Test Harness, Chroma Vector DB, LiteLLM Gateway
- **Symptom:**
  Running `pytest` or initial agent triage stalled indefinitely (~14 seconds per test import), followed by errors:
  `chromadb.errors.InternalError: error returned from database: (code: 8) attempt to write a readonly database` and `PytestCacheWarning: cache could not write path E:\MLSD_MINI\.pytest_cache\v\cache\nodeids: [Errno 13] Permission denied`.
- **Root Cause Analysis:**
  1. Under containerized/sandboxed Windows process isolation on a secondary volume (`E:\`), file handles to SQLite databases and `.pytest_cache` defaulted to read-only access modes, preventing Chroma's persistent SQLite migration lock from acquiring.
  2. Concurrently, `LiteLLM` attempted to fetch remote cost model metadata (`model_prices_and_context_window.json`) over HTTPS upon first import. In offline/sandboxed environments without direct internet routing, the socket retried 3 times with exponential backoff, delaying every test worker by 14.5 seconds.
- **Confirmation:**
  - Ran `python -c "import litellm"`: confirmed network retry warnings and delay.
  - Ran `python -c "open('test_write.txt', 'w').write('test')"`: threw `PermissionError: [Errno 13]`.
- **Recovery & Fix:**
  - Injected `LITELLM_LOCAL_MODEL_COST_MAP=True` and `LITELLM_TELEMETRY=False` across `.env`, docker-compose, and test fixtures to force local offline cost mapping without remote HTTP polling.
  - Configured persistent volume mounts in `docker-compose.yml` (`chroma_data:/chroma/chroma`) and in-memory test fixtures for unit tests so local disk permission quirks do not lock runtime databases.
- **Resolution Status:** Resolved and verified.

---

## 2. Operational Failure Runbooks for Production Deployment

### Runbook 1: Downstream LLM Provider Outage or Rate Limit Depletion (A5, D8)
- **Symptom:**
  `504 Gateway Timeout` or `502 Bad Gateway` logged by `worker` container; runs transitioning to `ESCALATED` or `FAILED` status; LiteLLM error logs reporting `RateLimitError` or HTTP 429/503 from provider (Groq/Gemini).
- **Confirmation:**
  1. Inspect worker logs: `docker compose logs --tail=100 worker | grep "Circuit breaker"`
  2. Confirm circuit breaker state: if consecutive failures exceed threshold (3), log reads:
     `"Circuit breaker TRIPPED to OPEN state ... Fast-failing for 30.0s."`
  3. Query health endpoint: `curl http://localhost:8000/health`
- **Recovery:**
  1. Verify upstream provider status page.
  2. Switch to an alternative free-tier provider in `.env` (e.g. swap `LITELLM_MODEL=groq/llama-3.1-70b-versatile` to `gemini/gemini-1.5-flash` with corresponding `GEMINI_API_KEY`).
  3. Restart worker containers: `docker compose restart worker`.
  4. The circuit breaker will automatically enter `HALF_OPEN` state after the 30-second cooldown and reset to `CLOSED` once a canary request succeeds.

---

### Runbook 2: Chroma Vector DB Heartbeat Failure / Disk Full (D8)
- **Symptom:**
  `api` and `worker` fail health checks with `DependencyError`; agent tool calls to `corpus_search` throw `ChromaConnectionError`; HTTP `GET /health` reports index status as unavailable or connection refused on port 8000.
- **Confirmation:**
  1. Probe Chroma heartbeat directly: `curl -f http://localhost:8001/api/v1/heartbeat`
  2. Inspect container status: `docker compose ps chroma`
  3. Check container logs: `docker compose logs --tail=50 chroma`
- **Recovery:**
  1. If container exited unexpectedly, inspect container exit code: `docker inspect incidentops-chroma --format='{{.State.ExitCode}}'`
  2. Restart Chroma container: `docker compose restart chroma`
  3. Verify volume integrity and disk space: `docker volume inspect mlsd_mini_chroma_data`
  4. Once heartbeat responds with 200 OK, re-verify API health: `curl http://localhost:8000/health`
