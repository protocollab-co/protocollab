"""Python L3 socket-server generator for `protocollab`."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.generators.base_generator import BaseGenerator
from protocollab.generators.utils import to_class_name

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "python"


class L3ServerGenerator(BaseGenerator):
    """Generate a Python TCP socket server for a protocol parser."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        meta = spec.get("meta") or {}
        proto_id = meta.get("id", "protocol")
        class_name = to_class_name(proto_id)

        output_file = output_dir / f"{proto_id}_l3_server.py"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            keep_trailing_newline=True,
        )
        template = env.get_template("l3_server.py.j2")
        content = template.render(
            source_file=spec.get("_source_file", "unknown"),
            protocol_class_name=class_name,
            parser_module_name=f"{proto_id}_parser",
        )

        output_file.write_text(content, encoding="utf-8")
        return [output_file]
