"""
Shared metrics module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

Metrics are exported via OTLP gRPC to the OTel Collector, which forwards them
to Prometheus. The same code runs unchanged in Docker Compose and Kubernetes.
Only the OTLP endpoint changes via env vars.

Why OTLP for metrics:
  - Metrics need aggregation, histograms, and background-thread reporting
  - OTel Collector handles batching, retry, and backend routing
"""

import os
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from shared.tracing import _resource


# =============================================================================
# METRICS: OTLP metrics -> Prometheus (via OTel Collector)
# =============================================================================
#Exports metrics every 15s via OTLP gRPC
_metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://otel-collector:4317")),
    export_interval_millis=15000,  # export every 15s
)

#Creates meters with service resource attributes
_metric_provider = MetricProvider(resource=_resource, metric_readers=[_metric_reader])


#Returns a Meter to create counters/histograms
def get_metric():
    """
    Get the OTLP metrics meter.

    Use this to create counters, histograms, gauges.
    Metrics are exported to Prometheus via OTel Collector every 15s.
    """
    return _meter_provider.get_meter(__name__)
