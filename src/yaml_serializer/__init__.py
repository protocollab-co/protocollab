import logging
from .serializer import SerializerSession
from .modify import (
    new_commented_map,
    new_commented_seq,
    add_to_dict,
    add_to_list,
    update_in_dict,
    remove_from_dict,
    remove_from_list,
    get_node_hash,
)

__all__ = [
    "SerializerSession",
    "new_commented_map",
    "new_commented_seq",
    "add_to_dict",
    "add_to_list",
    "update_in_dict",
    "remove_from_dict",
    "remove_from_list",
    "get_node_hash",
]

# Register a NullHandler so library users see no output by default.
logging.getLogger(__name__).addHandler(logging.NullHandler())
