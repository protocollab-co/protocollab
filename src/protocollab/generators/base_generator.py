"""Abstract base class for all ProtocolLab code generators."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


ProtocolData = Dict[str, Any]


class GeneratorError(Exception):
    """Raised when code generation fails (unknown type, missing field, etc.)."""


class BaseGenerator(ABC):
    """Generate target-language artefacts from a parsed protocol specification.

    Sub-classes implement :meth:`generate` and document the files they create.
    """

    @abstractmethod
    def generate(self, spec: ProtocolData, output_dir: Path) -> List[Path]:
        """Generate files from *spec* into *output_dir*.

        Parameters
        ----------
        spec:
            Protocol specification dict (as returned by ``load_protocol``).
        output_dir:
            Directory where generated files are written.  Created if absent.

        Returns
        -------
        List[Path]
            Paths of every file that was written.

        Raises
        ------
        GeneratorError
            When a field type is unsupported or the spec is malformed.
        """
