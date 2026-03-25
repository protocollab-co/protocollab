"""Shared helpers for protocollab code generators."""

import re


def to_class_name(identifier: str) -> str:
    """Convert a protocol identifier into a Python class name."""
    parts = re.split(r"[^0-9a-zA-Z]+", str(identifier))
    return "".join(part[:1].upper() + part[1:] for part in parts if part)
