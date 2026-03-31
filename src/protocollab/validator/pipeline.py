"""Validation pipeline — orchestrates all validators in sequence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from protocollab.validator.base_validator import BaseValidator
from protocollab.validator.expression_validator import ExpressionValidator
from protocollab.validator.models import (
    PipelineResult,
    ValidationIssue,
    ValidationLevel,
)
from protocollab.validator.schema_validator import SchemaValidator
from protocollab.validator.semantic_validator import SemanticValidator

if TYPE_CHECKING:
    from protocollab.core.models import ProtocolSpec


class _SchemaValidatorAdapter(BaseValidator):
    """Adapts the existing :class:`SchemaValidator` (dict-based) to the ABC."""

    def __init__(self, schema_path: Optional[str] = None) -> None:
        self._inner = SchemaValidator(schema_path=schema_path)
        self._last_data: Optional[Dict[str, Any]] = None

    def set_raw_data(self, data: Dict[str, Any]) -> None:
        self._last_data = data

    def validate(self, spec: "ProtocolSpec") -> List[ValidationIssue]:
        """Convert SchemaValidator errors to ValidationIssue list."""
        if self._last_data is None:
            return []
        errors = self._inner.validate(self._last_data)
        return [
            ValidationIssue(
                path=e.path,
                message=e.message,
                level=ValidationLevel.ERROR,
                code="E0",
            )
            for e in errors
        ]


class ValidationPipeline:
    """Run multiple :class:`BaseValidator` instances and aggregate results.

    The default pipeline is:

    1. :class:`~protocollab.validator.schema_validator.SchemaValidator` (structural)
    2. :class:`~protocollab.validator.semantic_validator.SemanticValidator`
    3. :class:`~protocollab.validator.expression_validator.ExpressionValidator`

    All validators run even if earlier ones find errors — all issues are
    collected before returning.

    Parameters
    ----------
    validators:
        Override the default validator list.  Each must implement
        :class:`BaseValidator`.
    schema_path:
        Optional path to a custom JSON Schema (passed to the structural
        validator when using the default pipeline).
    """

    def __init__(
        self,
        validators: Optional[List[BaseValidator]] = None,
        schema_path: Optional[str] = None,
    ) -> None:
        if validators is not None:
            self.validators: List[BaseValidator] = validators
        else:
            self._schema_adapter = _SchemaValidatorAdapter(schema_path)
            self.validators = [
                self._schema_adapter,
                SemanticValidator(),
                ExpressionValidator(),
            ]

    def run(
        self,
        spec: "ProtocolSpec",
        raw_data: Optional[Dict[str, Any]] = None,
        file_path: str = "",
    ) -> PipelineResult:
        """Execute all validators against *spec* and return aggregated results.

        Parameters
        ----------
        spec:
            Fully-parsed :class:`~protocollab.core.models.ProtocolSpec`.
        raw_data:
            Raw YAML data dict (needed by the structural validator).
        file_path:
            Source file path stored in :attr:`PipelineResult.file_path`.
        """
        # Feed raw data to the schema adapter if present
        if raw_data is not None and hasattr(self, "_schema_adapter"):
            self._schema_adapter.set_raw_data(raw_data)

        all_issues: List[ValidationIssue] = []
        for validator in self.validators:
            all_issues.extend(validator.validate(spec))

        errors = [i for i in all_issues if i.level == ValidationLevel.ERROR]
        warnings = [i for i in all_issues if i.level == ValidationLevel.WARNING]

        return PipelineResult(errors=errors, warnings=warnings, file_path=file_path)
