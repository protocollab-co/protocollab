"""Python parser generator for `protocollab` protocol specifications."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.generators.base_generator import BaseGenerator, GeneratorError
from protocollab.generators.utils import to_class_name

# fmt_char, size_bytes, python_type
_PY_TYPE_MAP: Dict[str, tuple] = {
    "u1": ("B", 1, "int"),
    "u2": ("H", 2, "int"),
    "u3": ("3s", 3, "int"),
    "u4": ("I", 4, "int"),
    "u8": ("Q", 8, "int"),
    "s1": ("b", 1, "int"),
    "s2": ("h", 2, "int"),
    "s4": ("i", 4, "int"),
    "s8": ("q", 8, "int"),
    "str": (None, None, "str"),  # requires 'size' in field spec
}

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "python"


def _process_field(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a single seq-entry *raw* to a field descriptor dict.

    Raises :class:`GeneratorError` for unsupported or misconfigured types.
    Returns an empty dict when ``id`` or ``type`` are absent (caller skips it).
    """
    field_id = raw.get("id")
    spec_type = raw.get("type")
    if not field_id or not spec_type:
        return {}

    if spec_type not in _PY_TYPE_MAP:
        raise GeneratorError(
            f"Unsupported field type '{spec_type}' for field '{field_id}'. "
            f"Supported types: {', '.join(sorted(_PY_TYPE_MAP))}."
        )

    fmt_char, size, py_type = _PY_TYPE_MAP[spec_type]

    if spec_type == "str":
        size = raw.get("size")
        if size is None:
            raise GeneratorError(f"Field '{field_id}' of type 'str' requires a 'size' attribute.")
        fmt_char = f"{size}s"
        py_type = "bytes"

    return {
        "id": field_id,
        "spec_type": spec_type,
        "py_type": py_type,
        "fmt_char": fmt_char,
        "size": size,
        "is_u3": spec_type == "u3",
    }


def _render_output(context: Dict[str, Any], output_dir: Path, proto_id: str) -> Path:
    """Render the Jinja2 parser template and write it to *output_dir*.

    Returns the path of the written file.
    """
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)
    template = env.get_template("parser.py.j2")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{proto_id}_parser.py"
    out_path.write_text(template.render(**context), encoding="utf-8")
    return out_path


class PythonGenerator(BaseGenerator):
    """Generates a Python dataclass parser from a protocol specification."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        """Generate a Python parser file into *output_dir*.

        Returns
        -------
        List[Path]
            Single-element list with the path of the written ``.py`` file.
        """
        meta = spec.get("meta", {})
        proto_id: str = meta.get("id", "protocol")
        endian: str = meta.get("endian", "le")
        endian_char = "<" if endian == "le" else ">"

        seq = spec.get("seq") or []
        fields = []
        fmt_chars: List[str] = []
        total_size = 0

        for raw in seq:
            field = _process_field(raw)
            if not field:
                continue
            fmt_chars.append(field["fmt_char"])
            total_size += field["size"]
            fields.append(field)

        context = {
            "source_file": str(spec.get("_source_file", "<unknown>")),
            "class_name": to_class_name(proto_id),
            "endian_char": endian_char,
            "format_string": "".join(fmt_chars),
            "total_size": total_size,
            "fields": fields,
        }
        return [_render_output(context, output_dir, proto_id)]
