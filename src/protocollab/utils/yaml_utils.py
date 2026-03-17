"""YAML serialization helpers for `protocollab` output."""

import io
import json
import sys
from typing import Any

from ruamel.yaml import YAML


def to_json(data: Any, indent: int = 2) -> str:
    """Serialise *data* to a JSON string."""
    return json.dumps(data, indent=indent, ensure_ascii=False)


def to_yaml(data: Any) -> str:
    """Serialise *data* to a YAML string (ruamel round-trip)."""
    y = YAML()
    y.default_flow_style = False
    buf = io.StringIO()
    y.dump(data, buf)
    return buf.getvalue()


def print_data(data: Any, output_format: str = "yaml") -> None:
    """Print *data* to stdout in the requested format (``"json"`` or ``"yaml"``)."""
    if output_format == "json":
        print(to_json(data))
    else:
        text = to_yaml(data)
        sys.stdout.write(text)
