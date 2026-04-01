"""Tests for stable public API declarations and metadata integrity."""

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yaml_serializer import utils

STABLE_UTILS_API = {
    "canonical_repr",
    "compute_hash",
    "resolve_include_path",
    "is_path_within_root",
    "mark_node",
    "mark_dirty",
    "clear_dirty",
    "update_file_attr",
    "replace_included",
    "mark_includes",
}


def test_utils_all_contains_only_stable_api():
    assert set(utils.__all__) == STABLE_UTILS_API


def test_stable_api_functions_are_marked():
    for name in STABLE_UTILS_API:
        assert getattr(getattr(utils, name), "__stable_api__", False) is True


def test_internal_helpers_are_not_exported_and_are_marked():
    for name in (
        "_hash_file_path",
        "_load_hash_from_file",
        "_save_hash_to_file",
        "_update_parent_file_attr",
    ):
        assert name not in utils.__all__
        assert getattr(getattr(utils, name), "__internal_use_only__", False) is True


def test_mark_node_sets_file_parent_hash_and_dirty_flags():
    root = CommentedMap()
    child = CommentedMap()
    items = CommentedSeq()
    items.append(child)
    root["items"] = items

    utils.mark_node(root, "root.yaml")

    assert root._yaml_file == "root.yaml"
    assert items._yaml_file == "root.yaml"
    assert child._yaml_file == "root.yaml"
    assert items._yaml_parent is root
    assert child._yaml_parent is items
    assert root._yaml_dirty is False
    assert items._yaml_dirty is False
    assert child._yaml_dirty is False
    assert isinstance(root._yaml_hash, str)
    assert isinstance(items._yaml_hash, str)
    assert isinstance(child._yaml_hash, str)


def test_mark_dirty_and_clear_dirty_preserve_parent_chain():
    root = CommentedMap()
    child = CommentedMap({"value": 1})
    root["child"] = child
    utils.mark_node(root, "root.yaml")

    child["value"] = 2
    utils.mark_dirty(child)

    assert child._yaml_dirty is True
    assert root._yaml_dirty is True
    assert child._yaml_parent is root

    utils.clear_dirty(root)

    assert root._yaml_dirty is False
    assert child._yaml_dirty is False
    assert child._yaml_parent is root


def test_replace_included_preserves_include_metadata_for_nested_nodes(tmp_path):
    parent_file = tmp_path / "main.yaml"
    old_file = tmp_path / "old.yaml"
    new_file = tmp_path / "renamed" / "new.yaml"
    new_file.parent.mkdir()

    root = CommentedMap()
    included = CommentedMap()
    root["included"] = included
    included._yaml_file = str(old_file)
    included._yaml_parent = root
    included._yaml_parent_file = str(parent_file)
    included._yaml_include_path = "old.yaml"

    changed = utils.replace_included(root, str(old_file), str(new_file))

    assert changed is True
    assert included._yaml_file == str(new_file)
    assert included._yaml_parent is root
    assert included._yaml_parent_file == str(parent_file)
    assert included._yaml_include_path.endswith("new.yaml")
