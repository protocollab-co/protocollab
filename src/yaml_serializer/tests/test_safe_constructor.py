import io

import pytest
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import ScalarNode
from yaml_serializer.safe_constructor import RestrictedSafeConstructor, create_safe_yaml_instance


def test_remove_dangerous_constructors():
    cons = RestrictedSafeConstructor()
    # Add a dangerous tag manually
    cons.yaml_constructors["tag:yaml.org,2002:python/object"] = lambda x, y: None
    cons._remove_dangerous_constructors()
    assert "tag:yaml.org,2002:python/object" not in cons.yaml_constructors


def test_construct_object_blocks_python_tag():
    cons = RestrictedSafeConstructor()
    node = ScalarNode("tag:yaml.org,2002:python/object", "data")
    with pytest.raises(YAMLError):
        cons.construct_object(node)


def test_construct_object_blocks_unknown_tag():
    cons = RestrictedSafeConstructor()
    node = ScalarNode("!unknown", "data")
    with pytest.raises(YAMLError):
        cons.construct_object(node)


def test_construct_mapping_and_sequence_depth():
    yaml = create_safe_yaml_instance(max_depth=1)
    deep_mapping = "a:\n  b:\n    c: 1"
    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 1"):
        yaml.load(io.StringIO(deep_mapping))

    deep_seq = "-\n  -\n    - 1"
    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 1"):
        yaml.load(io.StringIO(deep_seq))


# Tests for RestrictedSafeConstructor and create_safe_yaml_instance


def test_load_simple_yaml():
    yaml = create_safe_yaml_instance()
    data = yaml.load(io.StringIO("a: 1\nb: test\nc:\n  - 1\n  - 2"))
    assert data["a"] == 1
    assert data["b"] == "test"
    assert data["c"] == [1, 2]


def test_block_dangerous_python_tag():
    yaml = create_safe_yaml_instance()
    dangerous = 'a: !!python/object/apply:os.system ["echo hacked"]'
    with pytest.raises(YAMLError):
        yaml.load(io.StringIO(dangerous))


def test_block_unknown_custom_tag():
    yaml = create_safe_yaml_instance()
    unknown = "a: !customtag value"
    with pytest.raises(YAMLError):
        yaml.load(io.StringIO(unknown))


def test_max_depth_none_raises():
    with pytest.raises(ValueError, match="max_depth cannot be None"):
        RestrictedSafeConstructor(max_depth=None)


def test_max_depth_zero_raises():
    with pytest.raises(ValueError, match="max_depth must be a positive integer"):
        RestrictedSafeConstructor(max_depth=0)


def test_max_depth_negative_raises():
    with pytest.raises(ValueError, match="max_depth must be a positive integer"):
        RestrictedSafeConstructor(max_depth=-1)


def test_valid_max_depth_works():
    cons = RestrictedSafeConstructor(max_depth=10)
    assert cons.max_depth == 10
