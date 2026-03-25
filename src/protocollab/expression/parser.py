"""Recursive-descent parser — converts token list into an AST.

Grammar (PEG-style, highest precedence last)
--------------------------------------------
::

    expr        = ternary
    ternary     = or_expr ('if' or_expr 'else' or_expr)?
    or_expr     = and_expr ('or' and_expr)*
    and_expr    = not_expr ('and' not_expr)*
    not_expr    = 'not' not_expr | comparison
    comparison  = additive (('==' | '!=' | '<' | '>' | '<=' | '>=') additive)?
    additive    = mult (('+' | '-') mult)*
    mult        = unary (('*' | '/' | '//' | '%') unary)*
    unary       = '-' unary | postfix
    postfix     = primary ('.' NAME | '[' expr ']')*
    primary     = INTEGER | STRING | 'true' | 'false'
                | NAME | '(' expr ')'
"""

from __future__ import annotations

from typing import List

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
from protocollab.expression.lexer import (
    ExpressionSyntaxError,
    Token,
    TokenKind,
    tokenize,
)

# ---------------------------------------------------------------------------
# Operator token → string mapping
# ---------------------------------------------------------------------------
_COMPARISON_OPS: dict[TokenKind, str] = {
    TokenKind.EQ: "==",
    TokenKind.NEQ: "!=",
    TokenKind.LT: "<",
    TokenKind.GT: ">",
    TokenKind.LEQ: "<=",
    TokenKind.GEQ: ">=",
}
_ADDITIVE_OPS: dict[TokenKind, str] = {
    TokenKind.PLUS: "+",
    TokenKind.MINUS: "-",
}
_MULT_OPS: dict[TokenKind, str] = {
    TokenKind.STAR: "*",
    TokenKind.SLASH: "/",
    TokenKind.FLOOR_DIV: "//",
    TokenKind.PERCENT: "%",
}

# Names that must NOT appear as free identifiers (security / safety)
_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "__class__",
        "__dict__",
        "__globals__",
        "__builtins__",
        "import",
        "exec",
        "eval",
        "compile",
        "open",
        "getattr",
        "setattr",
        "delattr",
        "globals",
        "locals",
        "vars",
        "dir",
        "type",
    }
)


class Parser:
    """Recursive-descent parser that consumes a token list."""

    def __init__(self, tokens: List[Token], source: str = "") -> None:
        self._tokens = tokens
        self._pos = 0
        self._source = source

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        if tok.kind != TokenKind.EOF:
            self._pos += 1
        return tok

    def _expect(self, kind: TokenKind) -> Token:
        tok = self._peek()
        if tok.kind != kind:
            raise ExpressionSyntaxError(
                f"Expected {kind.name} but got {tok.kind.name!r} ({tok.value!r})"
                f" at position {tok.pos}",
                expr=self._source,
                pos=tok.pos,
            )
        return self._advance()

    def _match(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _match_name(self, *names: str) -> bool:
        tok = self._peek()
        return tok.kind == TokenKind.NAME and tok.value in names

    # ------------------------------------------------------------------
    # Grammar rules
    # ------------------------------------------------------------------

    def parse(self) -> ASTNode:
        """Parse the full expression and assert no trailing tokens."""
        node = self._expr()
        if self._peek().kind != TokenKind.EOF:
            tok = self._peek()
            raise ExpressionSyntaxError(
                f"Unexpected token {tok.value!r} at position {tok.pos}",
                expr=self._source,
                pos=tok.pos,
            )
        return node

    def _expr(self) -> ASTNode:
        return self._ternary()

    def _ternary(self) -> ASTNode:
        # value_if_true 'if' condition 'else' value_if_false
        node = self._or_expr()
        if self._match_name("if"):
            self._advance()  # consume 'if'
            condition = self._or_expr()
            if not self._match_name("else"):
                raise ExpressionSyntaxError(
                    "Expected 'else' in ternary expression",
                    expr=self._source,
                    pos=self._peek().pos,
                )
            self._advance()  # consume 'else'
            value_if_false = self._or_expr()
            return Ternary(
                value_if_true=node,
                condition=condition,
                value_if_false=value_if_false,
            )
        return node

    def _or_expr(self) -> ASTNode:
        node = self._and_expr()
        while self._match_name("or"):
            self._advance()
            right = self._and_expr()
            node = BinOp(left=node, op="or", right=right)
        return node

    def _and_expr(self) -> ASTNode:
        node = self._not_expr()
        while self._match_name("and"):
            self._advance()
            right = self._not_expr()
            node = BinOp(left=node, op="and", right=right)
        return node

    def _not_expr(self) -> ASTNode:
        if self._match_name("not"):
            self._advance()
            operand = self._not_expr()
            return UnaryOp(op="not", operand=operand)
        return self._comparison()

    def _comparison(self) -> ASTNode:
        node = self._additive()
        if self._peek().kind in _COMPARISON_OPS:
            op_str = _COMPARISON_OPS[self._advance().kind]
            right = self._additive()
            node = BinOp(left=node, op=op_str, right=right)
        return node

    def _additive(self) -> ASTNode:
        node = self._mult()
        while self._peek().kind in _ADDITIVE_OPS:
            op_str = _ADDITIVE_OPS[self._advance().kind]
            right = self._mult()
            node = BinOp(left=node, op=op_str, right=right)
        return node

    def _mult(self) -> ASTNode:
        node = self._unary()
        while self._peek().kind in _MULT_OPS:
            op_str = _MULT_OPS[self._advance().kind]
            right = self._unary()
            node = BinOp(left=node, op=op_str, right=right)
        return node

    def _unary(self) -> ASTNode:
        if self._match(TokenKind.MINUS):
            self._advance()
            operand = self._unary()
            return UnaryOp(op="-", operand=operand)
        return self._postfix()

    def _postfix(self) -> ASTNode:
        node = self._primary()
        while True:
            if self._match(TokenKind.DOT):
                self._advance()
                attr_tok = self._expect(TokenKind.NAME)
                node = Attribute(obj=node, attr=str(attr_tok.value))
            elif self._match(TokenKind.LBRACKET):
                self._advance()
                index = self._expr()
                self._expect(TokenKind.RBRACKET)
                node = Subscript(obj=node, index=index)
            else:
                break
        return node

    def _primary(self) -> ASTNode:
        tok = self._peek()

        if tok.kind == TokenKind.INTEGER:
            self._advance()
            return Literal(value=int(tok.value))  # type: ignore[arg-type]

        if tok.kind == TokenKind.STRING:
            self._advance()
            return Literal(value=str(tok.value))

        if tok.kind == TokenKind.NAME:
            # true / false literals
            if tok.value is True:
                self._advance()
                return Literal(value=True)
            if tok.value is False:
                self._advance()
                return Literal(value=False)
            # Forbidden identifiers
            name_str = str(tok.value)
            if name_str in _FORBIDDEN_NAMES:
                raise ExpressionSyntaxError(
                    f"Forbidden identifier {name_str!r} at position {tok.pos}",
                    expr=self._source,
                    pos=tok.pos,
                )
            self._advance()
            return Name(name=name_str)

        if tok.kind == TokenKind.LPAREN:
            self._advance()
            node = self._expr()
            self._expect(TokenKind.RPAREN)
            return node

        raise ExpressionSyntaxError(
            f"Unexpected token {tok.kind.name!r} ({tok.value!r}) at position {tok.pos}",
            expr=self._source,
            pos=tok.pos,
        )


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def parse_expr(expr: str) -> ASTNode:
    """Parse *expr* into an AST.

    Parameters
    ----------
    expr:
        Expression string, e.g. ``"has_checksum != 0"`` or
        ``"total_length - 8"``.

    Returns
    -------
    ASTNode
        Root of the parsed AST.

    Raises
    ------
    ExpressionSyntaxError
        On any lexical or syntactic error.
    """
    tokens = tokenize(expr)
    return Parser(tokens, source=expr).parse()
