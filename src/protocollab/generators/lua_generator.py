"""Lua / Wireshark dissector generator for `protocollab` protocol specifications."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.generators.base_generator import BaseGenerator, GeneratorError

# lua_type, size_bytes, optional_base
_LUA_TYPE_MAP: Dict[str, tuple] = {
    "u1": ("uint8",  1, None),
    "u2": ("uint16", 2, "base.DEC"),
    "u4": ("uint32", 4, "base.DEC"),
    "u8": ("uint64", 8, "base.DEC"),
    "s1": ("int8",   1, None),
    "s2": ("int16",  2, "base.DEC"),
    "s4": ("int32",  4, "base.DEC"),
    "s8": ("int64",  8, "base.DEC"),
    "str": ("string", None, None),  # requires 'size' in field spec
}

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "lua"


class LuaGenerator(BaseGenerator):
    """Generates a Wireshark Lua dissector from a protocol specification."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        """Generate a ``.lua`` dissector file into *output_dir*.

        Returns
        -------
        List[Path]
            Single-element list with the path of the written ``.lua`` file.
        """
        meta = spec.get("meta", {})
        proto_id: str = meta.get("id", "protocol")
        proto_title: str = meta.get("title", proto_id)

        seq = spec.get("seq") or []
        fields = []

        for raw in seq:
            field_id = raw.get("id")
            spec_type = raw.get("type")
            if not field_id or not spec_type:
                continue

            if spec_type not in _LUA_TYPE_MAP:
                raise GeneratorError(
                    f"Unsupported field type '{spec_type}' for field '{field_id}'. "
                    f"Supported types: {', '.join(sorted(_LUA_TYPE_MAP))}."
                )

            lua_type, size, lua_base = _LUA_TYPE_MAP[spec_type]

            if spec_type == "str":
                size = raw.get("size")
                if size is None:
                    raise GeneratorError(
                        f"Field '{field_id}' of type 'str' requires a 'size' attribute."
                    )

            fields.append(
                {
                    "id": field_id,
                    "spec_type": spec_type,
                    "label": field_id.replace("_", " ").title(),
                    "lua_type": lua_type,
                    "lua_base": lua_base,
                    "size": size,
                }
            )

        env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)
        template = env.get_template("dissector.lua.j2")

        context = {
            "source_file": str(spec.get("_source_file", "<unknown>")),
            "proto_id": proto_id,
            "proto_title": proto_title,
            "proto_id_upper": proto_id.upper(),
            "fields": fields,
            "fields_list": ", ".join(f"f_{f['id']}" for f in fields),
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{proto_id}.lua"
        out_path.write_text(template.render(**context), encoding="utf-8")
        return [out_path]
