# `protocollab`

> **Describe once. Generate everything.**

`protocollab` is an open-source framework for declaring, validating, and generating implementations of **network and binary protocols** from human-readable YAML specifications.

Write a single `.yaml` spec → get Python parsers, Wireshark dissectors, test suites, and documentation — all from the same source of truth.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#current-state)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20yaml__serializer-brightgreen)](#current-state)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#installation)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Why `protocollab`?

Most serialization tools (Protobuf, Thrift, FlatBuffers) are **data-first** or **RPC-first**. `protocollab` is **protocol-first**:

| Feature | Protobuf / Thrift | Kaitai Struct | `protocollab` |
|---|---|---|---|
| Stateful protocols (FSM) | No | No | Planned (CE: flat, Pro: hierarchical) |
| Wireshark dissector generation | No | Yes | Yes |
| Built-in security hardening | No | No | Yes — multi-layer loader |
| Spec validation (JSON Schema) | No | No | Yes |
| Python parser generation | Yes | Yes | Yes |
| Community open-source | Yes | Yes | Yes |

---

## Who is it for?

- **Protocol developers** — embedded, telecom, IoT, fintech
- **QA engineers** — auto-generated test suites for protocol compliance
- **Network analysts** — Wireshark dissector generation from specs
- **Data engineers** — structured extraction from binary formats (roadmap)

---

## Quick Start

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/cherninkiy/protocollab
cd protocollab

# 2. Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Install the package in development mode (editable)
pip install -e .
```

> **Note:** For development, install additional dependencies:
>
>     pip install -r requirements-dev.txt

### Write a spec

```yaml
# examples/simple/ping_protocol.yaml
meta:
  id: ping_protocol
  endian: le
  title: "Ping Protocol"
  description: "Simple ICMP-like ping/pong protocol"

seq:
  - id: type_id
    type: u1
    doc: "Message type (0 = request, 1 = reply)"
  - id: sequence_number
    type: u4
    doc: "Sequence number, wraps at 2^32"
  - id: payload_size
    type: u2
    doc: "Size of payload that follows this header, in bytes"
```

### Load and validate

```bash
# Load and inspect (JSON or YAML output)
protocollab load examples/simple/ping_protocol.yaml --output-format json

# Validate against the base schema
protocollab validate examples/simple/ping_protocol.yaml

# Strict validation (no unknown fields)
protocollab validate examples/simple/ping_protocol.yaml --strict
```

### Generate code

```bash
# Python dataclass parser
protocollab generate python examples/simple/ping_protocol.yaml --output build/

# Wireshark Lua dissector
protocollab generate wireshark examples/simple/ping_protocol.yaml --output build/
```

```python
# Use the generated parser
from build.ping_protocol_parser import PingProtocol
import io

data = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x40, 0x00])
proto = PingProtocol.parse(io.BytesIO(data))
print(proto.type_id, proto.sequence_number, proto.payload_size)
```

---

## Current State

**Phase 1 is complete.** The test suite is passing.

| Component | Status | Notes |
|---|---|---|
| `yaml_serializer` | ✅ 100% coverage | Secure YAML loader: `!include`, depth/size limits, path traversal, Billion Laughs |
| `protocollab.loader` | ✅ | `load_protocol()`, `get_global_loader()`, `configure_global()`, `ProtocolLoader`, LRU `MemoryCache` |
| `protocollab.validator` | ✅ | JSON Schema Draft 7, `base` and `strict` schemas |
| `protocollab.generators` | ✅ | `PythonGenerator` (dataclass), `LuaGenerator` (Wireshark dissector), Jinja2 |
| CLI `protocollab load` | ✅ | `--output-format json\|yaml`, `--no-cache`, security flags |
| CLI `protocollab validate` | ✅ | `--strict`, `--schema`, exit codes 0/1/2/3 |
| CLI `protocollab generate` | ✅ | `generate python\|wireshark FILE -o DIR`, exit codes 0/1/2/4 |
| Examples | ✅ | `examples/simple/` — ping protocol, Ethernet frame |
| Tests — `yaml_serializer` | ✅ | 100% coverage |
| Tests — `protocollab` | ✅ | loader, cache, utils, CLI, validator, generators |
| **Test suite** | ✅ | All passing |

**Security-first YAML loader**: The `yaml_serializer` module is hardened against common attacks: protection against Billion Laughs (XML entity expansion), path traversal in `!include`, recursion depth limits, and file size restrictions. This ensures safe handling of untrusted specifications.

### Phase 2 (in progress)
- Type system: primitive and user-defined types (`protocollab.core`)
- Import resolution across files
- Expression engine (safe, no `eval`)
- Semantic validation
- C++ code generation (preview)

### Phase 3+ (roadmap)
- Stateful protocols — flat FSM (Community), hierarchical statecharts (Pro)
- C++ / Rust / Java generators (Pro)
- Automated test generation and fuzzing (Pro)
- Plugin system (Enterprise)

---

## Architecture

```
src/
├── yaml_serializer/          # Secure YAML loader submodule
│   ├── serializer.py         # SerializerSession — primary API
│   ├── safe_constructor.py   # Security constraints
│   ├── utils.py              # canonical_repr, is_path_within_root, ...
│   ├── merge.py              # !include tree merging
│   └── modify.py             # Structure mutations
│
└── protocollab/              # Main package
    ├── main.py               # CLI (Click): load | validate | generate
    ├── exceptions.py         # FileLoadError (exit 1), YAMLParseError (exit 2)
    ├── loader/               # load_protocol(), get_global_loader(), configure_global(), LRU MemoryCache
    ├── validator/            # validate_protocol() + JSON Schema
    │   └── schemas/
    │       ├── base.schema.json      # permissive, KSY-compatible
    │       └── protocol.schema.json  # strict (additionalProperties: false)
    ├── generators/           # generate() + PythonGenerator + LuaGenerator
    │   └── templates/
    │       ├── python/parser.py.j2
    │       └── lua/dissector.lua.j2
    └── utils/                # resolve_path, to_json, to_yaml, print_data

examples/
├── simple/                   # ping_protocol.yaml, ethernet_frame.yaml
└── with_includes/            # base_types.yaml, tcp_like.yaml
```

**Dependency chain:**
```
CLI (main.py)
 └─ protocollab.loader     ──→ yaml_serializer.serializer
 └─ protocollab.validator  ──→ jsonschema.Draft7Validator
 └─ protocollab.generators ──→ jinja2.Environment
```

---

## Tech Stack

| Area | Tool |
|---|---|
| Language | Python 3.10+ |
| YAML parser | ruamel.yaml |
| CLI | Click 8.x |
| Schema validation | jsonschema 4.x (Draft 7) |
| Code generation | Jinja2 3.x |
| Data models | Pydantic v2 |
| Build | pyproject.toml (Poetry) + setup.py |
| Testing | pytest + pytest-cov |

---

## Running Tests

```bash
# All tests with coverage
pytest src/ -q

# yaml_serializer only (100% coverage)
pytest src/yaml_serializer/tests/ --cov=yaml_serializer --cov-report=term-missing

# protocollab
pytest src/protocollab/tests/ --cov=protocollab --cov-report=term-missing
```

---

## Community Edition vs Pro

| | Community (this repo) | Pro | Enterprise |
|---|---|---|---|
| Python + Lua generation | ✅ | ✅ | ✅ |
| Base + strict schema validation | ✅ | ✅ | ✅ |
| Flat FSM (≤10 states) | Planned | ✅ | ✅ |
| C++ / Rust / Java generation | — | ✅ | ✅ |
| Hierarchical statecharts | — | ✅ | ✅ |
| Test generation + fuzzing | — | ✅ | ✅ |
| CI/CD actions, custom generators | — | — | ✅ |

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

1. Fork the repository
2. Create your feature branch from `dev`: `git checkout -b feature/my-feature`
3. Write tests for any new functionality
4. Run the full test suite: `pytest src/ -q`
5. Open a Pull Request against `dev`

Development branch: `dev` · Remote: [github.com/cherninkiy/protocollab/tree/dev](https://github.com/cherninkiy/protocollab/tree/dev)

---

## Inspiration

- [Kaitai Struct](https://kaitai.io/) — declarative binary format description
- [OpenAPI](https://www.openapis.org/) — specification-first API design
- [Protocol Buffers](https://protobuf.dev/) — strong typing and code generation
- [Scapy](https://scapy.net/) — protocol construction and testing
- [Harel statecharts](https://www.sciencedirect.com/science/article/pii/0167642387900359) — reactive system formalism

---

## License

[Apache 2.0](LICENSE)
