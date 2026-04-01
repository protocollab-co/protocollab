"""Tests for jsonschema_validator — models, backends, and factory."""

from __future__ import annotations

import importlib.util

import pytest

from jsonschema_validator.models import SchemaValidationError
from jsonschema_validator.backends.base import AbstractSchemaValidator
from jsonschema_validator.backends.jsonschema_backend import JsonschemaBackend
from jsonschema_validator.backends.jsonscreamer_backend import JsonscreamerBackend
from jsonschema_validator.factory import (
    ValidatorFactory,
    BackendNotAvailableError,
    available_backends,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SIMPLE_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
    "additionalProperties": False,
}

VALID_DATA: dict = {"name": "Alice", "age": 30}
MISSING_NAME: dict = {"age": 30}
BAD_TYPE_DATA: dict = {"name": 42}
EXTRA_KEY_DATA: dict = {"name": "Alice", "unexpected": True}


def _has_dependency(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _require_jsonscreamer() -> None:
    pytest.importorskip(
        "jsonscreamer", reason="Install the validator-jsonscreamer extra to run these tests"
    )


def _require_fastjsonschema() -> None:
    pytest.importorskip(
        "fastjsonschema",
        reason="Install the validator-fastjsonschema extra to run these tests",
    )


# ===========================================================================
# SchemaValidationError model
# ===========================================================================


class TestSchemaValidationError:
    def test_str_includes_path_and_message(self) -> None:
        err = SchemaValidationError(path="meta.id", message="does not match pattern")
        assert "meta.id" in str(err)
        assert "does not match pattern" in str(err)

    def test_default_schema_path_is_empty(self) -> None:
        err = SchemaValidationError(path="x", message="y")
        assert err.schema_path == ""

    def test_fields_stored(self) -> None:
        err = SchemaValidationError(path="a.b", message="msg", schema_path="props/a")
        assert err.path == "a.b"
        assert err.message == "msg"
        assert err.schema_path == "props/a"


# ===========================================================================
# AbstractSchemaValidator ABC
# ===========================================================================


class TestAbstractSchemaValidator:
    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            AbstractSchemaValidator()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class AlwaysOk(AbstractSchemaValidator):
            def validate(self, schema, data):
                return []

        v = AlwaysOk()
        assert v.validate({}, {}) == []


# ===========================================================================
# JsonschemaBackend
# ===========================================================================


class TestJsonschemaBackend:
    def test_valid_data_returns_empty(self) -> None:
        v = JsonschemaBackend()
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_missing_required_field(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert len(errors) > 0
        assert all(isinstance(e, SchemaValidationError) for e in errors)

    def test_missing_required_field_path(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert any("(root)" in e.path or "name" in e.message for e in errors)

    def test_wrong_type_detected(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, BAD_TYPE_DATA)
        assert len(errors) > 0
        assert any("name" in e.path for e in errors)

    def test_additional_properties_rejected(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, EXTRA_KEY_DATA)
        assert len(errors) > 0

    def test_error_has_non_empty_message(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert all(len(e.message) > 0 for e in errors)

    def test_error_has_schema_path(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert all(isinstance(e.schema_path, str) for e in errors)

    def test_cache_enabled_by_default(self) -> None:
        v = JsonschemaBackend()
        assert v._cache_enabled is True

    def test_cache_disabled(self) -> None:
        v = JsonschemaBackend(cache=False)
        assert v._cache_enabled is False
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_nested_path_dot_notation(self) -> None:
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["meta"],
            "properties": {
                "meta": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "string", "pattern": "^[a-z_]+$"}},
                }
            },
        }
        v = JsonschemaBackend()
        errors = v.validate(schema, {"meta": {"id": "INVALID_UPPER"}})
        assert any("id" in e.path for e in errors)

    def test_seq_array_index_dot_notation(self) -> None:
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "seq": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    },
                }
            },
        }
        v = JsonschemaBackend()
        errors = v.validate(schema, {"seq": [{"id": 123}]})
        assert any("[0]" in e.path for e in errors)

    def test_validator_cached_same_schema(self) -> None:
        v = JsonschemaBackend(cache=True)
        schema = dict(SIMPLE_SCHEMA)
        v.validate(schema, VALID_DATA)
        v.validate(schema, VALID_DATA)
        assert id(schema) in v._cache

    def test_empty_schema_accepts_anything(self) -> None:
        v = JsonschemaBackend()
        assert v.validate({}, {"any": "value"}) == []


# ===========================================================================
# JsonscreamerBackend
# ===========================================================================


class TestJsonscreamerBackend:
    @pytest.fixture(autouse=True)
    def _require_backend(self) -> None:
        _require_jsonscreamer()

    def test_valid_data_returns_empty(self) -> None:
        v = JsonscreamerBackend()
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_missing_required_field(self) -> None:
        v = JsonscreamerBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert len(errors) > 0
        assert all(isinstance(e, SchemaValidationError) for e in errors)

    def test_wrong_type_detected(self) -> None:
        v = JsonscreamerBackend()
        errors = v.validate(SIMPLE_SCHEMA, BAD_TYPE_DATA)
        assert len(errors) > 0
        assert any("name" in e.path for e in errors)

    def test_error_has_non_empty_message(self) -> None:
        v = JsonscreamerBackend()
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert all(len(e.message) > 0 for e in errors)

    def test_cache_enabled_by_default(self) -> None:
        v = JsonscreamerBackend()
        assert v._cache_enabled is True

    def test_cache_disabled(self) -> None:
        v = JsonscreamerBackend(cache=False)
        assert v._cache_enabled is False
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_nested_path_dot_notation(self) -> None:
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["meta"],
            "properties": {
                "meta": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "string", "pattern": "^[a-z_]+$"}},
                }
            },
        }
        v = JsonscreamerBackend()
        errors = v.validate(schema, {"meta": {"id": "INVALID_UPPER"}})
        assert any("id" in e.path for e in errors)

    def test_seq_array_index_dot_notation(self) -> None:
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "seq": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    },
                }
            },
        }
        v = JsonscreamerBackend()
        errors = v.validate(schema, {"seq": [{"id": 123}]})
        assert any("[0]" in e.path for e in errors)

    def test_validator_cached_same_schema(self) -> None:
        v = JsonscreamerBackend(cache=True)
        schema = dict(SIMPLE_SCHEMA)
        v.validate(schema, VALID_DATA)
        v.validate(schema, VALID_DATA)
        assert id(schema) in v._cache

    def test_empty_schema_accepts_anything(self) -> None:
        v = JsonscreamerBackend()
        assert v.validate({}, {"any": "value"}) == []

    def test_is_instance_of_abstract(self) -> None:
        v = JsonscreamerBackend()
        assert isinstance(v, AbstractSchemaValidator)


# ===========================================================================
# ValidatorFactory
# ===========================================================================


class TestValidatorFactory:
    def test_auto_returns_backend(self) -> None:
        v = ValidatorFactory.create(backend="auto")
        assert isinstance(v, AbstractSchemaValidator)

    def test_auto_prefers_jsonscreamer(self) -> None:
        _require_jsonscreamer()
        v = ValidatorFactory.create(backend="auto")
        assert isinstance(v, JsonscreamerBackend)

    def test_explicit_jsonschema_backend(self) -> None:
        v = ValidatorFactory.create(backend="jsonschema")
        assert isinstance(v, JsonschemaBackend)

    def test_explicit_jsonscreamer_backend(self) -> None:
        _require_jsonscreamer()
        v = ValidatorFactory.create(backend="jsonscreamer")
        assert isinstance(v, JsonscreamerBackend)

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(BackendNotAvailableError):
            ValidatorFactory.create(backend="nonexistent_backend")

    def test_auto_mode_validates_correctly(self) -> None:
        v = ValidatorFactory.create(backend="auto")
        errors = v.validate(SIMPLE_SCHEMA, MISSING_NAME)
        assert len(errors) > 0

    def test_auto_mode_valid_data(self) -> None:
        v = ValidatorFactory.create(backend="auto")
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_cache_false_still_works(self) -> None:
        v = ValidatorFactory.create(backend="jsonschema", cache=False)
        assert v.validate(SIMPLE_SCHEMA, VALID_DATA) == []

    def test_instance_method_returns_same_instance(self) -> None:
        factory = ValidatorFactory()
        v1 = factory._get_or_create("jsonschema")
        v2 = factory._get_or_create("jsonschema")
        assert v1 is v2

    def test_fastjsonschema_not_in_auto(self) -> None:
        from jsonschema_validator.factory import _AUTO_PRIORITY

        assert "fastjsonschema" not in _AUTO_PRIORITY


# ===========================================================================
# available_backends()
# ===========================================================================


class TestAvailableBackends:
    def test_returns_list(self) -> None:
        result = available_backends()
        assert isinstance(result, list)

    def test_jsonschema_always_available(self) -> None:
        result = available_backends()
        assert "jsonschema" in result

    def test_jsonscreamer_available_when_installed(self) -> None:
        _require_jsonscreamer()
        result = available_backends()
        assert "jsonscreamer" in result

    def test_fastjsonschema_not_in_auto(self) -> None:
        from jsonschema_validator.factory import _AUTO_PRIORITY

        assert "fastjsonschema" not in _AUTO_PRIORITY


# ===========================================================================
# Error path normalization — edge cases
# ===========================================================================


class TestErrorPathNormalization:
    def test_root_level_error_returns_root(self) -> None:
        v = JsonschemaBackend()
        errors = v.validate({"type": "object", "required": ["x"]}, {})
        assert any("(root)" in e.path or e.path == "(root)" for e in errors)

    def test_nested_key_path(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "properties": {"b": {"type": "integer"}},
                }
            },
        }
        v = JsonschemaBackend()
        errors = v.validate(schema, {"a": {"b": "not-an-int"}})
        assert any("a" in e.path for e in errors)
        assert any("b" in e.path for e in errors)

    def test_jsonscreamer_root_level_error(self) -> None:
        _require_jsonscreamer()
        v = JsonscreamerBackend()
        errors = v.validate({"type": "object", "required": ["x"]}, {})
        assert any("(root)" in e.path or e.path == "(root)" for e in errors)

    def test_jsonscreamer_nested_key_path(self) -> None:
        _require_jsonscreamer()
        schema = {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "properties": {"b": {"type": "integer"}},
                }
            },
        }
        v = JsonscreamerBackend()
        errors = v.validate(schema, {"a": {"b": "not-an-int"}})
        assert any("a" in e.path for e in errors)
        assert any("b" in e.path for e in errors)


# ===========================================================================
# Integration: protocollab-like schema
# ===========================================================================


class TestProtocollabLikeSchema:
    """Verify the backends handle the actual protocollab base.schema.json."""

    BASE_SCHEMA: dict = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["meta"],
        "properties": {
            "meta": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {
                        "type": "string",
                        "pattern": "^[a-z_][a-z0-9_]*$",
                    },
                    "endian": {"type": "string", "enum": ["le", "be"]},
                },
                "additionalProperties": True,
            },
            "seq": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": True,
    }

    @pytest.mark.parametrize("backend_cls", [JsonschemaBackend, JsonscreamerBackend])
    def test_valid_spec(self, backend_cls) -> None:
        if backend_cls is JsonscreamerBackend:
            _require_jsonscreamer()
        v = backend_cls()
        assert v.validate(self.BASE_SCHEMA, {"meta": {"id": "ping_protocol"}}) == []

    @pytest.mark.parametrize("backend_cls", [JsonschemaBackend, JsonscreamerBackend])
    def test_missing_meta(self, backend_cls) -> None:
        if backend_cls is JsonscreamerBackend:
            _require_jsonscreamer()
        v = backend_cls()
        errors = v.validate(self.BASE_SCHEMA, {"seq": []})
        assert len(errors) > 0

    @pytest.mark.parametrize("backend_cls", [JsonschemaBackend, JsonscreamerBackend])
    def test_bad_id_pattern(self, backend_cls) -> None:
        if backend_cls is JsonscreamerBackend:
            _require_jsonscreamer()
        v = backend_cls()
        errors = v.validate(self.BASE_SCHEMA, {"meta": {"id": "PingProtocol"}})
        assert len(errors) > 0
        assert any("id" in e.path for e in errors)

    @pytest.mark.parametrize("backend_cls", [JsonschemaBackend, JsonscreamerBackend])
    def test_bad_endian_enum(self, backend_cls) -> None:
        if backend_cls is JsonscreamerBackend:
            _require_jsonscreamer()
        v = backend_cls()
        errors = v.validate(self.BASE_SCHEMA, {"meta": {"id": "ping_protocol", "endian": "middle"}})
        assert len(errors) > 0
        assert any("endian" in e.path for e in errors)


# ===========================================================================
# FastjsonschemaBackend
# ===========================================================================


class TestFastjsonschemaBackend:
    """Tests for the fastjsonschema backend."""

    @pytest.fixture(autouse=True)
    def _require_backend(self) -> None:
        _require_fastjsonschema()

    @pytest.fixture
    def backend(self):
        from jsonschema_validator.backends.fastjsonschema_backend import FastjsonschemaBackend

        return FastjsonschemaBackend()

    def test_valid_data_returns_empty(self, backend) -> None:
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        assert backend.validate(schema, {"x": "hello"}) == []

    def test_invalid_data_returns_error(self, backend) -> None:
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        errors = backend.validate(schema, {})
        assert len(errors) > 0
        assert all(isinstance(e, SchemaValidationError) for e in errors)

    def test_collects_all_errors(self, backend) -> None:
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        }
        errors = backend.validate(schema, {"name": 1, "age": "x"})
        assert len(errors) == 2
        assert {error.path for error in errors} == {"name", "age"}

    def test_error_has_non_empty_message(self, backend) -> None:
        schema = {"type": "object", "required": ["x"]}
        errors = backend.validate(schema, {})
        assert all(len(e.message) > 0 for e in errors)

    def test_cache_enabled_by_default(self, backend) -> None:
        assert backend._cache_enabled is True

    def test_cache_stores_compiled_validator(self, backend) -> None:
        schema = {"type": "object"}
        backend.validate(schema, {})
        assert id(schema) in backend._cache

    def test_cache_disabled_does_not_store(self) -> None:
        from jsonschema_validator.backends.fastjsonschema_backend import FastjsonschemaBackend

        v = FastjsonschemaBackend(cache=False)
        schema = {"type": "object"}
        v.validate(schema, {})
        assert len(v._cache) == 0

    def test_cache_reuses_compiled_validator(self, backend) -> None:
        schema = {"type": "object"}
        backend.validate(schema, {})
        first = backend._cache[id(schema)]
        backend.validate(schema, {})
        assert backend._cache[id(schema)] is first

    def test_jsonschema_fallback_validator_cache_reuse(self, backend) -> None:
        schema = {"type": "object"}
        first = backend._get_jsonschema_validator(schema)
        second = backend._get_jsonschema_validator(schema)
        assert backend._jsonschema_cache[id(schema)] is first
        assert second is first

    def test_jsonschema_fallback_validator_without_cache(self) -> None:
        from jsonschema_validator.backends.fastjsonschema_backend import FastjsonschemaBackend

        backend = FastjsonschemaBackend(cache=False)
        schema = {"type": "object"}
        first = backend._get_jsonschema_validator(schema)
        second = backend._get_jsonschema_validator(schema)
        assert first is not second
        assert backend._jsonschema_cache == {}

    def test_is_instance_of_abstract(self, backend) -> None:
        from jsonschema_validator.backends.base import AbstractSchemaValidator

        assert isinstance(backend, AbstractSchemaValidator)

    def test_init_raises_import_error_when_not_installed(self, monkeypatch) -> None:
        import sys

        monkeypatch.setitem(sys.modules, "fastjsonschema", None)
        from jsonschema_validator.backends.fastjsonschema_backend import FastjsonschemaBackend

        with pytest.raises(ImportError, match="fastjsonschema"):
            FastjsonschemaBackend()


# ===========================================================================
# Integer-first path coverage (jsonschema and jsonscreamer _format_path)
# ===========================================================================


class TestIntegerFirstPathCoverage:
    """Covers the ``else: parts.append(f'[{segment}]')`` branch in both backends
    when the first path component is an array index."""

    def test_jsonschema_backend_integer_first_segment(self) -> None:
        # Validate an array — produces a path starting with an integer index
        v = JsonschemaBackend()
        schema = {"type": "array", "items": {"type": "string"}}
        errors = v.validate(schema, [123])
        assert any("[0]" in e.path for e in errors)

    def test_jsonscreamer_backend_integer_first_segment(self) -> None:
        _require_jsonscreamer()
        v = JsonscreamerBackend()
        schema = {"type": "array", "items": {"type": "string"}}
        errors = v.validate(schema, [123])
        assert any("[0]" in e.path for e in errors)

    def test_jsonscreamer_format_path_integer_only(self) -> None:
        if not _has_dependency("jsonscreamer"):
            pytest.skip("Install the validator-jsonscreamer extra to run these tests")
        from jsonschema_validator.backends.jsonscreamer_backend import _format_path

        assert _format_path([0]) == "[0]"

    def test_jsonscreamer_format_path_integer_after_key(self) -> None:
        if not _has_dependency("jsonscreamer"):
            pytest.skip("Install the validator-jsonscreamer extra to run these tests")
        from jsonschema_validator.backends.jsonscreamer_backend import _format_path

        assert _format_path(["seq", 0]) == "seq[0]"

    def test_jsonscreamer_format_schema_path(self) -> None:
        if not _has_dependency("jsonscreamer"):
            pytest.skip("Install the validator-jsonscreamer extra to run these tests")
        from jsonschema_validator.backends.jsonscreamer_backend import _format_schema_path

        assert _format_schema_path(["properties", "meta", "required"]) == "properties/meta/required"


# ===========================================================================
# JsonscreamerBackend — ImportError when not installed
# ===========================================================================


class TestJsonscreamerImportError:
    def test_init_raises_import_error_when_not_installed(self, monkeypatch) -> None:
        import sys

        monkeypatch.setitem(sys.modules, "jsonscreamer", None)
        with pytest.raises(ImportError, match="jsonscreamer"):
            JsonscreamerBackend()


# ===========================================================================
# ValidatorFactory — error paths
# ===========================================================================


class TestValidatorFactoryErrorPaths:
    def test_auto_select_raises_when_no_backends_available(self, monkeypatch) -> None:
        """Cover factory.py lines 143-145: _auto_select raises when all backends fail."""
        import jsonschema_validator.factory as _fac

        monkeypatch.setattr(_fac, "_AUTO_PRIORITY", [])
        with pytest.raises(BackendNotAvailableError, match="No suitable JSON Schema backend"):
            ValidatorFactory.create(backend="auto")

    def test_auto_select_exception_handling_and_raises(self, monkeypatch) -> None:
        """Cover factory.py lines 143-144: except clause fires when probe raises."""
        import sys
        from unittest.mock import MagicMock
        from jsonschema_validator import factory as _fac

        # A probe backend whose instantiation raises ImportError
        broken_mod = MagicMock()
        broken_mod.BrokenProbe.side_effect = ImportError("broken probe")
        monkeypatch.setitem(sys.modules, "_broken_probe_mod_test", broken_mod)
        monkeypatch.setitem(
            _fac._BACKEND_REGISTRY, "_broken_probe", ("_broken_probe_mod_test", "BrokenProbe")
        )
        # Only this broken backend in auto list → probe fails → continue → raise at end
        monkeypatch.setattr(_fac, "_AUTO_PRIORITY", ["_broken_probe"])
        with pytest.raises(BackendNotAvailableError):
            ValidatorFactory.create(backend="auto")

    def test_build_raises_when_module_not_importable(self, monkeypatch) -> None:
        """Cover factory.py lines 155-156: _build catches module ImportError."""
        from jsonschema_validator import factory as _fac

        monkeypatch.setitem(
            _fac._BACKEND_REGISTRY, "_fake_nomod", ("_no_such_module_xyz123", "Cls")
        )
        f = ValidatorFactory()
        with pytest.raises(BackendNotAvailableError, match="_fake_nomod"):
            f._build("_fake_nomod")

    def test_build_raises_when_class_init_raises_import_error(self, monkeypatch) -> None:
        """Cover factory.py lines 162-163: _build catches class-level ImportError."""
        import sys
        from unittest.mock import MagicMock
        from jsonschema_validator import factory as _fac

        fake_mod = MagicMock()
        fake_mod.FakeBackend.side_effect = ImportError("missing dep")
        monkeypatch.setitem(sys.modules, "_fake_init_mod_test", fake_mod)
        monkeypatch.setitem(
            _fac._BACKEND_REGISTRY, "_fake_init", ("_fake_init_mod_test", "FakeBackend")
        )
        f = ValidatorFactory()
        with pytest.raises(BackendNotAvailableError, match="missing dep"):
            f._build("_fake_init")


# ===========================================================================
# available_backends() — exception handling
# ===========================================================================


class TestAvailableBackendsExceptionHandling:
    def test_broken_backend_is_silently_skipped(self, monkeypatch) -> None:
        """Cover factory.py lines 177-178: exception from broken backend is silently passed."""
        import sys
        from unittest.mock import MagicMock
        from jsonschema_validator import factory as _fac

        broken_mod = MagicMock()
        broken_mod.BrokenBackend.side_effect = Exception("unexpected failure")
        monkeypatch.setitem(sys.modules, "_broken_mod_xyz_test", broken_mod)
        monkeypatch.setitem(
            _fac._BACKEND_REGISTRY, "_broken", ("_broken_mod_xyz_test", "BrokenBackend")
        )
        result = available_backends()
        assert "_broken" not in result
        assert "jsonschema" in result  # other backends still work
