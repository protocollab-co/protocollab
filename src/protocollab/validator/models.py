"""Data models for validation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ValidationLevel(Enum):
    """Severity level of a validation finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationError:
    """A single schema validation error (backward-compatible model)."""

    path: str  # dot-notation path, e.g. "meta.id" or "seq[0].type"
    message: str  # human-readable description
    schema_path: str = ""  # path inside the JSON Schema where the rule is defined


@dataclass
class ValidationIssue:
    """A single issue from any validator — with severity level and optional code.

    Used by the semantic / expression validators and the pipeline.
    """

    path: str
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    code: str = ""  # optional diagnostic code, e.g. "E1", "W1"

    def __str__(self) -> str:
        prefix = f"[{self.code}] " if self.code else ""
        return f"{prefix}{self.path}: {self.message}"


@dataclass
class ValidationResult:
    """Aggregated result of validating a single protocol file (structural pass)."""

    is_valid: bool
    errors: List[ValidationError]
    file_path: str

    def __bool__(self) -> bool:
        return self.is_valid


@dataclass
class PipelineResult:
    """Result of running the full multi-stage validation pipeline."""

    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    file_path: str = ""

    @property
    def is_valid(self) -> bool:
        """``True`` if no ERROR-level issues were found."""
        return len(self.errors) == 0

    def __bool__(self) -> bool:
        return self.is_valid

    def all_issues(self) -> List[ValidationIssue]:
        """Return errors + warnings combined, errors first."""
        return list(self.errors) + list(self.warnings)
