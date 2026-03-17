"""Custom exceptions for `protocollab` CLI and loader."""


class ProtocolLabError(Exception):
    """Base exception for all `protocollab` errors."""


class FileLoadError(ProtocolLabError):
    """Raised when a protocol file cannot be opened or read.

    Corresponds to CLI exit code 1.
    """


class YAMLParseError(ProtocolLabError):
    """Raised when a protocol file contains invalid YAML or violates security limits.

    Corresponds to CLI exit code 2.
    """
