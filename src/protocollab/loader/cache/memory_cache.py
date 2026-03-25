"""In-process LRU memory cache for loaded protocol data."""

from collections import OrderedDict
from typing import Optional
from protocollab.types import ProtocolData
from protocollab.loader.cache.base_cache import BaseCache


class MemoryCache(BaseCache):
    """LRU cache backed by an :class:`~collections.OrderedDict`.

    Parameters
    ----------
    max_size:
        Maximum number of entries to keep.  When the limit is reached the
        *least recently used* entry is evicted automatically on the next
        :meth:`set` call.  ``None`` (default) means the cache is unbounded.

    Notes
    -----
    This class is **not thread-safe**.  For concurrent use, create separate
    :class:`~protocollab.loader.base_loader.ProtocolLoader` instances, each
    with its own ``MemoryCache``.
    """

    def __init__(self, max_size: Optional[int] = None) -> None:
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be a positive integer or None")
        self._max_size = max_size
        self._store: OrderedDict[str, ProtocolData] = OrderedDict()

    def get(self, key: str) -> Optional[ProtocolData]:
        """Return cached value for *key*, promoting it to most-recently-used.

        Returns ``None`` if *key* is not in the cache.
        """
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def set(self, key: str, value: ProtocolData) -> None:
        """Store *value* under *key*, evicting the LRU entry if needed."""
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = value
        else:
            if self._max_size is not None and len(self._store) >= self._max_size:
                self._store.popitem(last=False)  # evict least-recently-used
            self._store[key] = value

    def clear(self) -> None:
        """Evict all cached entries."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
