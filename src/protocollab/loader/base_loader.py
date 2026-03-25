"""Base protocol loader — wraps yaml_serializer and applies caching."""

import logging
from pathlib import Path
from typing import Optional

from ruamel.yaml.error import YAMLError

from protocollab.exceptions import FileLoadError, YAMLParseError
from protocollab.loader.cache.base_cache import BaseCache
from protocollab.loader.cache.memory_cache import MemoryCache
from protocollab.types import ProtocolData
from yaml_serializer.serializer import SerializerSession
from yaml_serializer.utils import canonical_repr

logger = logging.getLogger(__name__)


class ProtocolLoader:
    """Loads protocol YAML files, resolves ``!include`` directives, and caches results.

    Parameters
    ----------
    cache:
        Cache backend to use.  Defaults to a fresh :class:`MemoryCache`.
        Pass ``None`` to use a new unbounded in-memory cache, or supply a
        :class:`MemoryCache` with ``max_size`` set for bounded LRU behaviour.
    config:
        Security / limit overrides forwarded to ``yaml_serializer``.
        Supported keys: ``max_file_size``, ``max_struct_depth``,
        ``max_include_depth``, ``max_imports``.

    Notes
    -----
    Each ``ProtocolLoader`` instance is fully independent.  For
    multi-threaded applications, create one instance per thread rather
    than sharing the default global loader.
    """

    def __init__(
        self,
        cache: Optional[BaseCache] = None,
        config: Optional[dict] = None,
    ) -> None:
        self._cache: BaseCache = cache if cache is not None else MemoryCache()
        self._config: dict = config or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, file_path: str) -> ProtocolData:
        """Load *file_path* and return a plain-Python representation.

        The result is a deeply-nested ``dict`` / ``list`` tree with all
        ``!include`` references resolved.  All YAML-specific metadata
        (comments, anchors, custom attributes) is stripped.

        Raises
        ------
        FileLoadError
            When the file (or any included file) cannot be opened.
        YAMLParseError
            When the file contains invalid YAML or violates any security
            limit (nesting depth, import count, path traversal, …).
        """
        abs_path = str(Path(file_path).resolve())

        cached = self._cache.get(abs_path)
        if cached is not None:
            logger.debug("Cache hit for %s", abs_path)
            return cached

        logger.debug("Loading protocol from %s", abs_path)
        raw = self._load_raw(abs_path)
        result = canonical_repr(raw)
        assert isinstance(result, dict)
        self._cache.set(abs_path, result)
        return result

    def clear_cache(self) -> None:
        """Evict all cached protocol data."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_raw(self, abs_path: str):
        """Call yaml_serializer and translate exceptions."""
        try:
            return SerializerSession(config=self._config).load(abs_path)
        except FileNotFoundError as exc:
            raise FileLoadError(f"File not found: {exc.filename}") from exc
        except PermissionError as exc:
            raise FileLoadError(str(exc)) from exc
        except (YAMLError, ValueError) as exc:
            raise YAMLParseError(str(exc)) from exc
        except OSError as exc:
            raise FileLoadError(str(exc)) from exc
