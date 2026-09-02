"""
Repository interfaces (ABCs). Concrete implementations live in each service's
``app/repository/`` and use raw psycopg2.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

# (new_id) -> (topic, payload): builds an outbox event once the row id is known.
OutboxEvent = Callable[[int], Tuple[str, dict]]


class Repository(ABC):
    """Base interface for all repositories (order, payment, notification)."""

    @abstractmethod
    async def create(self, data: Any) -> Any:
        """Create a new record."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Any]:
        """Get records with pagination."""
        ...


class OrderRepository(Repository):
    @abstractmethod
    async def create(self, order_data: Any, outbox_event: Optional[OutboxEvent] = None) -> int:
        """Create an order and return its id, optionally enqueuing an outbox event."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        ...

    @abstractmethod
    async def get_by_id(self, order_id: int) -> Optional[Dict]:
        ...


class NotificationRepository(Repository):
    @abstractmethod
    async def create(self, notification_data: Any) -> int:
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        ...


class PaymentRepository(Repository):
    @abstractmethod
    async def create(self, payment_data: Any, outbox_event: Optional[OutboxEvent] = None) -> int:
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        ...

    @abstractmethod
    async def get_by_order_id(self, order_id: int) -> Optional[Dict]:
        """Get payment by order id (for idempotency checks)."""
        ...
