"""Tests for protocollab.validator — pipeline, semantic, and expression validators."""

from __future__ import annotations

from pathlib import Path

import pytest

from protocollab.core import parse_spec
from protocollab.validator import (
    PipelineResult,
    ValidationIssue,
    ValidationLevel,
    ValidationPipeline,
    validate_pipeline,
    validate_protocol,
)
from protocollab.validator.base_validator import BaseValidator
from protocollab.validator.expression_validator import ExpressionValidator
from protocollab.validator.models import ValidationResult
from protocollab.validator.semantic_validator import SemanticValidator

EXAMPLES = Path(__file__).parents[3] / "examples"
SIMPLE = EXAMPLES / "simple"
WITH_INCLUDES = EXAMPLES / "with_includes"


# ===========================================================================
# ValidationLevel
# ===========================================================================


class TestValidationLevel:
    def test_error_value(self) -> None:
        assert ValidationLevel.ERROR.value == "error"

    def test_warning_value(self) -> None:
        assert ValidationLevel.WARNING.value == "warning"


# ===========================================================================
# ValidationIssue
# ===========================================================================


class TestValidationIssue:
    def test_str_with_code(self) -> None:
        issue = ValidationIssue(path="seq[0].type", message="Unknown type", code="E1")
        s = str(issue)
        assert "E1" in s
        assert "seq[0].type" in s

    def test_str_without_code(self) -> None:
        issue = ValidationIssue(path="meta.id", message="Missing")
        s = str(issue)
        assert "meta.id" in s
        assert "Missing" in s

    def test_default_level_is_error(self) -> None:
        issue = ValidationIssue(path="x", message="y")
        assert issue.level == ValidationLevel.ERROR


# ===========================================================================
# PipelineResult
# ===========================================================================


class TestPipelineResult:
    def _error(self, msg: str = "err") -> ValidationIssue:
        return ValidationIssue(path="x", message=msg, level=ValidationLevel.ERROR)

    def _warning(self, msg: str = "warn") -> ValidationIssue:
        return ValidationIssue(path="x", message=msg, level=ValidationLevel.WARNING)

    def test_is_valid_no_errors(self) -> None:
        result = PipelineResult()
        assert result.is_valid is True

    def test_is_valid_with_errors(self) -> None:
        result = PipelineResult(errors=[self._error()])
        assert result.is_valid is False

    def test_bool_true(self) -> None:
        result = PipelineResult()
        assert bool(result) is True

    def test_bool_false(self) -> None:
        result = PipelineResult(errors=[self._error()])
        assert bool(result) is False

    def test_warnings_dont_affect_validity(self) -> None:
        result = PipelineResult(warnings=[self._warning()])
        assert result.is_valid is True

    def test_all_issues(self) -> None:
        e = self._error()
        w = self._warning()
        result = PipelineResult(errors=[e], warnings=[w])
        all_issues = result.all_issues()
        assert e in all_issues
        assert w in all_issues
        # errors first
        assert all_issues[0] is e

    def test_file_path(self) -> None:
        result = PipelineResult(file_path="/tmp/foo.yaml")
        assert result.file_path == "/tmp/foo.yaml"


# ===========================================================================
# BaseValidator ABC
# ===========================================================================


class TestBaseValidator:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseValidator()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class AlwaysOk(BaseValidator):
            def validate(self, spec):
                return []

        v = AlwaysOk()
        spec = parse_spec({"meta": {"id": "p", "endian": "le"}})
        assert v.validate(spec) == []


# ===========================================================================
# SemanticValidator
# ===========================================================================

VALID_DICT: dict = {
    "meta": {"id": "ping", "endian": "le"},
    "seq": [
        {"id": "type_id", "type": "u1"},
        {"id": "sequence", "type": "u4"},
    ],
}

UNKNOWN_TYPE_DICT: dict = {
    "meta": {"id": "bad", "endian": "le"},
    "seq": [
        {"id": "field", "type": "ghost_type"},
    ],
}

DUPLICATE_IDS_DICT: dict = {
    "meta": {"id": "dup", "endian": "le"},
    "seq": [
        {"id": "field_a", "type": "u1"},
        {"id": "field_a", "type": "u4"},  # duplicate!
    ],
}

WITH_CUSTOM_TYPES_DICT: dict = {
    "meta": {"id": "typed", "endian": "le"},
    "seq": [{"id": "ts", "type": "timestamp_t"}],
    "types": {
        "timestamp_t": {
            "seq": [
                {"id": "seconds", "type": "u4"},
                {"id": "micros", "type": "u4"},
            ]
        }
    },
}


class TestSemanticValidator:
    def test_valid_spec_no_issues(self) -> None:
        spec = parse_spec(VALID_DICT)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert issues == []

    def test_unknown_type_raises_error(self) -> None:
        spec = parse_spec(UNKNOWN_TYPE_DICT)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert any(i.level == ValidationLevel.ERROR for i in issues)
        assert any("ghost_type" in i.message for i in issues)

    def test_unknown_type_path(self) -> None:
        spec = parse_spec(UNKNOWN_TYPE_DICT)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert any("seq[0].type" in i.path for i in issues)

    def test_duplicate_ids_detected(self) -> None:
        spec = parse_spec(DUPLICATE_IDS_DICT)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert any("Duplicate" in i.message for i in issues)

    def test_custom_types_valid(self) -> None:
        spec = parse_spec(WITH_CUSTOM_TYPES_DICT)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert issues == []

    def test_unknown_type_in_types_section(self) -> None:
        data = {
            "meta": {"id": "p", "endian": "le"},
            "types": {"hdr": {"seq": [{"id": "x", "type": "ghost_type"}]}},
        }
        spec = parse_spec(data)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert any("ghost_type" in i.message for i in issues)

    def test_duplicate_ids_in_type_section(self) -> None:
        data = {
            "meta": {"id": "p", "endian": "le"},
            "types": {
                "hdr": {
                    "seq": [
                        {"id": "x", "type": "u1"},
                        {"id": "x", "type": "u4"},  # duplicate
                    ]
                }
            },
        }
        spec = parse_spec(data)
        v = SemanticValidator()
        issues = v.validate(spec)
        assert any("Duplicate" in i.message for i in issues)


# ===========================================================================
# ExpressionValidator
# ===========================================================================

GOOD_EXPR_DICT: dict = {
    "meta": {"id": "cond", "endian": "le"},
    "seq": [
        {"id": "has_flag", "type": "u1"},
        {"id": "opt_field", "type": "u4", "if": "has_flag != 0"},
    ],
}

BAD_EXPR_DICT: dict = {
    "meta": {"id": "bad_expr", "endian": "le"},
    "seq": [
        {"id": "opt", "type": "u4", "if": "@illegal_syntax"},
    ],
}


class TestExpressionValidator:
    def test_valid_spec_no_issues(self) -> None:
        spec = parse_spec(GOOD_EXPR_DICT)
        v = ExpressionValidator()
        issues = v.validate(spec)
        assert issues == []

    def test_invalid_expr_detected(self) -> None:
        spec = parse_spec(BAD_EXPR_DICT)
        v = ExpressionValidator()
        issues = v.validate(spec)
        assert len(issues) > 0
        assert any(i.level == ValidationLevel.ERROR for i in issues)

    def test_invalid_expr_path(self) -> None:
        spec = parse_spec(BAD_EXPR_DICT)
        v = ExpressionValidator()
        issues = v.validate(spec)
        assert any("seq[0].if" in i.path for i in issues)

    def test_no_expression_no_issues(self) -> None:
        data = {
            "meta": {"id": "p", "endian": "le"},
            "seq": [{"id": "x", "type": "u1"}],
        }
        spec = parse_spec(data)
        v = ExpressionValidator()
        assert v.validate(spec) == []


# ===========================================================================
# ValidationPipeline
# ===========================================================================


class TestValidationPipeline:
    def test_valid_spec_passes(self) -> None:
        raw = VALID_DICT
        spec = parse_spec(raw)
        pipeline = ValidationPipeline()
        result = pipeline.run(spec, raw_data=raw)
        assert result.is_valid

    def test_result_is_pipeline_result(self) -> None:
        spec = parse_spec(VALID_DICT)
        pipeline = ValidationPipeline()
        result = pipeline.run(spec, raw_data=VALID_DICT)
        assert isinstance(result, PipelineResult)

    def test_custom_validators_list(self) -> None:
        class AlwaysError(BaseValidator):
            def validate(self, spec):
                return [
                    ValidationIssue(
                        path="test",
                        message="always fails",
                        level=ValidationLevel.ERROR,
                    )
                ]

        pipeline = ValidationPipeline(validators=[AlwaysError()])
        spec = parse_spec(VALID_DICT)
        result = pipeline.run(spec)
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_warnings_collected(self) -> None:
        class WarnValidator(BaseValidator):
            def validate(self, spec):
                return [
                    ValidationIssue(
                        path="meta",
                        message="suggestion",
                        level=ValidationLevel.WARNING,
                    )
                ]

        pipeline = ValidationPipeline(validators=[WarnValidator()])
        spec = parse_spec(VALID_DICT)
        result = pipeline.run(spec)
        assert result.is_valid
        assert len(result.warnings) == 1

    def test_all_validators_run_even_on_errors(self) -> None:
        collected: list = []

        class Counter(BaseValidator):
            def validate(self, spec):
                collected.append(1)
                return []

        class AlwaysError(BaseValidator):
            def validate(self, spec):
                return [ValidationIssue(path="x", message="err")]

        pipeline = ValidationPipeline(validators=[AlwaysError(), Counter(), Counter()])
        spec = parse_spec(VALID_DICT)
        pipeline.run(spec)
        assert len(collected) == 2  # both Counter instances ran

    def test_file_path_in_result(self) -> None:
        spec = parse_spec(VALID_DICT)
        pipeline = ValidationPipeline(validators=[])
        result = pipeline.run(spec, file_path="/foo/bar.yaml")
        assert result.file_path == "/foo/bar.yaml"


# ===========================================================================
# validate_pipeline() function
# ===========================================================================


class TestValidatePipelineFunction:
    def test_valid_file_passes(self) -> None:
        result = validate_pipeline(str(SIMPLE / "ping_protocol.yaml"))
        assert result.is_valid

    def test_returns_pipeline_result(self) -> None:
        result = validate_pipeline(str(SIMPLE / "ping_protocol.yaml"))
        assert isinstance(result, PipelineResult)

    def test_missing_file_raises(self) -> None:
        from protocollab.exceptions import FileLoadError

        with pytest.raises(FileLoadError):
            validate_pipeline("/nonexistent/file.yaml")

    def test_with_includes_valid(self) -> None:
        result = validate_pipeline(str(WITH_INCLUDES / "tcp_like.yaml"))
        assert result.is_valid


# ===========================================================================
# validate_protocol() backward-compat
# ===========================================================================


class TestValidateProtocolBackcompat:
    def test_returns_validation_result(self) -> None:
        result = validate_protocol(str(SIMPLE / "ping_protocol.yaml"))
        assert isinstance(result, ValidationResult)

    def test_valid_file(self) -> None:
        result = validate_protocol(str(SIMPLE / "ping_protocol.yaml"))
        assert result.is_valid

    def test_file_path_in_result(self) -> None:
        path = str(SIMPLE / "ping_protocol.yaml")
        result = validate_protocol(path)
        assert result.file_path == path
