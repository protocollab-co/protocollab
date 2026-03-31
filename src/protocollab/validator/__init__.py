"""Validation subsystem for `protocollab` protocol specifications."""

from typing import Optional

from protocollab.exceptions import FileLoadError, YAMLParseError
from protocollab.loader import load_protocol
from protocollab.validator.models import (
    PipelineResult,
    ValidationError,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)
from protocollab.validator.pipeline import ValidationPipeline
from protocollab.validator.schema_validator import SchemaValidator

__all__ = [
    # legacy structural API
    "validate_protocol",
    "ValidationResult",
    "ValidationError",
    "SchemaValidator",
    # pipeline API
    "validate_pipeline",
    "ValidationPipeline",
    "PipelineResult",
    "ValidationIssue",
    "ValidationLevel",
    # re-exported exceptions
    "FileLoadError",
    "YAMLParseError",
]


def validate_protocol(
    file_path: str,
    schema_path: Optional[str] = None,
) -> ValidationResult:
    """Load and structurally validate a protocol YAML file.

    Parameters
    ----------
    file_path:
        Path to the root protocol YAML file.
    schema_path:
        Optional path to a custom JSON Schema.  Defaults to
        ``validator/schemas/base.schema.json``.

    Returns
    -------
    ValidationResult
        Contains ``is_valid``, ``errors`` (list of :class:`ValidationError`),
        and ``file_path``.

    Raises
    ------
    FileLoadError
        When the file cannot be opened.
    YAMLParseError
        When the file contains invalid YAML.
    """
    data = load_protocol(file_path)
    validator = SchemaValidator(schema_path=schema_path)
    errors = validator.validate(data)
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        file_path=file_path,
    )


def validate_pipeline(
    file_path: str,
    schema_path: Optional[str] = None,
) -> PipelineResult:
    """Run the full multi-stage validation pipeline on *file_path*.

    Stages
    ------
    1. Structural (JSON Schema)
    2. Semantic (type resolution, duplicate ids)
    3. Expression (``if:`` / ``repeat-expr:`` syntax)

    Parameters
    ----------
    file_path:
        Path to the root protocol YAML file.
    schema_path:
        Optional path to a custom JSON Schema.

    Returns
    -------
    PipelineResult
        Contains ``errors``, ``warnings``, ``is_valid``, and ``file_path``.

    Raises
    ------
    FileLoadError
        When the file cannot be opened.
    YAMLParseError
        When the file contains invalid YAML.
    """
    from pathlib import Path as _Path

    from pydantic import ValidationError as _PydanticError

    from protocollab.core import ImportResolver, parse_spec

    raw_data = load_protocol(file_path)

    # Convert Pydantic structural errors into PipelineResult errors so callers
    # always get a PipelineResult back (never a raw Pydantic exception).
    try:
        if raw_data.get("imports"):
            spec = ImportResolver().resolve(_Path(file_path))
        else:
            spec = parse_spec(raw_data)
    except _PydanticError as exc:
        errors = [
            ValidationIssue(
                path=".".join(str(loc) for loc in e["loc"]) or "(root)",
                message=e["msg"],
                level=ValidationLevel.ERROR,
                code="E0",
            )
            for e in exc.errors()
        ]
        return PipelineResult(errors=errors, file_path=file_path)

    pipeline = ValidationPipeline(schema_path=schema_path)
    return pipeline.run(spec, raw_data=raw_data, file_path=file_path)
