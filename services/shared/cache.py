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
    """Redis implementation of CacheClient."""

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        self._redis.set(key, value, ex=ttl)

    def get(self, key: str) -> Optional[str]:
        return self._redis.get(key)

    def delete(self, key: str) -> None:
        self._redis.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        for key in self._redis.scan_iter(match=pattern, count=100):
            self._redis.delete(key)
