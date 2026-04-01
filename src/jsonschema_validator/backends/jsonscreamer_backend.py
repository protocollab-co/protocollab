"""jsonscreamer backend for jsonschema_validator.

Uses the ``jsonscreamer`` library for validation. The ``jsonscreamer``
``Validator`` provides a ``jsonschema``-compatible interface (``iter_errors``,
``absolute_path``, ``message``), making it a drop-in replacement that can be
safely used with untrusted schemas.

This backend is included in the ``auto`` priority list and is preferred over
``jsonschema`` when available, since it offers the same safety guarantees with
improved performance.

This module is an **optional** backend: if ``jsonscreamer`` is not installed,
constructing :class:`JsonscreamerBackend` directly will raise ``ImportError``.
When used via :mod:`jsonschema_validator.factory`, a missing dependency is
surfaced as
:class:`~jsonschema_validator.factory.BackendNotAvailableError`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List

from jsonschema_validator.backends.base import AbstractSchemaValidator
from jsonschema_validator.models import SchemaValidationError


def _format_path(path: list) -> str:
    """Convert a jsonscreamer absolute_path list to dot-notation string."""
    parts: list[str] = []
    for segment in path:
        if isinstance(segment, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{segment}]"
            else:
                parts.append(f"[{segment}]")
        else:
            parts.append(str(segment))
    return ".".join(parts) if parts else "(root)"


def _format_schema_path(path: Any) -> str:
    if not path:
        return ""
    return "/".join(str(segment) for segment in path)


@contextmanager
def _suppress_jsonscreamer_warnings(jsonscreamer_module: Any) -> Any:
    """Temporarily mute jsonscreamer's unsupported-format warning hook."""
    warning_func = jsonscreamer_module.basic._logging.warning
    jsonscreamer_module.basic._logging.warning = lambda *args, **kwargs: None
    try:
        yield
    finally:
        jsonscreamer_module.basic._logging.warning = warning_func


def _create_jsonscreamer_validator(jsonscreamer_module: Any, schema: Dict[str, Any]) -> Any:
    """Construct a ``jsonscreamer.Validator``, suppressing its format-warning noise.

    ``jsonscreamer`` emits ``logging.warning()`` for JSON Schema format keywords
    it does not support (e.g. ``uri``, ``uri-reference``). These warnings are
    harmless for protocollab schemas but interact badly with Click's test-runner
    stream capture. They are suppressed here by temporarily replacing only the
    warning hook used by ``jsonscreamer.basic`` during construction.
    """
    with _suppress_jsonscreamer_warnings(jsonscreamer_module):
        return jsonscreamer_module.Validator(schema)


class JsonscreamerBackend(AbstractSchemaValidator):
    """JSON Schema validation backed by the ``jsonscreamer`` library.

    ``jsonscreamer`` provides a ``jsonschema``-compatible interface, making it
    a safe drop-in that can be used with untrusted schemas. Validators are
    cached per schema object identity when *cache* is ``True`` (default).

    Parameters
    ----------
    cache:
        When ``True`` (default) ``Validator`` instances are cached by schema
        object identity. Set to ``False`` to always create a fresh instance.

    Raises
    ------
    ImportError
        If ``jsonscreamer`` is not installed.
    """

    def __init__(self, cache: bool = True) -> None:
        try:
            import jsonscreamer  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "The 'jsonscreamer' package is required for the jsonscreamer backend. "
                "Install it with: pip install jsonscreamer"
            ) from exc
        self._jsonscreamer = __import__("jsonscreamer")
        self._cache: dict[int, Any] = {}
        self._cache_enabled = cache

    def validate(
        self,
        schema: Dict[str, Any],
        data: Any,
    ) -> List[SchemaValidationError]:
        """Validate *data* against *schema* using ``jsonscreamer``."""
        validator = self._get_validator(schema)
        errors: List[SchemaValidationError] = []
        for err in validator.iter_errors(data):
            errors.append(
                SchemaValidationError(
                    path=_format_path(list(err.absolute_path)),
                    message=err.message,
                    schema_path=_format_schema_path(getattr(err, "absolute_schema_path", None)),
                )
            )
        return errors

    def _get_validator(self, schema: Dict[str, Any]) -> Any:
        if not self._cache_enabled:
            return _create_jsonscreamer_validator(self._jsonscreamer, schema)
        key = id(schema)
        if key not in self._cache:
            self._cache[key] = _create_jsonscreamer_validator(self._jsonscreamer, schema)
        return self._cache[key]
