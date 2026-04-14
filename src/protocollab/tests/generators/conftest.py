"""Fixtures for generator tests."""

from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture()
def ping_spec() -> dict:
    """Minimal ping protocol spec (little-endian, 3 fields)."""
    return {
        "meta": {"id": "ping_protocol", "endian": "le", "title": "Ping Protocol"},
        "seq": [
            {"id": "type_id", "type": "u1"},
            {"id": "sequence_number", "type": "u4"},
            {"id": "payload_size", "type": "u2"},
        ],
    }


@pytest.fixture()
def ping_spec_with_instances() -> dict:
    """Ping spec with Wireshark virtual fields backed by expressions."""
    return {
        "meta": {"id": "ping_protocol", "endian": "le", "title": "Ping Protocol"},
        "seq": [
            {"id": "type_id", "type": "u1"},
            {"id": "src_ip", "type": "u4"},
            {"id": "dst_ip", "type": "u4"},
        ],
        "instances": {
            "lan": {
                "value": (
                    "((src_ip & 0xFF000000) == 0x0A000000) or "
                    "((src_ip & 0xFFFF0000) == 0xC0A80000)"
                ),
                "wireshark": {"type": "bool", "filter-only": True, "label": "LAN"},
            },
            "scope": {
                "value": '"lan" if lan else "inet"',
                "wireshark": {"type": "string", "label": "Scope"},
            },
        },
    }


@pytest.fixture()
def ping_spec_with_reordered_instances() -> dict:
    """Ping spec where instance declaration order does not match dependencies."""
    return {
        "meta": {"id": "ping_protocol", "endian": "le", "title": "Ping Protocol"},
        "seq": [{"id": "src_ip", "type": "u4"}],
        "instances": {
            "scope": {
                "value": '"lan" if lan else "inet"',
                "wireshark": {"type": "string", "label": "Scope"},
            },
            "lan": {
                "value": "(src_ip & 0xFFFF0000) == 0xC0A80000",
                "wireshark": {"type": "bool", "filter-only": True, "label": "LAN"},
            },
        },
    }


@pytest.fixture()
def be_spec() -> dict:
    """Big-endian protocol spec."""
    return {
        "meta": {"id": "be_proto", "endian": "be"},
        "seq": [{"id": "value", "type": "u2"}],
    }


@pytest.fixture()
def empty_seq_spec() -> dict:
    """Protocol with no fields."""
    return {"meta": {"id": "empty_proto", "endian": "le"}, "seq": []}


@pytest.fixture()
def ping_yaml(tmp_path: Path) -> Path:
    """File path to a ping_protocol.yaml in tmp_path."""
    file_path = tmp_path / "ping_protocol.yaml"
    file_path.write_text(
        "meta:\n  id: ping_protocol\n  endian: le\nseq:\n"
        "  - id: type_id\n    type: u1\n"
        "  - id: sequence_number\n    type: u4\n"
        "  - id: payload_size\n    type: u2\n",
        encoding="utf-8",
    )
    return file_path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()
