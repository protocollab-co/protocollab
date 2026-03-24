"""Tests for protocollab.loader.cache — MemoryCache and BaseCache contract."""

import pytest
from protocollab.loader.cache.memory_cache import MemoryCache


@pytest.fixture()
def cache():
    return MemoryCache()


class TestMemoryCache:
    def test_get_on_empty_returns_none(self, cache):
        assert cache.get("any_key") is None

    def test_set_and_get_round_trip(self, cache):
        value = {"version": "1.0"}
        cache.set("key1", value)
        assert cache.get("key1") == value

    def test_get_unknown_key_returns_none(self, cache):
        cache.set("key1", {"a": 1})
        assert cache.get("unknown") is None

    def test_set_overwrites_existing(self, cache):
        cache.set("k", {"v": 1})
        cache.set("k", {"v": 2})
        assert cache.get("k") == {"v": 2}

    def test_clear_removes_all_entries(self, cache):
        cache.set("k1", {"a": 1})
        cache.set("k2", {"b": 2})
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None
        assert len(cache) == 0

    def test_len_reflects_entry_count(self, cache):
        assert len(cache) == 0
        cache.set("k1", {})
        assert len(cache) == 1
        cache.set("k2", {})
        assert len(cache) == 2

    def test_clear_on_empty_is_safe(self, cache):
        cache.clear()  # must not raise
        assert len(cache) == 0

    def test_multiple_independent_caches(self):
        c1, c2 = MemoryCache(), MemoryCache()
        c1.set("k", {"source": "c1"})
        assert c2.get("k") is None  # isolated


class TestMemoryCacheLRU:
    """MemoryCache LRU eviction behaviour when max_size is set."""

    def test_max_size_none_is_unbounded(self):
        cache = MemoryCache(max_size=None)
        for i in range(100):
            cache.set(f"k{i}", {"v": i})
        assert len(cache) == 100

    def test_max_size_limits_entry_count(self):
        cache = MemoryCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a" (LRU)
        assert len(cache) == 3
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_get_updates_recency(self):
        cache = MemoryCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # "a" is now MRU; "b" becomes LRU
        cache.set("d", 4)  # "b" should be evicted
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_set_update_moves_entry_to_mru(self):
        cache = MemoryCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("a", 99)  # update "a" → it becomes MRU
        cache.set("d", 4)  # "b" should be evicted (LRU)
        assert cache.get("b") is None
        assert cache.get("a") == 99

    def test_max_size_one_keeps_only_latest(self):
        cache = MemoryCache(max_size=1)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert len(cache) == 1

    def test_max_size_zero_raises_value_error(self):
        with pytest.raises(ValueError):
            MemoryCache(max_size=0)

    def test_max_size_negative_raises_value_error(self):
        with pytest.raises(ValueError):
            MemoryCache(max_size=-5)

    def test_clear_resets_lru_state(self):
        cache = MemoryCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0
        cache.set("c", 3)  # must not raise after clear
        assert cache.get("c") == 3
