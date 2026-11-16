"""Async Background Agent Worker (A4, D3).

Consumes incident alert triage jobs from Redis task queue, executes the LangGraph
multi-agent reasoning graph (Triage -> Investigator -> Verifier), and records
the results and status transitions in the RunStore.
"""

import logging
import signal
import time
from typing import Any

from src.agent.graph import run_multi_agent_triage
from src.agent.state import InvestigationOutput
from src.worker.queue import TaskQueue, get_task_queue
from src.worker.store import RunStore, get_run_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("incidentops.worker")


class IncidentOpsWorker:
    """Background worker processing incident triage runs from queue."""

    def __init__(
        self,
        queue: TaskQueue | None = None,
        store: RunStore | None = None,
        poll_timeout_seconds: int = 2,
    ):
        self.queue = queue or get_task_queue()
        self.store = store or get_run_store()
        self.poll_timeout = poll_timeout_seconds
        self._running = False

    def process_one(self, run_id: str, alert_payload: dict[str, Any]) -> bool:
        """Process a single triage run end-to-end."""
        logger.info(
            "Starting processing for run_id=%s alert=%s", run_id, alert_payload.get("alert_name")
        )
        self.store.update_status(run_id, status="running")

        try:
            start_time = time.time()
            graph_result = run_multi_agent_triage(alert_payload)
            elapsed = time.time() - start_time

            output: InvestigationOutput | None = graph_result.get("final_output")
            error = graph_result.get("error")
            fallback = graph_result.get("fallback_triggered", False)

            if output:
                # Determine final status based on routing and verification
                if output.route in ["page-secondary", "incident-commander"] and (
                    not output.verified or output.escalation_reason
                ):
                    status = "escalated"
                elif fallback:
                    status = "failed"
                else:
                    status = "completed"

                self.store.update_status(run_id, status=status, result=output, error=error)
                logger.info(
                    "Completed run_id=%s status=%s cause=%s route=%s in %.2fs",
                    run_id,
                    status,
                    output.cause_class,
                    output.route,
                    elapsed,
                )
            else:
                self.store.update_status(
                    run_id,
                    status="failed",
                    error=error or "Agent produced no output",
                )
                logger.error("Run_id=%s produced no output (error=%s)", run_id, error)

            return True

        except Exception as exc:
            logger.exception("Unexpected exception executing run_id=%s", run_id)
            self.store.update_status(run_id, status="failed", error=str(exc))
            return False

    def run(self) -> None:
        """Run consumer loop until interrupted."""
        self._running = True
        logger.info("IncidentOps worker started. Waiting for runs...")
        backoff_seconds = 1

        while self._running:
            try:
                task = self.queue.dequeue(timeout=self.poll_timeout)
                if task:
                    run_id, payload = task
                    self.process_one(run_id, payload)
                    # Reset backoff on successful task
                    backoff_seconds = 1
            except (KeyboardInterrupt, SystemExit):
                logger.info("Worker shutdown requested.")
                break
            except MemoryError as exc:
                logger.critical("Out of memory; worker cannot continue: %s", exc)
                raise
            except Exception as exc:  # noqa: BLE001 - Resilient worker consumer loop
                logger.error("Error in worker loop: %s", exc)
                time.sleep(min(backoff_seconds, 30))  # Cap backoff at 30s
                backoff_seconds = min(backoff_seconds * 2, 30)

        self._running = False
        logger.info("Worker stopped cleanly.")

    def stop(self) -> None:
        """Signal worker to stop processing."""
        self._running = False


def main() -> None:
    """Worker CLI entrypoint."""
    try:
        worker = IncidentOpsWorker()

        def _sig_handler(signum: int, frame: Any) -> None:
            logger.info("Signal %s received; stopping worker...", signum)
            worker.stop()

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

        worker.run()
    except MemoryError:
        logger.critical("Fatal: Worker out of memory.")
        raise
    except Exception as exc:
        logger.critical("Fatal exception in worker: %s", exc, exc_info=True)
        raise


if __name__ == "__main__":
    main()
