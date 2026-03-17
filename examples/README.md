# Examples

This directory contains sample protocol specifications in `protocollab` YAML format
(compatible with [Kaitai Struct](https://kaitai.io/) `.ksy` files).

## Format overview

A protocol specification is a YAML file with the following top-level sections:

```yaml
meta:
  id: my_protocol        # required — snake_case identifier
  endian: le             # byte order: le (little-endian) or be (big-endian)
  title: "My Protocol"  # optional — human-readable name
  description: "..."    # optional

seq:                     # ordered list of fields
  - id: field_name
    type: u1             # primitive type (see table below)
    doc: "description"

types:                   # optional reusable sub-structures
  my_struct:
    seq:
      - id: x
        type: u2
```

### Supported primitive types

| Type | Size | Description          |
|------|------|----------------------|
| `u1` | 1    | unsigned 8-bit int   |
| `u2` | 2    | unsigned 16-bit int  |
| `u4` | 4    | unsigned 32-bit int  |
| `u8` | 8    | unsigned 64-bit int  |
| `s1` | 1    | signed 8-bit int     |
| `s2` | 2    | signed 16-bit int    |
| `s4` | 4    | signed 32-bit int    |
| `s8` | 8    | signed 64-bit int    |
| `str`| N    | byte string (requires `size: N`) |

---

## Examples in this directory

### `simple/ping_protocol.yaml`

A minimal ICMP-like ping/pong protocol with little-endian byte order.

**Fields:** `type_id` (u1) · `sequence_number` (u4) · `payload_size` (u2)

### `simple/ethernet_frame.yaml`

An Ethernet frame header (big-endian).

**Fields:** `dst_mac` (u1) · `ethertype` (u2)

---

## Usage

### Load and inspect

```bash
protocollab load examples/simple/ping_protocol.yaml
protocollab load examples/simple/ping_protocol.yaml --output-format json
```

### Validate against schema

```bash
protocollab validate examples/simple/ping_protocol.yaml
protocollab validate examples/simple/ping_protocol.yaml --strict
```

### Generate a Python parser

```bash
protocollab generate python examples/simple/ping_protocol.yaml --output build/
```

The generated `build/ping_protocol_parser.py` contains a dataclass with `parse()` and `serialize()` methods:

```python
from build.ping_protocol_parser import PingProtocol
import struct

data = struct.pack("<BIH", 0, 42, 64)   # type=0, seq=42, size=64
msg = PingProtocol.parse(data)
print(msg.sequence_number)              # 42
assert msg.serialize() == data          # round-trip
```

### Generate a Wireshark Lua dissector

```bash
protocollab generate wireshark examples/simple/ping_protocol.yaml --output build/
```

The generated `build/ping_protocol.lua` can be loaded in Wireshark via
**Help → About Wireshark → Folders → Personal Lua Plugins**.
