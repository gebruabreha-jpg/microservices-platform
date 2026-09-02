"""
Shared library, organised by concern. Each module carries its interface and its
implementation(s) together:

    cache.py          CacheClient           + RedisCacheClient
    events.py         EventPublisher        + Kafka/RabbitMQ publishers
    health.py         HealthChecker         + Database/RabbitMQ checkers
    repository.py     Repository ABCs       (impls live in each service)
    factories.py      create_db_pool / create_redis_client / ... / circuit breakers
    outbox.py         enqueue_event + OutboxPoller
    config.py         require_env / get_env
    ratelimit.py      setup_rate_limiting
    observability/    logging, metrics, tracing

Import from the specific module (``from shared.cache import RedisCacheClient``),
not from this package root.
"""
