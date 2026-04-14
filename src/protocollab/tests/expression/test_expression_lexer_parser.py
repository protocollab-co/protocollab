"""Lexer and parser tests for protocollab.expression."""

from __future__ import annotations

import pytest

from protocollab.expression import (
    Attribute,
    BinOp,
    Comprehension,
    DictLiteral,
    ExpressionSyntaxError,
    InOp,
    ListLiteral,
    Literal,
    Match,
    Name,
    Subscript,
    Ternary,
    TokenKind,
    UnaryOp,
    Wildcard,
    parse_expr,
    tokenize,
)


class TestTokenize:
    def test_integer_and_radix_literals(self) -> None:
        assert tokenize("42")[0].value == 42
        assert tokenize("0xFF")[0].value == 255
        assert tokenize("0b1010")[0].value == 10
        assert tokenize("0o17")[0].value == 15

    def test_string_and_name_tokens(self) -> None:
        assert tokenize('"hello"')[0].kind == TokenKind.STRING
        assert tokenize("'world'")[0].kind == TokenKind.STRING
        token = tokenize("has_checksum")[0]
        assert token.kind == TokenKind.NAME
        assert token.value == "has_checksum"

    def test_boolean_literals_tokenized_as_name_values(self) -> None:
        assert tokenize("true")[0].value is True
        assert tokenize("false")[0].value is False

    def test_operator_tokens(self) -> None:
        assert tokenize("==")[0].kind == TokenKind.EQ
        assert tokenize("!=")[0].kind == TokenKind.NEQ
        assert tokenize("<=")[0].kind == TokenKind.LEQ
        assert tokenize(">=")[0].kind == TokenKind.GEQ
        assert tokenize("//")[0].kind == TokenKind.FLOOR_DIV
        assert tokenize("<<")[0].kind == TokenKind.LSHIFT
        assert tokenize(">>")[0].kind == TokenKind.RSHIFT
        assert tokenize("&")[0].kind == TokenKind.AMP
        assert tokenize("|")[0].kind == TokenKind.PIPE
        assert tokenize("^")[0].kind == TokenKind.CARET

    def test_punctuation_tokens(self) -> None:
        assert any(t.kind == TokenKind.DOT for t in tokenize("a.b"))
        bracket_kinds = {t.kind for t in tokenize("a[0]")}
        assert TokenKind.LBRACKET in bracket_kinds and TokenKind.RBRACKET in bracket_kinds
        brace_kinds = {t.kind for t in tokenize('{"a": 1, "b": 2}')}
        assert TokenKind.LBRACE in brace_kinds
        assert TokenKind.RBRACE in brace_kinds
        assert TokenKind.COLON in brace_kinds
        assert TokenKind.COMMA in brace_kinds
        assert any(t.kind == TokenKind.ARROW for t in tokenize("1 -> 2"))

    def test_whitespace_and_eof(self) -> None:
        kinds = [t.kind for t in tokenize("  42  ")]
        assert kinds == [TokenKind.INTEGER, TokenKind.EOF]
        assert tokenize("x")[-1].kind == TokenKind.EOF

    def test_invalid_char_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            tokenize("@bad")


class TestParseExpr:
    def test_literals_and_names(self) -> None:
        assert parse_expr("42") == Literal(value=42)
        assert parse_expr("true") == Literal(value=True)
        assert parse_expr("false") == Literal(value=False)
        assert parse_expr('"hello"') == Literal(value="hello")
        assert parse_expr("0xFF") == Literal(value=255)
        assert parse_expr("has_flag") == Name(name="has_flag")
        assert parse_expr("_io") == Name(name="_io")

    def test_attribute_and_subscript(self) -> None:
        attr = parse_expr("parent.length")
        assert isinstance(attr, Attribute)
        assert attr.attr == "length"
        sub = parse_expr("arr[0]")
        assert isinstance(sub, Subscript)
        assert isinstance(sub.index, Literal)

    def test_subscript_negative(self) -> None:
        node = parse_expr("arr[-1]")
        assert isinstance(node, Subscript)
        assert isinstance(node.index, UnaryOp)
        assert node.index.op == "-"

    def test_new_nodes(self) -> None:
        assert isinstance(parse_expr("[1, 2, x]"), ListLiteral)
        assert isinstance(parse_expr('{"a": 1, "b": 2}'), DictLiteral)
        assert isinstance(parse_expr("x in [1, 2, 3]"), InOp)

    def test_comprehension_parsing(self) -> None:
        any_node = parse_expr("any(x > 5 for x in items)")
        assert isinstance(any_node, Comprehension)
        assert any_node.kind == "any"
        first_node = parse_expr("first(x for x in items if x > 5)")
        assert isinstance(first_node, Comprehension)
        assert first_node.condition is not None
        first_simple = parse_expr("first(items)")
        assert isinstance(first_simple, Comprehension)
        assert first_simple.kind == "first"

    def test_match_parsing(self) -> None:
        node = parse_expr('match x with 1 -> "one" | else -> "other"')
        assert isinstance(node, Match)
        assert node.else_case is not None
        wildcard_node = parse_expr('match x with _ -> "fallback"')
        assert isinstance(wildcard_node.cases[0].pattern, Wildcard)

    def test_unary_binary_ternary_and_precedence(self) -> None:
        assert isinstance(parse_expr("-x"), UnaryOp)
        assert isinstance(parse_expr("not flag"), UnaryOp)
        assert parse_expr("a + b").op == "+"
        assert parse_expr("a // b").op == "//"
        assert parse_expr("a << 8").op == "<<"
        assert parse_expr("a & 255").op == "&"
        assert parse_expr("a and b").op == "and"
        ternary = parse_expr("x if cond else y")
        assert isinstance(ternary, Ternary)
        mul_before_add = parse_expr("a + b * c")
        assert isinstance(mul_before_add, BinOp)
        assert mul_before_add.op == "+"
        assert isinstance(mul_before_add.right, BinOp)

    def test_errors(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("")
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("(a + b")
        with pytest.raises(ExpressionSyntaxError, match="Forbidden"):
            parse_expr("eval")
        with pytest.raises(ExpressionSyntaxError, match="Forbidden"):
            parse_expr("__class__")
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("a b")
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("x if cond")
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("match x with y -> 1")
