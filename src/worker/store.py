"""Run status and result storage supporting Redis and in-memory backends (A4, D3)."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Literal

import redis

from config.settings import get_settings
from src.agent.state import InvestigationOutput

logger = logging.getLogger(__name__)

RunStatusType = Literal["queued", "running", "completed", "escalated", "failed"]


class RunRecord:
    """Represents the complete state and result of an incident triage run."""

    def __init__(
        self,
        run_id: str,
        status: RunStatusType = "queued",
        created_at: str | None = None,
        updated_at: str | None = None,
        alert: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ):
        self.run_id = run_id
        self.status = status
        now_str = datetime.now(UTC).isoformat()
        self.created_at = created_at or now_str
        self.updated_at = updated_at or now_str
        self.alert = alert or {}
        self.result = result
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Serialize run record to dictionary."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "alert": self.alert,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        """Deserialize run record from dictionary."""
        return cls(
            run_id=data["run_id"],
            status=data.get("status", "queued"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            alert=data.get("alert"),
            result=data.get("result"),
            error=data.get("error"),
        )


class RunStore(ABC):
    """Abstract interface for storing and retrieving run state."""

    @abstractmethod
    def create_run(self, run_id: str, alert: dict[str, Any]) -> RunRecord:
        """Create initial run in queued state."""

    @abstractmethod
    def update_status(
        self,
        run_id: str,
        status: RunStatusType,
        result: InvestigationOutput | dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RunRecord | None:
        """Update status and optional result/error."""

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord | None:
        """Retrieve run record by id."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all runs (for testing)."""


class InMemoryRunStore(RunStore):
    """In-memory run storage for testing and local operation."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def create_run(self, run_id: str, alert: dict[str, Any]) -> RunRecord:
        now_str = datetime.now(UTC).isoformat()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            created_at=now_str,
            updated_at=now_str,
            alert=alert,
        )
        self._runs[run_id] = record
        return record

    def update_status(
        self,
        run_id: str,
        status: RunStatusType,
        result: InvestigationOutput | dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RunRecord | None:
        record = self._runs.get(run_id)
        if not record:
            return None
        record.status = status
        record.updated_at = datetime.now(UTC).isoformat()
        if result is not None:
            if isinstance(result, InvestigationOutput):
                record.result = result.model_dump(mode="json")
            else:
                record.result = result
        if error is not None:
            record.error = error
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def clear(self) -> None:
        self._runs.clear()


class RedisRunStore(RunStore):
    """Production Redis-backed run storage."""

    def __init__(self, redis_url: str | None = None) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.REDIS_URL
        self.client = redis.Redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=True,
        )
        self.key_prefix = "incidentops:run:"

    def _key(self, run_id: str) -> str:
        return f"{self.key_prefix}{run_id}"

    def create_run(self, run_id: str, alert: dict[str, Any]) -> RunRecord:
        now_str = datetime.now(UTC).isoformat()
        record = RunRecord(
            run_id=run_id,
            status="queued",
            created_at=now_str,
            updated_at=now_str,
            alert=alert,
        )
        self.client.set(self._key(run_id), json.dumps(record.to_dict()))
        return record

    def update_status(
        self,
        run_id: str,
        status: RunStatusType,
        result: InvestigationOutput | dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RunRecord | None:
        key = self._key(run_id)
        raw = self.client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        data["status"] = status
        data["updated_at"] = datetime.now(UTC).isoformat()
        if result is not None:
            if isinstance(result, InvestigationOutput):
                data["result"] = result.model_dump(mode="json")
            else:
                data["result"] = result
        if error is not None:
            data["error"] = error

        self.client.set(key, json.dumps(data))
        return RunRecord.from_dict(data)

    def get_run(self, run_id: str) -> RunRecord | None:
        raw = self.client.get(self._key(run_id))
        if not raw:
            return None
        return RunRecord.from_dict(json.loads(raw))

    def clear(self) -> None:
        keys = self.client.keys(f"{self.key_prefix}*")
        if keys:
            self.client.delete(*keys)


_global_run_store: RunStore | None = None


def get_run_store() -> RunStore:
    """Return the configured run store instance."""
    global _global_run_store
    if _global_run_store is None:
        settings = get_settings()
        try:
            rs = RedisRunStore(settings.REDIS_URL)
            rs.client.ping()
            _global_run_store = rs
        except (redis.RedisError, ConnectionError, OSError) as exc:
            logger.warning("Redis connection failed for RunStore (%s); using InMemoryRunStore", exc)
            _global_run_store = InMemoryRunStore()
    return _global_run_store


def set_run_store(store: RunStore) -> None:
    """Explicitly set the run store instance (for testing)."""
    global _global_run_store
    _global_run_store = store
