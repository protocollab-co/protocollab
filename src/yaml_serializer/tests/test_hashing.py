"""
Tests for canonical representation and hashing utilities.
"""

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from yaml_serializer.utils import canonical_repr, compute_hash


class TestCanonicalRepr:
    """Tests for canonical_repr()."""

    def test_primitive_types(self):
        """canonical_repr must pass through primitive Python types unchanged."""
        assert canonical_repr(42) == 42
        assert canonical_repr("string") == "string"
        assert canonical_repr(None) is None
        assert canonical_repr(True) is True

    def test_nested_structures(self):
        """canonical_repr converts nested CommentedMap/Seq to plain dicts/lists."""
        data = CommentedMap()
        data["level1"] = CommentedMap()
        data["level1"]["level2"] = CommentedSeq(["a", "b"])

        canonical = canonical_repr(data)
        assert isinstance(canonical, dict)
        assert isinstance(canonical["level1"], dict)
        assert canonical["level1"]["level2"] == ["a", "b"]

    def test_sorts_dict_keys(self):
        """canonical_repr must sort dictionary keys for determinism."""
        data = CommentedMap()
        data["z"] = 1
        data["a"] = 2
        data["m"] = 3

        canonical = canonical_repr(data)
        assert isinstance(canonical, dict)
        keys = list(canonical.keys())
        assert keys == ["a", "m", "z"]


class TestComputeHash:
    """Tests for compute_hash()."""

    def test_consistency(self):
        """Identical structures must produce the same hash."""
        data1 = CommentedMap()
        data1["key"] = "value"

        data2 = CommentedMap()
        data2["key"] = "value"

        hash1 = compute_hash(data1)
        hash2 = compute_hash(data2)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 returns 64 hex characters

    def test_different_for_different_data(self):
        """Different structures must produce different hashes."""
        data1 = CommentedMap({"key": "value1"})
        data2 = CommentedMap({"key": "value2"})

        hash1 = compute_hash(data1)
        hash2 = compute_hash(data2)

        assert hash1 != hash2

    def test_order_independence(self):
        """Hash must not depend on the order in which keys were inserted."""
        data1 = CommentedMap()
        data1["b"] = 2
        data1["a"] = 1

        data2 = CommentedMap()
        data2["a"] = 1
        data2["b"] = 2

        assert compute_hash(data1) == compute_hash(data2)
