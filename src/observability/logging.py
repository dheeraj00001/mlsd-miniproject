"""Structured JSON Logging Formatter (D5)."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from src.observability.correlation import get_correlation_id


class StructuredJsonFormatter(logging.Formatter):
    """JSON log formatter injecting timestamps, log levels, correlation IDs, and context."""

    def __init__(self, service_name: str = "incidentops"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "correlation_id": get_correlation_id(),
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_structured_logging(
    service_name: str = "incidentops", log_level: str = "INFO"
) -> None:
    """Configure root logger with StructuredJsonFormatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter(service_name=service_name))

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers = [handler]
