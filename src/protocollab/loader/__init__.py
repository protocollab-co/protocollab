"""Public API for the ``protocollab`` loader subsystem.

Hybrid design
-------------
A module-level *global loader* (backed by a shared :class:`MemoryCache`) is
provided for convenience so that simple scripts can call :func:`load_protocol`
without any setup.

For **long-running services** or applications that load many distinct files,
create explicit :class:`ProtocolLoader` instances::

    from protocollab.loader import ProtocolLoader
    from protocollab.loader.cache.memory_cache import MemoryCache

    loader = ProtocolLoader(cache=MemoryCache(max_size=256))
    data = loader.load("path/to/protocol.yaml")

Cache management
----------------
The global cache can be bounded or cleared at startup::

    from protocollab.loader import configure_global
    configure_global(max_cache_size=128)   # limit to 128 entries (LRU)

Thread-safety warning
---------------------
The global loader and :class:`ProtocolLoader` instances are **not
thread-safe**.  In multi-threaded applications, create one
:class:`ProtocolLoader` per thread (or per request) instead of sharing the
global instance.
"""

from typing import Optional

from protocollab.loader.base_loader import ProtocolLoader
from protocollab.loader.cache.base_cache import BaseCache
from protocollab.loader.cache.memory_cache import MemoryCache
from protocollab.types import ProtocolData

__all__ = [
    "load_protocol",
    "get_global_loader",
    "configure_global",
    "ProtocolLoader",
    "BaseCache",
    "MemoryCache",
]

# Module-level loader instance with a shared in-memory cache.
# WARNING: not thread-safe — see module docstring.
_default_loader = ProtocolLoader()


def _build_loader(
    cache: Optional[BaseCache] = None,
    config: Optional[dict] = None,
) -> ProtocolLoader:
    return ProtocolLoader(cache=cache, config=config)


def _should_use_isolated_loader(config: Optional[dict], use_cache: bool) -> bool:
    return bool(config) or not use_cache


def _build_isolated_loader(config: Optional[dict], use_cache: bool) -> ProtocolLoader:
    cache = MemoryCache() if use_cache else None
    return _build_loader(cache=cache, config=config)


def _load_with_loader(loader: ProtocolLoader, file_path: str) -> ProtocolData:
    return loader.load(file_path)


def get_global_loader() -> ProtocolLoader:
    """Return the module-level global :class:`ProtocolLoader`.

    Useful for inspecting or clearing the shared cache::

        from protocollab.loader import get_global_loader
        get_global_loader().clear_cache()

    .. warning::
        The global loader is **not thread-safe**.  For concurrent code,
        create separate :class:`ProtocolLoader` instances instead.
    """
    return _default_loader


def configure_global(
    max_cache_size: Optional[int] = None,
    config: Optional[dict] = None,
) -> None:
    """Reinitialise the global loader with new cache and/or security settings.

    Call this **once at application startup**, before any :func:`load_protocol`
    calls, to tune the shared cache or apply custom security limits.

    Parameters
    ----------
    max_cache_size:
        Maximum number of entries in the global LRU cache.  ``None`` (default)
        means unbounded.  Previously cached entries are discarded when this
        function is called.
    config:
        Security / limit overrides for all subsequent loads through the global
        loader.  Supported keys: ``max_file_size``, ``max_struct_depth``,
        ``max_include_depth``, ``max_imports``.

    .. warning::
        This function is **not thread-safe**.  It must not be called while
        other threads are using :func:`load_protocol`.
    """
    global _default_loader
    _default_loader = _build_loader(
        cache=MemoryCache(max_size=max_cache_size),
        config=config,
    )


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
        Optional per-call security settings forwarded to the loader:
        ``max_file_size``, ``max_struct_depth``, ``max_include_depth``,
        ``max_imports``.  When provided, a **fresh isolated loader** is used
        so the global cache is not polluted.
    use_cache:
        When *True* (default) the global :class:`MemoryCache` is used so
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

    Notes
    -----
    The global loader is **not thread-safe**.  For multi-threaded
    applications, create separate :class:`ProtocolLoader` instances.
    """
    if _should_use_isolated_loader(config, use_cache):
        # Create a fresh loader so the config and cache behaviour are isolated.
        return _load_with_loader(_build_isolated_loader(config, use_cache), file_path)

    return _load_with_loader(_default_loader, file_path)
