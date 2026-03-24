# yaml_serializer/utils.py

import os
import hashlib
import json
import logging
from pathlib import Path
from ruamel.yaml.comments import CommentedMap, CommentedSeq

logger = logging.getLogger(__name__)


def canonical_repr(node):
    """Build a canonical Python representation of a YAML node for hashing."""
    logger.debug("Building canonical representation for %s", type(node).__name__)
    if isinstance(node, CommentedMap):
        items = [(k, canonical_repr(v)) for k, v in node.items()]
        items.sort(key=lambda x: x[0])
        return dict(items)
    elif isinstance(node, CommentedSeq):
        return [canonical_repr(item) for item in node]
    else:
        return node


def compute_hash(node):
    """Compute the SHA-256 hash of a YAML node's canonical representation."""
    logger.debug("Computing hash for node")
    rep = canonical_repr(node)
    json_str = json.dumps(rep, sort_keys=True, ensure_ascii=False).encode("utf-8")
    logger.debug("JSON representation length: %d bytes", len(json_str))
    hash_value = hashlib.sha256(json_str).hexdigest()
    logger.debug("Hash: %s", hash_value)
    return hash_value


def hash_file_path(yaml_path: str) -> str:
    result = yaml_path + ".hash"
    logger.debug("Hash file path for %s: %s", yaml_path, result)
    return result


def load_hash_from_file(yaml_path: str) -> str | None:
    path = hash_file_path(yaml_path)
    logger.debug("Loading hash from %s", path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            hash_value = f.read().strip()
        logger.debug("Hash found: %s", hash_value)
        return hash_value
    logger.debug("No hash file found at %s", path)
    return None


def save_hash_to_file(yaml_path: str, hash_value: str) -> None:
    path = hash_file_path(yaml_path)
    logger.debug("Saving hash %s to %s", hash_value, path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(hash_value)


def update_file_attr(node, old_file, new_file):
    """Recursively update ``_yaml_file`` from *old_file* to *new_file*."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if getattr(node, "_yaml_file", None) != old_file:
            return
        node._yaml_file = new_file
        if isinstance(node, CommentedMap):
            for v in node.values():
                update_file_attr(v, old_file, new_file)
        elif isinstance(node, CommentedSeq):
            for item in node:
                update_file_attr(item, old_file, new_file)


def update_parent_file_attr(node, old_file, new_file):
    """Recursively replace ``_yaml_parent_file`` references from *old_file* to *new_file*."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        if getattr(node, "_yaml_parent_file", None) == old_file:
            node._yaml_parent_file = new_file
        if isinstance(node, CommentedMap):
            for v in node.values():
                update_parent_file_attr(v, old_file, new_file)
        elif isinstance(node, CommentedSeq):
            for item in node:
                update_parent_file_attr(item, old_file, new_file)


def is_path_within_root(path: str, root_dir: str) -> bool:
    """Return True if *path* resolves to a location inside *root_dir*, else False."""
    try:
        Path(path).resolve().relative_to(Path(root_dir).resolve())
        return True
    except ValueError:
        return False


def mark_dirty(node):
    """Mark *node* as dirty and propagate up through the parent chain."""
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


def mark_node(node, filename, parent=None):
    """Recursively stamp *filename* and initial hash onto nodes belonging to that file."""
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
        elif isinstance(node, CommentedSeq):
            for item in node:
                mark_node(item, filename, parent=node)


def clear_dirty(node):
    """Recursively clear the dirty flag on *node* and all its descendants."""
    if isinstance(node, (CommentedMap, CommentedSeq)):
        node._yaml_dirty = False
        logger.debug("Cleared dirty flag for node %s", node)
        if isinstance(node, CommentedMap):
            for v in node.values():
                clear_dirty(v)
        elif isinstance(node, CommentedSeq):
            for item in node:
                clear_dirty(item)


def resolve_include_path(base_file: str, include_path: str) -> str:
    base = Path(base_file).resolve().parent
    result = str((base / include_path).resolve())
    logger.debug("Resolved include path %s relative to %s -> %s", include_path, base_file, result)
    return result


def mark_includes(node, target_file, mark_dirty_func, logger=None):
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
        elif isinstance(node, CommentedSeq):
            for item in node:
                if mark_includes(item, target_file, mark_dirty_func, logger):
                    found = True
    return found


def replace_included(node, old_file, new_file, logger=None):
    from pathlib import Path

    if isinstance(node, (CommentedMap, CommentedSeq)):
        if hasattr(node, "_yaml_file") and node._yaml_file == old_file:
            node._yaml_file = new_file
            if logger:
                logger.debug("Updated _yaml_file from %s to %s", old_file, new_file)
        if hasattr(node, "_yaml_include_path") and hasattr(node, "_yaml_parent_file"):
            if getattr(node, "_yaml_file", None) == new_file:
                parent_dir = Path(node._yaml_parent_file).parent
                new_path = Path(new_file)
                try:
                    rel_path = new_path.relative_to(parent_dir)
                    node._yaml_include_path = str(rel_path).replace("\\", "/")
                    if logger:
                        logger.debug("Updated _yaml_include_path to %s", node._yaml_include_path)
                except ValueError:
                    node._yaml_include_path = str(new_path).replace("\\", "/")
                    if logger:
                        logger.debug(
                            "Updated _yaml_include_path to absolute: %s", node._yaml_include_path
                        )
        if isinstance(node, CommentedMap):
            for v in node.values():
                replace_included(v, old_file, new_file, logger)
        elif isinstance(node, CommentedSeq):
            for item in node:
                replace_included(item, old_file, new_file, logger)
