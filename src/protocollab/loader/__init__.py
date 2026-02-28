"""Public API for the ProtocolLab loader subsystem."""

from typing import Optional

from protocollab.loader.base_loader import ProtocolLoader
from protocollab.loader.cache.base_cache import BaseCache
from protocollab.loader.cache.memory_cache import MemoryCache
from protocollab.types import ProtocolData

__all__ = [
    "load_protocol",
    "ProtocolLoader",
    "BaseCache",
    "MemoryCache",
]

# Module-level loader instance with a shared in-memory cache.
_default_loader = ProtocolLoader()


def load_protocol(
    file_path: str,
    config: Optional[dict] = None,
    use_cache: bool = True,
) -> ProtocolData:
    """Load a protocol YAML file and return a plain-Python data tree.

    Parameters
    ----------
    file_path:
        Path to the root YAML file.  Relative paths are resolved against
        the current working directory.
    config:
        Optional security settings forwarded to the loader:
        ``max_file_size``, ``max_struct_depth``, ``max_include_depth``,
        ``max_imports``.
    use_cache:
        When *True* (default) a module-level :class:`MemoryCache` is used so
        that repeated calls with the same path skip disk I/O.  Pass *False*
        to always reload from disk (e.g. in watch-mode tooling).

    Returns
    -------
    ProtocolData
        Fully-resolved ``dict`` tree.

    Raises
    ------
    protocollab.exceptions.FileLoadError
        When the file cannot be opened (exit code 1 in CLI).
    protocollab.exceptions.YAMLParseError
        When parsing fails or a security limit is exceeded (exit code 2).
    """
    if config or not use_cache:
        # Create a fresh loader so the config and cache behaviour are isolated.
        loader = ProtocolLoader(
            cache=MemoryCache() if use_cache else None,
            config=config,
        )
        return loader.load(file_path)

    return _default_loader.load(file_path)
