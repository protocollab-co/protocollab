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

### `simple/ip_scoped_packet.yaml`

A minimal IPv4-like packet header with `instances:` for Wireshark filter-only
fields and a summary `scope` field.

**Fields:** `version` (u1) · `src_ip` (u4) · `dst_ip` (u4) · `payload_size` (u2)

### `simple/ip_scoped_frame.yaml`

A minimal IPv4-like frame with directional `src_scope` / `dst_scope` summary
fields plus source and destination filter-only Wireshark fields.

**Fields:** `version` (u1) · `src_ip` (u4) · `dst_ip` (u4) · `payload_size` (u2)

---

## Usage

### Load and inspect

```bash
pc load examples/simple/ping_protocol.yaml
pc load examples/simple/ping_protocol.yaml --output-format json
```

### Validate against schema

```bash
pc validate examples/simple/ping_protocol.yaml
pc validate examples/simple/ping_protocol.yaml --strict
```

### Generate a Python parser

```bash
pc generate python examples/simple/ping_protocol.yaml --output build/
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
pc generate wireshark examples/simple/ping_protocol.yaml --output build/
```

The generated `build/ping_protocol.lua` can be loaded in Wireshark via
**Help → About Wireshark → Folders → Personal Lua Plugins**.

You can also expose extra display-filter fields through `instances:` when an
entry has both a `value:` expression and a `wireshark:` block:

```yaml
instances:
  lan:
    value: ((src_ip & 0xFF000000) == 0x0A000000) or ((src_ip & 0xFFFF0000) == 0xC0A80000)
    wireshark:
      type: bool
      filter-only: true
      label: LAN

  scope:
    value: '"lan" if lan else "inet"'
    wireshark:
      type: string
      label: Scope
```

This generates Wireshark fields such as:

- `myproto.lan` as a filter-only boolean field that is added only when the expression is true
- `myproto.scope == "lan"` as a regular string field

That gives short display filters like `myproto.lan` and summary filters like
`myproto.scope == "inet"` without duplicating the logic in Wireshark.

For source and destination scopes, see `examples/simple/ip_scoped_frame.yaml`.
It generates directional filters such as `myproto.src_lan`,
`myproto.dst_multicast`, `myproto.src_scope == "lan"`, and
`myproto.dst_scope == "bcast"`.
