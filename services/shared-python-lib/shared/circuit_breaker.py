import pybreaker

redis_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="redis",
)

kafka_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="kafka",
)

rabbitmq_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="rabbitmq",
)

postgres_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="postgres",
)
