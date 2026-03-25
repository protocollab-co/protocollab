"""Shared fixtures for protocollab tests."""

import pytest


@pytest.fixture()
def simple_yaml(tmp_path):
    """A minimal YAML file with no includes."""
    f = tmp_path / "simple.yaml"
    f.write_text(
        "version: '1.0'\n"
        "description: 'Simple test protocol'\n"
        "protocol:\n"
        "  endianness: little\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture()
def yaml_with_include(tmp_path):
    """A YAML file that !includes a sibling file."""
    types_file = tmp_path / "types.yaml"
    types_file.write_text("uint32:\n  size: 4\n", encoding="utf-8")

    proto = tmp_path / "proto_with_include.yaml"
    proto.write_text(
        "version: '1.0'\ntypes: !include types.yaml\n",
        encoding="utf-8",
    )
    return proto


@pytest.fixture()
def invalid_yaml(tmp_path):
    """A file with invalid YAML syntax."""
    f = tmp_path / "bad.yaml"
    f.write_text("key: [\nnot closed", encoding="utf-8")
    return f
