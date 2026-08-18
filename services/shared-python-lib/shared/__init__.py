from shared.config import load_env, get_env
from shared.logger import get_logger, log_event
from shared.models import Order, Payment, InventoryItem

try:
    from shared.circuit_breaker import redis_breaker, kafka_breaker, rabbitmq_breaker, postgres_breaker
except ImportError:
    redis_breaker = None
    kafka_breaker = None
    rabbitmq_breaker = None
    postgres_breaker = None