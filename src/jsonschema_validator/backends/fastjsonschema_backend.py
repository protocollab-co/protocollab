"""fastjsonschema backend for jsonschema_validator.

Uses the ``fastjsonschema`` library for high-performance validation.

.. warning::
   ``fastjsonschema`` compiles a schema to Python source code and evaluates it
   with ``exec``.  This makes it unsuitable for validating **untrusted schemas**.
   Always use the default ``jsonscreamer`` or ``jsonschema`` backend (or
   ``auto``) when the schema originates from an untrusted source.

   This backend is **never** selected by ``auto`` mode; you must opt in
   explicitly by passing ``backend="fastjsonschema"`` to
   :class:`~jsonschema_validator.factory.ValidatorFactory`.

This module is an **optional** backend: if ``fastjsonschema`` is not installed,
constructing :class:`FastjsonschemaBackend` directly will raise
:class:`ImportError`. When used via :mod:`jsonschema_validator.factory`, a
missing dependency is surfaced as
:class:`~jsonschema_validator.factory.BackendNotAvailableError`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from jsonschema import Draft7Validator

from jsonschema_validator.backends.base import AbstractSchemaValidator
from jsonschema_validator.backends.jsonschema_backend import _format_path, _format_schema_path
from jsonschema_validator.models import SchemaValidationError


class FastjsonschemaBackend(AbstractSchemaValidator):
    """JSON Schema validation backed by ``fastjsonschema``.

    Compiled validators are cached by schema object identity when *cache* is
    ``True`` (default). To preserve the project-wide validator contract of
    collecting all errors in one full pass, invalid payloads fall back to a
    ``jsonschema`` validation sweep after the fast precompiled validator
    reports a failure.

    Parameters
    ----------
    cache:
        Cache compiled validators by schema identity.  Defaults to ``True``.

    Raises
    ------
    ImportError
        If ``fastjsonschema`` is not installed.
    """

    def __init__(self, cache: bool = True) -> None:
        try:
            import fastjsonschema  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "The 'fastjsonschema' package is required for the fastjsonschema backend. "
                "Install it with: pip install fastjsonschema"
            ) from exc
        self._fastjsonschema = __import__("fastjsonschema")
        self._cache: dict[int, Any] = {}
        self._jsonschema_cache: dict[int, Draft7Validator] = {}
        self._cache_enabled = cache

    def validate(
        self,
        schema: Dict[str, Any],
        data: Any,
    ) -> List[SchemaValidationError]:
        """Validate *data* against *schema* using ``fastjsonschema``."""
        compiled = self._get_compiled(schema)
        try:
            compiled(data)
        except self._fastjsonschema.JsonSchemaValueException:
            return self._collect_all_errors(schema, data)
        return []

    def _collect_all_errors(
        self,
        schema: Dict[str, Any],
        data: Any,
    ) -> List[SchemaValidationError]:
        validator = self._get_jsonschema_validator(schema)
        return [
            SchemaValidationError(
                path=_format_path(err),
                message=err.message,
                schema_path=_format_schema_path(err),
            )
            for err in sorted(validator.iter_errors(data), key=lambda err: list(err.absolute_path))
        ]

    def _get_compiled(self, schema: Dict[str, Any]) -> Any:
        if not self._cache_enabled:
            return self._fastjsonschema.compile(schema)
        key = id(schema)
        if key not in self._cache:
            self._cache[key] = self._fastjsonschema.compile(schema)
        return self._cache[key]

    def _get_jsonschema_validator(self, schema: Dict[str, Any]) -> Draft7Validator:
        if not self._cache_enabled:
            return Draft7Validator(schema)
        key = id(schema)
        if key not in self._jsonschema_cache:
            self._jsonschema_cache[key] = Draft7Validator(schema)
        return self._jsonschema_cache[key]
