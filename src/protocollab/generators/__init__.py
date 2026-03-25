"""Public API for `protocollab` code generators."""

from pathlib import Path
from typing import Any, Dict, List

from protocollab.generators.base_generator import BaseGenerator, GeneratorError
from protocollab.generators.python_generator import PythonGenerator
from protocollab.generators.lua_generator import LuaGenerator
from protocollab.generators.mock_client import MockClientGenerator
from protocollab.generators.mock_server import MockServerGenerator

__all__ = [
    "generate",
    "PythonGenerator",
    "LuaGenerator",
    "MockClientGenerator",
    "MockServerGenerator",
    "BaseGenerator",
    "GeneratorError",
]

_GENERATORS: Dict[str, type] = {
    "python": PythonGenerator,
    "wireshark": LuaGenerator,
    "mock-client": MockClientGenerator,
    "mock-server": MockServerGenerator,
}

# Register Pro generators when available (local-only, not in public repo)
try:
    from protocollab.generators.cpp_generator import CppGenerator  # noqa: F401

    _GENERATORS["cpp"] = CppGenerator
    __all__.append("CppGenerator")
except ImportError:
    pass


def generate(
    spec: Dict[str, Any],
    target: str,
    output_dir: str | Path,
) -> List[Path]:
    """Generate code from *spec* for the given *target*.

    Parameters
    ----------
    spec:
        Protocol specification dict (as returned by ``load_protocol``).
    target:
        One of ``"python"``, ``"wireshark"``, ``"mock-client"``,
        ``"mock-server"``, or any additionally registered target.
        The ``"mock-client"`` and ``"mock-server"`` targets first generate
        the ``"python"`` parser module into the same output directory and
        then generate the mock module that imports it. If the parser file
        already exists in *output_dir*, it is overwritten with regenerated
        output.
    output_dir:
        Directory where generated files are written.

    Returns
    -------
    List[Path]
        Paths of every file that was written. For ``"mock-client"`` and
        ``"mock-server"`` this includes both the generated parser path and
        the generated mock module path.

    Raises
    ------
    ValueError
        When *target* is not recognised.
    GeneratorError
        When generation fails (unsupported type, malformed spec, etc.).
    """
    if target not in _GENERATORS:
        raise ValueError(
            f"Unknown target '{target}'. Supported targets: {', '.join(sorted(_GENERATORS))}."
        )

    output_path = Path(output_dir)
    if target in {"mock-client", "mock-server"}:
        parser_paths = PythonGenerator().generate(spec, output_path)
        generator: BaseGenerator = _GENERATORS[target]()
        return parser_paths + generator.generate(spec, output_path)

    gen: BaseGenerator = _GENERATORS[target]()
    return gen.generate(spec, output_path)
