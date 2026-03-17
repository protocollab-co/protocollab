"""Pydantic models for `protocollab` protocol specifications."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Endianness(str, Enum):
    """Byte order for multi-byte fields."""

    LE = "le"
    BE = "be"


class MetaSection(BaseModel):
    """The ``meta:`` block of a .yaml protocol spec."""

    model_config = ConfigDict(extra="allow")

    id: str
    version: Optional[str] = None
    description: Optional[str] = None
    title: Optional[str] = None
    endian: Endianness = Endianness.LE


class FieldDef(BaseModel):
    """A single element inside a ``seq:`` list or a type's ``seq:``."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    type: Optional[str] = None
    size: Optional[int] = None
    doc: Optional[str] = None
    if_expr: Optional[str] = Field(None, alias="if")
    repeat: Optional[str] = None
    repeat_expr: Optional[str] = Field(None, alias="repeat-expr")


class TypeDef(BaseModel):
    """A user-defined type declared under ``types:``."""

    model_config = ConfigDict(extra="allow")

    seq: List[FieldDef] = Field(default_factory=list)
    doc: Optional[str] = None


class ProtocolSpec(BaseModel):
    """The complete, parsed representation of a .yaml protocol spec file."""

    model_config = ConfigDict(extra="allow")

    meta: MetaSection
    seq: List[FieldDef] = Field(default_factory=list)
    types: Dict[str, TypeDef] = Field(default_factory=dict)
    doc: Optional[str] = None
    imports: List[str] = Field(default_factory=list)
    #: Populated by ImportResolver — maps import path → resolved ProtocolSpec
    resolved_imports: Dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        """Convenience shortcut for ``spec.meta.id``."""
        return self.meta.id

    @property
    def endian(self) -> Endianness:
        """Convenience shortcut for ``spec.meta.endian``."""
        return self.meta.endian
