"""
Shared metrics module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

Every service records metrics through an OpenTelemetry meter. Those metrics are
exported two ways from the same MeterProvider:

  - OTLP gRPC -> OTel Collector (for pipelines that aggregate centrally)
  - Prometheus text format on GET /metrics (for direct scraping by Prometheus)

The Prometheus reader registers instruments into the default ``prometheus_client``
registry, so ``generate_latest()`` returns the real application counters and
histograms, not just process stats.
"""

import os

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from shared.tracing import _resource

# Push metrics to the OTel Collector every 15s.
_readers = [
    PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://otel-collector:4317")
        ),
        export_interval_millis=15000,
    )
]

# Expose the same metrics in Prometheus text format for GET /metrics scraping.
try:
    from opentelemetry.exporter.prometheus import PrometheusMetricReader

    _readers.append(PrometheusMetricReader())
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - exporter not installed
    _PROMETHEUS_AVAILABLE = False

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
