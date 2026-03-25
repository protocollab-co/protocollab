"""Tests for protocollab.expression — lexer, parser, AST, evaluator, validator."""

from __future__ import annotations

import pytest

from protocollab.expression import (
    Attribute,
    BinOp,
    ExpressionEvalError,
    ExpressionSyntaxError,
    Literal,
    Name,
    Subscript,
    Ternary,
    TokenKind,
    UnaryOp,
    evaluate,
    parse_expr,
    tokenize,
    validate_expr,
)

# ===========================================================================
# Lexer
# ===========================================================================


class TestTokenize:
    def test_integer(self) -> None:
        tokens = tokenize("42")
        assert tokens[0].kind == TokenKind.INTEGER
        assert tokens[0].value == 42

    def test_hex_integer(self) -> None:
        tokens = tokenize("0xFF")
        assert tokens[0].value == 255

    def test_binary_integer(self) -> None:
        tokens = tokenize("0b1010")
        assert tokens[0].value == 10

    def test_octal_integer(self) -> None:
        tokens = tokenize("0o17")
        assert tokens[0].value == 15

    def test_string_double_quote(self) -> None:
        tokens = tokenize('"hello"')
        assert tokens[0].kind == TokenKind.STRING
        assert tokens[0].value == "hello"

    def test_string_single_quote(self) -> None:
        tokens = tokenize("'world'")
        assert tokens[0].kind == TokenKind.STRING
        assert tokens[0].value == "world"

    def test_name(self) -> None:
        tokens = tokenize("has_checksum")
        assert tokens[0].kind == TokenKind.NAME
        assert tokens[0].value == "has_checksum"

    def test_true_literal(self) -> None:
        tokens = tokenize("true")
        assert tokens[0].kind == TokenKind.NAME
        assert tokens[0].value is True

    def test_false_literal(self) -> None:
        tokens = tokenize("false")
        assert tokens[0].value is False

    def test_eq_operator(self) -> None:
        tokens = tokenize("==")
        assert tokens[0].kind == TokenKind.EQ

    def test_neq_operator(self) -> None:
        tokens = tokenize("!=")
        assert tokens[0].kind == TokenKind.NEQ

    def test_leq_operator(self) -> None:
        tokens = tokenize("<=")
        assert tokens[0].kind == TokenKind.LEQ

    def test_geq_operator(self) -> None:
        tokens = tokenize(">=")
        assert tokens[0].kind == TokenKind.GEQ

    def test_floor_div(self) -> None:
        tokens = tokenize("//")
        assert tokens[0].kind == TokenKind.FLOOR_DIV

    def test_whitespace_skipped(self) -> None:
        tokens = tokenize("  42  ")
        kinds = [t.kind for t in tokens]
        assert kinds == [TokenKind.INTEGER, TokenKind.EOF]

    def test_eof_sentinel(self) -> None:
        tokens = tokenize("x")
        assert tokens[-1].kind == TokenKind.EOF

    def test_complex_expression(self) -> None:
        tokens = tokenize("has_flag != 0")
        kinds = [t.kind for t in tokens]
        assert TokenKind.NAME in kinds
        assert TokenKind.NEQ in kinds
        assert TokenKind.INTEGER in kinds

    def test_unknown_char_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            tokenize("@bad")

    def test_dot_token(self) -> None:
        tokens = tokenize("a.b")
        assert any(t.kind == TokenKind.DOT for t in tokens)

    def test_bracket_tokens(self) -> None:
        tokens = tokenize("a[0]")
        kinds = {t.kind for t in tokens}
        assert TokenKind.LBRACKET in kinds
        assert TokenKind.RBRACKET in kinds


# ===========================================================================
# Parser — parse_expr returns correct AST
# ===========================================================================


class TestParseExpr:
    # -----------------------------------------------------------------------
    # Literals
    # -----------------------------------------------------------------------

    def test_integer_literal(self) -> None:
        node = parse_expr("42")
        assert isinstance(node, Literal)
        assert node.value == 42

    def test_true_literal(self) -> None:
        node = parse_expr("true")
        assert isinstance(node, Literal)
        assert node.value is True

    def test_false_literal(self) -> None:
        node = parse_expr("false")
        assert isinstance(node, Literal)
        assert node.value is False

    def test_string_literal(self) -> None:
        node = parse_expr('"hello"')
        assert isinstance(node, Literal)
        assert node.value == "hello"

    def test_hex_literal(self) -> None:
        node = parse_expr("0xFF")
        assert isinstance(node, Literal)
        assert node.value == 255

    # -----------------------------------------------------------------------
    # Names
    # -----------------------------------------------------------------------

    def test_name(self) -> None:
        node = parse_expr("has_flag")
        assert isinstance(node, Name)
        assert node.name == "has_flag"

    def test_special_name_io(self) -> None:
        node = parse_expr("_io")
        assert isinstance(node, Name)
        assert node.name == "_io"

    # -----------------------------------------------------------------------
    # Attribute access
    # -----------------------------------------------------------------------

    def test_attribute_access(self) -> None:
        node = parse_expr("parent.length")
        assert isinstance(node, Attribute)
        assert isinstance(node.obj, Name)
        assert node.obj.name == "parent"
        assert node.attr == "length"

    def test_io_size(self) -> None:
        node = parse_expr("_io.size")
        assert isinstance(node, Attribute)
        assert node.attr == "size"

    # -----------------------------------------------------------------------
    # Subscript
    # -----------------------------------------------------------------------

    def test_subscript(self) -> None:
        node = parse_expr("arr[0]")
        assert isinstance(node, Subscript)
        assert isinstance(node.obj, Name)
        assert isinstance(node.index, Literal)
        assert node.index.value == 0

    def test_subscript_negative(self) -> None:
        node = parse_expr("arr[-1]")
        assert isinstance(node, Subscript)
        # -1 parsed as UnaryOp(-, 1)
        assert isinstance(node.index, UnaryOp)
        assert node.index.op == "-"

    # -----------------------------------------------------------------------
    # Unary operators
    # -----------------------------------------------------------------------

    def test_unary_minus(self) -> None:
        node = parse_expr("-x")
        assert isinstance(node, UnaryOp)
        assert node.op == "-"
        assert isinstance(node.operand, Name)

    def test_unary_not(self) -> None:
        node = parse_expr("not flag")
        assert isinstance(node, UnaryOp)
        assert node.op == "not"

    # -----------------------------------------------------------------------
    # Binary operators
    # -----------------------------------------------------------------------

    def test_addition(self) -> None:
        node = parse_expr("a + b")
        assert isinstance(node, BinOp)
        assert node.op == "+"

    def test_subtraction(self) -> None:
        node = parse_expr("total - 8")
        assert isinstance(node, BinOp)
        assert node.op == "-"

    def test_multiplication(self) -> None:
        node = parse_expr("a * b")
        assert isinstance(node, BinOp)
        assert node.op == "*"

    def test_floor_division(self) -> None:
        node = parse_expr("a // b")
        assert isinstance(node, BinOp)
        assert node.op == "//"

    def test_modulo(self) -> None:
        node = parse_expr("a % 2")
        assert isinstance(node, BinOp)
        assert node.op == "%"

    def test_equality(self) -> None:
        node = parse_expr("has_checksum != 0")
        assert isinstance(node, BinOp)
        assert node.op == "!="

    def test_comparison_lt(self) -> None:
        node = parse_expr("x < 10")
        assert isinstance(node, BinOp)
        assert node.op == "<"

    def test_comparison_geq(self) -> None:
        node = parse_expr("x >= 10")
        assert isinstance(node, BinOp)
        assert node.op == ">="

    def test_logical_and(self) -> None:
        node = parse_expr("a and b")
        assert isinstance(node, BinOp)
        assert node.op == "and"

    def test_logical_or(self) -> None:
        node = parse_expr("a or b")
        assert isinstance(node, BinOp)
        assert node.op == "or"

    # -----------------------------------------------------------------------
    # Ternary
    # -----------------------------------------------------------------------

    def test_ternary(self) -> None:
        node = parse_expr("x if cond else y")
        assert isinstance(node, Ternary)
        assert isinstance(node.condition, Name)
        assert node.condition.name == "cond"

    def test_ternary_value_if_true(self) -> None:
        node = parse_expr("10 if flag else 20")
        assert isinstance(node, Ternary)
        assert isinstance(node.value_if_true, Literal)
        assert node.value_if_true.value == 10

    def test_ternary_value_if_false(self) -> None:
        node = parse_expr("10 if flag else 20")
        assert isinstance(node, Ternary)
        assert isinstance(node.value_if_false, Literal)
        assert node.value_if_false.value == 20

    # -----------------------------------------------------------------------
    # Parentheses
    # -----------------------------------------------------------------------

    def test_parenthesized(self) -> None:
        node = parse_expr("(a + b) * c")
        assert isinstance(node, BinOp)
        assert node.op == "*"
        assert isinstance(node.left, BinOp)
        assert node.left.op == "+"

    # -----------------------------------------------------------------------
    # Precedence
    # -----------------------------------------------------------------------

    def test_mul_before_add(self) -> None:
        node = parse_expr("a + b * c")
        assert isinstance(node, BinOp)
        assert node.op == "+"
        assert isinstance(node.right, BinOp)
        assert node.right.op == "*"

    def test_cmp_lower_than_add(self) -> None:
        node = parse_expr("a + 1 == b - 2")
        assert isinstance(node, BinOp)
        assert node.op == "=="

    # -----------------------------------------------------------------------
    # Errors
    # -----------------------------------------------------------------------

    def test_empty_expression_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("")

    def test_unclosed_paren_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("(a + b")

    def test_forbidden_name_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError, match="Forbidden"):
            parse_expr("eval")

    def test_forbidden_dunder_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError, match="Forbidden"):
            parse_expr("__class__")

    def test_trailing_token_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("a b")

    def test_ternary_missing_else_raises(self) -> None:
        with pytest.raises(ExpressionSyntaxError):
            parse_expr("x if cond")


# ===========================================================================
# Evaluator
# ===========================================================================


class TestEvaluate:
    # -----------------------------------------------------------------------
    # Literals
    # -----------------------------------------------------------------------

    def test_integer_literal(self) -> None:
        assert evaluate(parse_expr("42"), {}) == 42

    def test_true_literal(self) -> None:
        assert evaluate(parse_expr("true"), {}) is True

    def test_false_literal(self) -> None:
        assert evaluate(parse_expr("false"), {}) is False

    def test_string_literal(self) -> None:
        assert evaluate(parse_expr('"hi"'), {}) == "hi"

    # -----------------------------------------------------------------------
    # Name lookup
    # -----------------------------------------------------------------------

    def test_name_lookup(self) -> None:
        assert evaluate(parse_expr("x"), {"x": 7}) == 7

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ExpressionEvalError, match="Undefined"):
            evaluate(parse_expr("missing"), {})

    # -----------------------------------------------------------------------
    # Attribute
    # -----------------------------------------------------------------------

    def test_attribute_dict(self) -> None:
        ctx = {"_io": {"size": 100}}
        assert evaluate(parse_expr("_io.size"), ctx) == 100

    def test_attribute_missing_raises(self) -> None:
        ctx = {"obj": {"x": 1}}
        with pytest.raises(ExpressionEvalError):
            evaluate(parse_expr("obj.y"), ctx)

    # -----------------------------------------------------------------------
    # Subscript
    # -----------------------------------------------------------------------

    def test_subscript_list(self) -> None:
        ctx = {"arr": [10, 20, 30]}
        assert evaluate(parse_expr("arr[0]"), ctx) == 10

    def test_subscript_negative_index(self) -> None:
        ctx = {"arr": [10, 20, 30]}
        assert evaluate(parse_expr("arr[-1]"), ctx) == 30

    def test_subscript_out_of_range_raises(self) -> None:
        ctx = {"arr": [1, 2]}
        with pytest.raises(ExpressionEvalError):
            evaluate(parse_expr("arr[99]"), ctx)

    # -----------------------------------------------------------------------
    # Arithmetic
    # -----------------------------------------------------------------------

    def test_addition(self) -> None:
        assert evaluate(parse_expr("3 + 4"), {}) == 7

    def test_subtraction(self) -> None:
        assert evaluate(parse_expr("10 - 3"), {}) == 7

    def test_multiplication(self) -> None:
        assert evaluate(parse_expr("3 * 4"), {}) == 12

    def test_true_division(self) -> None:
        assert evaluate(parse_expr("7 / 2"), {}) == 3.5

    def test_floor_division(self) -> None:
        assert evaluate(parse_expr("7 // 2"), {}) == 3

    def test_modulo(self) -> None:
        assert evaluate(parse_expr("10 % 3"), {}) == 1

    def test_unary_minus_literal(self) -> None:
        assert evaluate(parse_expr("-5"), {}) == -5

    def test_unary_minus_name(self) -> None:
        assert evaluate(parse_expr("-x"), {"x": 3}) == -3

    def test_division_by_zero_raises(self) -> None:
        with pytest.raises(ExpressionEvalError, match="Division by zero"):
            evaluate(parse_expr("1 / 0"), {})

    def test_floor_div_by_zero_raises(self) -> None:
        with pytest.raises(ExpressionEvalError):
            evaluate(parse_expr("1 // 0"), {})

    # -----------------------------------------------------------------------
    # Comparisons
    # -----------------------------------------------------------------------

    def test_eq_true(self) -> None:
        assert evaluate(parse_expr("1 == 1"), {}) is True

    def test_eq_false(self) -> None:
        assert evaluate(parse_expr("1 == 2"), {}) is False

    def test_neq(self) -> None:
        assert evaluate(parse_expr("has_checksum != 0"), {"has_checksum": 1}) is True

    def test_lt(self) -> None:
        assert evaluate(parse_expr("x < 10"), {"x": 5}) is True

    def test_geq(self) -> None:
        assert evaluate(parse_expr("x >= 10"), {"x": 10}) is True

    # -----------------------------------------------------------------------
    # Logic
    # -----------------------------------------------------------------------

    def test_and_true(self) -> None:
        assert evaluate(parse_expr("true and true"), {}) is True

    def test_and_false(self) -> None:
        assert evaluate(parse_expr("true and false"), {}) is False

    def test_or_true(self) -> None:
        assert evaluate(parse_expr("false or true"), {}) is True

    def test_not_true(self) -> None:
        assert evaluate(parse_expr("not true"), {}) is False

    def test_not_false(self) -> None:
        assert evaluate(parse_expr("not false"), {}) is True

    def test_not_name(self) -> None:
        assert evaluate(parse_expr("not flag"), {"flag": 0}) is True

    # -----------------------------------------------------------------------
    # Ternary
    # -----------------------------------------------------------------------

    def test_ternary_true_branch(self) -> None:
        result = evaluate(parse_expr("10 if flag else 20"), {"flag": True})
        assert result == 10

    def test_ternary_false_branch(self) -> None:
        result = evaluate(parse_expr("10 if flag else 20"), {"flag": False})
        assert result == 20

    def test_ternary_condition_expr(self) -> None:
        ctx = {"total_length": 20, "has_ext": True, "fixed_size": 12}
        result = evaluate(parse_expr("total_length - 8 if has_ext else fixed_size"), ctx)
        assert result == 12

    # -----------------------------------------------------------------------
    # Complex real-world expressions
    # -----------------------------------------------------------------------

    def test_if_field_expr(self) -> None:
        ctx = {"has_checksum": 1}
        assert evaluate(parse_expr("has_checksum != 0"), ctx) is True

    def test_size_expr(self) -> None:
        ctx = {"total_length": 20}
        assert evaluate(parse_expr("total_length - 8"), ctx) == 12

    def test_io_size_expr(self) -> None:
        ctx = {"_io": {"size": 100}}
        assert evaluate(parse_expr("_io.size - 4"), ctx) == 96

    def test_compound_and_expr(self) -> None:
        ctx = {"a": 1, "b": 2, "c": 3}
        assert evaluate(parse_expr("a < b and b < c"), ctx) is True


# ===========================================================================
# Validator
# ===========================================================================


class TestValidateExpr:
    def test_valid_returns_empty(self) -> None:
        errors = validate_expr("has_checksum != 0")
        assert errors == []

    def test_syntax_error_returns_errors(self) -> None:
        errors = validate_expr("@bad")
        assert len(errors) == 1
        assert errors[0].pos >= 0

    def test_unclosed_paren_error(self) -> None:
        errors = validate_expr("(a + b")
        assert len(errors) > 0

    def test_empty_expression_error(self) -> None:
        errors = validate_expr("")
        assert len(errors) > 0

    def test_complex_valid_expr(self) -> None:
        errors = validate_expr("total_length - 8 if has_ext else fixed_size")
        assert errors == []

    def test_forbidden_name_error(self) -> None:
        errors = validate_expr("eval")
        assert len(errors) > 0

    def test_error_str_with_pos(self) -> None:
        from protocollab.expression.validator import ExprError

        e = ExprError(message="boom", pos=5)
        assert "5" in str(e)
        assert "boom" in str(e)

    def test_error_str_no_pos(self) -> None:
        from protocollab.expression.validator import ExprError

        e = ExprError(message="boom")
        assert "boom" in str(e)
        assert "pos" not in str(e)
