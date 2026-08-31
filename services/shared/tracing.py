"""
Shared tracing module.

ONE CONFIG FOR BOTH DOCKER COMPOSE AND KUBERNETES:

Traces are exported via OTLP gRPC to the OTel Collector, which forwards them
to Tempo. The same code runs unchanged in Docker Compose and Kubernetes.
Only the OTLP endpoint changes via env vars.
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


# =============================================================================
# RESOURCE: Service identity attached to all telemetry
# =============================================================================
_resource = Resource.create({
    "service.name": os.getenv("SERVICE_NAME", "unknown-service"),
    "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
    "deployment.environment": os.getenv("ENVIRONMENT", "development"),
})


# =============================================================================
# TRACING: OTLP traces -> Tempo
# =============================================================================
_trace_provider = TracerProvider(resource=_resource)
_trace_provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"))
))
trace.set_tracer_provider(_trace_provider)


def setup_tracing(app, service_name: str):
    """
    Initialize tracing for a FastAPI service.

    Enables:
    - Automatic HTTP request/response span creation
    - Resource attributes (service.name, version, environment)
    """
    tracer = trace.get_tracer(service_name)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_trace_provider,
    )
    return tracer


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


def flush_telemetry(timeout_millis=5000):
    """Flush all telemetry exporters before shutdown."""
    try:
        from opentelemetry.sdk.trace import get_tracer_provider
        get_tracer_provider().force_flush(timeout_millis=timeout_millis)
    except Exception as e:
        import logging
        logging.error(f"Error flushing telemetry: {e}")
