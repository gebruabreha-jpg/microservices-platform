"""Observability: structured logging, OTel metrics, OTel tracing."""

from dataclasses import dataclass
from typing import Any

from shared.observability.logging import StructuredLogger, get_logger
from shared.observability.metrics import get_metric, setup_metrics_endpoint
from shared.observability.tracing import (
    flush_telemetry,
    get_tracer,
    setup_tracing,
)

__all__ = [
    "StructuredLogger",
    "get_logger",
    "get_metric",
    "setup_metrics_endpoint",
    "get_tracer",
    "setup_tracing",
    "flush_telemetry",
    "ServiceTelemetry",
    "get_service_telemetry",
]


@dataclass(frozen=True)
class ServiceTelemetry:
    """Logger + tracer + standard request counter/histogram for one service.

    Every service class built this same bundle by hand in its constructor
    (get_logger + get_tracer + create_counter + create_histogram). Bundling it
    here means the `{prefix}_requests_total` / `{prefix}_request_duration_seconds`
    naming convention is defined once instead of copy-pasted three times.
    """

    logger: StructuredLogger
    tracer: Any
    request_counter: Any
    request_duration: Any


def get_service_telemetry(service_name: str, metric_prefix: str, noun: str) -> ServiceTelemetry:
    """Build the standard logger/tracer/request-metrics bundle for a service.

    ``service_name`` names the logger/tracer (e.g. "order-service").
    ``metric_prefix`` names the metrics per the service-specific-metric-names
    rule (e.g. "order" -> order_requests_total, order_request_duration_seconds).
    ``noun`` is used in the metric descriptions (e.g. "order").
    """
    metrics = get_metric()
    return ServiceTelemetry(
        logger=get_logger(service_name),
        tracer=get_tracer(service_name),
        request_counter=metrics.create_counter(
            f"{metric_prefix}_requests_total",
            description=f"Total {noun} requests",
            unit="1",
        ),
        request_duration=metrics.create_histogram(
            f"{metric_prefix}_request_duration_seconds",
            description=f"{noun} request duration in seconds",
            unit="s",
        ),
    )
