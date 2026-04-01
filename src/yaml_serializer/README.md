# yaml_serializer

**A secure YAML loader/dumper with `!include` support, change tracking, and round‑trip preservation**  
*Part of the [`protocollab`](https://github.com/yourname/protocollab) framework.*

`yaml_serializer` is a Python library built on top of `ruamel.yaml` that provides a safe, production‑ready way to load, modify, and save YAML files. It is the foundation of `protocollab’s` protocol definition handling, but can also be used independently in any Python project that needs robust YAML processing.

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
pip install git+https://github.com/yourname/protocollab.git
```

After installation, import it as:

```python
from yaml_serializer import SerializerSession
```

> **Note:** `yaml_serializer` requires Python 3.8 or later.

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

All modification functions automatically update parent links and dirty flags.

- `new_commented_map(initial: Optional[dict] = None, parent: Optional[Node] = None) -> CommentedMap`
- `new_commented_seq(initial: Optional[list] = None, parent: Optional[Node] = None) -> CommentedSeq`
- `add_to_dict(target: CommentedMap, key: str, value: Any)`
- `update_in_dict(target: CommentedMap, key: str, value: Any)`
- `remove_from_dict(target: CommentedMap, key: str)`
- `add_to_list(target: CommentedSeq, value: Any)`
- `remove_from_list(target: CommentedSeq, index: int)`
- `get_node_hash(node: Union[CommentedMap, CommentedSeq]) -> str` – returns the node’s hash (recalculates if dirty).

### Utility functions

- `is_path_within_root(path: str, root_dir: str) -> bool` – checks whether a resolved path is inside the root directory.
- `canonical_repr(data: Any) -> dict/list` – builds a canonical representation for hashing.
- `compute_hash(data: Any) -> str` – computes a SHA‑256 hash of the canonical representation.

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

`yaml_serializer` is part of `protocollab` and is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

Built on the shoulders of [ruamel.yaml](https://yaml.readthedocs.io/), [pydantic](https://docs.pydantic.dev/), and the Python community.