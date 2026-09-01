"""
Interfaces/Abstractions for dependency injection.

These interfaces decouple services from concrete implementations,
following the Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class Repository(ABC):
    """Base interface for all repositories."""

    @abstractmethod
    async def create(self, data: Any) -> Any:
        """Create a new record."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Any]:
        """Get all records with pagination."""
        ...


class OrderRepository(Repository):
    """Interface for order data access."""

    @abstractmethod
    async def create(self, order_data: Any) -> int:
        """Create a new order and return its ID."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Get all orders with pagination."""
        ...


class NotificationRepository(Repository):
    """Interface for notification data access."""

    @abstractmethod
    async def create(self, notification_data: Any) -> int:
        """Create a new notification and return its ID."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Get all notifications with pagination."""
        ...


class CacheClient(ABC):
    """Interface for cache operations."""

    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """Set a cache value with TTL."""
        ...

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """Get a cache value."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a cache value."""
        ...

    @abstractmethod
    def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a pattern."""
        ...


class EventPublisher(ABC):
    """Interface for event publishing."""

    @abstractmethod
    async def publish(self, topic: str, event: dict) -> None:
        """Publish an event to a topic/queue."""
        ...


class MetricsClient(ABC):
    """Interface for metrics collection."""

    @abstractmethod
    def create_counter(self, name: str, description: str, unit: str = "1") -> Any:
        """Create a counter metric."""
        ...

    @abstractmethod
    def create_histogram(self, name: str, description: str, unit: str = "s") -> Any:
        """Create a histogram metric."""
        ...


class Logger(ABC):
    """Interface for structured logging."""

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        ...

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        ...


class HealthChecker(ABC):
    """Interface for health checking."""

    @abstractmethod
    async def check(self) -> Dict[str, bool]:
        """Check health of dependencies."""
        ...
