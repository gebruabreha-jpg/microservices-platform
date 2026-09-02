"""
Shared structured logging.

Logs are written as one JSON object per line to stdout; promtail scrapes the
container's stdout and ships to Loki. `get_logger(name)` returns a
``StructuredLogger`` whose ``.info()/.error()/.warning()`` take arbitrary
keyword fields, and it folds in the current trace/span id so logs and traces
correlate in Grafana.

    log = get_logger("order-service")
    log.info("Order created", order_id=123, correlation_id="abc")
"""

import json
import logging
import os
from datetime import datetime

LOG_BACKEND = os.getenv("LOG_BACKEND", "json").lower()


class _JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "unknown"),
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry.update(record.extra_data)
        return json.dumps(entry)


class _OTLPFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "severity": record.levelname,
            "body": record.getMessage(),
            "service.name": os.getenv("SERVICE_NAME", "unknown"),
        }
        if hasattr(record, "extra_data"):
            entry["attributes"] = record.extra_data
        return json.dumps(entry)


def _stdlib_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_OTLPFormatter() if LOG_BACKEND == "otlp" else _JSONFormatter())
        logger.addHandler(handler)
    return logger


def _trace_fields() -> dict:
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
    except Exception:
        pass
    return {}


class StructuredLogger:
    """Thin wrapper over a stdlib logger that accepts structured keyword fields."""

    def __init__(self, name: str):
        self._logger = _stdlib_logger(name)

    def _emit(self, level: str, message: str, **fields) -> None:
        data = {**fields, **_trace_fields()}
        getattr(self._logger, level, self._logger.info)(
            message, extra={"extra_data": data} if data else {}
        )

    def debug(self, message: str, **fields) -> None:
        self._emit("debug", message, **fields)

    def info(self, message: str, **fields) -> None:
        self._emit("info", message, **fields)

    def warning(self, message: str, **fields) -> None:
        self._emit("warning", message, **fields)

    def error(self, message: str, **fields) -> None:
        self._emit("error", message, **fields)


def get_logger(name: str) -> StructuredLogger:
    """Return a structured logger for the given service/component name."""
    return StructuredLogger(name)
