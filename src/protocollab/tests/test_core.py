"""Tests for protocollab.core — Pydantic models, parser, and import resolver.

Tests
-----
test_parse_spec_*        — parse_spec() / ProtocolSpec
test_models_*            — Model-level invariants (Endianness, FieldDef aliases …)
test_import_resolver_*   — ImportResolver happy-path and error cases
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from protocollab.core import (
    CyclicImportError,
    Endianness,
    FieldDef,
    ImportResolver,
    MetaSection,
    ProtocolSpec,
    TypeDef,
    parse_spec,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_DICT: dict = {
    "meta": {"id": "proto", "endian": "le"},
}

FULL_DICT: dict = {
    "meta": {
        "id": "ping_protocol",
        "endian": "le",
        "title": "Ping Protocol",
        "description": "Simple ping",
        "version": "1.0",
    },
    "seq": [
        {"id": "type_id", "type": "u1", "doc": "Message type"},
        {"id": "sequence_number", "type": "u4"},
        {
            "id": "checksum",
            "type": "u4",
            "if": "has_checksum != 0",
            "doc": "Optional checksum",
        },
    ],
    "types": {
        "timestamp_t": {
            "doc": "Timestamp",
            "seq": [
                {"id": "seconds", "type": "u4"},
                {"id": "microseconds", "type": "u4"},
            ],
        }
    },
    "doc": "Top-level doc",
    "imports": ["base_types.yaml"],
}


# ---------------------------------------------------------------------------
# parse_spec — basic
# ---------------------------------------------------------------------------


class TestParseSpecBasic:
    def test_minimal_spec(self) -> None:
        spec = parse_spec(MINIMAL_DICT)
        assert isinstance(spec, ProtocolSpec)
        assert spec.meta.id == "proto"

    def test_returns_protocol_spec_instance(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert isinstance(spec, ProtocolSpec)

    def test_meta_fields(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.meta.id == "ping_protocol"
        assert spec.meta.title == "Ping Protocol"
        assert spec.meta.description == "Simple ping"
        assert spec.meta.version == "1.0"

    def test_endianness_le(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.meta.endian == Endianness.LE

    def test_endianness_be(self) -> None:
        data = {"meta": {"id": "p", "endian": "be"}}
        spec = parse_spec(data)
        assert spec.meta.endian == Endianness.BE

    def test_seq_parsed(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert len(spec.seq) == 3
        assert spec.seq[0].id == "type_id"
        assert spec.seq[0].type == "u1"

    def test_seq_default_empty(self) -> None:
        spec = parse_spec(MINIMAL_DICT)
        assert spec.seq == []

    def test_types_parsed(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert "timestamp_t" in spec.types
        ts = spec.types["timestamp_t"]
        assert isinstance(ts, TypeDef)
        assert len(ts.seq) == 2

    def test_types_default_empty(self) -> None:
        spec = parse_spec(MINIMAL_DICT)
        assert spec.types == {}

    def test_instances_default_empty(self) -> None:
        spec = parse_spec(MINIMAL_DICT)
        assert spec.instances == {}

    def test_instances_parsed(self) -> None:
        data = {
            "meta": {"id": "p", "endian": "le"},
            "instances": {"scope": {"value": '"lan"', "wireshark": {"type": "string"}}},
        }
        spec = parse_spec(data)
        assert "scope" in spec.instances

    def test_doc_field(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.doc == "Top-level doc"

    def test_imports_list(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.imports == ["base_types.yaml"]

    def test_imports_default_empty(self) -> None:
        spec = parse_spec(MINIMAL_DICT)
        assert spec.imports == []

    def test_resolved_imports_default_empty(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.resolved_imports == {}

    def test_extra_top_level_keys_allowed(self) -> None:
        data = {"meta": {"id": "p", "endian": "le"}, "future_key": 42}
        spec = parse_spec(data)
        assert spec is not None  # no ValidationError

    def test_extra_meta_keys_allowed(self) -> None:
        data = {"meta": {"id": "p", "endian": "le", "author": "Alice"}}
        spec = parse_spec(data)
        assert spec.meta.id == "p"


# ---------------------------------------------------------------------------
# parse_spec — errors
# ---------------------------------------------------------------------------


class TestParseSpecErrors:
    def test_missing_meta_raises(self) -> None:
        with pytest.raises(ValidationError):
            parse_spec({"seq": []})

    def test_missing_meta_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            parse_spec({"meta": {"endian": "le"}})

    def test_invalid_endian_raises(self) -> None:
        with pytest.raises(ValidationError):
            parse_spec({"meta": {"id": "p", "endian": "LE"}})  # uppercase invalid

    def test_invalid_endian_value_raises(self) -> None:
        with pytest.raises(ValidationError):
            parse_spec({"meta": {"id": "p", "endian": "big"}})

    def test_non_string_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            parse_spec({"meta": {"id": 123, "endian": "le"}})


# ---------------------------------------------------------------------------
# FieldDef alias
# ---------------------------------------------------------------------------


class TestFieldDefAlias:
    def test_if_expr_alias(self) -> None:
        field = FieldDef.model_validate({"id": "checksum", "type": "u4", "if": "has_flag != 0"})
        assert field.if_expr == "has_flag != 0"

    def test_if_expr_python_name(self) -> None:
        field = FieldDef.model_validate({"id": "checksum", "type": "u4", "if": "has_flag"})
        assert field.if_expr == "has_flag"

    def test_repeat_expr_alias(self) -> None:
        field = FieldDef.model_validate(
            {"id": "items", "type": "u1", "repeat": "expr", "repeat-expr": "count"}
        )
        assert field.repeat_expr == "count"

    def test_none_by_default(self) -> None:
        field = FieldDef.model_validate({"id": "x", "type": "u1"})
        assert field.if_expr is None
        assert field.repeat_expr is None

    def test_extra_field_allowed(self) -> None:
        field = FieldDef.model_validate({"id": "x", "type": "u1", "encoding": "utf8"})
        assert field.id == "x"


# ---------------------------------------------------------------------------
# Model shortcuts
# ---------------------------------------------------------------------------


class TestProtocolSpecShortcuts:
    def test_id_shortcut(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.id == spec.meta.id == "ping_protocol"

    def test_endian_shortcut(self) -> None:
        spec = parse_spec(FULL_DICT)
        assert spec.endian == spec.meta.endian == Endianness.LE


# ---------------------------------------------------------------------------
# Endianness enum
# ---------------------------------------------------------------------------


class TestEndianness:
    def test_le_value(self) -> None:
        assert Endianness.LE.value == "le"

    def test_be_value(self) -> None:
        assert Endianness.BE.value == "be"

    def test_is_str_subclass(self) -> None:
        assert isinstance(Endianness.LE, str)
        assert Endianness.LE == "le"

    def test_members(self) -> None:
        members = {e.value for e in Endianness}
        assert members == {"le", "be"}


# ---------------------------------------------------------------------------
# MetaSection optional fields
# ---------------------------------------------------------------------------


class TestMetaSection:
    def test_optional_fields_default_none(self) -> None:
        m = MetaSection(id="p")
        assert m.version is None
        assert m.description is None
        assert m.title is None

    def test_endian_default_le(self) -> None:
        m = MetaSection(id="p")
        assert m.endian == Endianness.LE


# ---------------------------------------------------------------------------
# TypeDef
# ---------------------------------------------------------------------------


class TestTypeDef:
    def test_empty_typedef(self) -> None:
        td = TypeDef()
        assert td.seq == []
        assert td.doc is None

    def test_typedef_with_fields(self) -> None:
        td = TypeDef(
            seq=[
                FieldDef.model_validate({"id": "x", "type": "u1"}),
                FieldDef.model_validate({"id": "y", "type": "u2"}),
            ],
            doc="Two bytes",
        )
        assert len(td.seq) == 2
        assert td.doc == "Two bytes"


# ---------------------------------------------------------------------------
# ImportResolver — happy-path (real files)
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).parents[3] / "examples"
WITH_INCLUDES = EXAMPLES_DIR / "with_includes"
SIMPLE_DIR = EXAMPLES_DIR / "simple"


@pytest.fixture
def resolver() -> ImportResolver:
    return ImportResolver()


class TestImportResolverHappyPath:
    def test_resolve_simple_spec(self, resolver: ImportResolver) -> None:
        spec = resolver.resolve(SIMPLE_DIR / "ping_protocol.yaml")
        assert isinstance(spec, ProtocolSpec)
        assert spec.meta.id == "ping_protocol"

    def test_resolve_returns_protocol_spec(self, resolver: ImportResolver) -> None:
        spec = resolver.resolve(SIMPLE_DIR / "ping_protocol.yaml")
        assert isinstance(spec, ProtocolSpec)

    def test_resolve_with_imports(self, resolver: ImportResolver) -> None:
        spec = resolver.resolve(WITH_INCLUDES / "tcp_like.yaml")
        assert "base_types.yaml" in spec.resolved_imports
        base = spec.resolved_imports["base_types.yaml"]
        assert isinstance(base, ProtocolSpec)
        assert base.meta.id == "base_types"

    def test_resolve_imports_recursively(self, resolver: ImportResolver) -> None:
        spec = resolver.resolve(WITH_INCLUDES / "tcp_like.yaml")
        # tcp_like imports base_types which has no imports
        base = spec.resolved_imports["base_types.yaml"]
        assert base.resolved_imports == {}

    def test_cache_reuse(self, resolver: ImportResolver) -> None:
        path = SIMPLE_DIR / "ping_protocol.yaml"
        spec1 = resolver.resolve(path)
        spec2 = resolver.resolve(path)
        assert spec1 is spec2  # same cached object

    def test_clear_cache(self, resolver: ImportResolver) -> None:
        path = SIMPLE_DIR / "ping_protocol.yaml"
        spec1 = resolver.resolve(path)
        resolver.clear_cache()
        spec2 = resolver.resolve(path)
        assert spec1 is not spec2  # re-loaded after clear

    def test_no_imports_gives_empty_resolved(self, resolver: ImportResolver) -> None:
        spec = resolver.resolve(SIMPLE_DIR / "ping_protocol.yaml")
        assert spec.resolved_imports == {}


# ---------------------------------------------------------------------------
# ImportResolver — error cases
# ---------------------------------------------------------------------------


class TestImportResolverErrors:
    def test_missing_file_raises(self, resolver: ImportResolver, tmp_path: Path) -> None:
        from protocollab.exceptions import FileLoadError

        with pytest.raises(FileLoadError):
            resolver.resolve(tmp_path / "nonexistent.yaml")

    def test_cyclic_import_raises(self, resolver: ImportResolver, tmp_path: Path) -> None:
        # a.yaml imports b.yaml, b.yaml imports a.yaml
        a = tmp_path / "a.yaml"
        b = tmp_path / "b.yaml"

        a.write_text(
            textwrap.dedent("""\
                meta:
                  id: a_proto
                  endian: le
                imports:
                  - b.yaml
                """),
            encoding="utf-8",
        )
        b.write_text(
            textwrap.dedent("""\
                meta:
                  id: b_proto
                  endian: le
                imports:
                  - a.yaml
                """),
            encoding="utf-8",
        )

        with pytest.raises(CyclicImportError):
            resolver.resolve(a)

    def test_cyclic_self_import_raises(self, resolver: ImportResolver, tmp_path: Path) -> None:
        self_ref = tmp_path / "self.yaml"
        self_ref.write_text(
            textwrap.dedent("""\
                meta:
                  id: self_ref
                  endian: le
                imports:
                  - self.yaml
                """),
            encoding="utf-8",
        )
        with pytest.raises(CyclicImportError):
            resolver.resolve(self_ref)

    def test_cyclic_error_message_contains_path(
        self, resolver: ImportResolver, tmp_path: Path
    ) -> None:
        self_ref = tmp_path / "loop.yaml"
        self_ref.write_text(
            textwrap.dedent("""\
                meta:
                  id: loop
                  endian: le
                imports:
                  - loop.yaml
                """),
            encoding="utf-8",
        )
        with pytest.raises(CyclicImportError, match="loop"):
            resolver.resolve(self_ref)

    def test_cyclic_error_is_yaml_parse_error(
        self, resolver: ImportResolver, tmp_path: Path
    ) -> None:
        from protocollab.exceptions import YAMLParseError

        self_ref = tmp_path / "x.yaml"
        self_ref.write_text(
            textwrap.dedent("""\
                meta:
                  id: x
                  endian: le
                imports:
                  - x.yaml
                """),
            encoding="utf-8",
        )
        with pytest.raises((CyclicImportError, YAMLParseError)):
            resolver.resolve(self_ref)
