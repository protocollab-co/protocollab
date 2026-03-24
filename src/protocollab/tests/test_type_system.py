"""Tests for protocollab.type_system — primitives, composite types, registry, size calculator."""

from __future__ import annotations

import pytest

from protocollab.core import parse_spec
from protocollab.core.models import FieldDef, TypeDef
from protocollab.type_system import (
    ALIASES,
    PRIMITIVE_TYPES,
    CompositeType,
    PrimitiveType,
    ResolvedField,
    TypeRegistry,
    UnknownTypeError,
    calculate_size,
)
from protocollab.type_system.primitives import _UNSIGNED_ALIASES  # noqa: PLC2701

# ---------------------------------------------------------------------------
# PrimitiveType dataclass
# ---------------------------------------------------------------------------


class TestPrimitiveTypeDataclass:
    def test_is_frozen(self) -> None:
        pt = PRIMITIVE_TYPES["u4"]
        with pytest.raises(AttributeError):
            pt.size_bytes = 99  # type: ignore[misc]

    def test_u1_fields(self) -> None:
        pt = PRIMITIVE_TYPES["u1"]
        assert pt.name == "u1"
        assert pt.size_bytes == 1
        assert pt.struct_format == "B"
        assert pt.lua_field_type == "uint8"

    def test_u2_fields(self) -> None:
        pt = PRIMITIVE_TYPES["u2"]
        assert pt.size_bytes == 2
        assert pt.struct_format == "H"

    def test_u4_fields(self) -> None:
        pt = PRIMITIVE_TYPES["u4"]
        assert pt.size_bytes == 4
        assert pt.struct_format == "I"

    def test_u8_fields(self) -> None:
        pt = PRIMITIVE_TYPES["u8"]
        assert pt.size_bytes == 8
        assert pt.struct_format == "Q"

    def test_s1_fields(self) -> None:
        pt = PRIMITIVE_TYPES["s1"]
        assert pt.size_bytes == 1
        assert pt.struct_format == "b"

    def test_s4_fields(self) -> None:
        pt = PRIMITIVE_TYPES["s4"]
        assert pt.size_bytes == 4
        assert pt.struct_format == "i"

    def test_str_variable_size(self) -> None:
        pt = PRIMITIVE_TYPES["str"]
        assert pt.size_bytes is None
        assert pt.struct_format is None

    def test_strz_variable_size(self) -> None:
        pt = PRIMITIVE_TYPES["strz"]
        assert pt.size_bytes is None

    def test_bytes_variable_size(self) -> None:
        pt = PRIMITIVE_TYPES["bytes"]
        assert pt.size_bytes is None

    def test_f4_float(self) -> None:
        pt = PRIMITIVE_TYPES["f4"]
        assert pt.size_bytes == 4
        assert pt.struct_format == "f"

    def test_f8_double(self) -> None:
        pt = PRIMITIVE_TYPES["f8"]
        assert pt.size_bytes == 8
        assert pt.struct_format == "d"


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


class TestAliases:
    def test_uint8_alias(self) -> None:
        assert PRIMITIVE_TYPES["uint8"] is PRIMITIVE_TYPES["u1"]

    def test_uint16_alias(self) -> None:
        assert PRIMITIVE_TYPES["uint16"] is PRIMITIVE_TYPES["u2"]

    def test_uint32_alias(self) -> None:
        assert PRIMITIVE_TYPES["uint32"] is PRIMITIVE_TYPES["u4"]

    def test_uint64_alias(self) -> None:
        assert PRIMITIVE_TYPES["uint64"] is PRIMITIVE_TYPES["u8"]

    def test_int8_alias(self) -> None:
        assert PRIMITIVE_TYPES["int8"] is PRIMITIVE_TYPES["s1"]

    def test_int32_alias(self) -> None:
        assert PRIMITIVE_TYPES["int32"] is PRIMITIVE_TYPES["s4"]

    def test_byte_alias(self) -> None:
        assert PRIMITIVE_TYPES["byte"] is PRIMITIVE_TYPES["u1"]

    def test_dword_alias(self) -> None:
        assert PRIMITIVE_TYPES["dword"] is PRIMITIVE_TYPES["u4"]

    def test_aliases_dict_present(self) -> None:
        assert "uint32" in ALIASES
        assert ALIASES["uint32"] == "u4"

    def test_unsigned_aliases_dict(self) -> None:
        assert _UNSIGNED_ALIASES["uint8"] == "u1"
        assert _UNSIGNED_ALIASES["uint16"] == "u2"


# ---------------------------------------------------------------------------
# CompositeType
# ---------------------------------------------------------------------------


class TestCompositeType:
    def _make_u4_field(self, name: str) -> ResolvedField:
        fd = FieldDef.model_validate({"id": name, "type": "u4"})
        return ResolvedField(field_def=fd, resolved_type=PRIMITIVE_TYPES["u4"])

    def test_empty_composite(self) -> None:
        ct = CompositeType(name="empty")
        assert ct.fields == []
        assert ct.doc is None

    def test_from_def(self) -> None:
        td = TypeDef(
            seq=[
                FieldDef.model_validate({"id": "seconds", "type": "u4"}),
                FieldDef.model_validate({"id": "microseconds", "type": "u4"}),
            ],
            doc="Timestamp",
        )
        reg = TypeRegistry()
        ct = CompositeType.from_def("timestamp_t", td, reg)
        assert ct.name == "timestamp_t"
        assert len(ct.fields) == 2
        assert ct.doc == "Timestamp"

    def test_from_def_resolves_types(self) -> None:
        td = TypeDef(seq=[FieldDef.model_validate({"id": "x", "type": "u4"})])
        reg = TypeRegistry()
        ct = CompositeType.from_def("t", td, reg)
        assert ct.fields[0].resolved_type is PRIMITIVE_TYPES["u4"]

    def test_from_def_unknown_type_keeps_none(self) -> None:
        td = TypeDef(seq=[FieldDef.model_validate({"id": "x", "type": "ghost_type"})])
        reg = TypeRegistry()
        ct = CompositeType.from_def("t", td, reg)
        assert ct.fields[0].resolved_type is None

    def test_field_defs_property(self) -> None:
        rf1 = self._make_u4_field("a")
        rf2 = self._make_u4_field("b")
        ct = CompositeType(name="t", fields=[rf1, rf2])
        defs = ct.field_defs
        assert [fd.id for fd in defs] == ["a", "b"]


# ---------------------------------------------------------------------------
# TypeRegistry — basics
# ---------------------------------------------------------------------------


class TestTypeRegistry:
    def test_resolve_primitive(self) -> None:
        reg = TypeRegistry()
        pt = reg.resolve("u4")
        assert isinstance(pt, PrimitiveType)
        assert pt.name == "u4"

    def test_resolve_alias(self) -> None:
        reg = TypeRegistry()
        pt = reg.resolve("uint32")
        assert pt is PRIMITIVE_TYPES["u4"]

    def test_resolve_unknown_raises(self) -> None:
        reg = TypeRegistry()
        with pytest.raises(UnknownTypeError) as exc_info:
            reg.resolve("ghost")
        assert exc_info.value.type_name == "ghost"

    def test_unknown_type_error_message(self) -> None:
        reg = TypeRegistry()
        with pytest.raises(UnknownTypeError, match="ghost"):
            reg.resolve("ghost")

    def test_is_known_primitive(self) -> None:
        reg = TypeRegistry()
        assert reg.is_known("u1")
        assert reg.is_known("s4")

    def test_is_known_unknown(self) -> None:
        reg = TypeRegistry()
        assert not reg.is_known("made_up")

    def test_register_composite(self) -> None:
        reg = TypeRegistry()
        ct = CompositeType(name="hdr", fields=[])
        reg.register("hdr", ct)
        assert reg.resolve("hdr") is ct

    def test_register_overwrites(self) -> None:
        reg = TypeRegistry()
        ct1 = CompositeType(name="t")
        ct2 = CompositeType(name="t")
        reg.register("t", ct1)
        reg.register("t", ct2)
        assert reg.resolve("t") is ct2

    def test_all_names_contains_primitives(self) -> None:
        reg = TypeRegistry()
        names = reg.all_names()
        assert "u4" in names
        assert "str" in names
        assert "uint32" in names

    def test_all_names_sorted(self) -> None:
        reg = TypeRegistry()
        names = reg.all_names()
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# TypeRegistry.build()
# ---------------------------------------------------------------------------

PING_DICT = {
    "meta": {"id": "ping_protocol", "endian": "le"},
    "seq": [
        {"id": "type_id", "type": "u1"},
        {"id": "sequence_number", "type": "u4"},
    ],
}

TYPED_DICT = {
    "meta": {"id": "with_types", "endian": "le"},
    "seq": [{"id": "ts", "type": "timestamp_t"}],
    "types": {
        "timestamp_t": {
            "doc": "Timestamp",
            "seq": [
                {"id": "seconds", "type": "u4"},
                {"id": "microseconds", "type": "u4"},
            ],
        },
        "nested_t": {
            "seq": [
                {"id": "stamp", "type": "timestamp_t"},
                {"id": "flags", "type": "u1"},
            ]
        },
    },
}


class TestTypeRegistryBuild:
    def test_build_returns_self(self) -> None:
        spec = parse_spec(PING_DICT)
        reg = TypeRegistry()
        result = reg.build(spec)
        assert result is reg

    def test_build_no_custom_types(self) -> None:
        spec = parse_spec(PING_DICT)
        reg = TypeRegistry().build(spec)
        assert reg.is_known("u4")
        assert not reg.is_known("timestamp_t")

    def test_build_registers_custom_type(self) -> None:
        spec = parse_spec(TYPED_DICT)
        reg = TypeRegistry().build(spec)
        ct = reg.resolve("timestamp_t")
        assert isinstance(ct, CompositeType)
        assert ct.name == "timestamp_t"

    def test_build_composite_has_fields(self) -> None:
        spec = parse_spec(TYPED_DICT)
        reg = TypeRegistry().build(spec)
        ct = reg.resolve("timestamp_t")
        assert isinstance(ct, CompositeType)
        assert len(ct.fields) == 2

    def test_build_nested_composite_resolved(self) -> None:
        spec = parse_spec(TYPED_DICT)
        reg = TypeRegistry().build(spec)
        nested = reg.resolve("nested_t")
        assert isinstance(nested, CompositeType)
        # "stamp" field should resolve to timestamp_t CompositeType
        stamp_field = nested.fields[0]
        assert isinstance(stamp_field.resolved_type, CompositeType)
        assert stamp_field.resolved_type.name == "timestamp_t"

    def test_build_from_real_file(self) -> None:
        from pathlib import Path

        from protocollab.core import ImportResolver

        path = Path(__file__).parents[3] / "examples" / "with_includes" / "tcp_like.yaml"
        resolver = ImportResolver()
        spec = resolver.resolve(path)
        reg = TypeRegistry().build(spec)
        # tcp_like imports base_types.yaml which has timestamp_t and mac_address_t
        assert reg.is_known("timestamp_t")
        assert reg.is_known("mac_address_t")


# ---------------------------------------------------------------------------
# UnknownTypeError
# ---------------------------------------------------------------------------


class TestUnknownTypeError:
    def test_is_exception(self) -> None:
        err = UnknownTypeError("ghost")
        assert isinstance(err, Exception)

    def test_type_name_attribute(self) -> None:
        err = UnknownTypeError("ghost")
        assert err.type_name == "ghost"

    def test_message_contains_name(self) -> None:
        err = UnknownTypeError("ghost")
        assert "ghost" in str(err)


# ---------------------------------------------------------------------------
# calculate_size
# ---------------------------------------------------------------------------


class TestCalculateSize:
    def test_primitive_fixed(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["u4"]) == 4

    def test_primitive_u1(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["u1"]) == 1

    def test_primitive_u8(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["u8"]) == 8

    def test_primitive_str_none(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["str"]) is None

    def test_primitive_strz_none(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["strz"]) is None

    def test_primitive_bytes_none(self) -> None:
        assert calculate_size(PRIMITIVE_TYPES["bytes"]) is None

    def test_empty_composite_zero(self) -> None:
        ct = CompositeType(name="empty")
        assert calculate_size(ct) == 0

    def test_composite_two_u4(self) -> None:
        u4 = PRIMITIVE_TYPES["u4"]
        ct = CompositeType(
            name="ts",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "s", "type": "u4"}), resolved_type=u4
                ),
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "us", "type": "u4"}), resolved_type=u4
                ),
            ],
        )
        assert calculate_size(ct) == 8

    def test_composite_with_str_field_none(self) -> None:
        u4 = PRIMITIVE_TYPES["u4"]
        strtype = PRIMITIVE_TYPES["str"]
        ct = CompositeType(
            name="mixed",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "len", "type": "u4"}), resolved_type=u4
                ),
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "name", "type": "str"}),
                    resolved_type=strtype,
                ),
            ],
        )
        assert calculate_size(ct) is None

    def test_composite_with_if_expr_none(self) -> None:
        u4 = PRIMITIVE_TYPES["u4"]
        ct = CompositeType(
            name="cond",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate(
                        {"id": "opt", "type": "u4", "if": "has_flag != 0"}
                    ),
                    resolved_type=u4,
                ),
            ],
        )
        assert calculate_size(ct) is None

    def test_composite_with_repeat_none(self) -> None:
        u1 = PRIMITIVE_TYPES["u1"]
        ct = CompositeType(
            name="arr",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate(
                        {"id": "items", "type": "u1", "repeat": "expr", "repeat-expr": "count"}
                    ),
                    resolved_type=u1,
                ),
            ],
        )
        assert calculate_size(ct) is None

    def test_composite_with_unresolved_type_none(self) -> None:
        ct = CompositeType(
            name="unresolved",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "x", "type": "ghost"}),
                    resolved_type=None,
                ),
            ],
        )
        assert calculate_size(ct) is None

    def test_nested_composite_size(self) -> None:
        u4 = PRIMITIVE_TYPES["u4"]
        inner = CompositeType(
            name="inner",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "a", "type": "u4"}), resolved_type=u4
                ),
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "b", "type": "u4"}), resolved_type=u4
                ),
            ],
        )  # inner size = 8
        outer = CompositeType(
            name="outer",
            fields=[
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "hdr", "type": "inner"}),
                    resolved_type=inner,
                ),
                ResolvedField(
                    field_def=FieldDef.model_validate({"id": "extra", "type": "u4"}),
                    resolved_type=u4,
                ),
            ],
        )
        assert calculate_size(outer) == 12  # 8 + 4

    def test_unknown_type_object_returns_none(self) -> None:
        assert calculate_size(object()) is None

    def test_calculate_size_via_registry(self) -> None:
        spec = parse_spec(
            {
                "meta": {"id": "p", "endian": "le"},
                "types": {
                    "hdr": {
                        "seq": [
                            {"id": "type_id", "type": "u1"},
                            {"id": "length", "type": "u2"},
                        ]
                    }
                },
            }
        )
        reg = TypeRegistry().build(spec)
        ct = reg.resolve("hdr")
        assert calculate_size(ct) == 3
