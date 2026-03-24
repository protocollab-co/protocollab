"""Expression validation — checks ``if:`` and ``size:`` expression syntax."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from protocollab.expression import validate_expr
from protocollab.validator.base_validator import BaseValidator
from protocollab.validator.models import ValidationIssue, ValidationLevel

if TYPE_CHECKING:
    from protocollab.core.models import FieldDef, ProtocolSpec


def _check_field_exprs(
    fields: list["FieldDef"],
    context_path: str,
    issues: List[ValidationIssue],
) -> None:
    """Validate ``if_expr`` and ``size`` expressions in *fields*."""
    for idx, field in enumerate(fields):
        if field.if_expr:
            errs = validate_expr(field.if_expr)
            for err in errs:
                issues.append(
                    ValidationIssue(
                        path=f"{context_path}[{idx}].if",
                        message=f"Syntax error in expression {field.if_expr!r}: {err}",
                        level=ValidationLevel.ERROR,
                        code="E3",
                    )
                )
        if field.repeat_expr:
            errs = validate_expr(field.repeat_expr)
            for err in errs:
                issues.append(
                    ValidationIssue(
                        path=f"{context_path}[{idx}].repeat-expr",
                        message=f"Syntax error in expression {field.repeat_expr!r}: {err}",
                        level=ValidationLevel.ERROR,
                        code="E3",
                    )
                )


class ExpressionValidator(BaseValidator):
    """Validate expression syntax in ``if:`` and ``repeat-expr:`` fields.

    Walks all ``seq`` fields in the root spec and in every user-defined type,
    calling :func:`~protocollab.expression.validate_expr` on each expression.
    """

    def validate(self, spec: "ProtocolSpec") -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        _check_field_exprs(spec.seq, "seq", issues)
        for type_name, type_def in spec.types.items():
            _check_field_exprs(type_def.seq, f"types.{type_name}.seq", issues)
        return issues
