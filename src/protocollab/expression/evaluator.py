"""Evaluate a parsed AST in a field-value context."""

from __future__ import annotations

import operator
from typing import Any, Callable

from protocollab.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Literal,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
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
            obj_val = evaluate(obj_node, context)
            if isinstance(obj_val, dict):
                if attr not in obj_val:
                    raise ExpressionEvalError(f"Attribute {attr!r} not found in {obj_val!r}")
                return obj_val[attr]
            try:
                return getattr(obj_val, attr)
            except AttributeError:
                raise ExpressionEvalError(f"Object {obj_val!r} has no attribute {attr!r}")

        case Subscript(obj=obj_node, index=idx_node):
            obj_val = evaluate(obj_node, context)
            idx_val = evaluate(idx_node, context)
            try:
                return obj_val[idx_val]
            except (IndexError, KeyError, TypeError) as exc:
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
            fn = _BINOP_TABLE.get(op)
            if fn is None:
                raise ExpressionEvalError(f"Unknown operator {op!r}")
            lval = evaluate(left, context)
            rval = evaluate(right, context)
            try:
                return fn(lval, rval)
            except ZeroDivisionError:
                raise ExpressionEvalError("Division by zero")
            except TypeError as exc:
                raise ExpressionEvalError(str(exc))

        case Ternary(condition=cond, value_if_true=vt, value_if_false=vf):
            if evaluate(cond, context):
                return evaluate(vt, context)
            return evaluate(vf, context)

        case _:
            raise ExpressionEvalError(f"Unknown AST node type: {type(node)!r}")
