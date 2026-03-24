# yaml_serializer/serializer.py

import os
import logging
from pathlib import Path
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from . import utils
from .utils import (
    mark_node,
    clear_dirty,
    mark_dirty,
    mark_includes,
    replace_included,
    update_file_attr,
)

logger = logging.getLogger(__name__)

# Constants
INCLUDE_TAG = "!include"


def create_yaml_instance(session, register_include_representer=False, max_depth=None, base_depth=0):
    """
    Create a YAML instance that uses RestrictedSafeConstructor.
    session — the SerializerSession whose settings are applied.
    If register_include_representer is True, registers a representer for !include.
    max_depth — maximum allowed YAML structure depth.
    """
    logger.debug(
        "Creating secure YAML instance with RestrictedSafeConstructor and !include representer, max_depth=%s",
        max_depth,
    )
    from .safe_constructor import create_safe_yaml_instance

    yaml = create_safe_yaml_instance(
        max_depth=max_depth if max_depth is not None else 50, base_depth=base_depth
    )
    yaml._session = session  # attach session for constructor/representer access
    if register_include_representer:

        def _representer(dumper, data):
            return _make_include_representer(session)(dumper, data)

        yaml.representer.add_representer(CommentedMap, _representer)
        yaml.representer.add_representer(CommentedSeq, _representer)
    return yaml


def _make_include_representer(session):
    """Returns an include representer bound to *session*."""

    def include_representer(dumper, data):
        if hasattr(data, "_yaml_include_path") and hasattr(data, "_yaml_file"):
            if session._current_saving_file and data._yaml_file != session._current_saving_file:
                include_path = data._yaml_include_path
                logger.debug("Representing node as !include %s", include_path)
                return dumper.represent_scalar(INCLUDE_TAG, include_path)
        if isinstance(data, CommentedMap):
            return dumper.represent_dict(data)
        elif isinstance(data, CommentedSeq):
            return dumper.represent_list(data)
        return dumper.represent_data(data)  # pragma: no cover

    return include_representer


def _make_include_constructor(session):
    """Returns an include constructor bound to *session*."""

    def include_constructor(loader, node):
        """
        Tag constructor for !include.
        Validates path safety and enforces security limits.
        """
        filename = loader.construct_scalar(node)
        logger.info("Processing !include: %s", filename)

        session._import_counter += 1
        if session._max_imports is not None and session._import_counter > session._max_imports:
            raise ValueError(f"Exceeded maximum number of imports ({session._max_imports})")

        if not session._loading_stack:
            raise ValueError("!include used outside of file loading context")

        current_file = session._loading_stack[-1]
        included_path = utils.resolve_include_path(current_file, filename)
        logger.debug("Resolved include path: %s", included_path)

        if not utils.is_path_within_root(included_path, session._root_dir):
            logger.error("Attempt to include file outside root directory: %s", included_path)
            raise PermissionError(f"Include path {filename} is not allowed (outside root)")
        if session._max_file_size:
            file_size = os.path.getsize(included_path)
            if file_size > session._max_file_size:
                raise ValueError(
                    f"File {included_path} exceeds size limit {session._max_file_size}"
                )
        if included_path in session._loading_stack:
            logger.error("Circular include detected: %s", included_path)
            raise ValueError(f"Circular include detected: {included_path}")
        if session._max_include_depth and len(session._loading_stack) >= session._max_include_depth:
            raise ValueError(f"Exceeded maximum include depth ({session._max_include_depth})")

        base_depth = getattr(loader, "_base_depth", 0) + 1
        yaml_inc = create_yaml_instance(
            session,
            register_include_representer=False,
            max_depth=session._max_struct_depth,
            base_depth=base_depth,
        )
        if hasattr(yaml_inc, "_make_constructor"):
            yaml_inc.Constructor = yaml_inc._make_constructor(
                max_depth=session._max_struct_depth, base_depth=base_depth
            )
        yaml_inc.constructor.add_constructor(INCLUDE_TAG, include_constructor)
        data = None
        try:
            session._loading_stack.append(included_path)
            logger.debug("Loading included file %s", included_path)
            with open(included_path, "r", encoding="utf-8") as f:
                data = yaml_inc.load(f)
        finally:
            session._loading_stack.pop()
        if data is not None:
            mark_node(data, included_path)
            session._file_roots[included_path] = data
            data._yaml_include_path = filename
            data._yaml_parent_file = current_file
            logger.debug(
                "Marked included node with file %s, include path: %s", included_path, filename
            )
            saved_hash = utils.load_hash_from_file(included_path)
            session._loaded_hashes[included_path] = saved_hash
            logger.debug("Loaded saved hash for included file: %s", saved_hash)
            return data

    return include_constructor


# ---------------------------------------------------------------------------
# SerializerSession — the new thread-safe, multi-load-capable API
# ---------------------------------------------------------------------------


class SerializerSession:
    """
    Encapsulates all state required for loading, saving, renaming and tracking
    YAML files.  Each instance is completely independent of all others, making
    it safe to use concurrently or in parallel test cases.

    Configuration keys (passed as *config* dict to the constructor or to
    :meth:`load`):

    * ``max_file_size``     – maximum allowed file size in bytes (default 10 MB)
    * ``max_include_depth`` – maximum ``!include`` nesting depth (default 50)
    * ``max_struct_depth``  – maximum YAML mapping/sequence depth (default 50)
    * ``max_imports``       – maximum total ``!include`` operations (default 100)
    """

    def __init__(self, config=None):
        config = config or {}
        self.max_file_size = config.get("max_file_size", 10 * 1024 * 1024)
        self.max_include_depth = config.get("max_include_depth", 50)
        self.max_struct_depth = config.get("max_struct_depth", 50)
        self.max_imports = config.get("max_imports", 100)

        # Internal state – reset on each load()
        self._file_roots = {}
        self._loaded_hashes = {}
        self._yaml_instance = None
        self._root_filename = None
        self._current_saving_file = None
        self._root_dir = None
        self._max_file_size = self.max_file_size
        self._max_include_depth = self.max_include_depth
        self._max_struct_depth = self.max_struct_depth
        self._max_imports = self.max_imports
        self._loading_stack = []
        self._import_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, file_path, config=None):
        """Load *file_path* (and all ``!include`` references) into this session.

        *config* overrides the defaults set in the constructor for this load
        operation only.

        Returns the root YAML node.
        """
        logger.info("Loading root YAML from file: %s", file_path)
        cfg = config or {}
        main_path = str(Path(file_path).resolve())

        self._root_dir = str(Path(main_path).parent)
        self._max_file_size = cfg.get("max_file_size", self.max_file_size)
        self._max_include_depth = cfg.get("max_include_depth", self.max_include_depth)
        self._max_struct_depth = cfg.get("max_struct_depth", self.max_struct_depth)
        self._max_imports = cfg.get("max_imports", self.max_imports)
        logger.debug(
            "Security config: root_dir=%s, max_file_size=%s, max_struct_depth=%s, "
            "max_include_depth=%s, max_imports=%s",
            self._root_dir,
            self._max_file_size,
            self._max_struct_depth,
            self._max_include_depth,
            self._max_imports,
        )

        self._yaml_instance = create_yaml_instance(
            self, register_include_representer=True, max_depth=self._max_struct_depth, base_depth=0
        )
        assert self._yaml_instance is not None
        self._yaml_instance.constructor.add_constructor(
            INCLUDE_TAG, _make_include_constructor(self)
        )
        logger.debug("Added !include constructor")

        self._root_filename = main_path
        self._import_counter = 0
        self._loaded_hashes.clear()
        self._file_roots.clear()
        self._loading_stack.clear()
        self._loading_stack.append(main_path)
        with open(main_path, "r", encoding="utf-8") as f:
            logger.debug("Loading YAML content from %s", main_path)
            data = self._yaml_instance.load(f)
        self._loading_stack.pop()
        mark_node(data, main_path)
        self._file_roots[main_path] = data
        logger.debug("Root node marked with file %s", main_path)
        saved_hash = utils.load_hash_from_file(main_path)
        self._loaded_hashes[main_path] = saved_hash
        logger.debug("Loaded saved hash for %s: %s", main_path, saved_hash)
        return data

    def save(self, only_if_changed=True):
        """Save all loaded files back to disk.

        When *only_if_changed* is ``True`` (default) files whose content hash
        matches the on-load hash are skipped.
        """
        if self._yaml_instance is None:
            raise RuntimeError("No YAML loaded. Call load() first.")
        logger.info("Saving root YAML (only_if_changed=%s)", only_if_changed)
        for filename, root in self._file_roots.items():
            curr_hash = root._yaml_hash
            orig_hash = self._loaded_hashes.get(filename)
            if (
                only_if_changed
                and orig_hash is not None
                and curr_hash == orig_hash
                and not root._yaml_dirty
            ):
                logger.debug("File %s unchanged, skipping", filename)
                continue
            logger.info("Saving file %s", filename)
            self._current_saving_file = filename
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    self._yaml_instance.dump(root, f)
                    f.flush()
                    os.fsync(f.fileno())
            finally:
                self._current_saving_file = None
            utils.save_hash_to_file(filename, curr_hash)
            self._loaded_hashes[filename] = curr_hash
            clear_dirty(root)
            logger.debug("Saved hash and cleared dirty for %s", filename)

    def rename(self, old_path: str, new_path: str):
        """Rename a loaded YAML file on disk and update all internal references."""
        old_abs = str(Path(old_path).resolve())
        new_abs = str(Path(new_path).resolve())
        logger.info("Renaming YAML file from %s to %s", old_abs, new_abs)
        if old_abs not in self._file_roots:
            raise ValueError(f"File {old_abs} not loaded")
        Path(old_abs).rename(new_abs)
        logger.debug("Physical rename done")
        old_hash_file = utils.hash_file_path(old_abs)
        if os.path.exists(old_hash_file):
            new_hash_file = utils.hash_file_path(new_abs)
            Path(old_hash_file).rename(new_hash_file)
            logger.debug("Hash file renamed from %s to %s", old_hash_file, new_hash_file)
        root = self._file_roots.pop(old_abs)
        self._file_roots[new_abs] = root
        if old_abs in self._loaded_hashes:
            self._loaded_hashes[new_abs] = self._loaded_hashes.pop(old_abs)
        logger.debug("Updated session structures: _file_roots and _loaded_hashes")
        update_file_attr(root, new_abs)
        logger.debug("Updated _yaml_file attributes for root and descendants")
        logger.debug("Updating !include references in other loaded files")
        for fpath, froot in self._file_roots.items():
            if fpath == new_abs:
                continue
            replace_included(froot, old_abs, new_abs, logger)
            if hasattr(froot, "_yaml_dirty"):
                mark_dirty(froot)
                logger.debug("Marked root of file %s as dirty after reference update", fpath)
        if old_abs == self._root_filename:
            self._root_filename = new_abs
            logger.debug("Updated main filename to %s", new_abs)

    def propagate_dirty(self, file_path: str):
        """Mark all files that include *file_path* as dirty."""
        abs_path = str(Path(file_path).resolve())
        logger.info("Propagating dirty for file %s", file_path)
        for fpath, root in self._file_roots.items():
            if fpath == abs_path:
                continue
            found = mark_includes(root, abs_path, mark_dirty, logger)
            if found:
                mark_dirty(root)
                logger.debug("Marked root of file %s as dirty due to included references", fpath)

    def clear(self):
        """Reset all session state without changing configuration defaults."""
        self._file_roots.clear()
        self._loaded_hashes.clear()
        self._yaml_instance = None
        self._root_filename = None
        self._current_saving_file = None
        self._root_dir = None
        self._max_file_size = self.max_file_size
        self._max_include_depth = self.max_include_depth
        self._max_struct_depth = self.max_struct_depth
        self._max_imports = self.max_imports
        self._loading_stack.clear()
        self._import_counter = 0

    def reset(self):
        """Alias for :meth:`clear` kept for backward compatibility."""
        self.clear()


__all__ = [
    "SerializerSession",
    "create_yaml_instance",
]
