"""AST node definitions for `protocollab` expression language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

# ---------------------------------------------------------------------------
# Type alias for any AST node
# ---------------------------------------------------------------------------
ASTNode = Union[
    "Literal",
    "Name",
    "Attribute",
    "Subscript",
    "UnaryOp",
    "BinOp",
    "Ternary",
]


# ---------------------------------------------------------------------------
# Leaf nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Literal:
    """An integer, string, or boolean literal value.

    Examples: ``42``, ``"hello"``, ``true``, ``false``, ``0xFF``.
    """

    value: Any  # int | str | bool


@dataclass(frozen=True)
class Name:
    """A bare identifier that looks up a value in the evaluation context.

    Examples: ``length``, ``_io``, ``parent``.
    """

    name: str


# ---------------------------------------------------------------------------
# Compound nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Attribute:
    """Dotted attribute access: ``parent.field_name``.

    Attributes
    ----------
    obj:
        The object expression (typically a :class:`Name`).
    attr:
        The attribute name string.
    """

    obj: ASTNode
    attr: str


@dataclass(frozen=True)
class Subscript:
    """Indexing: ``arr[0]``, ``arr[-1]``.

    Attributes
    ----------
    obj:
        The sequence expression.
    index:
        The index expression.
    """

    obj: ASTNode
    index: ASTNode


@dataclass(frozen=True)
class UnaryOp:
    """Unary prefix operator: ``-x``, ``not flag``.

    Attributes
    ----------
    op:
        Operator string: ``"-"`` or ``"not"``.
    operand:
        The operand expression.
    """

    op: str  # "-" | "not"
    operand: ASTNode


@dataclass(frozen=True)
class BinOp:
    """Binary infix operator.

    Attributes
    ----------
    left, right:
        Operand expressions.
    op:
        Operator string: ``"+"``, ``"-"``, ``"*"``, ``"/"``, ``"//"``,
        ``"%"``, ``"=="``, ``"!="``, ``"<"``, ``">"``, ``"<="``, ``">="``
        ``"and"``, ``"or"``.
    """

    left: ASTNode
    op: str
    right: ASTNode


@dataclass(frozen=True)
class Ternary:
    """Python-style ternary: ``value_if_true if condition else value_if_false``.

    In Kaitai-like specs this appears as::

        size: total_length - 8 if has_ext else fixed_size
    """

    condition: ASTNode
    value_if_true: ASTNode
    value_if_false: ASTNode
