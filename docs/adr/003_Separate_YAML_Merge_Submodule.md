# ADR 003: Extract YAML Merge into a Separate Submodule

| **Date**       | 2026-04-01 |
|----------------|------------|
| **Status**     | Accepted   |
| **Author**     | @cherninkiy |
| **Deciders**   | Protocollab maintainers |

## Context

The `yaml_serializer` module currently contains an empty placeholder file `merge.py` with a TODO comment indicating that three‑way merge functionality should be implemented. The module is otherwise focused on secure loading, saving, and change‑tracking of YAML files (with `!include` support and comment preservation).  

Three‑way merge is a complex feature that involves:
- Recursive merging of YAML nodes (`CommentedMap`, `CommentedSeq`, scalars).
- Preserving comments and formatting.
- Handling `!include` references (merging nested file trees).
- Detecting file renames and updating `!include` paths.
- Providing a conflict resolution interface.

The project is still in early stages and can accommodate breaking changes. We must decide whether to implement merge **inside** `yaml_serializer` or **extract it into a separate submodule**.

## Decision

We will **extract the merge functionality into a new submodule called `yaml_merger`**, which will have a **linear dependency on `yaml_serializer`**.  

- `yaml_serializer` will remain a self‑contained library for safe YAML loading/saving, with no knowledge of merging.
- `yaml_merger` will import `yaml_serializer` and use its public API (node types, utilities, file tracking attributes) to implement three‑way merge.
- Both modules will live in the same monorepository under `packages/`.
- The empty `merge.py` inside `yaml_serializer` will be **deleted immediately** (as step 0), since it is unused and the placeholder is no longer needed.

### Rationale

- **Separation of concerns**: `yaml_serializer` stays focused on its core responsibility: safe loading, saving, and change tracking. Merge is an optional, advanced feature that can evolve independently.
- **Flexibility**: A separate submodule allows future reuse of merge logic with other YAML backends if needed, without pulling in the entire loader.
- **Stability**: Users who do not need merge are not forced to include its code or dependencies.
- **Clean architecture**: The dependency direction is natural (`yaml_merger` → `yaml_serializer`), avoiding circular dependencies.
- **Early stage advantage**: With no existing merge code, extracting it now avoids future breaking changes when we would have to split a larger merged implementation.

## Consequences

### Positive
- `yaml_serializer` becomes simpler and more maintainable.
- Merge logic can be developed, tested, and released independently.
- The monorepository structure encourages modularity and clear ownership.

### Negative
- Two packages instead of one: users who want merge must install an additional package.
- Slight overhead in maintaining two sets of tests, documentation, and versioning.
- Some internal functions of `yaml_serializer` must be made public to support `yaml_merger` (e.g., `canonical_repr`, `compute_hash`, `mark_includes`, `update_file_attr`). We must document these as “internal but stable for advanced use”.

### Mitigations
- Keep both packages in a single monorepository with a shared toolchain (Poetry workspace) to minimise coordination overhead.
- Provide a simple method in `yaml_serializer.Session` (e.g., `session.merge()`) that internally imports `yaml_merger` if available, offering a unified user experience without mandatory dependency.
- Add a stabilization phase for `yaml_serializer` before building `yaml_merger` (see Implementation Plan).

## Implementation Plan

### Phase 0: Stabilize `yaml_serializer` (before extraction)

**Goal:** Ensure `yaml_serializer` has a clean, stable public API that `yaml_merger` can rely on.

1. **Delete `merge.py`** – remove the empty placeholder file.
2. **Review and define public API**:
   - Identify all functions that `yaml_merger` will need (e.g., `canonical_repr`, `compute_hash`, `resolve_include_path`, `is_path_within_root`, `mark_node`, `mark_dirty`, `clear_dirty`, `update_file_attr`, `replace_included`, `mark_includes`).
   - Add these functions to `__all__` in their respective modules.
   - Mark internal functions with a leading underscore (`_`) to clarify they are not public.
3. **Add stability markers** (optional, using docstrings or custom decorators):
   - `@stable_api` for functions with backward compatibility guarantees.
   - `@internal_use_only` for functions that may change without notice.
4. **Update documentation**:
   - Add a “Public API Stability” section in `yaml_serializer/README.md` listing stable functions.
   - Ensure docstrings clearly describe behaviour and any preconditions.
5. **Expand test coverage** for the exposed stable functions:
   - Edge cases (empty inputs, invalid types).
   - Error handling.
   - Correctness of return values.
6. **Verify data integrity**:
   - Confirm that critical attributes (`_yaml_file`, `_yaml_parent`, `_yaml_include_path`) are correctly maintained after modifications.
7. **Refactor and clean up**:
   - Remove any dead code.
   - Unify style (PEP 8, type hints).
   - Ensure all exceptions are properly caught and documented.
8. **Release `yaml_serializer v1.0.0`** with a clearly documented stable API and semver guarantees.

### Phase 1: Infrastructure setup

1. Create `packages/yaml_merger/` with its own `pyproject.toml`, declaring a dependency on `yaml_serializer >= 1.0.0`.
2. Configure root `pyproject.toml` as a Poetry workspace.
3. Update CI to run tests for both packages.

### Phase 2: Implement `yaml_merger`

1. **Core merge logic** (`merger.py`):
   - Recursive merge of scalars, sequences, and mappings.
   - Comment preservation strategy (start with simple left/right preference).
2. **`!include` handling** (`include_handler.py`):
   - Recursively merge included files using the same algorithm.
   - Update `_yaml_file`, `_yaml_include_path`, and `_yaml_parent` attributes accordingly.
3. **Conflict resolution** (`conflict.py`):
   - Define `Conflict` data classes.
   - Provide built‑in resolvers (`take_left`, `take_right`, `keep_base`, `manual`).
   - Allow custom callback resolvers.
4. **Testing**:
   - Unit tests for each component.
   - Integration tests with real YAML files and `!include` trees.

### Phase 3: Integration and documentation

1. Add a convenience method `SerializerSession.merge()` that, if `yaml_merger` is installed, loads three versions and returns the merged result.
2. Update `yaml_serializer` documentation to mention the optional `yaml_merger` package.
3. Write comprehensive documentation for `yaml_merger` with examples and conflict resolution guides.

### Phase 4: Release

1. Release `yaml_merger v1.0.0`, compatible with `yaml_serializer v1.0.0`.
2. Optionally publish a meta‑package (e.g., `protocollab-yaml`) that includes both.

## Alternatives Considered

### Implement merge inside `yaml_serializer`
- **Pros**: Single package, no extra dependency.
- **Cons**: Bloat, tighter coupling, harder to evolve separately, and later extraction would be a breaking change.

### Create a completely independent merge library with its own YAML abstraction
- **Pros**: Could support multiple YAML backends.
- **Cons**: Overkill for the current needs, would duplicate a lot of logic already in `yaml_serializer` (comment handling, `!include` resolution). Not justified.

## References

- [YAML Serializer README](https://github.com/cherninkiy/protocollab/tree/dev/packages/yaml_serializer)
- [ruamel.yaml documentation](https://yaml.readthedocs.io/)
- [Three‑way merge algorithm (Wikipedia)](https://en.wikipedia.org/wiki/Merge_(version_control)#Three-way_merge)

---

This ADR is final and will serve as the blueprint for implementing the merge functionality.