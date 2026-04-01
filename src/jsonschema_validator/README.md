# jsonschema_validator

**A pluggable JSON Schema validation facade with a single error model and safe backend selection**  
*Part of the [`protocollab`](https://github.com/cherninkiy/protocollab) framework.*

`jsonschema_validator` is a small Python library that normalizes JSON Schema validation across multiple engines. It gives you one factory, one result model, and one backend-agnostic API, while letting you choose between compatibility, safety, and raw speed.

---

## Key Features

- Unified validation API via `ValidatorFactory`
- Backend-agnostic error model via `SchemaValidationError`
- Safe `auto` backend selection that prefers `jsonscreamer` and falls back to `jsonschema`
- Explicit opt-in support for `fastjsonschema` when performance matters
- Consistent path formatting such as `(root)`, `meta.id`, and `seq[0].type`
- Full test coverage for the module and its backends

---

## Installation

Install the standalone package:

```bash
pip install jsonschema-validator
```

Install the whole framework when you also need the `protocollab` CLI and generators:

```bash
pip install protocollab
```

Install the preferred optional `jsonscreamer` backend for the standalone package:

```bash
pip install "jsonschema-validator[jsonscreamer]"
```

Install the optional `fastjsonschema` backend:

```bash
pip install "jsonschema-validator[fastjsonschema]"
```

For development from this repository, either install the full monorepo from the
repository root or install this package in editable mode:

```bash
pip install -e "src/jsonschema_validator[jsonscreamer,fastjsonschema]"
```

After installation, import it as:

```python
from jsonschema_validator import ValidatorFactory, SchemaValidationError
```

> Note: `jsonschema_validator` requires Python 3.10 or later.

---

## Quick Start

```python
from jsonschema_validator import ValidatorFactory

schema = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
}

data = {"name": 42, "age": -1}

validator = ValidatorFactory.create(backend="auto")
errors = validator.validate(schema, data)

for error in errors:
    print(error.path, error.message, error.schema_path)
```

Example output:

```text
name 42 is not of type 'string' properties/name/type
age -1 is less than the minimum of 0 properties/age/minimum
```

---

## Module Structure

```text
jsonschema_validator/
|-- __init__.py                     # Public API exports
|-- factory.py                      # Backend selection and instance creation
|-- models.py                       # SchemaValidationError dataclass
|-- backends/
|   |-- base.py                     # Abstract validator interface
|   |-- jsonschema_backend.py       # Compatibility-first backend
|   |-- jsonscreamer_backend.py     # Preferred safe backend for auto mode
|   `-- fastjsonschema_backend.py   # Explicit high-performance backend
|-- tests/                          # Backend, factory, and model tests
`-- LICENSE                         # Local Apache 2.0 license copy
```

---

## Backend Selection

### `backend="auto"`

This is the default and recommended mode.

- Prefers `jsonscreamer` when it is installed
- Falls back to `jsonschema` when `jsonscreamer` is unavailable
- Never selects `fastjsonschema` automatically

### `backend="jsonschema"`

Use this when you want the most predictable Draft 7 behavior and broad compatibility.

### `backend="jsonscreamer"`

Use this when you want the preferred safe backend explicitly.

### `backend="fastjsonschema"`

Use this only when you explicitly want the faster backend.

```python
validator = ValidatorFactory.create(backend="fastjsonschema")
```

---

## API Reference

### `ValidatorFactory`

```python
from jsonschema_validator import ValidatorFactory
```

#### `ValidatorFactory.create(backend: str = "auto", cache: bool = True)`

Creates a validator instance for the requested backend.

- `backend="auto"` chooses the safest available backend
- `backend="jsonschema"` forces the `jsonschema` backend
- `backend="jsonscreamer"` forces the `jsonscreamer` backend
- `backend="fastjsonschema"` forces the `fastjsonschema` backend
- `cache=True` enables validator caching inside the backend

### `available_backends() -> list[str]`

Returns the backend names that can be instantiated in the current environment.

```python
from jsonschema_validator import available_backends

print(available_backends())
```

### `SchemaValidationError`

```python
from jsonschema_validator import SchemaValidationError
```

Normalized validation result with the following fields:

- `path`: location in the validated data, for example `meta.id` or `seq[0].type`
- `message`: human-readable validation failure text
- `schema_path`: location inside the JSON Schema document, when provided by the backend

---

## Public API Stability

The stable public API for `jsonschema_validator 1.0.0` is the package-root API
exported through `jsonschema_validator.__all__`:

- `ValidatorFactory`
- `BackendNotAvailableError`
- `SchemaValidationError`
- `available_backends`

Internal backend modules under `jsonschema_validator.backends` are implementation
details and may evolve independently as long as the package-root API remains
backward compatible within the `1.x` line.

---

## Error Handling Example

```python
from jsonschema_validator import ValidatorFactory

schema = {
    "type": "object",
    "required": ["meta"],
    "properties": {
        "meta": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z_][a-z0-9_]*$"}
            },
        }
    },
}

data = {"meta": {"id": "InvalidName"}}

validator = ValidatorFactory.create(backend="jsonschema")
errors = validator.validate(schema, data)

assert errors[0].path == "meta.id"
assert errors[0].schema_path.endswith("pattern")
```

---

## Security Notes

- `auto` mode intentionally excludes `fastjsonschema`
- `fastjsonschema` is explicit opt-in because it relies on generated code and `exec`
- When safety and predictability matter more than raw speed, prefer `auto`, `jsonscreamer`, or `jsonschema`

---

## Testing and Coverage

The module has focused tests for:

- backend-specific validation behavior
- normalized error paths and schema paths
- optional dependency handling
- factory error paths and backend probing
- backend cache behavior

Run the module test suite locally from the package directory:

```bash
pytest tests/ --cov=jsonschema_validator
```

For a detailed coverage report:

```bash
pytest tests/ --cov=jsonschema_validator --cov-report=term-missing
```

Current coverage: 100% for `jsonschema_validator`.

---

## Development Notes

- The package targets JSON Schema Draft 7 behavior through the supported backends
- Backend availability depends on installed optional dependencies
- The facade is designed so callers do not need backend-specific exception types or result formats

---

## License

`jsonschema_validator` is released under the Apache License 2.0.

- Local package license: `LICENSE`
- Repository license: `LICENSE`