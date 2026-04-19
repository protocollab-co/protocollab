"""Recursive-descent parser — converts token list into an AST.

Grammar (PEG-style, highest precedence last)
--------------------------------------------
::

    expr        = ternary
    ternary     = or_expr ('if' or_expr 'else' or_expr)?
    or_expr     = and_expr ('or' and_expr)*
    and_expr    = not_expr ('and' not_expr)*
    not_expr    = 'not' not_expr | in_expr
    in_expr     = comparison ('in' comparison)*
    comparison  = bitwise_or (('==' | '!=' | '<' | '>' | '<=' | '>=') bitwise_or)?
    bitwise_or  = bitwise_xor ('|' bitwise_xor)*
    bitwise_xor = bitwise_and ('^' bitwise_and)*
    bitwise_and = shift ('&' shift)*
    shift       = additive (('<<' | '>>') additive)*
    additive    = mult (('+' | '-') mult)*
    mult        = unary (('*' | '/' | '//' | '%') unary)*
    unary       = '-' unary | postfix
    postfix     = primary ('.' NAME | '[' expr ']')*
    primary     = INTEGER | STRING | 'true' | 'false'
                | NAME | '(' expr ')'
                | list_lit | dict_lit
                | match_expr | comprehension

    list_lit      = '[' (expr (',' expr)*)? ']'
    dict_lit      = '{' ((expr ':' expr) (',' expr ':' expr)*)? '}'
    comprehension = ('any'|'all'|'first'|'filter'|'map')
                                        '(' expr 'for' NAME 'in' expr ('if' expr)? ')'
                                    | 'first' '(' expr ')'
    match_expr    = 'match' expr 'with'
                                        (pattern '->' expr ('|' pattern '->' expr)*)
                                        ('|' 'else' '->' expr)?
    pattern       = INTEGER | STRING | 'true' | 'false' | '_'
"""

from __future__ import annotations

from typing import Callable

from protocollab.expression.ast_nodes import (
    ASTNode,
    Attribute,
    BinOp,
    Comprehension,
    DictLiteral,
    InOp,
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
_SHIFT_OPS: dict[TokenKind, str] = {
    TokenKind.LSHIFT: "<<",
    TokenKind.RSHIFT: ">>",
}
_BITWISE_AND_OPS: dict[TokenKind, str] = {
    TokenKind.AMP: "&",
}
_BITWISE_XOR_OPS: dict[TokenKind, str] = {
    TokenKind.CARET: "^",
}
_BITWISE_OR_OPS: dict[TokenKind, str] = {
    TokenKind.PIPE: "|",
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

    def __init__(self, tokens: list[Token], source: str = "") -> None:
        self._tokens = tokens
        self._pos = 0
        self._source = source

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _peek_n(self, offset: int) -> Token:
        idx = self._pos + offset
        if idx >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[idx]

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

    def _parse_from_token_slice(self, tokens: list[Token]) -> ASTNode:
        if not tokens:
            raise ExpressionSyntaxError(
                "Expected expression",
                expr=self._source,
                pos=self._peek().pos,
            )
        if tokens[-1].kind != TokenKind.EOF:
            eof_pos = tokens[-1].pos
            tokens = [*tokens, Token(kind=TokenKind.EOF, value=None, pos=eof_pos)]
        return Parser(tokens, source=self._source).parse()

    def _parse_until_case_separator(self) -> ASTNode:
        start = self._pos
        paren = 0
        bracket = 0
        brace = 0

        while True:
            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                break
            if tok.kind == TokenKind.PIPE and paren == 0 and bracket == 0 and brace == 0:
                break
            if tok.kind == TokenKind.RPAREN and paren == 0 and bracket == 0 and brace == 0:
                break

            if tok.kind == TokenKind.LPAREN:
                paren += 1
            elif tok.kind == TokenKind.RPAREN:
                paren -= 1
            elif tok.kind == TokenKind.LBRACKET:
                bracket += 1
            elif tok.kind == TokenKind.RBRACKET:
                bracket -= 1
            elif tok.kind == TokenKind.LBRACE:
                brace += 1
            elif tok.kind == TokenKind.RBRACE:
                brace -= 1

            self._advance()

        body_tokens = self._tokens[start : self._pos]
        return self._parse_from_token_slice(body_tokens)

    def _parse_until_delimiters(
        self,
        stop_kinds: set[TokenKind] | None = None,
        stop_names: set[str] | None = None,
    ) -> ASTNode:
        stop_kinds = set() if stop_kinds is None else set(stop_kinds)
        stop_names = set() if stop_names is None else set(stop_names)
        start = self._pos
        paren = 0
        bracket = 0
        brace = 0

        while True:
            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                break
            if paren == 0 and bracket == 0 and brace == 0:
                if tok.kind in stop_kinds:
                    break
                if tok.kind == TokenKind.NAME and str(tok.value) in stop_names:
                    break

            if tok.kind == TokenKind.LPAREN:
                paren += 1
            elif tok.kind == TokenKind.RPAREN:
                if paren == 0:
                    break
                paren -= 1
            elif tok.kind == TokenKind.LBRACKET:
                bracket += 1
            elif tok.kind == TokenKind.RBRACKET:
                if bracket == 0:
                    break
                bracket -= 1
            elif tok.kind == TokenKind.LBRACE:
                brace += 1
            elif tok.kind == TokenKind.RBRACE:
                if brace == 0:
                    break
                brace -= 1

            self._advance()

        expr_tokens = self._tokens[start : self._pos]
        return self._parse_from_token_slice(expr_tokens)

    def _parse_left_associative(
        self,
        parse_operand: Callable[[], ASTNode],
        operators: dict[TokenKind, str],
    ) -> ASTNode:
        node = parse_operand()
        while self._peek().kind in operators:
            op_str = operators[self._advance().kind]
            right = parse_operand()
            node = BinOp(left=node, op=op_str, right=right)
        return node

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
        return self._in_expr()

    def _in_expr(self) -> ASTNode:
        node = self._comparison()
        while self._match_name("in"):
            self._advance()
            right = self._comparison()
            node = InOp(left=node, right=right)
        return node

    def _comparison(self) -> ASTNode:
        node = self._bitwise_or()
        if self._peek().kind in _COMPARISON_OPS:
            op_str = _COMPARISON_OPS[self._advance().kind]
            right = self._bitwise_or()
            node = BinOp(left=node, op=op_str, right=right)
        return node

    def _bitwise_or(self) -> ASTNode:
        return self._parse_left_associative(self._bitwise_xor, _BITWISE_OR_OPS)

    def _bitwise_xor(self) -> ASTNode:
        return self._parse_left_associative(self._bitwise_and, _BITWISE_XOR_OPS)

    def _bitwise_and(self) -> ASTNode:
        return self._parse_left_associative(self._shift, _BITWISE_AND_OPS)

    def _shift(self) -> ASTNode:
        return self._parse_left_associative(self._additive, _SHIFT_OPS)

    def _additive(self) -> ASTNode:
        return self._parse_left_associative(self._mult, _ADDITIVE_OPS)

    def _mult(self) -> ASTNode:
        return self._parse_left_associative(self._unary, _MULT_OPS)

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
            if (
                tok.value in {"any", "all", "first", "filter", "map"}
                and self._peek_n(1).kind == TokenKind.LPAREN
            ):
                return self._parse_comprehension_or_first_simple()

            if tok.value == "match":
                return self._parse_match()

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

        if tok.kind == TokenKind.LBRACKET:
            return self._parse_list_literal()

        if tok.kind == TokenKind.LBRACE:
            return self._parse_dict_literal()

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

    def _parse_list_literal(self) -> ASTNode:
        self._expect(TokenKind.LBRACKET)
        elements: list[ASTNode] = []
        if not self._match(TokenKind.RBRACKET):
            while True:
                elements.append(self._expr())
                if self._match(TokenKind.COMMA):
                    self._advance()
                    continue
                break
        self._expect(TokenKind.RBRACKET)
        return ListLiteral(elements=elements)

    def _parse_dict_literal(self) -> ASTNode:
        self._expect(TokenKind.LBRACE)
        keys: list[ASTNode] = []
        values: list[ASTNode] = []
        if not self._match(TokenKind.RBRACE):
            while True:
                key_node = self._expr()
                self._expect(TokenKind.COLON)
                value_node = self._expr()
                keys.append(key_node)
                values.append(value_node)
                if self._match(TokenKind.COMMA):
                    self._advance()
                    continue
                break
        self._expect(TokenKind.RBRACE)
        return DictLiteral(keys=keys, values=values)

    def _parse_comprehension_or_first_simple(self) -> ASTNode:
        kind_tok = self._expect(TokenKind.NAME)
        kind = str(kind_tok.value)
        self._expect(TokenKind.LPAREN)

        first_expr = self._expr()
        if self._match_name("for"):
            self._advance()
            var_tok = self._expect(TokenKind.NAME)
            var_name = str(var_tok.value)
            if var_name in _FORBIDDEN_NAMES:
                raise ExpressionSyntaxError(
                    f"Forbidden identifier {var_name!r} at position {var_tok.pos}",
                    expr=self._source,
                    pos=var_tok.pos,
                )
            if not self._match_name("in"):
                raise ExpressionSyntaxError(
                    "Expected 'in' in comprehension",
                    expr=self._source,
                    pos=self._peek().pos,
                )
            self._advance()
            iterable = self._parse_until_delimiters(
                stop_kinds={TokenKind.RPAREN},
                stop_names={"if"},
            )
            condition = None
            if self._match_name("if"):
                self._advance()
                condition = self._expr()
            self._expect(TokenKind.RPAREN)
            return Comprehension(
                kind=kind,
                expr=first_expr,
                var=Name(name=var_name),
                iterable=iterable,
                condition=condition,
            )

        if kind == "first":
            self._expect(TokenKind.RPAREN)
            item_name = Name(name="_item")
            return Comprehension(
                kind="first",
                expr=item_name,
                var=item_name,
                iterable=first_expr,
                condition=None,
            )

        raise ExpressionSyntaxError(
            f"Expected comprehension syntax for '{kind}'",
            expr=self._source,
            pos=self._peek().pos,
        )

    def _parse_match_pattern(self) -> ASTNode:
        tok = self._peek()
        if tok.kind == TokenKind.NAME and tok.value == "_":
            self._advance()
            return Wildcard()
        if tok.kind == TokenKind.INTEGER:
            self._advance()
            return Literal(value=int(tok.value))  # type: ignore[arg-type]
        if tok.kind == TokenKind.STRING:
            self._advance()
            return Literal(value=str(tok.value))
        if tok.kind == TokenKind.NAME and tok.value in (True, False):
            self._advance()
            return Literal(value=bool(tok.value))
        raise ExpressionSyntaxError(
            f"Invalid match pattern at position {tok.pos}: {tok.value!r}",
            expr=self._source,
            pos=tok.pos,
        )

    def _parse_match(self) -> ASTNode:
        match_tok = self._expect(TokenKind.NAME)
        if match_tok.value != "match":
            raise ExpressionSyntaxError(
                f"Expected 'match' but got {match_tok.value!r} at position {match_tok.pos}",
                expr=self._source,
                pos=match_tok.pos,
            )
        subject = self._expr()
        if not self._match_name("with"):
            raise ExpressionSyntaxError(
                "Expected 'with' in match expression",
                expr=self._source,
                pos=self._peek().pos,
            )
        self._advance()

        cases: list[MatchCase] = []
        else_case: ASTNode | None = None

        while True:
            if self._match_name("else"):
                self._advance()
                self._expect(TokenKind.ARROW)
                else_case = self._expr()
                break

            pattern = self._parse_match_pattern()
            self._expect(TokenKind.ARROW)
            body = self._parse_until_case_separator()
            cases.append(MatchCase(pattern=pattern, body=body))

            if self._match(TokenKind.PIPE):
                self._advance()
                continue
            break

        return Match(subject=subject, cases=cases, else_case=else_case)


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
