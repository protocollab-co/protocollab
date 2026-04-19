"""Evaluate a parsed AST in a field-value context."""

from __future__ import annotations

import operator
from typing import Any, Callable

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
    Literal,
    Match,
    MatchCase,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
    Wildcard,
)


class ExpressionEvalError(Exception):
    """Raised when expression evaluation fails at runtime.

    Examples: division by zero, missing field name, type error.

    Attributes
    ----------
    expr_source:
        The original expression string (if available).
    """

    def __init__(self, message: str, expr_source: str = "") -> None:
        self.expr_source = expr_source
        super().__init__(message)


# ---------------------------------------------------------------------------
# Operator dispatch table
# ---------------------------------------------------------------------------
_BINOP_TABLE: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "//": operator.floordiv,
    "%": operator.mod,
    "<<": operator.lshift,
    ">>": operator.rshift,
    "&": operator.and_,
    "^": operator.xor,
    "|": operator.or_,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}


def _evaluate_sequence(
    elements: list[ASTNode] | tuple[ASTNode, ...], context: dict[str, Any]
) -> list[Any]:
    return [evaluate(element, context) for element in elements]


def _evaluate_dict_pairs(
    pairs: list[tuple[ASTNode, ASTNode]] | tuple[tuple[ASTNode, ASTNode], ...],
    context: dict[str, Any],
) -> dict[Any, Any]:
    out: dict[Any, Any] = {}
    for key_node, value_node in pairs:
        key = evaluate(key_node, context)
        try:
            hash(key)
        except TypeError as exc:
            raise ExpressionEvalError(f"Unhashable dict key {key!r}: {exc}")
        out[key] = evaluate(value_node, context)
    return out


def _iter_comprehension_contexts(
    iterable_value: Any,
    var_name: str,
    context: dict[str, Any],
) -> Any:
    try:
        iterator = iter(iterable_value)
    except TypeError as exc:
        raise ExpressionEvalError(f"Object is not iterable: {iterable_value!r} ({exc})")

    for item in iterator:
        local_ctx = dict(context)
        local_ctx[var_name] = item
        yield item, local_ctx


def _evaluate_comprehension(node: Comprehension, context: dict[str, Any]) -> Any:
    iterable_value = evaluate(node.iterable, context)

    if node.kind == "any":
        for _, local_ctx in _iter_comprehension_contexts(iterable_value, node.var.name, context):
            if node.condition is not None and not evaluate(node.condition, local_ctx):
                continue
            if evaluate(node.expr, local_ctx):
                return True
        return False

    if node.kind == "all":
        for _, local_ctx in _iter_comprehension_contexts(iterable_value, node.var.name, context):
            if node.condition is not None and not evaluate(node.condition, local_ctx):
                continue
            if not evaluate(node.expr, local_ctx):
                return False
        return True

    if node.kind == "first":
        for _, local_ctx in _iter_comprehension_contexts(iterable_value, node.var.name, context):
            if node.condition is not None and not evaluate(node.condition, local_ctx):
                continue
            return evaluate(node.expr, local_ctx)
        return None

    if node.kind == "filter":
        result: list[Any] = []
        for item, local_ctx in _iter_comprehension_contexts(iterable_value, node.var.name, context):
            if node.condition is not None and not evaluate(node.condition, local_ctx):
                continue
            if evaluate(node.expr, local_ctx):
                result.append(item)
        return result

    if node.kind == "map":
        result = []
        for _, local_ctx in _iter_comprehension_contexts(iterable_value, node.var.name, context):
            if node.condition is not None and not evaluate(node.condition, local_ctx):
                continue
            result.append(evaluate(node.expr, local_ctx))
        return result

    raise ExpressionEvalError(f"Unsupported comprehension kind {node.kind!r}")


def _evaluate_attribute(node: Attribute, context: dict[str, Any]) -> Any:
    obj_val = evaluate(node.obj, context)
    if isinstance(obj_val, dict):
        if node.attr not in obj_val:
            raise ExpressionEvalError(f"Attribute {node.attr!r} not found in {obj_val!r}")
        return obj_val[node.attr]
    try:
        return getattr(obj_val, node.attr)
    except AttributeError:
        raise ExpressionEvalError(f"Object {obj_val!r} has no attribute {node.attr!r}")


def _evaluate_subscript(node: Subscript, context: dict[str, Any]) -> Any:
    obj_val = evaluate(node.obj, context)
    idx_val = evaluate(node.index, context)
    try:
        return obj_val[idx_val]
    except (IndexError, KeyError, TypeError) as exc:
        raise ExpressionEvalError(str(exc))


def _evaluate_binop(node: BinOp, context: dict[str, Any]) -> Any:
    fn = _BINOP_TABLE.get(node.op)
    if fn is None:
        raise ExpressionEvalError(f"Unknown operator {node.op!r}")

    lval = evaluate(node.left, context)
    rval = evaluate(node.right, context)
    try:
        return fn(lval, rval)
    except ZeroDivisionError:
        raise ExpressionEvalError("Division by zero")
    except TypeError as exc:
        raise ExpressionEvalError(str(exc))


def _evaluate_match(node: Match, context: dict[str, Any]) -> Any:
    subject_value = evaluate(node.subject, context)
    for case in node.cases:
        if _match_case(case, subject_value, context):
            return evaluate(case.body, context)
    if node.else_case is not None:
        return evaluate(node.else_case, context)
    return None


def evaluate(node: ASTNode, context: dict[str, Any]) -> Any:
    """Recursively evaluate *node* in the given *context*.

    Parameters
    ----------
    node:
        Root of the AST (or any sub-tree).
    context:
        A mapping of field names to their values.  Special names:
        - ``_io``: a mapping with ``size`` (total buffer size).
        - ``parent``: an optional parent context mapping.

    Returns
    -------
    Any
        The computed value (int, bool, str, …).

    Raises
    ------
    ExpressionEvalError
        On runtime errors such as division by zero, missing field, or
        unsupported operation.
    """
    match node:
        case Literal(value=v):
            return v

        case Name(name=n):
            if n not in context:
                raise ExpressionEvalError(f"Undefined field {n!r}. Available: {sorted(context)}")
            return context[n]

        case Attribute(obj=obj_node, attr=attr):
            return _evaluate_attribute(node, context)

        case Subscript(obj=obj_node, index=idx_node):
            return _evaluate_subscript(node, context)

        case ListLiteral(elements=elements):
            return _evaluate_sequence(elements, context)

        case List(elements=elements):
            return _evaluate_sequence(elements, context)

        case DictLiteral(keys=keys, values=values):
            return _evaluate_dict_pairs(list(zip(keys, values)), context)

        case Dict(pairs=pairs):
            return _evaluate_dict_pairs(pairs, context)

        case InOp(left=left, right=right):
            left_val = evaluate(left, context)
            right_val = evaluate(right, context)
            try:
                return left_val in right_val
            except TypeError as exc:
                raise ExpressionEvalError(str(exc))

        case UnaryOp(op="-", operand=operand):
            val = evaluate(operand, context)
            try:
                return -val
            except TypeError:
                raise ExpressionEvalError(f"Cannot negate {val!r}")

        case UnaryOp(op="not", operand=operand):
            return not evaluate(operand, context)

        case BinOp(left=left, op=op, right=right):
            return _evaluate_binop(node, context)

        case Ternary(condition=cond, value_if_true=vt, value_if_false=vf):
            if evaluate(cond, context):
                return evaluate(vt, context)
            return evaluate(vf, context)

        case Comprehension(kind=kind, expr=expr, var=var, iterable=iterable, condition=condition):
            return _evaluate_comprehension(node, context)

        case Match(subject=subject, cases=cases, else_case=else_case):
            return _evaluate_match(node, context)

        case _:
            raise ExpressionEvalError(f"Unknown AST node type: {type(node)!r}")


def _match_case(case: MatchCase, subject_value: Any, context: dict[str, Any]) -> bool:
    if isinstance(case.pattern, Wildcard):
        return True
    return evaluate(case.pattern, context) == subject_value
