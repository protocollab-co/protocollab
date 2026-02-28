"""In-process memory cache for loaded protocol data."""

from typing import Optional
from protocollab.types import ProtocolData
from protocollab.loader.cache.base_cache import BaseCache


class MemoryCache(BaseCache):
    """Simple dict-backed cache scoped to a single process / CLI invocation."""

    def __init__(self) -> None:
        self._store: dict[str, ProtocolData] = {}

    def get(self, key: str) -> Optional[ProtocolData]:
        return self._store.get(key)

    def set(self, key: str, value: ProtocolData) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
