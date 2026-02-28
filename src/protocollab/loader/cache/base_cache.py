"""Base class for protocol data caches."""

from abc import ABC, abstractmethod
from typing import Optional
from protocollab.types import ProtocolData


class BaseCache(ABC):
    """Abstract base for caching loaded protocol data."""

    @abstractmethod
    def get(self, key: str) -> Optional[ProtocolData]:
        """Return cached data for *key*, or None if not cached."""

    @abstractmethod
    def set(self, key: str, value: ProtocolData) -> None:
        """Store *value* under *key*."""

    @abstractmethod
    def clear(self) -> None:
        """Evict all cached entries."""
