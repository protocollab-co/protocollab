"""JSON Schema-based structural validator for protocol specifications."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from jsonschema import Draft7Validator

from protocollab.validator.models import ValidationError

_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_DEFAULT_SCHEMA_PATH = _SCHEMAS_DIR / "base.schema.json"


def _format_path(error: jsonschema.ValidationError) -> str:
    """Convert a jsonschema error path to dot-notation string."""
    parts: list[str] = []
    for segment in error.absolute_path:
        if isinstance(segment, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
        else:
            parts.append(str(segment))
    return ".".join(parts) if parts else "(root)"


def _format_schema_path(error: jsonschema.ValidationError) -> str:
    return "/".join(str(s) for s in error.absolute_schema_path)


class SchemaValidator:
    """Validates a protocol data dict against a JSON Schema.

    Parameters
    ----------
    schema_path:
        Path to a custom JSON Schema file.  Defaults to ``base.schema.json``.
    """

    def __init__(self, schema_path: Optional[str] = None) -> None:
        path = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
        with open(path, encoding="utf-8") as fh:
            self._schema: Dict[str, Any] = json.load(fh)
        self._validator = Draft7Validator(self._schema)

    def validate(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Return a list of :class:`ValidationError` for *data* (empty = valid)."""
        errors: List[ValidationError] = []
        for err in sorted(self._validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
            errors.append(
                ValidationError(
                    path=_format_path(err),
                    message=err.message,
                    schema_path=_format_schema_path(err),
                )
            )
        return errors
