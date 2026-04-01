# yaml_serializer

**A secure YAML loader/dumper with `!include` support, change tracking, and round‑trip preservation**  
*Part of the [`protocollab`](https://github.com/cherninkiy/protocollab) framework.*

`yaml_serializer` is a Python library built on top of `ruamel.yaml` that provides a safe, production‑ready way to load, modify, and save YAML files. It is the foundation of `protocollab`'s protocol definition handling, but can also be used independently in any Python project that needs robust YAML processing.

---

## ✨ Key Features

- 🔒 **Security‑first loading** – protects against path traversal, billion laughs, and arbitrary code execution via YAML tags.  
- 🔗 **`!include` tag** – split large YAML files into reusable components.  
- 📝 **Round‑trip preservation** – comments, quotes, and formatting are kept intact when dumping.  
- 🔄 **Change tracking** – automatic dirty marking and hash‑based change detection for efficient saving.  
- 🧩 **Easy modification** – helper functions to modify YAML structures while maintaining parent links and dirty flags.  
- 🔀 **Smart file renaming** – automatically updates `!include` paths when files are renamed.  
- ✅ **High test coverage** (100%) – battle‑tested and ready for production use.

---

## 📦 Installation

`yaml_serializer` is part of the `protocollab` package. You can install the whole framework (recommended):

```bash
pip install protocollab
```

If you prefer to use only the serializer without the rest of `protocollab`, you can copy the `yaml_serializer` folder into your project or install directly from the repository:

```bash
pip install git+https://github.com/cherninkiy/protocollab.git
```

After installation, import it as:

```python
from yaml_serializer import SerializerSession
```

> **Note:** `yaml_serializer` requires Python 3.10 or later.

---

## 🚀 Quick Start

```python
from yaml_serializer import SerializerSession
from yaml_serializer.modify import add_to_dict

# Create a session (encapsulates all state — thread-safe and test-friendly)
session = SerializerSession()

# Load a YAML file (all !include references are resolved automatically)
data = session.load("path/to/file.yaml")

# Modify the structure (parent links and dirty flags are updated automatically)
add_to_dict(data, "new_key", "new_value")

# Save only changed files, preserving all comments and formatting
session.save()
```

---

## 📁 Module Structure

```
yaml_serializer/
├── __init__.py           # Public API exports
├── serializer.py         # SerializerSession, loading, saving, renaming
├── safe_constructor.py   # Restricted YAML constructor and safety limits
├── modify.py             # Helpers for mutating YAML trees with dirty tracking
├── utils.py              # Path checks, hashing, include helpers, dirty propagation
└── tests/                # Test suite for loading, includes, security, and sessions
```

---

## 📚 Detailed Examples

### Working with `!include`

**person.yaml**
```yaml
name: Alice
age: 30
```

**main.yaml**
```yaml
team:
  lead: !include person.yaml
```

```python
from yaml_serializer import SerializerSession

session = SerializerSession()
data = session.load("main.yaml")
print(data["team"]["lead"]["name"])  # prints "Alice"
```

### Modifying nested structures

```python
from yaml_serializer import SerializerSession
from yaml_serializer.modify import add_to_dict

session = SerializerSession()
data = session.load('protocol.yaml')

# Add a new field to a nested type
add_to_dict(data['types']['Message'], 'timestamp', 'u64')

# Add a new type definition (will mark the file as dirty)
add_to_dict(data['types'], 'NewType', {'field': 'value'})

# Save only changed files
session.save(only_if_changed=True)
```

### Secure loading with custom limits

```python
from yaml_serializer import SerializerSession

config = {
    'max_file_size': 5 * 1024 * 1024,   # 5 MB
    'max_struct_depth': 20,               # max YAML nesting depth (default 50)
    'max_include_depth': 20,              # max !include nesting depth (default 50)
    'max_imports': 50                      # max number of included files (default 100)
}

# Config can be given at construction time (applies to every load call) …
session = SerializerSession(config)
data = session.load('protocol.yaml')

# … or overridden per-load:
data = session.load('protocol.yaml', config={'max_imports': 10})
```

### Renaming files with automatic `!include` updates

```python
from yaml_serializer import SerializerSession

session = SerializerSession()
session.load('main.yaml')

# Rename an included file – all !include references are automatically updated
session.rename('old_name.yaml', 'new_name.yaml')

session.save()
```

### Multiple independent sessions

```python
from yaml_serializer import SerializerSession

# Two sessions can load the same (or different) files without interfering:
session_a = SerializerSession()
session_b = SerializerSession()

data_a = session_a.load('spec_v1.yaml')
data_b = session_b.load('spec_v2.yaml')

# Modifications to data_a are invisible to session_b and vice-versa.
```

---

## 📖 API Reference

### `SerializerSession` (primary API)

```python
from yaml_serializer import SerializerSession
```

Each instance is completely independent — thread-safe, reusable, and isolated from
other sessions.

#### `SerializerSession(config: Optional[dict] = None)`
Create a session with optional default configuration.

| Key | Default | Description |
|-----|---------|-------------|
| `max_file_size` | 10 MB | Maximum file size in bytes |
| `max_struct_depth` | 50 | Maximum YAML nesting depth |
| `max_include_depth` | 50 | Maximum `!include` chain depth |
| `max_imports` | 100 | Maximum total included files |

#### `session.load(path: str, config: Optional[dict] = None) -> CommentedMap`
Load *path* and all `!include` references. *config* overrides per-call defaults.

#### `session.save(only_if_changed: bool = True)`
Write modified files back to disk.

#### `session.rename(old_path: str, new_path: str)`
Rename a file and update all `!include` references to it.

#### `session.propagate_dirty(file_path: str)`
Mark as dirty all files that `!include` *file_path*.

#### `session.clear()`
Reset all loaded state. Configuration defaults are preserved.

---

The public helper functions exported from `yaml_serializer` complement the
session API and automatically update parent links and dirty flags.

- `new_commented_map(initial: Optional[dict] = None, parent: Optional[Node] = None) -> CommentedMap`
- `new_commented_seq(initial: Optional[list] = None, parent: Optional[Node] = None) -> CommentedSeq`
- `add_to_dict(target: CommentedMap, key: str, value: Any)`
- `update_in_dict(target: CommentedMap, key: str, value: Any)`
- `remove_from_dict(target: CommentedMap, key: str)`
- `add_to_list(target: CommentedSeq, value: Any)`
- `remove_from_list(target: CommentedSeq, index: int)`
- `get_node_hash(node: Union[CommentedMap, CommentedSeq]) -> str` – returns the node’s hash (recalculates if dirty).

The lower-level internals in `safe_constructor.py` and most of `serializer.py`
are implementation details of the current codebase. When using the library
directly, prefer `SerializerSession` plus the re-exported helpers from
`yaml_serializer`.

---

## 🛡️ Public API Stability

The following functions from `yaml_serializer.utils` are considered part of the
intended public API for advanced use. While the project is still in the `0.x`
phase, this API may still evolve when needed, but breaking changes should be
called out explicitly in the release notes. Once `yaml_serializer` reaches
`1.0.0`, these functions will be covered by backward-compatibility guarantees
for the `yaml_serializer 1.x` line:

- `canonical_repr`
- `compute_hash`
- `resolve_include_path`
- `is_path_within_root`
- `mark_node`
- `mark_dirty`
- `clear_dirty`
- `update_file_attr`
- `replace_included`
- `mark_includes`

These functions are exported via `yaml_serializer.utils.__all__` and marked with
the `_stable_api` metadata decorator in the source.

Helpers prefixed with `_` are internal implementation details and may change
without notice.

---

## 🛡️ Security

`yaml_serializer` was designed with security as a first‑class concern, addressing the shortcomings of many YAML libraries:

- **Restricted YAML tags** – only the custom `!include` tag is allowed; all others (including dangerous Python‑specific tags) are rejected.
- **File size limit** – prevents memory exhaustion attacks (configurable, default 10 MB).
- **Nesting depth limit** – prevents stack overflow from deeply nested structures (default 50).
- **Path traversal protection** – `!include` can only reference files inside the project root (or an explicitly allowed directory).
- **Circular import detection** – prevents infinite recursion.
- **Import count limit** – stops bomb‑style attacks with thousands of inclusions (default 100).

These measures make `yaml_serializer` suitable for processing untrusted YAML files – a key advantage over many alternatives.

---

## 🧪 Testing & Coverage

The module has an extensive test suite covering all critical paths.

- **Test suite**: extensive coverage of critical paths  
- **Code coverage**: 100% (yaml_serializer)  
- **Structure**: thematic test modules + `conftest.py` (shared fixtures)

To run tests locally:

```bash
poetry run pytest src/yaml_serializer/tests/ --cov=yaml_serializer
```

For more detailed output:

```bash
poetry run pytest src/yaml_serializer/tests/ -v --cov=yaml_serializer --cov-report=term-missing
```

---

## 🔧 Development Setup

```bash
# Clone the repository (if not already done)
git clone https://github.com/cherninkiy/protocollab
cd protocollab

# Install dependencies
poetry install

# Run tests
poetry run pytest src/yaml_serializer/tests/
```

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](../../CONTRIBUTING.md) and [Code of Conduct](../../CODE_OF_CONDUCT.md) before submitting a pull request.

If you discover a security vulnerability, **do not** open a public issue; instead, please follow the steps outlined in our [Security Policy](../../SECURITY.md).

---

## 📄 License

`yaml_serializer` is part of the `protocollab` project and inherits the
project's **Apache License 2.0**. A copy of the license is available in
[LICENSE](LICENSE), and the repository root also contains the canonical project
license text in [../../LICENSE](../../LICENSE).

---

## 🙏 Acknowledgements

Built on the shoulders of [ruamel.yaml](https://yaml.readthedocs.io/), [pydantic](https://docs.pydantic.dev/), and the Python community.