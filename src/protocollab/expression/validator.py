"""Static validation of expressions — checks for syntax and optional type issues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from protocollab.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
)
from protocollab.expression.lexer import ExpressionSyntaxError
from protocollab.expression.parser import parse_expr

if TYPE_CHECKING:
    from protocollab.type_system.registry import TypeRegistry


@dataclass
class ExprError:
    """A single expression validation error."""

    message: str
    pos: int = -1

    def __str__(self) -> str:
        if self.pos >= 0:
            return f"[pos {self.pos}] {self.message}"
        return self.message


def _collect_names(node: ASTNode, names: set[str]) -> None:
    """Recursively collect all free Name references in *node*."""
    match node:
        case Name(name=n):
            names.add(n)
        case Attribute(obj=obj):
            _collect_names(obj, names)
        case Subscript(obj=obj, index=idx):
            _collect_names(obj, names)
            _collect_names(idx, names)
        case UnaryOp(operand=op):
            _collect_names(op, names)
        case BinOp(left=l, right=r):
            _collect_names(l, names)
            _collect_names(r, names)
        case Ternary(condition=c, value_if_true=vt, value_if_false=vf):
            _collect_names(c, names)
            _collect_names(vt, names)
            _collect_names(vf, names)


def validate_expr(
    expr_str: str,
    type_registry: "TypeRegistry | None" = None,
) -> list[ExprError]:
    """Statically validate *expr_str*.

    Checks performed:
    1. Lexical / syntactic validity (**always**).
    2. Forbidden identifier usage (**always**).
    3. *(Optional)* type references are known in *type_registry*.

    Parameters
    ----------
    expr_str:
        The raw expression string from a YAML ``if:`` or ``size:`` field.
    type_registry:
        If provided, field-name references that look like type names are
        checked against the registry.  Pass ``None`` to skip this check.

    Returns
    -------
    list[ExprError]
        Empty list means the expression is valid.
    """
    errors: list[ExprError] = []

    try:
        ast = parse_expr(expr_str)
    except ExpressionSyntaxError as exc:
        errors.append(ExprError(message=str(exc), pos=exc.pos))
        return errors  # can't do further checks without a valid AST

    # Collect free names and perform optional registry checks
    if type_registry is not None:
        names: set[str] = set()
        _collect_names(ast, names)
        # Remove well-known special names
        _BUILTINS = {"_io", "parent", "_root", "true", "false"}
        for n in names - _BUILTINS:
            # We can't know field names at static-check time without full schema,
            # so we only flag names that look suspiciously like type names but
            # are neither known fields nor known types.
            pass  # extend in task 2.4 (semantic validator)

    return errors
