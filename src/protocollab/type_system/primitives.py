"""Primitive types for `protocollab's` type system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PrimitiveType:
    """A built-in, atomic protocol field type.

    Attributes
    ----------
    name:
        Canonical type name (e.g. ``"u4"``).
    size_bytes:
        Fixed size in bytes, or ``None`` for variable-length types
        (``str``, ``strz``, ``bytes``).
    struct_format:
        :mod:`struct` format character (endianness prefix is added by the
        caller). ``None`` for types that cannot be decoded with ``struct``.
    lua_field_type:
        Wireshark ProtoField type string used by the Lua generator.
    """

    name: str
    size_bytes: Optional[int]
    struct_format: Optional[str]
    lua_field_type: str


# ---------------------------------------------------------------------------
# Built-in primitive type table
# ---------------------------------------------------------------------------

PRIMITIVE_TYPES: dict[str, PrimitiveType] = {
    # Unsigned integers
    "u1": PrimitiveType("u1", size_bytes=1, struct_format="B", lua_field_type="uint8"),
    "u2": PrimitiveType("u2", size_bytes=2, struct_format="H", lua_field_type="uint16"),
    "u4": PrimitiveType("u4", size_bytes=4, struct_format="I", lua_field_type="uint32"),
    "u8": PrimitiveType("u8", size_bytes=8, struct_format="Q", lua_field_type="uint64"),
    # Signed integers
    "s1": PrimitiveType("s1", size_bytes=1, struct_format="b", lua_field_type="int8"),
    "s2": PrimitiveType("s2", size_bytes=2, struct_format="h", lua_field_type="int16"),
    "s4": PrimitiveType("s4", size_bytes=4, struct_format="i", lua_field_type="int32"),
    "s8": PrimitiveType("s8", size_bytes=8, struct_format="q", lua_field_type="int64"),
    # Floating point
    "f4": PrimitiveType("f4", size_bytes=4, struct_format="f", lua_field_type="float"),
    "f8": PrimitiveType("f8", size_bytes=8, struct_format="d", lua_field_type="double"),
    # Strings
    "str": PrimitiveType("str", size_bytes=None, struct_format=None, lua_field_type="string"),
    "strz": PrimitiveType("strz", size_bytes=None, struct_format=None, lua_field_type="stringz"),
    # Raw bytes
    "bytes": PrimitiveType("bytes", size_bytes=None, struct_format=None, lua_field_type="bytes"),
}

# ---------------------------------------------------------------------------
# Unsigned integer aliases
# ---------------------------------------------------------------------------
_UNSIGNED_ALIASES: dict[str, str] = {
    "uint8": "u1",
    "uint16": "u2",
    "uint32": "u4",
    "uint64": "u8",
}

# Signed integer aliases
_SIGNED_ALIASES: dict[str, str] = {
    "int8": "s1",
    "int16": "s2",
    "int32": "s4",
    "int64": "s8",
}

# byte / word / dword shortcuts (common in Kaitai-like specs)
_WORD_ALIASES: dict[str, str] = {
    "byte": "u1",
    "word": "u2",
    "dword": "u4",
    "qword": "u8",
}

ALIASES: dict[str, str] = {
    **_UNSIGNED_ALIASES,
    **_SIGNED_ALIASES,
    **_WORD_ALIASES,
}

# Register alias entries so callers can look them up directly too
for _alias, _canonical in ALIASES.items():
    PRIMITIVE_TYPES[_alias] = PRIMITIVE_TYPES[_canonical]
