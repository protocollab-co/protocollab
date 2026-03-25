"""
Integration tests — complex multi-file workflows.
"""

import os
import pytest
from pathlib import Path
from yaml_serializer import (
    SerializerSession,
    add_to_dict,
    add_to_list,
)


class TestComplexProtocols:
    """Tests for protocols with multiple nested includes."""

    def test_complex_nested_includes(self, temp_dir, create_yaml_file):
        """Three levels of nested includes resolve to the correct values."""
        level3_yaml = os.path.join(temp_dir, "level3.yaml")
        level2_yaml = os.path.join(temp_dir, "level2.yaml")
        level1_yaml = os.path.join(temp_dir, "level1.yaml")

        create_yaml_file(level3_yaml, "value: 3\n")
        create_yaml_file(level2_yaml, "level3: !include level3.yaml\nvalue: 2\n")
        create_yaml_file(level1_yaml, "level2: !include level2.yaml\nvalue: 1\n")

        s = SerializerSession()
        data = s.load(level1_yaml)
        assert data["value"] == 1
        assert data["level2"]["value"] == 2
        assert data["level2"]["level3"]["value"] == 3


class TestModificationWorkflows:
    """Tests for modify-then-save workflows."""

    def test_modify_nested_included_file(self, temp_dir, create_yaml_file):
        """Modifying a nested included file and saving round-trips correctly."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        inc_yaml = os.path.join(temp_dir, "inc.yaml")

        create_yaml_file(inc_yaml, "items:\n  - first\n")
        create_yaml_file(main_yaml, "data: !include inc.yaml\n")

        s = SerializerSession()
        data = s.load(main_yaml)

        # Add an element to the list in the included file
        add_to_list(data["data"]["items"], "second")

        s.save()

        # Reload and verify
        data2 = s.load(main_yaml)
        assert len(data2["data"]["items"]) == 2
        assert data2["data"]["items"][1] == "second"

    def test_save_only_changed_files_multiple_includes(self, temp_dir, create_yaml_file):
        """When only one included file is modified, other included files are not rewritten."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        inc1_yaml = os.path.join(temp_dir, "inc1.yaml")
        inc2_yaml = os.path.join(temp_dir, "inc2.yaml")

        create_yaml_file(inc1_yaml, "value: 1\n")
        create_yaml_file(inc2_yaml, "value: 2\n")
        create_yaml_file(main_yaml, "inc1: !include inc1.yaml\ninc2: !include inc2.yaml\n")

        s = SerializerSession()
        data = s.load(main_yaml)
        s.save()

        with open(inc2_yaml, "r", encoding="utf-8") as f:
            inc2_content_before = f.read()

        # Modify only inc1
        data["inc1"]["value"] = 999
        s.save()

        with open(inc2_yaml, "r", encoding="utf-8") as f:
            inc2_content_after = f.read()

        # inc2 must not change
        assert inc2_content_after == inc2_content_before


class TestFileRenaming:
    """Tests for file renaming in multi-file sessions."""

    def test_rename_main_file(self, temp_dir, create_yaml_file):
        """Renaming the main file updates internal state correctly."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        new_main = os.path.join(temp_dir, "renamed_main.yaml")
        create_yaml_file(main_yaml, "key: value\n")

        s = SerializerSession()
        data = s.load(main_yaml)
        assert data._yaml_file == str(Path(main_yaml).resolve())

        s.rename(main_yaml, new_main)

        assert data._yaml_file == str(Path(new_main).resolve())
        assert s._root_filename == str(Path(new_main).resolve())
        assert os.path.exists(new_main)
        assert not os.path.exists(main_yaml)

    def test_rename_included_file(self, temp_dir, create_yaml_file):
        """Renaming an included file updates the !include tags in the parent."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        inc_yaml = os.path.join(temp_dir, "inc.yaml")
        new_inc = os.path.join(temp_dir, "renamed_inc.yaml")

        create_yaml_file(inc_yaml, "data: 42\n")
        create_yaml_file(main_yaml, "include: !include inc.yaml\n")

        s = SerializerSession()
        _ = s.load(main_yaml)
        s.rename(inc_yaml, new_inc)

        s.save()

        with open(main_yaml, "r") as f:
            content = f.read()

        assert "!include renamed_inc.yaml" in content

    def test_rename_with_existing_hash(self, temp_dir, create_yaml_file):
        """Renaming a file that has an existing .hash file also renames the hash file."""
        from yaml_serializer import utils

        main_yaml = os.path.join(temp_dir, "main.yaml")
        new_main = os.path.join(temp_dir, "new_main.yaml")
        create_yaml_file(main_yaml, "data: 1\n")

        s = SerializerSession()
        _ = s.load(main_yaml)
        s.save()

        assert os.path.exists(main_yaml + ".hash")
        old_hash = utils.load_hash_from_file(main_yaml)

        s.rename(main_yaml, new_main)

        assert not os.path.exists(main_yaml + ".hash")
        assert os.path.exists(new_main + ".hash")
        new_hash = utils.load_hash_from_file(new_main)
        assert new_hash == old_hash


class TestPropagateDirty:
    """Tests for dirty-flag propagation across files."""

    def test_propagate_dirty_marks_parent(self, temp_dir, create_yaml_file):
        """propagate_dirty marks parent files referencing the changed file."""
        main_yaml = os.path.join(temp_dir, "main.yaml")
        inc_yaml = os.path.join(temp_dir, "inc.yaml")

        create_yaml_file(inc_yaml, "value: 42\n")
        create_yaml_file(main_yaml, "inc: !include inc.yaml\n")

        s = SerializerSession()
        data = s.load(main_yaml)
        s.save()

        # Modify the included file
        inc_node = data["inc"]
        add_to_dict(inc_node, "new_field", "test")

        # The main file is not dirty yet
        assert data._yaml_dirty is False

        # Call propagate_dirty
        s.propagate_dirty(inc_yaml)

        # Now the main file must become dirty
        assert data._yaml_dirty is True

        s.save()

        # Reload and verify
        data_reloaded = s.load(main_yaml)
        assert data_reloaded["inc"]["new_field"] == "test"


class TestFullWorkflow:
    """End-to-end workflow tests."""

    def test_create_modify_rename_save_workflow(self, temp_dir, create_yaml_file):
        """Full cycle: create -> modify -> rename -> save -> reload -> verify."""
        # 1. Create files
        main_yaml = os.path.join(temp_dir, "protocol.yaml")
        types_yaml = os.path.join(temp_dir, "types.yaml")

        create_yaml_file(types_yaml, "Message:\n  id: u32\n")
        create_yaml_file(main_yaml, "meta:\n" "  id: my_protocol\n" "types: !include types.yaml\n")

        # 2. Load
        s = SerializerSession()
        data = s.load(main_yaml)
        assert data["types"]["Message"]["id"] == "u32"

        # 3. Modify
        add_to_dict(data["types"]["Message"], "data", "str")

        # 4. Rename types.yaml
        new_types_yaml = os.path.join(temp_dir, "message_types.yaml")
        s.rename(types_yaml, new_types_yaml)

        # 5. Save everything
        s.save()

        # 6. Verify the result
        data2 = s.load(main_yaml)
        assert data2["types"]["Message"]["data"] == "str"

        # Verify that the !include path has been updated
        with open(main_yaml, "r") as f:
            content = f.read()
        assert "!include message_types.yaml" in content


class TestErrorRecovery:
    """Tests for error recovery scenarios."""

    def test_load_after_failed_load(self, temp_dir, create_yaml_file):
        """A successful load after a failed attempt must work correctly."""
        bad_yaml = os.path.join(temp_dir, "bad.yaml")
        good_yaml = os.path.join(temp_dir, "good.yaml")

        # Create a file with a circular reference
        create_yaml_file(bad_yaml, "data: !include bad.yaml\n")
        create_yaml_file(good_yaml, "data: valid\n")

        # First load must fail
        with pytest.raises(ValueError):
            SerializerSession().load(bad_yaml)

        data = SerializerSession().load(good_yaml)
        assert data["data"] == "valid"
