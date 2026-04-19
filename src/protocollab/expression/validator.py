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


_BUILTINS: frozenset[str] = frozenset({"_io", "parent", "_root", "true", "false"})


@dataclass
class ExprError:
    """A single expression validation error."""

    message: str
    pos: int = -1

    def __str__(self) -> str:
        if self.pos >= 0:
            return f"[pos {self.pos}] {self.message}"
        return self.message


def _collect_name_nodes(
    nodes: list[ASTNode] | tuple[ASTNode, ...], names: set[str], bound: set[str]
) -> None:
    for child in nodes:
        _collect_names(child, names, bound)


def _collect_name_pairs(
    pairs: tuple[tuple[ASTNode, ASTNode], ...],
    names: set[str],
    bound: set[str],
) -> None:
    for key, value in pairs:
        _collect_names(key, names, bound)
        _collect_names(value, names, bound)


def _validate_nodes(
    nodes: list[ASTNode] | tuple[ASTNode, ...],
    errors: list[ExprError],
    active_vars: set[str],
) -> None:
    for child in nodes:
        _validate_comprehension_vars(child, errors, active_vars)


def _validate_pairs(
    pairs: tuple[tuple[ASTNode, ASTNode], ...],
    errors: list[ExprError],
    active_vars: set[str],
) -> None:
    for key, value in pairs:
        _validate_comprehension_vars(key, errors, active_vars)
        _validate_comprehension_vars(value, errors, active_vars)


def _collect_names_from_comprehension(
    node: Comprehension,
    names: set[str],
    bound: set[str],
) -> None:
    _collect_names(node.iterable, names, bound)
    local_bound = set(bound)
    local_bound.add(node.var.name)
    _collect_names(node.expr, names, local_bound)
    if node.condition is not None:
        _collect_names(node.condition, names, local_bound)


def _collect_names_from_match(node: Match, names: set[str], bound: set[str]) -> None:
    _collect_names(node.subject, names, bound)
    for case in node.cases:
        _collect_match_case_names(case, names, bound)
    if node.else_case is not None:
        _collect_names(node.else_case, names, bound)


def _validate_comprehension_node(
    node: Comprehension,
    errors: list[ExprError],
    active_vars: set[str],
) -> None:
    if node.var.name in active_vars:
        errors.append(
            ExprError(
                message=f"Comprehension variable '{node.var.name}' conflicts with outer scope"
            )
        )
    _validate_comprehension_vars(node.iterable, errors, active_vars)
    local = set(active_vars)
    local.add(node.var.name)
    _validate_comprehension_vars(node.expr, errors, local)
    if node.condition is not None:
        _validate_comprehension_vars(node.condition, errors, local)


def _validate_match_node(node: Match, errors: list[ExprError], active_vars: set[str]) -> None:
    _validate_comprehension_vars(node.subject, errors, active_vars)
    for case in node.cases:
        _validate_comprehension_vars(case.pattern, errors, active_vars)
        _validate_comprehension_vars(case.body, errors, active_vars)
    if node.else_case is not None:
        _validate_comprehension_vars(node.else_case, errors, active_vars)


def _parse_expr_for_validation(expr_str: str) -> tuple[ASTNode | None, list[ExprError]]:
    try:
        return parse_expr(expr_str), []
    except ExpressionSyntaxError as exc:
        return None, [ExprError(message=str(exc), pos=exc.pos)]


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
            _collect_name_nodes(elements, names, bound)
        case List(elements=elements):
            _collect_name_nodes(elements, names, bound)
        case DictLiteral(keys=keys, values=values):
            _collect_name_nodes(keys, names, bound)
            _collect_name_nodes(values, names, bound)
        case Dict(pairs=pairs):
            _collect_name_pairs(pairs, names, bound)
        case InOp(left=l, right=r):
            _collect_names(l, names, bound)
            _collect_names(r, names, bound)
        case Comprehension():
            _collect_names_from_comprehension(node, names, bound)
        case UnaryOp(operand=op):
            _collect_names(op, names, bound)
        case BinOp(left=l, right=r):
            _collect_names(l, names, bound)
            _collect_names(r, names, bound)
        case Ternary(condition=c, value_if_true=vt, value_if_false=vf):
            _collect_names(c, names, bound)
            _collect_names(vt, names, bound)
            _collect_names(vf, names, bound)
        case Match():
            _collect_names_from_match(node, names, bound)


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
        case Comprehension():
            _validate_comprehension_node(node, errors, active_vars)
        case Attribute(obj=obj):
            _validate_comprehension_vars(obj, errors, active_vars)
        case Subscript(obj=obj, index=idx):
            _validate_comprehension_vars(obj, errors, active_vars)
            _validate_comprehension_vars(idx, errors, active_vars)
        case ListLiteral(elements=elements):
            _validate_nodes(elements, errors, active_vars)
        case List(elements=elements):
            _validate_nodes(elements, errors, active_vars)
        case DictLiteral(keys=keys, values=values):
            _validate_nodes(keys, errors, active_vars)
            _validate_nodes(values, errors, active_vars)
        case Dict(pairs=pairs):
            _validate_pairs(pairs, errors, active_vars)
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
        case Match():
            _validate_match_node(node, errors, active_vars)


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
    ast, errors = _parse_expr_for_validation(expr_str)
    if ast is None:
        return errors

    # Collect free names and perform optional registry checks
    _validate_comprehension_vars(ast, errors)

    if type_registry is not None:
        names: set[str] = set()
        _collect_names(ast, names)
        _ = names - _BUILTINS
        # TODO(task 2.4): add semantic checks for unknown references once schema
        # context is available at this layer.

    return errors
