"""
Tests for modify.py — YAML structure modification helpers.
"""

import pytest
from yaml_serializer import (
    new_commented_map,
    new_commented_seq,
    add_to_dict,
    add_to_list,
    update_in_dict,
    remove_from_dict,
    remove_from_list,
    get_node_hash,
)


class TestNewCommented:
    """Tests for new node factories."""

    def test_new_commented_map_empty(self):
        """new_commented_map() creates an empty dirty CommentedMap."""
        dct = new_commented_map()
        assert len(dct) == 0
        assert dct._yaml_dirty is True

    def test_new_commented_map_with_initial_data(self):
        """new_commented_map(initial=...) populates the map with the given items."""
        initial = [("key1", "val1"), ("key2", "val2")]
        dct = new_commented_map(initial=initial)
        assert dct["key1"] == "val1"
        assert dct["key2"] == "val2"
        assert dct._yaml_dirty is True

    def test_new_commented_seq_empty(self):
        """new_commented_seq() creates an empty dirty CommentedSeq."""
        seq = new_commented_seq()
        assert len(seq) == 0
        assert seq._yaml_dirty is True

    def test_new_commented_seq_with_initial_data(self):
        """new_commented_seq(initial=...) populates the sequence with the given items."""
        initial = ["item1", "item2", "item3"]
        seq = new_commented_seq(initial=initial)
        assert len(seq) == 3
        assert seq[0] == "item1"
        assert seq._yaml_dirty is True


class TestDictOperations:
    """Tests for dictionary manipulation helpers."""

    def test_add_to_dict_simple_value(self):
        """add_to_dict adds a key-value pair and marks the dict dirty."""
        dct = new_commented_map()
        dct._yaml_dirty = False

        add_to_dict(dct, "key", "value")

        assert dct["key"] == "value"
        assert dct._yaml_dirty is True

    def test_add_to_dict_with_commented_value(self):
        """add_to_dict sets _yaml_parent on a CommentedMap value."""
        parent = new_commented_map()
        child = new_commented_map({"nested": "value"})
        add_to_dict(parent, "child", child)

        assert parent["child"]["nested"] == "value"
        assert hasattr(child, "_yaml_parent")
        assert child._yaml_parent is parent

    def test_add_to_dict_else_branch(self):
        """add_to_dict with a non-CommentedMap/Seq value still marks the dict dirty."""
        from yaml_serializer.modify import add_to_dict, new_commented_map

        dct = new_commented_map()
        dct._yaml_dirty = False
        add_to_dict(dct, "simple", 123)
        assert dct["simple"] == 123
        assert dct._yaml_dirty is True

    def test_update_in_dict_existing_key(self):
        """update_in_dict replaces the value for an existing key."""
        dct = new_commented_map({"key": "old_value"})
        update_in_dict(dct, "key", "new_value")
        assert dct["key"] == "new_value"
        assert dct._yaml_dirty is True

    def test_update_in_dict_new_key(self):
        """update_in_dict adds a new key when the key does not exist yet."""
        dct = new_commented_map({"existing": "value"})
        update_in_dict(dct, "new_key", "new_value")
        assert dct["new_key"] == "new_value"
        assert "existing" in dct

    def test_remove_from_dict_existing_key(self):
        """remove_from_dict removes an existing key and marks the dict dirty."""
        dct = new_commented_map({"key1": "val1", "key2": "val2"})
        remove_from_dict(dct, "key1")
        assert "key1" not in dct
        assert "key2" in dct
        assert dct._yaml_dirty is True

    def test_remove_from_dict_nonexistent_key(self):
        """remove_from_dict is a no-op for a key that does not exist."""
        dct = new_commented_map({"key1": "val1"})
        # Must not raise an exception
        remove_from_dict(dct, "nonexistent")
        assert "key1" in dct


class TestListOperations:
    """Tests for list manipulation helpers."""

    def test_add_to_list_simple_value(self):
        """add_to_list appends a value and marks the list dirty."""
        lst = new_commented_seq()
        lst._yaml_dirty = False

        add_to_list(lst, "item")

        assert len(lst) == 1
        assert lst[0] == "item"
        assert lst._yaml_dirty is True

    def test_add_to_list_with_commented_item(self):
        """add_to_list sets _yaml_parent on a CommentedMap item."""
        lst = new_commented_seq()
        item = new_commented_map({"key": "value"})
        add_to_list(lst, item)

        assert len(lst) == 1
        assert hasattr(item, "_yaml_parent")
        assert item._yaml_parent is lst

    def test_remove_from_list(self):
        """remove_from_list removes the element at the given index."""
        lst = new_commented_seq(["first", "second", "third"])
        remove_from_list(lst, 0)

        assert len(lst) == 2
        assert lst[0] == "second"
        assert lst._yaml_dirty is True


class TestNodeHash:
    """Tests for get_node_hash()."""

    def test_recalculates_when_dirty(self):
        """get_node_hash recomputes the hash and clears the dirty flag."""
        node = new_commented_map({"key": "value"})
        node._yaml_dirty = True

        hash1 = get_node_hash(node)
        assert node._yaml_dirty is False

        # Modify and retrieve the hash again
        node["key"] = "new_value"
        node._yaml_dirty = True
        hash2 = get_node_hash(node)

        assert hash1 != hash2

    def test_returns_cached_hash_for_clean_node(self):
        """get_node_hash returns the cached hash without recomputing for a clean node."""
        node = new_commented_map({"key": "value"})
        hash1 = get_node_hash(node)

        # Second call must return the same hash without recomputing
        node._yaml_dirty = False
        hash2 = get_node_hash(node)

        assert hash1 == hash2


@pytest.mark.parametrize(
    "operation",
    [
        lambda d: add_to_dict(d, "new_key", "new_value"),
        lambda d: update_in_dict(d, "key", "updated"),
        lambda d: add_to_dict(d, "another", 123),
    ],
)
def test_dict_operations_mark_dirty(operation):
    """All dictionary mutation operations must mark the node as dirty."""
    dct = new_commented_map({"key": "value"})
    dct._yaml_dirty = False

    operation(dct)

    assert dct._yaml_dirty is True
