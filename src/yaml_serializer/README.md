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
- ✅ **High test coverage** (>95%) – battle‑tested and ready for production use.

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
from yaml_serializer import load_yaml_root, save_yaml_root
```

> **Note:** `yaml_serializer` requires Python 3.8 or later.

---

## 🚀 Quick Start

```python
from yaml_serializer import load_yaml_root, save_yaml_root
from yaml_serializer.modify import add_to_dict

# Load a YAML file (all !include references are resolved automatically)
data = load_yaml_root("path/to/file.yaml")

# Modify the structure (parent links and dirty flags are updated automatically)
add_to_dict(data, "new_key", "new_value")

# Save only changed files, preserving all comments and formatting
save_yaml_root()
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
data = load_yaml_root("main.yaml")
print(data["team"]["lead"]["name"])  # prints "Alice"
```

### Modifying nested structures

```python
from yaml_serializer import load_yaml_root, save_yaml_root
from yaml_serializer.modify import add_to_dict

data = load_yaml_root('protocol.yaml')

# Add a new field to a nested type
add_to_dict(data['types']['Message'], 'timestamp', 'u64')

# Add a new type definition (will mark the file as dirty)
add_to_dict(data['types'], 'NewType', {'field': 'value'})

# Save only changed files
save_yaml_root(only_if_changed=True)
```

### Secure loading with custom limits

```python
config = {
    'max_file_size': 5 * 1024 * 1024,   # 5 MB
    'max_struct_depth': 20,               # max YAML nesting depth (default 50)
    'max_include_depth': 20,              # max !include nesting depth (default 50)
    'max_imports': 50                      # max number of included files (default 100)
}

data = load_yaml_root('protocol.yaml', config=config)
```

### Renaming files with automatic `!include` updates

```python
from yaml_serializer import load_yaml_root, rename_yaml_file, save_yaml_root

data = load_yaml_root('main.yaml')

# Rename an included file – all !include references are automatically updated
rename_yaml_file('old_name.yaml', 'new_name.yaml')

save_yaml_root()
```

---

## 📖 API Reference

### Core functions

#### `load_yaml_root(path: str, config: Optional[dict] = None) -> CommentedMap`
Loads a YAML file, resolving all `!include` directives.

- **path**: Path to the main YAML file.
- **config**: Optional dictionary with security settings:
  - `max_file_size` – maximum file size in bytes (default 10 MB).
  - `max_struct_depth` – maximum YAML nesting depth for structures (default 50).
  - `max_include_depth` – maximum nesting depth for `!include` chains (default 50).
  - `max_imports` – maximum number of included files (default 100).
- **Returns**: The loaded root node as a `CommentedMap`.

#### `save_yaml_root(only_if_changed: bool = True)`
Saves loaded YAML files back to disk.

- **only_if_changed**: If `True` (default), only files that were modified are written.

#### `rename_yaml_file(old_path: str, new_path: str)`
Renames a loaded file and updates all `!include` references pointing to it.

- **old_path**: Current absolute path.
- **new_path**: New absolute path.

#### `propagate_dirty(file_path: str)`
Marks as dirty any nodes that reference the given file. Used internally after modifications that affect includes.

### Modification helpers

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

- **Total tests**: 266  
- **Code coverage**: 95%  
- **Structure**: 12 thematic test modules + `conftest.py` (shared fixtures)

To run tests locally:

```bash
pytest yaml_serializer/tests/ --cov=yaml_serializer
```

For more detailed output:

```bash
pytest yaml_serializer/tests/ -v --cov=yaml_serializer --cov-report=term-missing
```

---

## 🔧 Development Setup

```bash
# Create a virtual environment (conda example)
conda create -n protocollab python=3.12
conda activate protocollab

# Install dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .

# Run tests
pytest tests/
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