# protocollab

[Русская версия](README_ru.md)

> Describe once. Generate everything.

`protocollab` is an open-source framework for declaring, validating, and generating implementations of network and binary protocols from human-readable YAML specifications.

Write a single `.yaml` spec and generate Python parsers, Wireshark dissectors, mock runtimes, Scapy Layer 2 demos, TCP Layer 3 demos, test suites, and documentation from the same source of truth.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#project-status)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20critical__modules-brightgreen)](#project-status)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#installation)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Why protocollab?

Most serialization tools are data-first or RPC-first. `protocollab` is protocol-first: it treats the protocol specification itself as the primary artifact and builds validators, generators, demos, and tooling around it.

| Feature | Protobuf / Thrift | Kaitai Struct | protocollab |
|---|---|---|---|
| Protocol-first workflow | No | Partial | Yes |
| Wireshark dissector generation | No | Yes | Yes |
| Python parser generation | Yes | Yes | Yes |
| JSON Schema validation | No | No | Yes |
| Hardened YAML loader | No | No | Yes |
| Live demo runtimes | No | No | Yes |
| Stateful protocol roadmap | Limited | No | Planned |

---

## What You Get

- A secure YAML-based authoring format for protocol definitions
- CLI commands to load, validate, and generate artifacts from a spec
- A dedicated `yaml_serializer` package for hardened YAML processing
- A dedicated `jsonschema_validator` package for pluggable JSON Schema validation
- Generators for Python parsers, Wireshark Lua dissectors, mock runtimes, L2 Scapy runtimes, and L3 socket runtimes
- Demo workflows that validate end-to-end generated artifacts

---

## Protocol Specs Repository

Community-driven protocol specifications live in [protocollab-specs](https://github.com/cherninkiy/protocollab-specs).

The `protocollab-specs` repository is the central, curated collection of YAML protocol definitions compatible with `protocollab`. Every spec can be validated, versioned, and used to generate parsers, Wireshark dissectors, and test suites.

Use `protocollab` when you want the framework and generators. Use `protocollab-specs` when you want reusable specifications maintained as a community catalog.

---

## Quick Start

### Installation

```bash
git clone https://github.com/cherninkiy/protocollab
cd protocollab

poetry install

# Optional JSON Schema validation backends for the full validator test suite
poetry install --extras "validator-jsonscreamer validator-fastjsonschema"
```

`protocollab` uses Poetry for dependency management. Core and optional dependencies are declared in `pyproject.toml`.

Optional backend tests in `src/jsonschema_validator/tests/` are skipped automatically unless the matching extras are installed.

### Write a Spec

```yaml
meta:
  id: ping_protocol
  endian: le
  title: Ping Protocol
  description: Simple ICMP-like ping/pong protocol

seq:
  - id: type_id
    type: u1
    doc: Message type (0 = request, 1 = reply)
  - id: sequence_number
    type: u4
    doc: Sequence number, wraps at 2^32
  - id: payload_size
    type: u2
    doc: Size of payload that follows this header, in bytes
```

### Load and Validate

```bash
protocollab load examples/simple/ping_protocol.yaml --output-format json
protocollab validate examples/simple/ping_protocol.yaml
protocollab validate examples/simple/ping_protocol.yaml --strict
```

### Generate Artifacts

```bash
protocollab generate python examples/simple/ping_protocol.yaml --output build/
protocollab generate wireshark examples/simple/ping_protocol.yaml --output build/
protocollab generate mock-client examples/simple/ping_protocol.yaml --output build/
protocollab generate mock-server examples/simple/ping_protocol.yaml --output build/
protocollab generate l2-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l2-server examples/simple/ping_protocol.yaml --output build/
protocollab generate l3-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l3-server examples/simple/ping_protocol.yaml --output build/
```

### Use the Generated Parser

```python
import io

from build.ping_protocol_parser import PingProtocol

data = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x40, 0x00])
proto = PingProtocol.parse(io.BytesIO(data))
print(proto.type_id, proto.sequence_number, proto.payload_size)
```

---

## Specification Notes

`instances:` can define virtual Wireshark fields when an entry contains a `value:` expression and a `wireshark:` block.

- Use `wireshark.type: bool` with `filter-only: true` for shortcut fields such as `myproto.lan`
- Use `wireshark.type: string` for summary fields such as `myproto.scope == "lan"`

Relevant examples:

- `examples/simple/ip_scoped_packet.yaml` for a single `scope` field
- `examples/simple/ip_scoped_frame.yaml` for split `src_scope` and `dst_scope` filters

---

## Project Status

Critical modules currently have full coverage and the main CLI and generator workflows are in place.

| Area | Status | Notes |
|---|---|---|
| `yaml_serializer` | Stable | Secure YAML loader, `!include`, round-trip preservation, 100% coverage |
| `jsonschema_validator` | Stable | Pluggable backends, unified error model, safe auto mode, 100% coverage |
| `protocollab.loader` | Available | Secure loading, caching, session-based integration |
| `protocollab.validator` | Available | Base and strict schema validation via facade backend selection |
| `protocollab.generators` | Available | Python, Wireshark, mock, L2, and L3 generators |
| CLI | Available | `load`, `validate`, and `generate` commands |
| Demo workflows | Available | `demo/mock`, `demo/l2`, `demo/l3` |

---

## Demo Workflows

Three demo entry points are included for the same `examples/simple/ping_protocol.yaml` specification.

- `demo/mock` generates a parser and queue-based `MockClient` and `MockServer` runtime
- `demo/l2` generates a parser, `L2ScapyClient`, `L2ScapyServer`, and a Wireshark Lua dissector
- `demo/l3` generates a parser, `L3SocketClient`, `L3SocketServer`, and a Wireshark Lua dissector

Validation commands:

- `python demo/mock/demo.py check`
- `python demo/l2/demo.py check`
- `python demo/l3/demo.py check`

Live transport demos:

- `python demo/l2/demo.py run --iface <name>`
- `python demo/l3/demo.py run`

---

## Repository Layout

```text
src/
|-- yaml_serializer/          # Secure YAML loading and round-trip saving
|-- jsonschema_validator/     # Pluggable JSON Schema validation facade
`-- protocollab/              # CLI, loaders, validators, generators, utilities

demo/
|-- mock/                     # Queue-based generated runtime demo
|-- l2/                       # Scapy Layer 2 generated runtime demo
`-- l3/                       # TCP Layer 3 generated runtime demo

examples/
|-- simple/                   # Standalone protocol definitions
`-- with_includes/            # Multi-file examples using !include

docs/
`-- adr/                      # Architecture decision records
```

High-level dependency chain:

```text
CLI
|-- protocollab.loader      -> yaml_serializer
|-- protocollab.validator   -> jsonschema_validator
`-- protocollab.generators  -> Jinja2 templates
```

---

## Tech Stack

| Area | Tool |
|---|---|
| Language | Python 3.10+ |
| YAML processing | ruamel.yaml |
| CLI | Click 8.x |
| Schema validation | jsonschema, jsonscreamer, fastjsonschema |
| Templates | Jinja2 3.x |
| Models | Pydantic v2 |
| Packaging | Poetry |
| Testing | pytest, pytest-cov |

---

## Running Tests

```bash
poetry run pytest src/ -q
poetry run pytest src/yaml_serializer/tests/ --cov=yaml_serializer --cov-report=term-missing
poetry run pytest src/jsonschema_validator/tests/ --cov=jsonschema_validator --cov-report=term-missing
poetry run pytest src/protocollab/tests/ --cov=protocollab --cov-report=term-missing
```

---

## Roadmap

### Near Term

- Primitive and user-defined types in `protocollab.core`
- Import resolution across files
- Safe expression engine without `eval`
- Semantic validation
- Early C++ generation support

### Longer Term

- Stateful protocols with flat FSM in Community Edition
- Hierarchical statecharts in Pro
- Additional generators for C++, Rust, and Java
- Test generation and fuzzing
- Plugin system and enterprise integrations

---

## Community Edition vs Pro

| Capability | Community | Pro | Enterprise |
|---|---|---|---|
| Python and Lua generation | Yes | Yes | Yes |
| Mock, L2, and L3 demo runtimes | Yes | Yes | Yes |
| Base and strict schema validation | Yes | Yes | Yes |
| Flat FSM | Planned | Yes | Yes |
| C++, Rust, Java generators | No | Yes | Yes |
| Hierarchical statecharts | No | Yes | Yes |
| Test generation and fuzzing | No | Yes | Yes |
| Custom generators and CI/CD actions | No | No | Yes |

---

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a pull request.

1. Fork the repository.
2. Create a feature branch from `dev`.
3. Add or update tests for your changes.
4. Run the relevant local test suite.
5. Open a pull request against `dev`.

Development branch: [github.com/cherninkiy/protocollab/tree/dev](https://github.com/cherninkiy/protocollab/tree/dev)

---

## License

[Apache 2.0](LICENSE)
