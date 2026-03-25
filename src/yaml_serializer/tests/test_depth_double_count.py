# tests/test_depth_double_count.py
"""
Tests for verifying correct nesting depth enforcement in RestrictedSafeConstructor.
Detect the double-counting problem that causes the effective limit to be half the configured value.
"""

import pytest
import ruamel.yaml
from io import StringIO

from yaml_serializer.safe_constructor import create_safe_yaml_instance

# ----------------------------------------------------------------------
# Helper functions for generating YAML strings with a given nesting depth
# ----------------------------------------------------------------------


def nested_mapping(depth: int, value=1):
    """Creates a nested dict of the given depth (number of mapping levels)."""
    result = value
    for i in range(depth):
        result = {f"level{i}": result}
    return result


def nested_sequence(depth: int, value=1):
    """Creates a nested list of the given depth (number of sequence levels)."""
    result = value
    for i in range(depth):
        result = [result]
    return result


def to_yaml(data) -> str:
    """Converts an object to a YAML string (without using our library)."""
    yaml = ruamel.yaml.YAML()
    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


# ----------------------------------------------------------------------
# Tests for mappings
# ----------------------------------------------------------------------


@pytest.mark.parametrize("depth", range(1, 51))
def test_mapping_depth_within_limit(depth):
    """
    For depths from 1 to max_depth (50) no exception should be raised.
    If the test fails at some depth <= 50, this indicates a double-counting problem.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_mapping(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Mapping depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_mapping_depth_exceeds_limit(depth):
    """
    At depth > max_depth a ValueError must be raised.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_mapping(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Tests for sequences
# ----------------------------------------------------------------------


@pytest.mark.parametrize("depth", range(1, 51))
def test_sequence_depth_within_limit(depth):
    """
    Same as the mapping tests, but for sequences.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_sequence(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Sequence depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_sequence_depth_exceeds_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_sequence(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Combined structures (mapping + sequence)
# ----------------------------------------------------------------------


def mixed_structure(depth: int):
    """Alternates mapping and sequence to create a structure of the given depth."""
    result = 1
    for i in range(depth):
        if i % 2 == 0:
            result = [result]
        else:
            result = {f"level{i}": result}
    return result


@pytest.mark.parametrize("depth", range(1, 51))
def test_mixed_depth_within_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = mixed_structure(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Mixed structure depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_mixed_depth_exceeds_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = mixed_structure(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Test specifically targeting double-counting detection
# ----------------------------------------------------------------------


def test_double_counting_manifestation():
    """
    Verifies that depth is not counted twice.
    With max_depth=50 a depth of 26 must be allowed (no double counting: 26 != 52).
    If this test fails (exception raised for depth 26), double counting is present.
    """
    # Use a separate instance for each load so that _depth is reset
    loader_25 = create_safe_yaml_instance(max_depth=50)
    data_25 = nested_mapping(25)
    yaml_25 = to_yaml(data_25)
    try:
        loader_25.load(yaml_25)
    except ValueError:
        pytest.fail("Depth 25 raised exception, but should be allowed.")

    # Depth 26 – must be allowed (no double counting: 26 <= 50)
    loader_26 = create_safe_yaml_instance(max_depth=50)
    data_26 = nested_mapping(26)
    yaml_26 = to_yaml(data_26)
    try:
        loader_26.load(yaml_26)
    except ValueError:
        pytest.fail("Depth 26 raised exception, double counting is still present (2*26=52 > 50).")
