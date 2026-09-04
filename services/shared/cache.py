"""Cache: interface + Redis implementation."""

from abc import ABC, abstractmethod
from typing import Optional

import redis


class CacheClient(ABC):
    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        ...

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def delete_pattern(self, pattern: str) -> None:
        ...


class RedisCacheClient(CacheClient):
    """Redis implementation of CacheClient.

    The cache is treated as strictly optional: if Redis was unavailable at
    startup (``redis_client`` is None) or a call fails, every read is a miss and
    every write is dropped - the service keeps serving from the database instead
    of 500-ing. ``client_factory`` lets a client that could not be built at
    startup be created lazily on a later call.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None, client_factory=None):
        self._redis = redis_client
        self._client_factory = client_factory
        self._warned = False

    def _client(self) -> Optional[redis.Redis]:
        if self._redis is None and self._client_factory is not None:
            self._redis = self._client_factory()
        return self._redis

    def _degrade(self, exc: Exception) -> None:
        if not self._warned:
            self._warned = True
            from shared.observability import get_logger

            get_logger("shared.cache").warning("Redis unavailable, running without cache", error=str(exc))

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        client = self._client()
        if client is None:
            return
        try:
            client.set(key, value, ex=ttl)
        except Exception as e:  # noqa: BLE001 - cache failures must not break the request
            self._redis = None
            self._degrade(e)

    def get(self, key: str) -> Optional[str]:
        client = self._client()
        if client is None:
            return None
        try:
            return client.get(key)
        except Exception as e:  # noqa: BLE001
            self._redis = None
            self._degrade(e)
            return None

    def delete(self, key: str) -> None:
        client = self._client()
        if client is None:
            return
        try:
            client.delete(key)
        except Exception as e:  # noqa: BLE001
            self._redis = None
            self._degrade(e)

    def delete_pattern(self, pattern: str) -> None:
        client = self._client()
        if client is None:
            return
        try:
            for key in client.scan_iter(match=pattern, count=100):
                client.delete(key)
        except Exception as e:  # noqa: BLE001
            self._redis = None
            self._degrade(e)
