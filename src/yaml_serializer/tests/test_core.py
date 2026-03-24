"""
Tests for core load/save functionality.
"""

import os
import pytest
from yaml_serializer import (
    add_to_dict,
)
from yaml_serializer.serializer import SerializerSession


class TestLoadProtocol:
    """Tests for SerializerSession.load()."""

    def test_load_simple_protocol(self, temp_dir, create_yaml_file):
        """Load a simple protocol file and verify basic attributes."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        content = """
meta:
  id: test_proto
  version: "1.0"
kaitai:
  types: {}
endpoints: []
"""
        create_yaml_file(main_yaml, content)

        s = SerializerSession()
        data = s.load(main_yaml)
        assert data["meta"]["id"] == "test_proto"
        assert hasattr(data, "_yaml_file")
        assert hasattr(data, "_yaml_hash")

    def test_load_nonexistent_file(self):
        """Loading a non-existent file must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SerializerSession().load("nonexistent_file.yaml")

    def test_load_with_config(self, temp_dir, create_yaml_file):
        """Load with security config overrides applies those settings."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: value\n")

        config = {"max_file_size": 1024, "max_include_depth": 10, "max_imports": 50}

        s = SerializerSession()
        data = s.load(main_yaml, config=config)
        assert data["data"] == "value"

        assert s._max_file_size == 1024
        assert s._max_include_depth == 10
        assert s._max_imports == 50

    def test_save_without_load(self):
        """save() without a prior load() must raise RuntimeError."""
        s = SerializerSession()
        with pytest.raises(RuntimeError, match="No YAML loaded"):
            s.save()

    def test_save_unchanged_protocol(self, temp_dir, create_yaml_file):
        """Saving without modifications must not rewrite the file content."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        content = "key: value\n"
        create_yaml_file(main_yaml, content)

        s = SerializerSession()
        _ = s.load(main_yaml)
        s.save(only_if_changed=True)

        with open(main_yaml, "r", encoding="utf-8") as f:
            content_before = f.read()

        s.save(only_if_changed=True)
        with open(main_yaml, "r", encoding="utf-8") as f:
            content_after = f.read()

        assert content_after == content_before

    def test_save_modified_protocol(self, temp_dir, create_yaml_file):
        """Saving a modified protocol must update the file on disk."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: {}\n")

        s = SerializerSession()
        data = s.load(main_yaml)
        s.save(only_if_changed=True)

        # Modify
        add_to_dict(data["data"], "new_key", "new_value")

        s.save(only_if_changed=True)

        # Reload and verify
        data2 = s.load(main_yaml)
        assert data2["data"]["new_key"] == "new_value"


class TestHashTracking:
    """Tests for file hash tracking."""

    def test_hash_file_created_on_save(self, temp_dir, create_yaml_file):
        """A .hash file must be created when saving."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: value\n")

        s = SerializerSession()
        _ = s.load(main_yaml)
        hash_file = main_yaml + ".hash"

        assert not os.path.exists(hash_file)

        s.save()

        assert os.path.exists(hash_file)

    def test_hash_changes_after_modification(self, temp_dir, create_yaml_file):
        """The hash must change after a modification."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: {}\n")

        s = SerializerSession()
        data = s.load(main_yaml)
        s.save()

        hash_file = main_yaml + ".hash"
        with open(hash_file, "r") as f:
            hash_before = f.read()

        # Modify
        add_to_dict(data["data"], "key", "value")
        s.save()

        with open(hash_file, "r") as f:
            hash_after = f.read()

        assert hash_after != hash_before


class TestFileRootTracking:
    """Tests for file-root bookkeeping."""

    def test_main_file_registered(self, temp_dir, create_yaml_file):
        """The main file must be registered in _file_roots after loading."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        create_yaml_file(main_yaml, "data: value\n")

        from pathlib import Path

        s = SerializerSession()
        data = s.load(main_yaml)

        main_abs = str(Path(main_yaml).resolve())
        assert main_abs in s._file_roots
        assert s._file_roots[main_abs] is data

    def test_file_roots_cleared_on_new_load(self, temp_dir, create_yaml_file):
        """_file_roots must be cleared when a new load() is called."""
        file1 = os.path.join(temp_dir, "file1.yaml")
        file2 = os.path.join(temp_dir, "file2.yaml")

        create_yaml_file(file1, "data: 1\n")
        create_yaml_file(file2, "data: 2\n")

        s = SerializerSession()
        s.load(file1)

        s.load(file2)

        # After the second load, only one file should remain
        assert len(s._file_roots) == 1
