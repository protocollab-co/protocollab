"""Common type aliases used across the ProtocolLab package."""

from typing import Any, Dict, List, Optional, Union

# Fully-resolved protocol data tree (plain Python dicts/lists, no YAML metadata).
ProtocolData = Dict[str, Any]

# A single scalar, mapping, or sequence value inside protocol data.
ProtocolValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
