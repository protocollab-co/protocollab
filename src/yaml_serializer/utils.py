# yaml_serializer/utils.py

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml.comments import CommentedMap, CommentedSeq

__all__ = [
    "canonical_repr",
    "compute_hash",
    "resolve_include_path",
    "is_path_within_root",
    "mark_node",
    "mark_dirty",
    "clear_dirty",
    "update_file_attr",
    "replace_included",
    "mark_includes",
]

YamlNode = CommentedMap | CommentedSeq


def stable_api(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a function as part of the stable advanced-use API."""
    func.__stable_api__ = True
    return func


def internal_use_only(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a function as internal and free to change without notice."""
    func.__internal_use_only__ = True
    return func


logger = logging.getLogger(__name__)


@stable_api
def canonical_repr(node: Any) -> Any:
    """Build a deterministic Python representation of a YAML node for hashing."""
    logger.debug("Building canonical representation for %s", type(node).__name__)
    if isinstance(node, CommentedMap):
        items = [(k, canonical_repr(v)) for k, v in node.items()]
        items.sort(key=lambda x: x[0])
        return dict(items)
    if isinstance(node, CommentedSeq):
        return [canonical_repr(item) for item in node]
    return node


@stable_api
def compute_hash(node: Any) -> str:
    """Compute a SHA-256 hash from the canonical representation of *node*."""
    logger.debug("Computing hash for node")
    rep = canonical_repr(node)
    json_str = json.dumps(rep, sort_keys=True, ensure_ascii=False).encode("utf-8")
    logger.debug("JSON representation length: %d bytes", len(json_str))
    hash_value = hashlib.sha256(json_str).hexdigest()
    logger.debug("Hash: %s", hash_value)
    return hash_value


@internal_use_only
def _hash_file_path(yaml_path: str) -> str:
    """Return the sidecar path used to store the persisted hash for *yaml_path*."""
    result = yaml_path + ".hash"
    logger.debug("Hash file path for %s: %s", yaml_path, result)
    return result


@internal_use_only
def _load_hash_from_file(yaml_path: str) -> str | None:
    """Load a previously saved hash sidecar for *yaml_path* if it exists."""
    path = _hash_file_path(yaml_path)
    logger.debug("Loading hash from %s", path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            hash_value = f.read().strip()
        logger.debug("Hash found: %s", hash_value)
        return hash_value
    logger.debug("No hash file found at %s", path)
    return None


@internal_use_only
def _save_hash_to_file(yaml_path: str, hash_value: str) -> None:
    """Persist *hash_value* to the sidecar file associated with *yaml_path*."""
    path = _hash_file_path(yaml_path)
    logger.debug("Saving hash %s to %s", hash_value, path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(hash_value)


@stable_api
def update_file_attr(node: Any, old_file: str, new_file: str) -> None:
    """Recursively update ``_yaml_file`` values from *old_file* to *new_file*."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if getattr(node, "_yaml_file", None) != old_file:
            return
        node._yaml_file = new_file
        if isinstance(node, CommentedMap):
            for v in node.values():
                update_file_attr(v, old_file, new_file)
        if isinstance(node, CommentedSeq):
            for item in node:
                update_file_attr(item, old_file, new_file)


@internal_use_only
def _update_parent_file_attr(node: Any, old_file: str, new_file: str) -> None:
    """Recursively replace ``_yaml_parent_file`` references from *old_file* to *new_file*."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if getattr(node, "_yaml_parent_file", None) == old_file:
            node._yaml_parent_file = new_file
        if isinstance(node, CommentedMap):
            for v in node.values():
                _update_parent_file_attr(v, old_file, new_file)
        if isinstance(node, CommentedSeq):
            for item in node:
                _update_parent_file_attr(item, old_file, new_file)


@stable_api
def is_path_within_root(path: str, root_dir: str) -> bool:
    """Return True if *path* resolves to a location inside *root_dir*, else False."""
    try:
        Path(path).resolve().relative_to(Path(root_dir).resolve())
        return True
    except ValueError:
        return False


@stable_api
def mark_dirty(node: Any) -> None:
    """Mark *node* as dirty, recompute its hash, and propagate to its parents."""
    if node is None:
        return
    old_hash = getattr(node, "_yaml_hash", None)
    node._yaml_hash = compute_hash(node)
    node._yaml_dirty = True
    logger.debug(
        "Marked dirty node %s (old hash: %s, new hash: %s)",
        type(node).__name__,
        old_hash,
        node._yaml_hash,
    )
    if hasattr(node, "_yaml_parent"):
        mark_dirty(node._yaml_parent)


@stable_api
def mark_node(node: Any, filename: str, parent: YamlNode | None = None) -> None:
    """Attach file, parent, hash, and dirty metadata to a YAML subtree."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if hasattr(node, "_yaml_file") and node._yaml_file != filename:
            return
        if not hasattr(node, "_yaml_file"):
            node._yaml_file = filename
        if parent is not None:
            node._yaml_parent = parent
        node._yaml_hash = compute_hash(node)
        node._yaml_dirty = False
        logger.debug(
            "Marked node %s with file=%s, parent=%s", type(node).__name__, filename, parent
        )
        if isinstance(node, CommentedMap):
            for v in node.values():
                mark_node(v, filename, parent=node)
        if isinstance(node, CommentedSeq):
            for item in node:
                mark_node(item, filename, parent=node)


@stable_api
def clear_dirty(node: Any) -> None:
    """Recursively clear the dirty flag on *node* and all descendants."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        node._yaml_dirty = False
        logger.debug("Cleared dirty flag for node %s", node)
        if isinstance(node, CommentedMap):
            for v in node.values():
                clear_dirty(v)
        if isinstance(node, CommentedSeq):
            for item in node:
                clear_dirty(item)


@stable_api
def resolve_include_path(base_file: str, include_path: str) -> str:
    """Resolve *include_path* relative to *base_file* and return an absolute path."""
    base = Path(base_file).resolve().parent
    result = str((base / include_path).resolve())
    logger.debug("Resolved include path %s relative to %s -> %s", include_path, base_file, result)
    return result


@stable_api
def mark_includes(
    node: Any,
    target_file: str,
    mark_dirty_func: Callable[[YamlNode], None],
    logger: logging.Logger | None = None,
) -> bool:
    """Mark nodes originating from *target_file* and return whether any were found."""
    found = False
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if hasattr(node, "_yaml_file") and node._yaml_file == target_file:
            mark_dirty_func(node)
            found = True
            if logger:
                logger.debug("Found reference to %s in node %s", target_file, node)
        if isinstance(node, CommentedMap):
            for v in node.values():
                if mark_includes(v, target_file, mark_dirty_func, logger):
                    found = True
        if isinstance(node, CommentedSeq):
            for item in node:
                if mark_includes(item, target_file, mark_dirty_func, logger):
                    found = True
    return found


@stable_api
def replace_included(
    node: Any,
    old_file: str,
    new_file: str,
    logger: logging.Logger | None = None,
) -> bool:
    """Update included-node file metadata after a referenced file rename."""
    changed = False
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if hasattr(node, "_yaml_file") and node._yaml_file == old_file:
            node._yaml_file = new_file
            changed = True
            if logger:
                logger.debug("Updated _yaml_file from %s to %s", old_file, new_file)
        if hasattr(node, "_yaml_include_path") and hasattr(node, "_yaml_parent_file"):
            if getattr(node, "_yaml_file", None) == new_file:
                parent_dir = Path(node._yaml_parent_file).parent
                new_path = Path(new_file)
                try:
                    rel_path = new_path.relative_to(parent_dir)
                    new_include_path = str(rel_path).replace("\\", "/")
                    if node._yaml_include_path != new_include_path:
                        node._yaml_include_path = new_include_path
                        changed = True
                    if logger:
                        logger.debug("Updated _yaml_include_path to %s", node._yaml_include_path)
                except ValueError:
                    new_include_path = str(new_path).replace("\\", "/")
                    if node._yaml_include_path != new_include_path:
                        node._yaml_include_path = new_include_path
                        changed = True
                    if logger:
                        logger.debug(
                            "Updated _yaml_include_path to absolute: %s", node._yaml_include_path
                        )
        if isinstance(node, CommentedMap):
            for v in node.values():
                if replace_included(v, old_file, new_file, logger):
                    changed = True
        if isinstance(node, CommentedSeq):
            for item in node:
                if replace_included(item, old_file, new_file, logger):
                    changed = True
    return changed
