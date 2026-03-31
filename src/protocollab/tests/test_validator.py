"""Tests for the protocollab.validator module."""

import json
import pytest
from pathlib import Path

from protocollab.validator import validate_protocol, ValidationResult, ValidationError
from protocollab.validator.schema_validator import SchemaValidator
from protocollab.exceptions import FileLoadError, YAMLParseError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_yaml(tmp_path):
    f = tmp_path / "valid.yaml"
    f.write_text("meta:\n  id: ping_protocol\n  endian: le\nseq: []\n")
    return f


@pytest.fixture()
def valid_yaml_no_endian(tmp_path):
    """Valid: endian is optional."""
    f = tmp_path / "no_endian.yaml"
    f.write_text("meta:\n  id: my_proto\nseq:\n  - id: x\n    type: u1\n")
    return f


@pytest.fixture()
def no_meta_yaml(tmp_path):
    f = tmp_path / "no_meta.yaml"
    f.write_text("seq:\n  - id: x\n    type: u1\n")
    return f


@pytest.fixture()
def bad_id_yaml(tmp_path):
    """meta.id uses CamelCase — fails pattern."""
    f = tmp_path / "bad_id.yaml"
    f.write_text("meta:\n  id: PingProtocol\n")
    return f


@pytest.fixture()
def bad_endian_yaml(tmp_path):
    """meta.endian has an invalid value."""
    f = tmp_path / "bad_endian.yaml"
    f.write_text("meta:\n  id: ping_protocol\n  endian: LE\n")
    return f


@pytest.fixture()
def missing_file():
    return "/nonexistent/path/does_not_exist.yaml"


@pytest.fixture()
def invalid_yaml(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("key: [\n  unclosed bracket\n")
    return f


@pytest.fixture()
def strict_schema_path():
    return str(Path(__file__).parent.parent / "validator" / "schemas" / "protocol.schema.json")


# ---------------------------------------------------------------------------
# validate_protocol — valid files
# ---------------------------------------------------------------------------


class TestValidateProtocolValid:
    def test_valid_returns_true(self, valid_yaml):
        result = validate_protocol(str(valid_yaml))
        assert result.is_valid is True

    def test_valid_has_no_errors(self, valid_yaml):
        result = validate_protocol(str(valid_yaml))
        assert result.errors == []

    def test_result_is_truthy(self, valid_yaml):
        result = validate_protocol(str(valid_yaml))
        assert bool(result) is True

    def test_file_path_in_result(self, valid_yaml):
        result = validate_protocol(str(valid_yaml))
        assert result.file_path == str(valid_yaml)

    def test_valid_no_endian(self, valid_yaml_no_endian):
        result = validate_protocol(str(valid_yaml_no_endian))
        assert result.is_valid is True

    def test_returns_validation_result_type(self, valid_yaml):
        result = validate_protocol(str(valid_yaml))
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# validate_protocol — invalid files
# ---------------------------------------------------------------------------


class TestValidateProtocolInvalid:
    def test_no_meta_is_invalid(self, no_meta_yaml):
        result = validate_protocol(str(no_meta_yaml))
        assert result.is_valid is False

    def test_no_meta_has_errors(self, no_meta_yaml):
        result = validate_protocol(str(no_meta_yaml))
        assert len(result.errors) > 0

    def test_bad_id_is_invalid(self, bad_id_yaml):
        result = validate_protocol(str(bad_id_yaml))
        assert result.is_valid is False

    def test_bad_id_error_path(self, bad_id_yaml):
        result = validate_protocol(str(bad_id_yaml))
        paths = [e.path for e in result.errors]
        assert any("id" in p for p in paths)

    def test_bad_endian_is_invalid(self, bad_endian_yaml):
        result = validate_protocol(str(bad_endian_yaml))
        assert result.is_valid is False

    def test_bad_endian_error_path(self, bad_endian_yaml):
        result = validate_protocol(str(bad_endian_yaml))
        paths = [e.path for e in result.errors]
        assert any("endian" in p for p in paths)

    def test_is_falsy_when_invalid(self, no_meta_yaml):
        result = validate_protocol(str(no_meta_yaml))
        assert bool(result) is False


# ---------------------------------------------------------------------------
# validate_protocol — file errors
# ---------------------------------------------------------------------------


class TestValidateProtocolFileErrors:
    def test_missing_file_raises_file_load_error(self, missing_file):
        with pytest.raises(FileLoadError):
            validate_protocol(missing_file)

    def test_invalid_yaml_raises_yaml_parse_error(self, invalid_yaml):
        with pytest.raises(YAMLParseError):
            validate_protocol(str(invalid_yaml))


# ---------------------------------------------------------------------------
# validate_protocol — custom schema
# ---------------------------------------------------------------------------


class TestValidateProtocolCustomSchema:
    def test_strict_schema_rejects_extra_top_level(self, tmp_path, strict_schema_path):
        f = tmp_path / "extra.yaml"
        f.write_text("meta:\n  id: ping\nunknown_key: 123\n")
        result = validate_protocol(str(f), schema_path=strict_schema_path)
        assert result.is_valid is False

    def test_strict_schema_valid_file(self, valid_yaml, strict_schema_path):
        result = validate_protocol(str(valid_yaml), schema_path=strict_schema_path)
        assert result.is_valid is True

    def test_strict_meta_no_extra_keys(self, tmp_path, strict_schema_path):
        f = tmp_path / "extra_meta.yaml"
        f.write_text("meta:\n  id: ping\n  unknown_meta_key: 1\n")
        result = validate_protocol(str(f), schema_path=strict_schema_path)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# SchemaValidator directly
# ---------------------------------------------------------------------------


class TestSchemaValidator:
    def test_valid_data_returns_empty(self):
        sv = SchemaValidator()
        errors = sv.validate({"meta": {"id": "my_proto"}})
        assert errors == []

    def test_no_meta_returns_errors(self):
        sv = SchemaValidator()
        errors = sv.validate({"seq": []})
        assert len(errors) > 0

    def test_errors_are_validation_error_instances(self):
        sv = SchemaValidator()
        errors = sv.validate({"seq": []})
        assert all(isinstance(e, ValidationError) for e in errors)

    def test_bad_id_pattern(self):
        sv = SchemaValidator()
        errors = sv.validate({"meta": {"id": "BAD-ID"}})
        assert len(errors) > 0
        assert any("id" in e.path for e in errors)

    def test_bad_endian_enum(self):
        sv = SchemaValidator()
        errors = sv.validate({"meta": {"id": "good_id", "endian": "middle"}})
        assert len(errors) > 0
        assert any("endian" in e.path for e in errors)

    def test_good_endian_le(self):
        sv = SchemaValidator()
        errors = sv.validate({"meta": {"id": "good_id", "endian": "le"}})
        assert errors == []

    def test_good_endian_be(self):
        sv = SchemaValidator()
        errors = sv.validate({"meta": {"id": "good_id", "endian": "be"}})
        assert errors == []

    def test_multiple_errors(self):
        sv = SchemaValidator()
        # No meta at all — only 'meta is required' error
        errors = sv.validate({})
        assert len(errors) >= 1

    def test_error_has_message(self):
        sv = SchemaValidator()
        errors = sv.validate({"seq": []})
        assert all(len(e.message) > 0 for e in errors)

    def test_error_has_schema_path(self):
        sv = SchemaValidator()
        errors = sv.validate({"seq": []})
        assert all(len(e.schema_path) > 0 for e in errors)

    def test_custom_schema_path(self, tmp_path):
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        schema_file = tmp_path / "custom.schema.json"
        schema_file.write_text(json.dumps(schema))
        sv = SchemaValidator(schema_path=str(schema_file))
        assert sv.validate({"name": "ok"}) == []
        assert len(sv.validate({"other": 1})) > 0


# ---------------------------------------------------------------------------
# SchemaValidator — DSL syntax fields (base schema)
# ---------------------------------------------------------------------------


class TestSchemaValidatorDslFields:
    """Verify the base schema accepts valid DSL expression fields in seq items."""

    def test_if_expr_string_accepted(self):
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [
                {"id": "flag", "type": "u1"},
                {"id": "opt", "type": "u4", "if": "flag != 0"},
            ],
        }
        assert sv.validate(data) == []

    def test_repeat_expr_string_accepted(self):
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [
                {"id": "count", "type": "u1"},
                {"id": "items", "type": "u1", "repeat": "expr", "repeat-expr": "count"},
            ],
        }
        assert sv.validate(data) == []

    def test_size_integer_accepted(self):
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "body", "size": 8}],
        }
        assert sv.validate(data) == []

    def test_size_string_accepted(self):
        """Base schema allows size to be a string (DSL expression or ksy compat)."""
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "body", "size": "payload_size"}],
        }
        assert sv.validate(data) == []

    def test_if_expr_non_string_rejected(self):
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "f", "type": "u1", "if": 123}],
        }
        errors = sv.validate(data)
        assert len(errors) > 0
        assert any("if" in e.path for e in errors)

    def test_repeat_expr_non_string_rejected(self):
        sv = SchemaValidator()
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "f", "type": "u1", "repeat": "expr", "repeat-expr": 6}],
        }
        errors = sv.validate(data)
        assert len(errors) > 0
        assert any("repeat-expr" in e.path for e in errors)


# ---------------------------------------------------------------------------
# SchemaValidator — DSL syntax fields (strict schema)
# ---------------------------------------------------------------------------


class TestStrictSchemaDslFields:
    """Verify the strict schema constrains DSL expression fields in seq items."""

    @pytest.fixture()
    def strict_sv(self):
        from pathlib import Path

        schema_path = str(
            Path(__file__).parent.parent / "validator" / "schemas" / "protocol.schema.json"
        )
        return SchemaValidator(schema_path=schema_path)

    def test_if_expr_string_accepted(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [
                {"id": "flag", "type": "u1"},
                {"id": "opt", "type": "u4", "if": "flag != 0"},
            ],
        }
        assert strict_sv.validate(data) == []

    def test_repeat_expr_string_accepted(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [
                {"id": "count", "type": "u1"},
                {"id": "items", "type": "u1", "repeat": "expr", "repeat-expr": "count"},
            ],
        }
        assert strict_sv.validate(data) == []

    def test_size_integer_accepted(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "body", "type": "str", "size": 8}],
        }
        assert strict_sv.validate(data) == []

    def test_if_non_string_rejected(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "f", "type": "u1", "if": 1}],
        }
        errors = strict_sv.validate(data)
        assert len(errors) > 0
        assert any("if" in e.path for e in errors)

    def test_repeat_expr_non_string_rejected(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "f", "type": "u1", "repeat": "expr", "repeat-expr": 6}],
        }
        errors = strict_sv.validate(data)
        assert len(errors) > 0
        assert any("repeat-expr" in e.path for e in errors)

    def test_size_non_integer_rejected(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "body", "size": "not_an_int"}],
        }
        errors = strict_sv.validate(data)
        assert len(errors) > 0
        assert any("size" in e.path for e in errors)

    def test_size_negative_rejected(self, strict_sv):
        data = {
            "meta": {"id": "p"},
            "seq": [{"id": "body", "size": -1}],
        }
        errors = strict_sv.validate(data)
        assert len(errors) > 0
        assert any("size" in e.path for e in errors)


# ---------------------------------------------------------------------------
# ValidationResult model
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_bool_true_when_valid(self):
        r = ValidationResult(is_valid=True, errors=[], file_path="x.yaml")
        assert bool(r) is True

    def test_bool_false_when_invalid(self):
        err = ValidationError(path="meta", message="missing", schema_path="required")
        r = ValidationResult(is_valid=False, errors=[err], file_path="x.yaml")
        assert bool(r) is False

    def test_file_path_stored(self):
        r = ValidationResult(is_valid=True, errors=[], file_path="proto.yaml")
        assert r.file_path == "proto.yaml"


# ---------------------------------------------------------------------------
# ValidationError model
# ---------------------------------------------------------------------------


class TestValidationError:
    def test_fields(self):
        e = ValidationError(
            path="meta.id",
            message="does not match",
            schema_path="properties/meta/properties/id/pattern",
        )
        assert e.path == "meta.id"
        assert e.message == "does not match"
        assert "id" in e.schema_path
