"""
Shared metrics module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

Every service records metrics through an OpenTelemetry meter whose reader
exposes them in Prometheus text format. `setup_metrics_endpoint(app)` serves
them at GET /metrics, and Prometheus scrapes each service directly (see
platform/prometheus/prometheus.yml). No collector hop for metrics.
"""

from opentelemetry.sdk.metrics import MeterProvider

_readers = []

# Expose metrics in Prometheus text format via the default prometheus_client
# registry, so generate_latest() returns the real application counters and
# histograms (plus process stats), not an empty registry.
try:
    from opentelemetry.exporter.prometheus import PrometheusMetricReader

    _readers.append(PrometheusMetricReader())
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - exporter not installed
    _PROMETHEUS_AVAILABLE = False

from shared.tracing import _resource

_meter_provider = MeterProvider(resource=_resource, metric_readers=_readers)


def get_metric():
    """Return the service meter used to create counters, histograms, and gauges."""
    return _meter_provider.get_meter(__name__)


def setup_metrics_endpoint(app):
    """Register GET /metrics on a FastAPI app, serving Prometheus text format."""
    try:
        from fastapi import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    except ImportError:  # pragma: no cover - prometheus_client not installed
        return

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
