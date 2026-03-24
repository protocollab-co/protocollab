"""File-system utilities for `protocollab`."""

from pathlib import Path


def resolve_path(file_path: str) -> str:
    """Return the absolute, normalised path for *file_path*."""
    return str(Path(file_path).resolve())


def check_file_exists(file_path: str) -> None:
    """Raise ``FileNotFoundError`` when *file_path* does not exist or is not a file."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"No such file: '{file_path}'")
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: '{file_path}'")
