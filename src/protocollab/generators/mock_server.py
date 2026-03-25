"""Python mock-server generator for `protocollab`."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.generators.base_generator import BaseGenerator, GeneratorError
from protocollab.generators.python_generator import _to_class_name

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "python"


class MockServerGenerator(BaseGenerator):
    """Generate a Python mock server that uses queues for testing."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        """
        Generate a mock server class.

        Parameters
        ----------
        spec : Dict[str, Any]
            Parsed protocol specification.
        output_dir : Path
            Directory where the file will be written.

        Returns
        -------
        List[Path]
            Paths of the generated file(s).

        Raises
        ------
        GeneratorError
            If the spec is missing required fields.
        """
        meta = spec.get("meta") or {}
        proto_id = meta.get("id", "protocol")
        class_name = _to_class_name(proto_id)

        # Prepare output file name
        output_file = output_dir / f"{proto_id}_mock_server.py"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Render template
        env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)
        template = env.get_template("mock_server.py.j2")
        content = template.render(
            source_file=spec.get("_source_file", "unknown"),
            protocol_class_name=class_name,
            parser_module_name=f"{proto_id}_parser",
        )

        output_file.write_text(content, encoding="utf-8")
        return [output_file]
