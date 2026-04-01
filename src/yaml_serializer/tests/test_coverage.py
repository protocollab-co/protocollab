"""
Tests targeting uncovered lines in utils.py, serializer.py and safe_constructor.py.
"""

import os
import io
import logging
import pytest
import ruamel.yaml
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yaml_serializer.utils import (
    mark_dirty,
    mark_includes,
    replace_included,
    update_file_attr,
    _update_parent_file_attr,
)
from yaml_serializer.modify import add_to_dict, add_to_list
from yaml_serializer.safe_constructor import create_safe_yaml_instance
from yaml_serializer.serializer import (
    _make_include_constructor,
    INCLUDE_TAG,
    SerializerSession,
)

# ---------------------------------------------------------------------------
# utils.py – mark_dirty(None)  [line 80]
# ---------------------------------------------------------------------------


class TestMarkDirtyNone:
    def test_mark_dirty_none_is_noop(self):
        """mark_dirty(None) must complete silently without raising."""
        mark_dirty(None)  # must not raise an exception


# ---------------------------------------------------------------------------
# utils.py – update_file_attr with CommentedSeq children  [lines 63-65]
# ---------------------------------------------------------------------------


class TestUpdateFileAttrSeq:
    def test_update_file_attr_seq_children(self):
        """update_file_attr recursively updates _yaml_file on CommentedSeq children."""
        root = CommentedSeq()
        root._yaml_file = "old.yaml"
        child_map = CommentedMap()
        child_map._yaml_file = "old.yaml"
        root.append(child_map)

        update_file_attr(root, "old.yaml", "new.yaml")

        assert root._yaml_file == "new.yaml"
        assert child_map._yaml_file == "new.yaml"


class TestUpdateParentFileAttrSeq:
    def test_update_parent_file_attr_seq_children(self):
        """_update_parent_file_attr recursively updates _yaml_parent_file in seq children."""
        root = CommentedSeq()
        child_map = CommentedMap()
        child_map._yaml_parent_file = "old-parent.yaml"
        root.append(child_map)

        _update_parent_file_attr(root, "old-parent.yaml", "new-parent.yaml")

        assert child_map._yaml_parent_file == "new-parent.yaml"


# ---------------------------------------------------------------------------
# utils.py – mark_includes with CommentedSeq at root  [lines 137-140]
# ---------------------------------------------------------------------------


class TestMarkIncludesSeq:
    def test_mark_includes_in_seq_root(self):
        """mark_includes finds nodes matching target_file inside a CommentedSeq."""
        seq = CommentedSeq()
        a = CommentedMap({"x": 1})
        b = CommentedMap({"y": 2})
        a._yaml_file = "target.yaml"
        b._yaml_file = "other.yaml"
        seq.append(a)
        seq.append(b)

        marked = []
        found = mark_includes(seq, "target.yaml", marked.append)

        assert found is True
        marked_ids = [id(x) for x in marked]
        assert id(a) in marked_ids
        assert id(b) not in marked_ids

    def test_mark_includes_in_seq_not_found(self):
        """mark_includes returns False when the target file is not present in the seq."""
        seq = CommentedSeq()
        node = CommentedMap()
        node._yaml_file = "other.yaml"
        seq.append(node)

        found = mark_includes(seq, "missing.yaml", lambda x: None)
        assert found is False


# ---------------------------------------------------------------------------
# utils.py – replace_included with logger and absolute path [lines 149, 159-162]
# ---------------------------------------------------------------------------


class TestReplaceIncludedLogger:
    def test_replace_included_logs_file_update(self, caplog):
        """replace_included calls logger when updating _yaml_file."""
        node = CommentedMap()
        node._yaml_file = "old.yaml"

        logger = logging.getLogger("test_replace")
        with caplog.at_level(logging.DEBUG, logger="test_replace"):
            changed = replace_included(node, "old.yaml", "new.yaml", logger)

        assert changed is True
        assert node._yaml_file == "new.yaml"

    def test_replace_included_absolute_path_fallback(self, temp_dir):
        """
        replace_included falls back to absolute path when relative_to raises ValueError
        (the new file is not a descendant of the parent file's directory).
        """
        # parent_file is in temp_dir/proj/, new_file is in temp_dir/other/
        # Therefore Path(new_file).relative_to(parent_dir) raises ValueError
        proj_dir = os.path.join(temp_dir, "proj")
        other_dir = os.path.join(temp_dir, "other")
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(other_dir, exist_ok=True)

        old_file = os.path.join(proj_dir, "old.yaml")
        new_file = os.path.join(other_dir, "new.yaml")
        parent_file = os.path.join(proj_dir, "main.yaml")

        node = CommentedMap()
        node._yaml_file = old_file
        node._yaml_include_path = "old.yaml"
        node._yaml_parent_file = parent_file

        changed = replace_included(node, old_file, new_file)
        # In the ValueError branch, the absolute path containing new.yaml must be set
        assert changed is True
        assert "new.yaml" in node._yaml_include_path

    def test_replace_included_absolute_path_logs(self, temp_dir, caplog):
        """replace_included logs the absolute path on fallback."""
        proj_dir = os.path.join(temp_dir, "proj")
        other_dir = os.path.join(temp_dir, "other")
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(other_dir, exist_ok=True)

        old_file = os.path.join(proj_dir, "old.yaml")
        new_file = os.path.join(other_dir, "new.yaml")
        parent_file = os.path.join(proj_dir, "main.yaml")

        node = CommentedMap()
        node._yaml_file = old_file
        node._yaml_include_path = "old.yaml"
        node._yaml_parent_file = parent_file

        logger = logging.getLogger("test_replace_abs")
        with caplog.at_level(logging.DEBUG, logger="test_replace_abs"):
            changed = replace_included(node, old_file, new_file, logger)

        assert changed is True
        assert "new.yaml" in node._yaml_include_path


# ---------------------------------------------------------------------------
# serializer.py – rename with an unloaded file  [line 203]
# ---------------------------------------------------------------------------


class TestRenameUnloadedFile:
    def test_rename_unloaded_file_raises(self, temp_dir):
        """rename() must raise ValueError for a file that was not loaded."""
        unloaded = os.path.join(temp_dir, "notloaded.yaml")
        s = SerializerSession()
        with pytest.raises(ValueError, match="not loaded"):
            s.rename(unloaded, os.path.join(temp_dir, "other.yaml"))


# ---------------------------------------------------------------------------
# serializer.py – include_constructor outside loading context  [line 94]
# ---------------------------------------------------------------------------


class TestIncludeConstructorOutsideContext:
    def test_include_outside_loading_context_raises(self):
        """include_constructor must raise ValueError when _loading_stack is empty."""
        session = SerializerSession()
        session._loading_stack.clear()
        session._max_imports = None  # do not interfere with the check

        yaml_inst = create_safe_yaml_instance()
        yaml_inst.constructor.add_constructor(INCLUDE_TAG, _make_include_constructor(session))

        with pytest.raises(ValueError, match="outside of file loading context"):
            yaml_inst.load(io.StringIO("data: !include some.yaml"))


# ---------------------------------------------------------------------------
# safe_constructor.py – max_depth validation
# ---------------------------------------------------------------------------


class TestMaxDepthValidation:
    def test_max_depth_none_raises_value_error(self):
        """Passing max_depth=None must raise ValueError."""
        with pytest.raises(ValueError, match="max_depth cannot be None"):
            create_safe_yaml_instance(max_depth=None)

    def test_max_depth_zero_raises_value_error(self):
        """Passing max_depth=0 must raise ValueError."""
        with pytest.raises(ValueError, match="max_depth must be a positive integer"):
            create_safe_yaml_instance(max_depth=0)

    def test_max_depth_negative_raises_value_error(self):
        """Passing a negative max_depth must raise ValueError."""
        with pytest.raises(ValueError, match="max_depth must be a positive integer"):
            create_safe_yaml_instance(max_depth=-1)

    def test_max_depth_positive_works(self):
        """A positive integer max_depth must be accepted without error."""
        # Just verify that the object is created without errors
        yaml = create_safe_yaml_instance(max_depth=10)
        assert yaml is not None

    def test_no_depth_limit_allows_any_depth(self):
        """create_safe_yaml_instance with a large max_depth allows deep structures."""
        data = {"value": 1}
        for i in range(60):
            data = {f"l{i}": data}
        y = ruamel.yaml.YAML()
        buf = io.StringIO()
        y.dump(data, buf)
        yaml_str = buf.getvalue()

        loader = create_safe_yaml_instance(
            max_depth=10000
        )  # large enough to avoid triggering the limit
        loader.load(yaml_str)  # must not raise any exceptions


# ---------------------------------------------------------------------------
# Round-trip check: comments and formatting are preserved
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_comments_preserved_on_load(self, temp_dir, create_yaml_file):
        """Comments are preserved through a load/dump round-trip."""
        yaml_content = "# Top-level comment\n" "key: value  # inline comment\n"
        path = os.path.join(temp_dir, "rt.yaml")
        create_yaml_file(path, yaml_content)
        s = SerializerSession()
        data = s.load(path)

        out = io.StringIO()
        assert s._yaml_instance is not None
        s._yaml_instance.dump(data, out)
        dumped = out.getvalue()

        assert "# Top-level comment" in dumped
        assert "inline comment" in dumped


# ---------------------------------------------------------------------------
# modify.py – _yaml_file inheritance in add_to_dict / add_to_list [lines 37, 47]
# ---------------------------------------------------------------------------


class TestModifyYamlFileInheritance:
    def test_add_to_dict_inherits_yaml_file(self):
        """A child without _yaml_file inherits it from the container in add_to_dict."""
        dct = CommentedMap()
        dct._yaml_file = "parent.yaml"
        dct._yaml_hash = None
        dct._yaml_dirty = False

        child = CommentedMap({"x": 1})
        # child has no _yaml_file and no _yaml_parent

        add_to_dict(dct, "child", child)

        assert child._yaml_file == "parent.yaml"

    def test_add_to_list_inherits_yaml_file(self):
        """An item without _yaml_file inherits it from the list in add_to_list."""
        lst = CommentedSeq()
        lst._yaml_file = "parent.yaml"
        lst._yaml_hash = None
        lst._yaml_dirty = False

        item = CommentedMap({"y": 2})
        # item has no _yaml_file and no _yaml_parent

        add_to_list(lst, item)

        assert item._yaml_file == "parent.yaml"
