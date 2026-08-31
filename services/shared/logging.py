"""
Shared logging module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

Logs are written as structured JSON to stdout. Promtail/Fluent Bit scrape
stdout and ship to Loki. The same code runs unchanged in Docker Compose
and Kubernetes.

Why JSON stdout for logs (not OTLP):
  - Works identically in Docker Compose and Kubernetes
  - Promtail, Fluent Bit, and OTel Collector can all scrape stdout
  - No extra dependencies or failure modes in the application
  - Loki is built for log aggregation, not trace storage
  - Trace/span context is manually added to JSON logs for correlation
"""

import os
import json
import logging
from datetime import datetime


LOG_BACKEND = os.getenv("LOG_BACKEND", "json").lower()


class _JSONFormatter(logging.Formatter):
    """Format logs as JSON to stdout. Works in Docker Compose and Kubernetes."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "unknown"),
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry)


class _OTLPFormatter(logging.Formatter):
    """Format logs for OTLP export. Used only if LOG_BACKEND=otlp."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "severity": record.levelname,
            "body": record.getMessage(),
            "service.name": os.getenv("SERVICE_NAME", "unknown"),
        }
        if hasattr(record, "extra_data"):
            log_entry["attributes"] = record.extra_data
        return json.dumps(log_entry)


def _setup_handler(handler):
    if LOG_BACKEND == "otlp":
        handler.setFormatter(_OTLPFormatter())
    else:
        handler.setFormatter(_JSONFormatter())


def get_logger(name: str) -> logging.Logger:
    """
    Get a structured JSON logger for the given service name.

    Works in both Docker Compose and Kubernetes without code changes.
    The log format is controlled by the LOG_BACKEND env var:
      - LOG_BACKEND=json (default): JSON structured logs to stdout
      - LOG_BACKEND=otlp: JSON formatted for OTLP log export
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        _setup_handler(handler)
        logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log a structured event with extra context.

    Automatically includes trace_id and span_id from the current OpenTelemetry
    span context if available, enabling correlation between logs and traces.

    Usage:
        log_event(logger, "info", "Order created", order_id=123, correlation_id="abc")
    """
    extra = {"extra_data": kwargs} if kwargs else {}

    # Add trace/span context for correlation with distributed traces
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            trace_data = {
                "trace_id": format(ctx.trace_id, '032x'),
                "span_id": format(ctx.span_id, '016x'),
            }
            extra.setdefault("extra_data", {}).update(trace_data)
    except Exception:
        pass

    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra)
