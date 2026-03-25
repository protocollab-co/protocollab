# ADR 002: Pluggable JSON Schema Validation Module

## Status
Proposed

## Context
`protocollab` relies on JSON Schema validation to verify protocol specifications (both permissive `base` and strict `protocol` schemas). Currently, validation is implemented using the `jsonschema` library directly inside the `protocollab.validator` module.

Several observations have been made:
- There are multiple Python libraries for JSON Schema validation (`jsonschema`, `fastjsonschema`, `jsonscreamer`), each with different trade-offs in speed, security, and feature coverage.
- Different usage scenarios demand different priorities:
  - **CI/CD pipelines** benefit from high‑speed validation (e.g., `fastjsonschema`).
  - **Untrusted or user‑provided schemas** require a safe backend that avoids code execution (e.g., `jsonschema` or `jsonscreamer`).
  - **Complex schemas** may need full draft support (currently `jsonschema` provides the best coverage).
- The validation logic could be useful outside `protocollab` (e.g., in other Python projects that handle JSON/YAML configuration).
- Future plans may include supporting OpenAPI, AsyncAPI, or other schema‑based formats, which could reuse a generic validation facade.

## Decision
We will create a **standalone, reusable Python module** called `jsonschema_validator` (or a similar name) that provides a unified interface for JSON Schema validation with pluggable backends. The module will:

1. **Define an abstract base class** `BaseValidator` and a `ValidationResult` dataclass for unified output.
2. **Implement adapters** for at least three backends:
   - `jsonschema` – maximum compatibility, default fallback.
   - `fastjsonschema` – high performance (optional, uses `exec`).
   - `jsonscreamer` – high performance, no `exec` (optional).
   - (future) Pydantic integration for model‑based validation.
3. **Provide a factory** (`ValidatorFactory.create(backend="auto", cache=True, **options)`) that selects an available backend using the proposed default priority order `jsonscreamer` -> `jsonschema` -> `fastjsonschema`. Explicit backend selection remains available for callers that want to optimize primarily for speed or draft coverage.
4. **Include caching** of compiled validators (keyed by schema hash + backend version) to avoid repeated compilation overhead.
5. **Normalize error messages** across backends to a common format (including JSON Pointer‑style paths where possible).
6. **Integrate into `protocollab`** by replacing direct `jsonschema` calls with the new module and exposing a CLI option `--validator-backend` for the `validate` command.
7. **Publish the module as part of the `protocollab` monorepo** with its own tests, documentation, and optional dependencies, but keep it completely independent (no imports from `protocollab.*`).

The module is intended to be installable via proposed extras such as:
```bash
pip install protocollab[validator-jsonschema]   # minimal
pip install protocollab[validator-all]          # all backends
```

## Consequences
### Positive
- **Flexibility**: Users can select the backend that best fits their performance, security, and compatibility needs.
- **Security**: For untrusted schemas, one can enforce backends that do not rely on `exec`.
- **Performance**: CI and batch validation can leverage faster backends.
- **Reusability**: The validation module can be used independently of `protocollab` in any Python project.
- **Testability**: Validation logic can be tested against multiple backends, ensuring consistent behavior.

### Negative
- **Increased complexity**: We must maintain multiple backend adapters and a factory with caching.
- **Dependency management**: Backends are optional, but we need to document installation and availability.
- **Potential behavioral differences**: Different backends may implement JSON Schema variations; we must document supported drafts for each.
- **Slightly larger codebase**: Additional files and tests for the new module.

## Alternatives Considered
1. **Keep current `jsonschema`‑only implementation**  
   – Simple, but lacks flexibility and performance gains. Does not address future needs for other validation formats.

2. **Replace `jsonschema` with a single alternative (e.g., `fastjsonschema`)**  
   – Gains speed but may sacrifice compatibility or introduce security risks for untrusted schemas.

3. **Provide a standalone module with only `jsonschema`**  
   – Achieves reusability but does not solve the need for different backends.

4. **Use a configuration flag inside `protocollab` to switch between hard‑coded libraries**  
   – Still tightly coupled; would not be reusable and would duplicate code.

The chosen approach offers the best long‑term maintainability and flexibility.

## References
- [JSON Schema Specification](https://json-schema.org/)
- [`jsonschema`](https://github.com/python-jsonschema/jsonschema)
- [`fastjsonschema`](https://github.com/horejsek/python-fastjsonschema)
- [`jsonscreamer`](https://github.com/openedx/jsonscreamer)
- [Pydantic](https://docs.pydantic.dev/) (future integration)
- `protocollab` tracking issue: TBD (to be linked once created)

## Approval
*Pending review*