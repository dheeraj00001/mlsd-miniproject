"""Student 3: Knowledge Retrieval, Evaluation & Frontend Engineer.

Locust Load Testing Suite with Stub LLM and Declared p95 SLOs (D6).
Simulates concurrent on-call incident submissions and validates asynchronous run lifecycle latency.

Declared Target SLOs:
- Complete end-to-end run latency: p95 <= 8.00 seconds.
- Ingestion submission latency: p95 <= 0.20 seconds.
"""

import time
from typing import Any

from locust import HttpUser, between, events, task

# Declared Service Level Objectives (SLOs)
DECLARED_E2E_P95_SLO_SECONDS = 8.00
DECLARED_SUBMIT_P95_SLO_SECONDS = 0.20


class IncidentOpsLoadTestUser(HttpUser):
    """Simulates on-call engineers submitting incident alerts and polling for recommendations."""

    wait_time = between(0.5, 2.0)

    @task(3)
    def submit_and_poll_section_4_1_alert(self) -> None:
        """Submit Section 4.1 replication slot alert and poll to completion."""
        payload: dict[str, Any] = {
            "alert_name": "PostgresWalAccumulationWarning",
            "source": "prometheus",
            "fired_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metrics": {
                "disk_utilization": 88.5,
                "replication_lag_bytes": 104857600.0,
                "active_connections": 42.0,
            },
            "pg_version": "18.0",
            "severity_hint": "CRITICAL",
            "on_call_note": "Disk usage on primary climbing steadily in /pg_wal. Replication slot suspected.",
            "tags": {"cluster": "prod-db-primary"},
        }

        start_time = time.time()

        # 1. Submit alert
        with self.client.post("/runs", json=payload, catch_response=True) as post_res:
            if post_res.status_code == 202:
                data = post_res.json()
                run_id = data.get("run_id")
                post_res.success()
            else:
                post_res.failure(f"Submit failed with code {post_res.status_code}: {post_res.text}")
                return

        # 2. Poll until completed or timeout
        poll_start = time.time()
        max_poll_seconds = 20.0
        poll_interval = 0.5
        completed = False

        while (time.time() - poll_start) < max_poll_seconds:
            with self.client.get(
                f"/runs/{run_id}", name="/runs/{id}", catch_response=True
            ) as get_res:
                if get_res.status_code == 200:
                    run_info = get_res.json()
                    status = run_info.get("status")
                    if status in ["completed", "escalated"]:
                        completed = True
                        get_res.success()
                        break
                    elif status == "failed":
                        get_res.failure(f"Run {run_id} failed: {run_info.get('error')}")
                        break
                else:
                    get_res.failure(f"Poll failed with {get_res.status_code}")
                    break

            time.sleep(poll_interval)

        total_latency = time.time() - start_time

        # Report custom event for complete submission-to-result latency
        events.request.fire(
            request_type="E2E_RUN",
            name="complete_run_submission_to_result",
            response_time=total_latency * 1000.0,  # ms
            response_length=0,
            exception=None
            if completed
            else TimeoutError("Run did not complete within SLA timeout"),
            context=self.context(),
        )

    @task(1)
    def query_quarantine_log(self) -> None:
        """Query quarantine log."""
        self.client.get("/quarantine?limit=20", name="/quarantine")

    @task(1)
    def query_health_and_metrics(self) -> None:
        """Health check endpoint."""
        self.client.get("/health", name="/health")
