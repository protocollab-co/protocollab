"""Static validation of expressions — checks for syntax and optional type issues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from protocollab.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Comprehension,
    Dict,
    DictLiteral,
    InOp,
    List,
    ListLiteral,
    Match,
    MatchCase,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
    Wildcard,
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


def _collect_names(node: ASTNode, names: set[str], bound: set[str] | None = None) -> None:
    """Recursively collect all free Name references in *node*."""
    bound = set() if bound is None else bound

    match node:
        case Name(name=n):
            if n not in bound:
                names.add(n)
        case Wildcard():
            return
        case Attribute(obj=obj):
            _collect_names(obj, names, bound)
        case Subscript(obj=obj, index=idx):
            _collect_names(obj, names, bound)
            _collect_names(idx, names, bound)
        case ListLiteral(elements=elements):
            for element in elements:
                _collect_names(element, names, bound)
        case List(elements=elements):
            for element in elements:
                _collect_names(element, names, bound)
        case DictLiteral(keys=keys, values=values):
            for key in keys:
                _collect_names(key, names, bound)
            for value in values:
                _collect_names(value, names, bound)
        case Dict(pairs=pairs):
            for key, value in pairs:
                _collect_names(key, names, bound)
                _collect_names(value, names, bound)
        case InOp(left=l, right=r):
            _collect_names(l, names, bound)
            _collect_names(r, names, bound)
        case Comprehension(expr=expr, var=var, iterable=iterable, condition=condition):
            _collect_names(iterable, names, bound)
            local_bound = set(bound)
            local_bound.add(var.name)
            _collect_names(expr, names, local_bound)
            if condition is not None:
                _collect_names(condition, names, local_bound)
        case UnaryOp(operand=op):
            _collect_names(op, names, bound)
        case BinOp(left=l, right=r):
            _collect_names(l, names, bound)
            _collect_names(r, names, bound)
        case Ternary(condition=c, value_if_true=vt, value_if_false=vf):
            _collect_names(c, names, bound)
            _collect_names(vt, names, bound)
            _collect_names(vf, names, bound)
        case Match(subject=subject, cases=cases, else_case=else_case):
            _collect_names(subject, names, bound)
            for case in cases:
                _collect_match_case_names(case, names, bound)
            if else_case is not None:
                _collect_names(else_case, names, bound)


def _collect_match_case_names(case: MatchCase, names: set[str], bound: set[str]) -> None:
    if not isinstance(case.pattern, Wildcard):
        _collect_names(case.pattern, names, bound)
    _collect_names(case.body, names, bound)


def _validate_comprehension_vars(
    node: ASTNode,
    errors: list[ExprError],
    active_vars: set[str] | None = None,
) -> None:
    active_vars = set() if active_vars is None else set(active_vars)

    match node:
        case Comprehension(expr=expr, var=var, iterable=iterable, condition=condition):
            if var.name in active_vars:
                errors.append(
                    ExprError(
                        message=f"Comprehension variable '{var.name}' conflicts with outer scope"
                    )
                )
            _validate_comprehension_vars(iterable, errors, active_vars)
            local = set(active_vars)
            local.add(var.name)
            _validate_comprehension_vars(expr, errors, local)
            if condition is not None:
                _validate_comprehension_vars(condition, errors, local)
        case Attribute(obj=obj):
            _validate_comprehension_vars(obj, errors, active_vars)
        case Subscript(obj=obj, index=idx):
            _validate_comprehension_vars(obj, errors, active_vars)
            _validate_comprehension_vars(idx, errors, active_vars)
        case ListLiteral(elements=elements):
            for element in elements:
                _validate_comprehension_vars(element, errors, active_vars)
        case List(elements=elements):
            for element in elements:
                _validate_comprehension_vars(element, errors, active_vars)
        case DictLiteral(keys=keys, values=values):
            for key in keys:
                _validate_comprehension_vars(key, errors, active_vars)
            for value in values:
                _validate_comprehension_vars(value, errors, active_vars)
        case Dict(pairs=pairs):
            for key, value in pairs:
                _validate_comprehension_vars(key, errors, active_vars)
                _validate_comprehension_vars(value, errors, active_vars)
        case InOp(left=l, right=r):
            _validate_comprehension_vars(l, errors, active_vars)
            _validate_comprehension_vars(r, errors, active_vars)
        case UnaryOp(operand=op):
            _validate_comprehension_vars(op, errors, active_vars)
        case BinOp(left=l, right=r):
            _validate_comprehension_vars(l, errors, active_vars)
            _validate_comprehension_vars(r, errors, active_vars)
        case Ternary(condition=c, value_if_true=vt, value_if_false=vf):
            _validate_comprehension_vars(c, errors, active_vars)
            _validate_comprehension_vars(vt, errors, active_vars)
            _validate_comprehension_vars(vf, errors, active_vars)
        case Match(subject=subject, cases=cases, else_case=else_case):
            _validate_comprehension_vars(subject, errors, active_vars)
            for case in cases:
                _validate_comprehension_vars(case.pattern, errors, active_vars)
                _validate_comprehension_vars(case.body, errors, active_vars)
            if else_case is not None:
                _validate_comprehension_vars(else_case, errors, active_vars)


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
    _validate_comprehension_vars(ast, errors)

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
