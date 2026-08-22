"""
Shared telemetry module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

This module is environment-agnostic. The same code runs unchanged in
Docker Compose and Kubernetes. Only the infrastructure layer changes.

Docker Compose:
  Logs   -> JSON stdout -> Promtail -> Loki
  Traces -> OTLP gRPC   -> OTel Collector -> Tempo
  Metrics-> OTLP gRPC   -> OTel Collector -> Prometheus

Kubernetes + Istio:
  Logs   -> JSON stdout -> Promtail/FluentBit DaemonSet -> Loki
  Traces -> OTLP gRPC   -> OTel Collector (sidecar or gateway) -> Tempo
  Metrics-> OTLP gRPC   -> OTel Collector -> Prometheus

The application never needs to know which environment it's running in.
Only the log collector and network endpoints change, both via env vars.

Why JSON stdout for logs (not OTLP):
  - Works identically in Docker Compose and Kubernetes
  - Promtail, Fluent Bit, and OTel Collector can all scrape stdout
  - No extra dependencies or failure modes in the application
  - Loki is built for log aggregation, not trace storage
  - Trace/span context is manually added to JSON logs for correlation

Why OTLP for traces and metrics:
  - Traces need span context and parent-child relationships (only OTLP provides this well)
  - Metrics need aggregation, histograms, and background-thread reporting
  - OTel Collector handles batching, retry, and backend routing
"""

import os
import json
import logging
from datetime import datetime
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import Status, StatusCode


# =============================================================================
# RESOURCE: Service identity attached to all telemetry
# =============================================================================
# These env vars are set in docker-compose.yml and Kubernetes Deployments.
# The values stay the same across environments; only the backend endpoints change.
_resource = Resource.create({
    "service.name": os.getenv("SERVICE_NAME", "unknown-service"),
    "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
    "deployment.environment": os.getenv("ENVIRONMENT", "development"),
})


# =============================================================================
# TRACING: OTLP traces -> Tempo
# =============================================================================
# The OTLP endpoint changes per environment:
#   Docker Compose: http://otel-collector:4317
#   Kubernetes:     http://otel-collector.observability.svc.cluster.local:4317
_trace_provider = TracerProvider(resource=_resource)
_trace_provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"))
))
trace.set_tracer_provider(_trace_provider)


# =============================================================================
# METRICS: OTLP metrics -> Prometheus (via OTel Collector)
# =============================================================================
# The OTLP metrics endpoint changes per environment (same as traces above).
# The OTel Collector aggregates and exports to Prometheus-compatible format.
_metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://otel-collector:4317")),
    export_interval_millis=15000,  # export every 15s
)
_meter_provider = MeterProvider(resource=_resource, metric_readers=[_metric_reader])


# =============================================================================
# LOGGING: Structured JSON to stdout (universal - works everywhere)
# =============================================================================
# This is the ONE config that works for both Docker Compose and Kubernetes.
#
# Docker Compose:
#   Promtail scrapes Docker stdout and ships to Loki.
#
# Kubernetes:
#   Promtail or Fluent Bit DaemonSet scrapes container stdout and ships to Loki.
#   No code changes needed - same JSON format, same stdout stream.
#
# If you later want OTLP logs in Kubernetes:
#   1. Add OTLPLogExporter here
#   2. Add 'otlp' receiver to OTel Collector
#   3. Configure Loki OTLP receiver or export logs via OTLP to Loki
#   4. Set LOG_BACKEND=otlp env var
# =============================================================================

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


# =============================================================================
# PUBLIC API
# =============================================================================

def setup_tracing(service_name: str):
    """
    Initialize tracing for a FastAPI service.

    Enables:
    - Automatic HTTP request/response span creation
    - Resource attributes (service.name, version, environment)
    """
    tracer = trace.get_tracer(service_name)
    FastAPIInstrumentor.instrument_app(
        tracer_provider=_trace_provider,
        resource=_resource,
    )
    return tracer


def get_meter():
    """
    Get the OTLP metrics meter.

    Use this to create counters, histograms, gauges.
    Metrics are exported to Prometheus via OTel Collector every 15s.
    """
    return _meter_provider.get_meter(__name__)


def get_tracer(name: str):
    """
    Get a tracer for creating custom spans in business logic.

    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("process_order") as span:
            span.set_attribute("order.id", order_id)
            ...
    """
    return trace.get_tracer(name)
