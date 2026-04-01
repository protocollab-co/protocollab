"""JSON Schema-based structural validator for protocol specifications."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema_validator import ValidatorFactory

from protocollab.validator.models import ValidationError

_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_DEFAULT_SCHEMA_PATH = _SCHEMAS_DIR / "base.schema.json"


class SchemaValidator:
    """Validates a protocol data dict against a JSON Schema.

    Uses the :class:`~jsonschema_validator.ValidatorFactory` facade so that
    the underlying JSON Schema library can be swapped via *backend* without
    changing call sites.  All backend implementations collect **all** errors
    in a single full validation pass before returning.

    Parameters
    ----------
    schema_path:
        Path to a custom JSON Schema file.  Defaults to ``base.schema.json``.
    backend:
        JSON Schema backend to use — ``"auto"`` (default), ``"jsonscreamer"``,
        ``"jsonschema"``, or ``"fastjsonschema"``.  ``"auto"`` selects the
        best available safe backend.
    """

    def __init__(
        self,
        schema_path: Optional[str] = None,
        backend: str = "auto",
    ) -> None:
        path = Path(schema_path) if schema_path else _DEFAULT_SCHEMA_PATH
        with open(path, encoding="utf-8") as fh:
            self._schema: Dict[str, Any] = json.load(fh)
        factory = ValidatorFactory()
        self._backend = factory.get_or_create(backend)

    def validate(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Return a list of :class:`ValidationError` for *data* (empty = valid).

        All errors from the full validation pass are collected and returned —
        no early exit on first failure.
        """
        raw_errors = self._backend.validate(self._schema, data)
        return [
            ValidationError(
                path=e.path,
                message=e.message,
                schema_path=e.schema_path,
            )
            for e in raw_errors
        ]
