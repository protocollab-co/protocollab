"""
Tests for SerializerSession — the new explicit-session API.

Key goals:
- Verify full isolation between independent sessions.
- Validate constructor config defaults and per-load overrides.
- Cover all public methods: load(), save(), rename(), propagate_dirty(), clear().
"""

import os
import pytest
from pathlib import Path

from yaml_serializer.serializer import SerializerSession
from yaml_serializer.modify import add_to_dict

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir(tmp_path):
    return str(tmp_path)


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------


class TestSerializerSessionConstruction:
    def test_default_config(self):
        s = SerializerSession()
        assert s.max_file_size == 10 * 1024 * 1024
        assert s.max_include_depth == 50
        assert s.max_struct_depth == 50
        assert s.max_imports == 100

    def test_custom_config(self):
        s = SerializerSession({"max_file_size": 1024, "max_include_depth": 5, "max_imports": 10})
        assert s.max_file_size == 1024
        assert s.max_include_depth == 5
        assert s.max_imports == 10

    def test_initial_state_is_empty(self):
        s = SerializerSession()
        assert s._file_roots == {}
        assert s._loaded_hashes == {}
        assert s._yaml_instance is None
        assert s._root_filename is None


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestSerializerSessionLoad:
    def test_load_simple_file(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "key: value\n")
        s = SerializerSession()
        data = s.load(path)
        assert data["key"] == "value"
        assert hasattr(data, "_yaml_file")
        assert hasattr(data, "_yaml_hash")

    def test_load_populates_file_roots(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "a: 1\n")
        s = SerializerSession()
        s.load(path)
        assert str(Path(path).resolve()) in s._file_roots

    def test_load_config_override(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "a: 1\n")
        s = SerializerSession({"max_file_size": 10 * 1024 * 1024})
        s.load(path, config={"max_file_size": 512})
        assert s._max_file_size == 512

    def test_load_nonexistent_raises(self, temp_dir):
        s = SerializerSession()
        with pytest.raises(FileNotFoundError):
            s.load(os.path.join(temp_dir, "no_such.yaml"))

    def test_load_with_include(self, temp_dir):
        write(os.path.join(temp_dir, "child.yaml"), "x: 42\n")
        write(os.path.join(temp_dir, "main.yaml"), "child: !include child.yaml\n")
        s = SerializerSession()
        data = s.load(os.path.join(temp_dir, "main.yaml"))
        assert data["child"]["x"] == 42
        assert len(s._file_roots) == 2

    def test_repeated_include_reuses_same_root(self, temp_dir):
        child = os.path.join(temp_dir, "child.yaml")
        main = os.path.join(temp_dir, "main.yaml")
        write(child, "x: 42\n")
        write(main, "left: !include child.yaml\nright: !include child.yaml\n")

        s = SerializerSession()
        data = s.load(main)

        assert data["left"] is data["right"]
        assert len(s._file_roots) == 2

        add_to_dict(data["left"], "extra", "shared")
        s.save(only_if_changed=False)

        child_text = Path(child).read_text(encoding="utf-8")
        assert "extra: shared" in child_text

    def test_reload_clears_previous_state(self, temp_dir):
        path1 = os.path.join(temp_dir, "a.yaml")
        path2 = os.path.join(temp_dir, "b.yaml")
        write(path1, "v: 1\n")
        write(path2, "v: 2\n")
        s = SerializerSession()
        s.load(path1)
        assert len(s._file_roots) == 1
        s.load(path2)
        assert len(s._file_roots) == 1
        assert str(Path(path2).resolve()) in s._file_roots

    def test_load_failure_leaves_session_clean(self, temp_dir):
        """If load raises, session state must be fully reset (not half-populated)."""
        good = os.path.join(temp_dir, "good.yaml")
        bad = os.path.join(temp_dir, "bad.yaml")
        write(good, "ok: 1\n")
        write(bad, "invalid: [\n")  # malformed YAML
        s = SerializerSession()
        s.load(good)
        assert len(s._file_roots) == 1

        with pytest.raises(Exception):
            s.load(bad)

        # Session must be clean — no partial state from the failed load
        assert s._file_roots == {}
        assert s._loaded_hashes == {}
        assert s._loading_stack == []
        assert s._yaml_instance is None


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------


class TestSerializerSessionIsolation:
    def test_two_sessions_independent(self, temp_dir):
        """Loading into session A must not affect session B."""
        path_a = os.path.join(temp_dir, "a.yaml")
        path_b = os.path.join(temp_dir, "b.yaml")
        write(path_a, "label: alpha\n")
        write(path_b, "label: beta\n")

        sa = SerializerSession()
        sb = SerializerSession()
        da = sa.load(path_a)
        db = sb.load(path_b)

        assert da["label"] == "alpha"
        assert db["label"] == "beta"
        assert str(Path(path_a).resolve()) not in sb._file_roots
        assert str(Path(path_b).resolve()) not in sa._file_roots

    def test_modifying_one_session_does_not_affect_other(self, temp_dir):
        path = os.path.join(temp_dir, "shared.yaml")
        write(path, "count: 0\n")

        sa = SerializerSession()
        sb = SerializerSession()
        da = sa.load(path)
        sb.load(path)

        add_to_dict(da, "extra", "only_in_a")

        # sb's view is from its own load — no 'extra' key
        abs_path = str(Path(path).resolve())
        db = sb._file_roots[abs_path]
        assert "extra" not in db

    def test_concurrent_loads_same_file(self, temp_dir):
        """Both sessions can load the same file without interference."""
        path = os.path.join(temp_dir, "shared.yaml")
        write(path, "val: 1\n")
        sa = SerializerSession()
        sb = SerializerSession()
        da = sa.load(path)
        db = sb.load(path)
        assert da["val"] == db["val"] == 1
        # They are distinct objects
        assert da is not db

    def test_sessions_independent_configs(self, temp_dir):
        """Security configs are per-session and don't leak."""
        # Create structure deep enough to trigger the small-limit session
        content = "a:\n  b:\n    c:\n      d:\n        e: deep\n"
        path = os.path.join(temp_dir, "deep.yaml")
        write(path, content)

        s_strict = SerializerSession({"max_struct_depth": 3})
        s_lenient = SerializerSession({"max_struct_depth": 20})

        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            s_strict.load(path)

        data = s_lenient.load(path)
        assert data["a"]["b"]["c"]["d"]["e"] == "deep"


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


class TestSerializerSessionSave:
    def test_save_without_load_raises(self):
        s = SerializerSession()
        with pytest.raises(RuntimeError, match="No YAML loaded"):
            s.save()

    def test_save_unchanged_does_not_touch_file(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "key: value\n")
        s = SerializerSession()
        s.load(path)
        s.save()  # first save writes hash file
        with open(path, "r", encoding="utf-8") as f:
            content_before = f.read()
        s.save(only_if_changed=True)
        with open(path, "r", encoding="utf-8") as f:
            content_after = f.read()
        assert content_after == content_before

    def test_save_modified_writes_file(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "data: {}\n")
        s = SerializerSession()
        data = s.load(path)
        s.save()  # write initial hash
        add_to_dict(data["data"], "new_key", "new_value")
        s.save(only_if_changed=True)
        with open(path, "r", encoding="utf-8") as f:
            saved_content = f.read()
        assert "new_key" in saved_content
        assert "new_value" in saved_content


# ---------------------------------------------------------------------------
# rename()
# ---------------------------------------------------------------------------


class TestSerializerSessionRename:
    def test_rename_updates_file_roots(self, temp_dir):
        old = os.path.join(temp_dir, "old.yaml")
        new = os.path.join(temp_dir, "new.yaml")
        write(old, "v: 1\n")
        s = SerializerSession()
        s.load(old)
        s.rename(old, new)
        assert str(Path(new).resolve()) in s._file_roots
        assert str(Path(old).resolve()) not in s._file_roots
        assert os.path.exists(new)
        assert not os.path.exists(old)

    def test_rename_unloaded_file_raises(self, temp_dir):
        s = SerializerSession()
        with pytest.raises(ValueError, match="not loaded"):
            s.rename(
                os.path.join(temp_dir, "ghost.yaml"),
                os.path.join(temp_dir, "other.yaml"),
            )

    def test_rename_updates_include_paths(self, temp_dir):
        child_old = os.path.join(temp_dir, "child.yaml")
        child_new = os.path.join(temp_dir, "child_renamed.yaml")
        main = os.path.join(temp_dir, "main.yaml")
        write(child_old, "x: 1\n")
        write(main, "child: !include child.yaml\n")
        s = SerializerSession()
        s.load(main)
        s.rename(child_old, child_new)
        abs_new_child = str(Path(child_new).resolve())
        assert abs_new_child in s._file_roots
        # !include path attribute updated on the included node
        child_node = s._file_roots[abs_new_child]
        assert child_node._yaml_file == abs_new_child

    def test_rename_parent_across_directories_updates_child_parent_path(self, temp_dir):
        parent_old_dir = os.path.join(temp_dir, "root")
        parent_new_dir = os.path.join(parent_old_dir, "moved")
        child = os.path.join(parent_old_dir, "shared", "child.yaml")
        parent_old = os.path.join(parent_old_dir, "parent.yaml")
        parent_new = os.path.join(parent_new_dir, "parent.yaml")

        os.makedirs(os.path.dirname(child), exist_ok=True)
        os.makedirs(parent_old_dir, exist_ok=True)
        os.makedirs(parent_new_dir, exist_ok=True)

        write(child, "x: 1\n")
        write(parent_old, "child: !include shared/child.yaml\n")

        s = SerializerSession()
        parent_data = s.load(parent_old)
        child_data = parent_data["child"]

        s.rename(parent_old, parent_new)
        s.save(only_if_changed=False)

        saved_parent = Path(parent_new).read_text(encoding="utf-8")
        assert "../shared/child.yaml" in saved_parent
        assert child_data._yaml_parent_file == str(Path(parent_new).resolve())


# ---------------------------------------------------------------------------
# propagate_dirty()
# ---------------------------------------------------------------------------


class TestSerializerSessionPropagateDirty:
    def test_propagate_dirty_marks_parent(self, temp_dir):
        child = os.path.join(temp_dir, "child.yaml")
        main = os.path.join(temp_dir, "main.yaml")
        write(child, "x: 1\n")
        write(main, "child: !include child.yaml\n")
        s = SerializerSession()
        s.load(main)
        s.propagate_dirty(child)
        abs_main = str(Path(main).resolve())
        assert s._file_roots[abs_main]._yaml_dirty


# ---------------------------------------------------------------------------
# clear() / reset()
# ---------------------------------------------------------------------------


class TestSerializerSessionClear:
    def test_clear_resets_state(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "a: 1\n")
        s = SerializerSession()
        s.load(path)
        assert s._yaml_instance is not None
        s.clear()
        assert s._yaml_instance is None
        assert s._file_roots == {}
        assert s._loading_stack == []

    def test_clear_preserves_defaults(self):
        s = SerializerSession({"max_imports": 7})
        s.clear()
        assert s.max_imports == 7
        assert s._max_imports == 7

    def test_reset_is_alias_for_clear(self, temp_dir):
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "a: 1\n")
        s = SerializerSession()
        s.load(path)
        s.reset()
        assert s._yaml_instance is None

    def test_clear_releases_data_references(self, temp_dir):
        """clear() removes all strong references held by the session."""
        import weakref
        import gc

        path = os.path.join(temp_dir, "main.yaml")
        write(path, "key: value\n")
        s = SerializerSession()
        data = s.load(path)
        ref = weakref.ref(data)
        del data  # session is now the sole holder
        assert ref() is not None
        s.clear()
        gc.collect()
        assert ref() is None  # session released the reference


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


class TestSaveOnlyIfChangedFalse:
    def test_save_only_if_changed_false_always_writes(self, temp_dir):
        """save(only_if_changed=False) writes the file unconditionally."""
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "key: value\n")
        s = SerializerSession()
        s.load(path)
        s.save()  # write initial hash; file is now clean
        with open(path, "r", encoding="utf-8") as f:
            content_before = f.read()
        # Force-save even though nothing changed
        s.save(only_if_changed=False)
        with open(path, "r", encoding="utf-8") as f:
            content_after = f.read()
        # Content is preserved even though file was unconditionally written
        assert content_after == content_before


class TestConfigOverride:
    def test_load_config_does_not_affect_unspecified_keys(self, temp_dir):
        """load(config=...) leaves unspecified keys at their constructor defaults."""
        path = os.path.join(temp_dir, "main.yaml")
        write(path, "a: 1\n")
        # Constructor sets custom max_include_depth=5
        s = SerializerSession({"max_include_depth": 5})
        # Override only max_file_size; max_include_depth must stay 5
        s.load(path, config={"max_file_size": 1024})
        assert s._max_file_size == 1024
        assert s._max_include_depth == 5  # unchanged from constructor default


class TestPropagateDirtyMultipleParents:
    def test_propagate_dirty_marks_all_parents(self, temp_dir):
        """propagate_dirty marks every file that directly or indirectly includes the target."""
        child = os.path.join(temp_dir, "child.yaml")
        parent1 = os.path.join(temp_dir, "parent1.yaml")
        parent2 = os.path.join(temp_dir, "parent2.yaml")
        root = os.path.join(temp_dir, "root.yaml")

        write(child, "x: 1\n")
        write(parent1, "child: !include child.yaml\n")
        write(parent2, "child: !include child.yaml\n")
        # root includes both parents, each of which includes child.yaml (diamond pattern)
        write(root, "p1: !include parent1.yaml\np2: !include parent2.yaml\n")

        s = SerializerSession()
        root_data = s.load(root)

        abs_parent1 = str(Path(parent1).resolve())
        abs_parent2 = str(Path(parent2).resolve())
        parent1_data = s._file_roots.get(abs_parent1)
        parent2_data = s._file_roots.get(abs_parent2)
        assert parent1_data is not None
        assert parent2_data is not None
        assert not root_data._yaml_dirty

        s.propagate_dirty(child)

        # Both parents and the root must be marked dirty
        assert parent1_data._yaml_dirty
        assert parent2_data._yaml_dirty
        assert root_data._yaml_dirty


class TestRenameToDirectory:
    def test_rename_to_different_directory(self, temp_dir):
        """rename() works when moving a file to a different subdirectory."""
        sub1 = os.path.join(temp_dir, "sub1")
        sub2 = os.path.join(temp_dir, "sub2")
        os.makedirs(sub1)
        os.makedirs(sub2)

        old_path = os.path.join(sub1, "data.yaml")
        new_path = os.path.join(sub2, "data.yaml")
        write(old_path, "key: value\n")

        s = SerializerSession()
        data = s.load(old_path)

        s.rename(old_path, new_path)

        assert data._yaml_file == str(Path(new_path).resolve())
        assert str(Path(new_path).resolve()) in s._file_roots
        assert str(Path(old_path).resolve()) not in s._file_roots
        assert os.path.exists(new_path)
        assert not os.path.exists(old_path)


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_independent_sessions(self, temp_dir):
        """Multiple threads loading independent sessions do not interfere."""
        import threading

        def load_and_verify(path, expected_value, results, idx):
            try:
                s = SerializerSession()
                data = s.load(path)
                results[idx] = data["val"] == expected_value
            except Exception:
                results[idx] = False

        paths = []
        for i in range(4):
            p = os.path.join(temp_dir, f"file{i}.yaml")
            write(p, f"val: {i}\n")
            paths.append(p)

        results = [None] * 4
        threads = [
            threading.Thread(target=load_and_verify, args=(paths[i], i, results, i))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results), f"Thread results: {results}"

    def test_concurrent_loads_same_file(self, temp_dir):
        """Multiple threads loading the same file each get an independent data copy."""
        import threading

        path = os.path.join(temp_dir, "shared.yaml")
        write(path, "val: 42\n")

        data_objects = []
        lock = threading.Lock()

        def load_and_collect():
            s = SerializerSession()
            d = s.load(path)
            with lock:
                data_objects.append(d)

        threads = [threading.Thread(target=load_and_collect) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(data_objects) == 4
        assert all(d["val"] == 42 for d in data_objects)
        # Each session produced a distinct object
        ids = {id(d) for d in data_objects}
        assert len(ids) == 4
