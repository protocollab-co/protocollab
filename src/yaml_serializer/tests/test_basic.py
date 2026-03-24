import os
from ruamel.yaml.comments import CommentedSeq
from yaml_serializer import utils
import pytest
from pathlib import Path
from yaml_serializer import (
    SerializerSession,
    new_commented_map,
    new_commented_seq,
    add_to_dict,
    add_to_list,
    remove_from_list,
    get_node_hash,
)


def test_load_save_unchanged(temp_dir, create_yaml_file):
    """Load and save without modifications must not rewrite the file content."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    yaml_content = """
meta:
  id: test_proto
  name: Test Protocol
  version: 1.0
kaitai:
  types: {}
endpoints: []
"""
    create_yaml_file(main_yaml, yaml_content)

    s = SerializerSession()
    data = s.load(main_yaml)
    assert data["meta"]["id"] == "test_proto"

    hash_file = main_yaml + ".hash"
    assert not os.path.exists(hash_file)

    # First save -- file must be written (no previous hash)
    s.save(only_if_changed=True)
    assert os.path.exists(hash_file)

    # Capture content after first save
    with open(main_yaml, "r", encoding="utf-8") as f:
        content_before = f.read()

    # Second save without modifications -- content must stay identical
    s.save(only_if_changed=True)
    with open(main_yaml, "r", encoding="utf-8") as f:
        content_after = f.read()

    assert (
        content_after == content_before
    ), "File must not change on repeated save of unchanged data"


def test_modify_and_save(temp_dir, create_yaml_file):
    """Modifying data must cause the file to be rewritten with an updated hash."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    yaml_content = """
meta:
  id: test_proto
  name: Test Protocol
  version: 1.0
kaitai:
  types: {}
endpoints: []
"""
    create_yaml_file(main_yaml, yaml_content)

    s = SerializerSession()
    data = s.load(main_yaml)
    s.save(only_if_changed=True)

    hash_file = main_yaml + ".hash"
    with open(hash_file, "r") as f:
        hash_before = f.read()

    types = data["kaitai"]["types"]
    new_type = new_commented_map(parent=types)
    add_to_dict(new_type, "field1", "u4")
    add_to_dict(types, "NewPacket", new_type)

    assert types._yaml_dirty is True
    assert data._yaml_dirty is True

    s.save(only_if_changed=True)

    with open(hash_file, "r") as f:
        hash_after = f.read()
    assert hash_after != hash_before, "Hash must change after modification"

    data2 = s.load(main_yaml)
    assert "NewPacket" in data2["kaitai"]["types"]
    assert data2["kaitai"]["types"]["NewPacket"]["field1"] == "u4"


def test_include_basic(temp_dir, create_yaml_file):
    """External file included via !include must be loaded and saved correctly."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    included_yaml = os.path.join(temp_dir, "included.yaml")

    included_content = """
types:
  InnerType:
    field: u2
"""
    main_content = """
meta:
  id: include_test
  name: Include Test
  version: 1.0
kaitai: !include included.yaml
endpoints: []
"""
    create_yaml_file(included_yaml, included_content)
    create_yaml_file(main_yaml, main_content)

    s = SerializerSession()
    data = s.load(main_yaml)

    assert "types" in data["kaitai"]
    assert "InnerType" in data["kaitai"]["types"]
    assert data["kaitai"]["types"]["InnerType"]["field"] == "u2"

    assert data["kaitai"]._yaml_file == str(Path(included_yaml).resolve())
    assert data["kaitai"]["types"]._yaml_file == str(Path(included_yaml).resolve())

    s.save(only_if_changed=True)
    assert os.path.exists(main_yaml + ".hash")
    assert os.path.exists(included_yaml + ".hash")

    types_dict = data["kaitai"]["types"]
    new_type = new_commented_map(parent=types_dict)
    add_to_dict(new_type, "extra", "u8")
    add_to_dict(types_dict, "AnotherType", new_type)

    assert types_dict._yaml_dirty is True
    assert data["kaitai"]._yaml_dirty is True
    assert data._yaml_dirty is False

    s.save(only_if_changed=True)

    import ruamel.yaml

    yaml = ruamel.yaml.YAML()
    with open(included_yaml, "r") as f:
        inc_data = yaml.load(f)
    assert "AnotherType" in inc_data["types"]


def test_rename_main_file(temp_dir, create_yaml_file):
    """Renaming the main file updates all internal references."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    new_main = os.path.join(temp_dir, "renamed_main.yaml")
    create_yaml_file(main_yaml, "key: value\n")

    s = SerializerSession()
    data = s.load(main_yaml)
    assert data._yaml_file == str(Path(main_yaml).resolve())
    assert s._root_filename == str(Path(main_yaml).resolve())

    s.rename(main_yaml, new_main)

    assert data._yaml_file == str(Path(new_main).resolve())
    assert s._root_filename == str(Path(new_main).resolve())
    assert str(Path(new_main).resolve()) in s._file_roots
    assert str(Path(main_yaml).resolve()) not in s._file_roots

    assert not os.path.exists(main_yaml)
    assert os.path.exists(new_main)

    s.save()
    assert os.path.exists(new_main + ".hash")
    assert not os.path.exists(main_yaml + ".hash")


def test_rename_included_file(temp_dir, create_yaml_file):
    """Renaming an included file must update all !include references."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    inc_yaml = os.path.join(temp_dir, "inc.yaml")
    new_inc = os.path.join(temp_dir, "renamed_inc.yaml")

    create_yaml_file(inc_yaml, "data: 42\n")
    create_yaml_file(main_yaml, "include: !include inc.yaml\n")

    s = SerializerSession()
    data = s.load(main_yaml)
    assert data["include"]._yaml_file == str(Path(inc_yaml).resolve())

    s.rename(inc_yaml, new_inc)

    assert data["include"]._yaml_file == str(Path(new_inc).resolve())
    assert str(Path(new_inc).resolve()) in s._file_roots
    assert str(Path(inc_yaml).resolve()) not in s._file_roots

    s.save()
    with open(main_yaml, "r") as f:
        content = f.read()
    assert (
        "!include renamed_inc.yaml" in content
    ), f"Expected '!include renamed_inc.yaml' in content, got: {content}"


def test_rename_with_existing_hash(temp_dir, create_yaml_file):
    """Renaming a file that already has a .hash file renames the hash file too."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    new_main = os.path.join(temp_dir, "new_main.yaml")
    create_yaml_file(main_yaml, "data: 1\n")

    s = SerializerSession()
    s.load(main_yaml)
    s.save()

    assert os.path.exists(main_yaml + ".hash")
    old_hash = utils.load_hash_from_file(main_yaml)

    s.rename(main_yaml, new_main)

    assert not os.path.exists(main_yaml + ".hash")
    assert os.path.exists(new_main + ".hash")
    new_hash = utils.load_hash_from_file(new_main)
    assert new_hash == old_hash


def test_propagate_dirty_marks_parent(temp_dir, create_yaml_file):
    """propagate_dirty marks parent files that reference the changed included file."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    inc_yaml = os.path.join(temp_dir, "inc.yaml")

    create_yaml_file(inc_yaml, "value: 42\n")
    create_yaml_file(main_yaml, "inc: !include inc.yaml\n")

    s = SerializerSession()
    data = s.load(main_yaml)
    s.save()

    inc_node = data["inc"]
    add_to_dict(inc_node, "new_field", "test")

    assert data._yaml_dirty is False

    s.propagate_dirty(inc_yaml)

    assert data._yaml_dirty is True

    s.save()

    data_reloaded = s.load(main_yaml)
    assert data_reloaded["inc"]["new_field"] == "test"


def test_list_modifications(temp_dir, create_yaml_file):
    """Adding and removing elements in a CommentedSeq marks nodes dirty."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    yaml_content = """
list:
  - first
  - second
"""
    create_yaml_file(main_yaml, yaml_content)

    s = SerializerSession()
    data = s.load(main_yaml)
    lst = data["list"]
    assert isinstance(lst, CommentedSeq)

    new_item = new_commented_seq(parent=lst)
    add_to_list(lst, new_item)
    assert len(lst) == 3
    assert lst._yaml_dirty is True
    assert data._yaml_dirty is True

    remove_from_list(lst, 0)
    assert len(lst) == 2
    assert lst[0] == "second"


def test_node_hash_changes_on_modification(temp_dir, create_yaml_file):
    """A node's hash must change after modification and dirty flag must clear afterward."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    create_yaml_file(main_yaml, "key: value\n")

    s = SerializerSession()
    data = s.load(main_yaml)
    original_hash = get_node_hash(data)

    add_to_dict(data, "new", "value2")
    new_hash = get_node_hash(data)

    assert new_hash != original_hash
    assert data._yaml_dirty is False


def test_unchanged_included_file_not_saved(temp_dir, create_yaml_file):
    """Unchanged included files must not be rewritten on save."""
    main_yaml = os.path.join(temp_dir, "main.yaml")
    inc_yaml = os.path.join(temp_dir, "inc.yaml")

    create_yaml_file(inc_yaml, "data: 42\n")
    create_yaml_file(main_yaml, "inc: !include inc.yaml\n")

    s = SerializerSession()
    s.load(main_yaml)
    s.save()

    with open(inc_yaml, "r", encoding="utf-8") as f:
        inc_content_before = f.read()
    with open(main_yaml, "r", encoding="utf-8") as f:
        main_content_before = f.read()

    s.save(only_if_changed=True)

    with open(inc_yaml, "r", encoding="utf-8") as f:
        inc_content_after = f.read()
    with open(main_yaml, "r", encoding="utf-8") as f:
        main_content_after = f.read()

    assert inc_content_after == inc_content_before
    assert main_content_after == main_content_before
