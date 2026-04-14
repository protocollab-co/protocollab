"""Lexer — tokenises a `protocollab` expression string."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenKind(Enum):
    # Literals
    INTEGER = auto()
    STRING = auto()
    # Identifiers / keywords
    NAME = auto()
    # Two-character operators
    EQ = auto()  # ==
    NEQ = auto()  # !=
    LEQ = auto()  # <=
    GEQ = auto()  # >=
    FLOOR_DIV = auto()  # //
    LSHIFT = auto()  # <<
    RSHIFT = auto()  # >>
    ARROW = auto()  # ->
    # Single-character operators / punctuation
    LT = auto()  # <
    GT = auto()  # >
    AMP = auto()  # &
    PIPE = auto()  # |
    CARET = auto()  # ^
    PLUS = auto()  # +
    MINUS = auto()  # -
    STAR = auto()  # *
    SLASH = auto()  # /
    PERCENT = auto()  # %
    DOT = auto()  # .
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    LBRACE = auto()  # {
    RBRACE = auto()  # }
    COLON = auto()  # :
    COMMA = auto()  # ,
    # Sentinel
    EOF = auto()


# Keywords recognised by the lexer (returned as NAME tokens with .value set)
_KEYWORDS: set[str] = {
    "and",
    "or",
    "not",
    "if",
    "else",
    "true",
    "false",
    "in",
    "for",
    "any",
    "all",
    "first",
    "filter",
    "map",
    "match",
    "with",
}


@dataclass
class Token:
    kind: TokenKind
    value: object  # str, int, bool, or None for punctuation tokens
    pos: int  # byte offset in the source string


# ---------------------------------------------------------------------------
# Token patterns (ordered — longest / most-specific first)
# ---------------------------------------------------------------------------
_TOKEN_SPEC: list[tuple[str, TokenKind]] = [
    # Hex / binary / octal / decimal integers
    (r"0x[0-9A-Fa-f]+", TokenKind.INTEGER),
    (r"0b[01]+", TokenKind.INTEGER),
    (r"0o[0-7]+", TokenKind.INTEGER),
    (r"\d+", TokenKind.INTEGER),
    # Quoted strings
    (r'"(?:[^"\\]|\\.)*"', TokenKind.STRING),
    (r"'(?:[^'\\]|\\.)*'", TokenKind.STRING),
    # Identifiers / keywords
    (r"[A-Za-z_][A-Za-z0-9_]*", TokenKind.NAME),
    # Two-character operators (MUST come before single-char)
    (r"->", TokenKind.ARROW),
    (r"==", TokenKind.EQ),
    (r"!=", TokenKind.NEQ),
    (r"<=", TokenKind.LEQ),
    (r">=", TokenKind.GEQ),
    (r"//", TokenKind.FLOOR_DIV),
    (r"<<", TokenKind.LSHIFT),
    (r">>", TokenKind.RSHIFT),
    # Single-character
    (r"<", TokenKind.LT),
    (r">", TokenKind.GT),
    (r"&", TokenKind.AMP),
    (r"\|", TokenKind.PIPE),
    (r"\^", TokenKind.CARET),
    (r"\+", TokenKind.PLUS),
    (r"-", TokenKind.MINUS),
    (r"\*", TokenKind.STAR),
    (r"/", TokenKind.SLASH),
    (r"%", TokenKind.PERCENT),
    (r"\.", TokenKind.DOT),
    (r"\(", TokenKind.LPAREN),
    (r"\)", TokenKind.RPAREN),
    (r"\[", TokenKind.LBRACKET),
    (r"\]", TokenKind.RBRACKET),
    (r"\{", TokenKind.LBRACE),
    (r"\}", TokenKind.RBRACE),
    (r":", TokenKind.COLON),
    (r",", TokenKind.COMMA),
    # Whitespace — consumed but not emitted
    (r"\s+", None),  # type: ignore[misc]
]

_MASTER_RE = re.compile("|".join(f"(?P<g{i}>{pat})" for i, (pat, _) in enumerate(_TOKEN_SPEC)))
_KIND_BY_GROUP: dict[str, TokenKind | None] = {
    f"g{i}": kind for i, (_, kind) in enumerate(_TOKEN_SPEC)
}


class ExpressionSyntaxError(Exception):
    """Raised when the lexer or parser encounters invalid syntax.

    Attributes
    ----------
    expr:
        The original expression string.
    pos:
        Byte offset of the error in *expr*, or ``-1`` if unknown.
    """

    def __init__(self, message: str, expr: str = "", pos: int = -1) -> None:
        self.expr = expr
        self.pos = pos
        super().__init__(message)


def tokenize(expr: str) -> List[Token]:
    """Convert *expr* into a flat list of :class:`Token` objects.

    The list is always terminated by an :attr:`~TokenKind.EOF` sentinel.

    Raises
    ------
    ExpressionSyntaxError
        If an unrecognised character is encountered.
    """
    tokens: list[Token] = []
    pos = 0
    length = len(expr)
    while pos < length:
        m = _MASTER_RE.match(expr, pos)
        if not m:
            raise ExpressionSyntaxError(
                f"Unexpected character {expr[pos]!r} at position {pos}",
                expr=expr,
                pos=pos,
            )
        kind = _KIND_BY_GROUP[m.lastgroup]
        if kind is not None:
            raw = m.group()
            tokens.append(Token(kind=kind, value=_coerce(kind, raw), pos=pos))
        pos = m.end()

    tokens.append(Token(kind=TokenKind.EOF, value=None, pos=pos))
    return tokens


def _coerce(kind: TokenKind, raw: str) -> object:
    """Convert a raw matched string to the appropriate Python value."""
    if kind == TokenKind.INTEGER:
        return int(raw, 0)  # handles 0x, 0b, 0o prefixes
    if kind == TokenKind.STRING:
        return raw[1:-1].encode("raw_unicode_escape").decode("unicode_escape")
    if kind == TokenKind.NAME:
        if raw == "true":
            return True
        if raw == "false":
            return False
        return raw  # plain identifier string
    return raw  # punctuation — keep as-is for diagnostics
