"""Unit and integration tests for async runs and worker execution (A4, D3)."""

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.quarantine import QuarantineStore, set_quarantine_store
from src.worker.main import IncidentOpsWorker
from src.worker.queue import InMemoryTaskQueue, set_task_queue
from src.worker.store import InMemoryRunStore, set_run_store


def test_async_run_lifecycle_queued_to_completed():
    """Verify end-to-end async submission, queueing, worker execution, and status retrieval."""
    test_queue = InMemoryTaskQueue()
    test_store = InMemoryRunStore()
    test_quarantine = QuarantineStore(db_path=":memory:")

    set_task_queue(test_queue)
    set_run_store(test_store)
    set_quarantine_store(test_quarantine)

    client = TestClient(app)

    payload: dict[str, Any] = {
        "alert_id": "alert-async-001",
        "alert_name": "PostgresWalAccumulationWarning",
        "source": "prometheus",
        "fired_at": datetime.now(UTC).isoformat(),
        "metrics": {
            "replication_lag_bytes": 104857600.0,
            "disk_utilization": 88.5,
            "active_connections": 42.0,
        },
        "pg_version": "18.0",
        "severity_hint": "CRITICAL",
        "on_call_note": "Disk usage on primary node rapidly climbing in /pg_wal. Standby replica standby_1 had network blip earlier.",
        "tags": {"cluster": "prod-db-primary"},
    }

    # 1. Submit run
    post_res = client.post("/runs", json=payload)
    assert post_res.status_code == 202
    run_id = post_res.json()["run_id"]
    assert post_res.json()["status"] == "queued"

    # 2. Check status is queued
    get_res = client.get(f"/runs/{run_id}")
    assert get_res.status_code == 200
    run_data = get_res.json()
    assert run_data["run_id"] == run_id
    assert run_data["status"] == "queued"
    assert run_data["result"] is None

    # 3. Simulate worker dequeuing and processing
    worker = IncidentOpsWorker(queue=test_queue, store=test_store)
    assert test_queue.length() == 1
    task = test_queue.dequeue()
    assert task is not None
    tid, tpayload = task
    assert tid == run_id

    # Process one
    success = worker.process_one(run_id=tid, alert_payload=tpayload)
    assert success is True

    # 4. Check status is completed or escalated (with valid advisory guidance)
    final_res = client.get(f"/runs/{run_id}")
    assert final_res.status_code == 200
    final_data = final_res.json()
    assert final_data["status"] in ["completed", "escalated"]
    assert final_data["result"] is not None
    assert final_data["result"]["cause_class"] in [
        "saturation",
        "contention",
        "configuration",
        "dependency_failure",
        "data_volume",
    ]
    assert len(final_data["result"]["first_response_steps"]) > 0


def test_get_nonexistent_run_returns_404():
    """Verify querying an unknown run_id returns HTTP 404."""
    test_store = InMemoryRunStore()
    set_run_store(test_store)
    client = TestClient(app)

    res = client.get("/runs/run-nonexistent-12345")
    assert res.status_code == 404
