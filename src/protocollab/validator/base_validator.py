"""Abstract base class for all `protocollab` validators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from protocollab.validator.models import ValidationIssue

if TYPE_CHECKING:
    from protocollab.core.models import ProtocolSpec


class BaseValidator(ABC):
    """Interface that every validator in the pipeline must implement."""

    @abstractmethod
    def validate(self, spec: "ProtocolSpec") -> List[ValidationIssue]:
        """Validate *spec* and return a list of issues (empty = no issues).

        Parameters
        ----------
        spec:
            The fully-parsed :class:`~protocollab.core.models.ProtocolSpec`.

        Returns
        -------
        list[ValidationIssue]
            Validation issues found; may be a mix of ERRORs and WARNINGs.
        """
