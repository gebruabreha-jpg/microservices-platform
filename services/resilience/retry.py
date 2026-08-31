"""
Shared resilience patterns.

Resilience patterns help services handle failures gracefully:
- Circuit Breaker: prevent cascading failures by stopping calls to failing services
- Retry: automatically retry failed operations with backoff
- Timeout: fail fast if a dependency is too slow

These patterns are defined in shared/resilience/ so all services use
consistent configuration.
"""

from tenacity import retry, stop_after_attempt, wait_exponential


RETRY_CONFIG = {
    "max_attempts": 3,
    "multiplier": 1,
    "min_wait": 1,
    "max_wait": 10,
}


def default_retry(func):
    """
    Default retry decorator: 3 attempts with exponential backoff.

    Usage:
        @default_retry
        def call_external_service():
            ...
    """
    return retry(
        stop=stop_after_attempt(RETRY_CONFIG["max_attempts"]),
        wait=wait_exponential(
            multiplier=RETRY_CONFIG["multiplier"],
            min=RETRY_CONFIG["min_wait"],
            max=RETRY_CONFIG["max_wait"],
        ),
        reraise=True,
    )(func)
