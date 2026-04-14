"""Evaluator tests for protocollab.expression."""

from __future__ import annotations

import pytest

from protocollab.expression import ExpressionEvalError, evaluate, parse_expr


class TestEvaluate:
    def test_literals_and_name_lookup(self) -> None:
        assert evaluate(parse_expr("42"), {}) == 42
        assert evaluate(parse_expr("true"), {}) is True
        assert evaluate(parse_expr("false"), {}) is False
        assert evaluate(parse_expr('"hi"'), {}) == "hi"
        assert evaluate(parse_expr("x"), {"x": 7}) == 7
        with pytest.raises(ExpressionEvalError, match="Undefined"):
            evaluate(parse_expr("missing"), {})

    def test_attribute_and_subscript(self) -> None:
        assert evaluate(parse_expr("_io.size"), {"_io": {"size": 100}}) == 100
        with pytest.raises(ExpressionEvalError):
            evaluate(parse_expr("obj.y"), {"obj": {"x": 1}})
        arr_ctx = {"arr": [10, 20, 30]}
        assert evaluate(parse_expr("arr[0]"), arr_ctx) == 10
        assert evaluate(parse_expr("arr[-1]"), arr_ctx) == 30
        with pytest.raises(ExpressionEvalError):
            evaluate(parse_expr("arr[99]"), {"arr": [1, 2]})

    def test_list_dict_and_in(self) -> None:
        assert evaluate(parse_expr("[1, 2, x]"), {"x": 3}) == [1, 2, 3]
        assert evaluate(parse_expr('{"a": x}'), {"x": 10}) == {"a": 10}
        assert evaluate(parse_expr("x in [1, 2, 3]"), {"x": 2}) is True

    def test_arithmetic_and_bitwise(self) -> None:
        assert evaluate(parse_expr("3 + 4"), {}) == 7
        assert evaluate(parse_expr("10 - 3"), {}) == 7
        assert evaluate(parse_expr("3 * 4"), {}) == 12
        assert evaluate(parse_expr("7 / 2"), {}) == 3.5
        assert evaluate(parse_expr("7 // 2"), {}) == 3
        assert evaluate(parse_expr("10 % 3"), {}) == 1
        assert evaluate(parse_expr("1 << 8"), {}) == 256
        assert evaluate(parse_expr("256 >> 8"), {}) == 1
        assert evaluate(parse_expr("0xC0A80101 & 0xFFFF0000"), {}) == 0xC0A80000
        assert evaluate(parse_expr("0b1100 ^ 0b1010"), {}) == 0b0110
        assert evaluate(parse_expr("0b1100 | 0b0011"), {}) == 0b1111
        assert evaluate(parse_expr("-5"), {}) == -5
        assert evaluate(parse_expr("-x"), {"x": 3}) == -3
        with pytest.raises(ExpressionEvalError, match="Division by zero"):
            evaluate(parse_expr("1 / 0"), {})

    def test_comparisons_and_logic(self) -> None:
        assert evaluate(parse_expr("1 == 1"), {}) is True
        assert evaluate(parse_expr("1 == 2"), {}) is False
        assert evaluate(parse_expr("has_checksum != 0"), {"has_checksum": 1}) is True
        assert evaluate(parse_expr("x < 10"), {"x": 5}) is True
        assert evaluate(parse_expr("x >= 10"), {"x": 10}) is True
        assert evaluate(parse_expr("true and false"), {}) is False
        assert evaluate(parse_expr("false or true"), {}) is True
        assert evaluate(parse_expr("not true"), {}) is False
        assert evaluate(parse_expr("not flag"), {"flag": 0}) is True

    def test_comprehensions(self) -> None:
        assert (
            evaluate(parse_expr("any(item > 5 for item in values)"), {"values": [1, 6, 3]}) is True
        )
        assert (
            evaluate(parse_expr("all(item > 0 for item in values)"), {"values": [1, 2, 3]}) is True
        )
        assert (
            evaluate(
                parse_expr("first(item for item in values if item > 5)"), {"values": [1, 6, 7]}
            )
            == 6
        )
        assert evaluate(parse_expr("first(values)"), {"values": [9, 8, 7]}) == 9
        assert evaluate(
            parse_expr("filter(item > 3 for item in values)"), {"values": [1, 4, 5]}
        ) == [4, 5]
        assert evaluate(parse_expr("map(item * 2 for item in values)"), {"values": [1, 2, 3]}) == [
            2,
            4,
            6,
        ]
        ctx = {"values": [1, 2], "item": 42}
        assert evaluate(parse_expr("map(item for item in values)"), ctx) == [1, 2]
        assert ctx["item"] == 42

    def test_match_and_ternary(self) -> None:
        expr = 'match x with 1 -> "a" | 2 -> "b" | else -> "c"'
        assert evaluate(parse_expr(expr), {"x": 1}) == "a"
        assert evaluate(parse_expr(expr), {"x": 2}) == "b"
        assert evaluate(parse_expr(expr), {"x": 10}) == "c"
        assert evaluate(parse_expr('match x with _ -> "fallback"'), {"x": 123}) == "fallback"
        assert evaluate(parse_expr("10 if flag else 20"), {"flag": True}) == 10
        assert evaluate(parse_expr("10 if flag else 20"), {"flag": False}) == 20

    def test_real_world_like_expressions(self) -> None:
        assert evaluate(parse_expr("has_checksum != 0"), {"has_checksum": 1}) is True
        assert evaluate(parse_expr("total_length - 8"), {"total_length": 20}) == 12
        assert evaluate(parse_expr("_io.size - 4"), {"_io": {"size": 100}}) == 96
        assert evaluate(parse_expr("a < b and b < c"), {"a": 1, "b": 2, "c": 3}) is True
        expr = "(src_ip & 0xFFFF0000) == 0xC0A80000"
        assert evaluate(parse_expr(expr), {"src_ip": 0xC0A80101}) is True
