"""
Tests for utils.py helper functions.
"""

import os
import pytest
from pathlib import Path
from yaml_serializer import utils


class TestHashFileOperations:
    """Tests for .hash file read/write helpers."""

    def test_hash_file_path(self, temp_dir):
        """_hash_file_path returns the YAML path with a .hash extension."""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        hash_path = utils._hash_file_path(yaml_path)
        assert hash_path == yaml_path + ".hash"

    def test_save_and_load_hash(self, temp_dir):
        """A saved hash can be loaded back with the correct value."""
        yaml_path = os.path.join(temp_dir, "test.yaml")
        test_hash = "abc123def456"

        utils._save_hash_to_file(yaml_path, test_hash)
        loaded_hash = utils._load_hash_from_file(yaml_path)

        assert loaded_hash == test_hash

    def test_load_hash_nonexistent_file(self, temp_dir):
        """_load_hash_from_file returns None when no hash file exists."""
        yaml_path = os.path.join(temp_dir, "nonexistent.yaml")
        hash_value = utils._load_hash_from_file(yaml_path)
        assert hash_value is None


class TestResolveIncludePath:
    """Tests for resolve_include_path()."""

    def test_resolve_relative_path(self, temp_dir):
        """Relative include paths are resolved relative to the base file's directory."""
        base_file = os.path.join(temp_dir, "main.yaml")
        include_path = "subdir/include.yaml"

        resolved = utils.resolve_include_path(base_file, include_path)
        expected = str((Path(temp_dir) / "subdir" / "include.yaml").resolve())

        assert resolved == expected

    def test_resolve_parent_path(self, temp_dir):
        """Paths containing ../ are resolved correctly."""
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)

        base_file = os.path.join(subdir, "main.yaml")
        include_path = "../include.yaml"

        resolved = utils.resolve_include_path(base_file, include_path)
        expected = str((Path(temp_dir) / "include.yaml").resolve())

        assert resolved == expected


class TestIsPathWithinRoot:
    """Tests for is_path_within_root()."""

    def test_path_within_root(self, temp_dir):
        """A path inside the root directory is accepted."""
        root_dir = temp_dir
        inner_path = os.path.join(temp_dir, "subdir", "file.yaml")

        assert utils.is_path_within_root(inner_path, root_dir) is True

    def test_path_outside_root(self, temp_dir):
        """A path outside the root directory is rejected."""
        root_dir = os.path.join(temp_dir, "restricted")
        os.makedirs(root_dir, exist_ok=True)

        outside_path = os.path.join(temp_dir, "outside.yaml")

        assert utils.is_path_within_root(outside_path, root_dir) is False

    def test_none_root_raises_error(self, temp_dir):
        """Passing None as root_dir must raise TypeError."""
        any_path = os.path.join(temp_dir, "any.yaml")
        with pytest.raises(TypeError):
            utils.is_path_within_root(any_path, None)

    def test_path_traversal_attack(self, temp_dir):
        """Path traversal attempts (../../../) are blocked by is_path_within_root."""
        root_dir = os.path.join(temp_dir, "safe")
        os.makedirs(root_dir, exist_ok=True)

        # Path traversal attempt via ../../../
        malicious_path = os.path.join(root_dir, "..", "..", "..", "etc", "passwd")

        # Must be blocked
        assert utils.is_path_within_root(malicious_path, root_dir) is False
