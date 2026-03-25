"""Python mock-client generator for `protocollab`."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.generators.base_generator import BaseGenerator, GeneratorError

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "python"


class MockClientGenerator(BaseGenerator):
    """Generate a Python mock client that uses queues for testing."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        """
        Generate a mock client class.

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
        try:
            proto_id = spec["meta"]["id"]
        except KeyError as e:
            raise GeneratorError("Spec missing 'meta.id'") from e

        # Build class name from protocol id
        class_name = proto_id.replace("_", " ").title().replace(" ", "")

        # Prepare output file name
        output_file = output_dir / f"{proto_id}_mock_client.py"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Render template
        env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)
        template = env.get_template("mock_client.py.j2")
        content = template.render(
            source_file=spec.get("_source_file", "unknown"),
            protocol_class_name=class_name,
            parser_module_name=f"{proto_id}_parser",
        )

        output_file.write_text(content, encoding="utf-8")
        return [output_file]
