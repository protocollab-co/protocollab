"""AST node definitions for `protocollab` expression language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union

# ---------------------------------------------------------------------------
# Type alias for any AST node
# ---------------------------------------------------------------------------
ASTNode = Union[
    "Literal",
    "Name",
    "Attribute",
    "Subscript",
    "List",
    "Dict",
    "ListLiteral",
    "DictLiteral",
    "InOp",
    "Comprehension",
    "Match",
    "Wildcard",
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


@dataclass(frozen=True)
class Wildcard:
    """Wildcard pattern for match cases: ``_``."""


@dataclass(frozen=True)
class List:
    """Legacy list-literal node.

    The parser emits :class:`ListLiteral` in current releases.
    """

    elements: tuple[ASTNode, ...]


@dataclass(frozen=True)
class Dict:
    """Legacy dict-literal node represented as key/value pairs.

    The parser emits :class:`DictLiteral` in current releases.
    """

    pairs: tuple[tuple[ASTNode, ASTNode], ...]


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
class ListLiteral:
    """List literal expression: ``[1, 2, x]``."""

    elements: list[ASTNode]


@dataclass(frozen=True)
class DictLiteral:
    """Dict literal expression: ``{"key": value}``."""

    keys: list[ASTNode]
    values: list[ASTNode]


@dataclass(frozen=True)
class InOp:
    """Membership expression: ``left in right``."""

    left: ASTNode
    right: ASTNode


@dataclass(frozen=True)
class Comprehension:
    """Comprehension-style call.

    Example: ``any(x > 0 for x in values if x != 3)``.
    """

    kind: str
    expr: ASTNode
    var: Name
    iterable: ASTNode
    condition: Optional[ASTNode]


@dataclass(frozen=True)
class MatchCase:
    """Single match case: ``pattern -> body``."""

    pattern: ASTNode
    body: ASTNode


@dataclass(frozen=True)
class Match:
    """Match expression.

    Example: ``match x with 1 -> "a" | else -> "b"``.
    """

    subject: ASTNode
    cases: list[MatchCase]
    else_case: Optional[ASTNode]


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
        ``"%"``, ``"<<"``, ``">>"``, ``"&"``, ``"^"``, ``"|"``,
        ``"=="``, ``"!="``, ``"<"``, ``">"``, ``"<="``, ``">="``,
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
