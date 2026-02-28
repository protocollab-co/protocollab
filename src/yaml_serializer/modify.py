# yaml_serializer/modify.py

import logging
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from .utils import mark_dirty
from .utils import compute_hash

logger = logging.getLogger(__name__)

def new_commented_map(initial=None, parent=None):
    obj = CommentedMap(initial or [])
    if parent is not None:
        if hasattr(parent, '_yaml_file'):
            obj._yaml_file = parent._yaml_file
        obj._yaml_parent = parent
    obj._yaml_hash = None
    obj._yaml_dirty = True
    logger.debug("Created new CommentedMap with parent %s", parent)
    return obj

def new_commented_seq(initial=None, parent=None):
    obj = CommentedSeq(initial or [])
    if parent is not None:
        if hasattr(parent, '_yaml_file'):
            obj._yaml_file = parent._yaml_file
        obj._yaml_parent = parent
    obj._yaml_hash = None
    obj._yaml_dirty = True
    logger.debug("Created new CommentedSeq with parent %s", parent)
    return obj

def add_to_dict(dct, key, value):
    if isinstance(value, (CommentedMap, CommentedSeq)):
        if not hasattr(value, '_yaml_parent'):
            value._yaml_parent = dct
        if not hasattr(value, '_yaml_file') and hasattr(dct, '_yaml_file'):
            value._yaml_file = dct._yaml_file
    dct[key] = value
    mark_dirty(dct)
    logger.debug("Added key '%s' to dict %s", key, dct)

def add_to_list(lst, item):
    if isinstance(item, (CommentedMap, CommentedSeq)):
        if not hasattr(item, '_yaml_parent'):
            item._yaml_parent = lst
        if not hasattr(item, '_yaml_file') and hasattr(lst, '_yaml_file'):
            item._yaml_file = lst._yaml_file
    lst.append(item)
    mark_dirty(lst)
    logger.debug("Appended item to list %s", lst)

def update_in_dict(dct, key, value):
    if key in dct:
        dct[key] = value
        mark_dirty(dct)
        logger.debug("Updated key '%s' in dict %s", key, dct)
    else:
        add_to_dict(dct, key, value)

def remove_from_dict(dct, key):
    if key in dct:
        del dct[key]
        mark_dirty(dct)
        logger.debug("Removed key '%s' from dict %s", key, dct)

def remove_from_list(lst, index):
    del lst[index]
    mark_dirty(lst)
    logger.debug("Removed index %s from list %s", index, lst)

def get_node_hash(node):
    dirty = getattr(node, '_yaml_dirty', False)
    logger.debug("Getting hash for node %s (dirty: %s)", node, dirty)
    if dirty:
        node._yaml_hash = compute_hash(node)
        node._yaml_dirty = False
        logger.debug("Recalculated hash for node: %s", node._yaml_hash)
    return node._yaml_hash