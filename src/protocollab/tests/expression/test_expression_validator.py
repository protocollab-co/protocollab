"""Validator tests for protocollab.expression."""

from __future__ import annotations

from protocollab.expression import validate_expr


class TestValidateExpr:
    def test_valid_returns_empty(self) -> None:
        assert validate_expr("has_checksum != 0") == []

    def test_syntax_errors(self) -> None:
        errors = validate_expr("@bad")
        assert len(errors) == 1
        assert errors[0].pos >= 0

        assert len(validate_expr("(a + b")) > 0
        assert len(validate_expr("")) > 0

    def test_complex_valid_exprs(self) -> None:
        assert validate_expr("total_length - 8 if has_ext else fixed_size") == []
        assert validate_expr("(src_ip & 0xFFFF0000) == 0xC0A80000") == []

    def test_forbidden_name_error(self) -> None:
        assert len(validate_expr("eval")) > 0

    def test_validate_comprehension_names(self) -> None:
        assert validate_expr("any(v > 1 for v in values)") == []

    def test_validate_comprehension_shadow_conflict(self) -> None:
        errors = validate_expr("any(any(v > 0 for v in ys) for v in xs)")
        assert len(errors) == 1
        assert "conflicts" in errors[0].message

    def test_error_str_with_pos(self) -> None:
        from protocollab.expression.validator import ExprError

        error = ExprError(message="boom", pos=5)
        assert "5" in str(error)
        assert "boom" in str(error)

    def test_error_str_no_pos(self) -> None:
        from protocollab.expression.validator import ExprError

        error = ExprError(message="boom")
        assert "boom" in str(error)
        assert "pos" not in str(error)
