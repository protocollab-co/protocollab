# ADR 004: YAML Transformation Library and ProtoCollab Architecture

## Status

Proposed (supersedes [ADR 003](003_Separate_YAML_Merge_Submodule.md))

## Date

2026-04-17

## Author

@cherninkiy

## Deciders

Protocollab maintainers

## Context

The `yaml_serializer` package provides secure loading, saving, and change‑tracking of YAML files with `!include` support and comment preservation. It currently contains no merge functionality (the placeholder `merge.py` has been removed).

The multi‑agent system (specifier, optimizer, tester, merger, reviewer, generator) that collaboratively works on a YAML specification repository requires a **broad set of YAML transformations** beyond simple merge:

- Three‑way merge with conflict resolution (including LLM‑assisted resolution)
- Filtering subsets of a specification (e.g., for testing)
- Variable substitution (`${VAR}`) in strings and keys
- Renaming keys while preserving comments
- Normalisation (sort keys, canonicalise types, remove duplicates)
- Applying JSON Patches (RFC 6902)
- Setting/deleting values by JSONPath
- Diffing two YAML trees
- Extracting subtrees, splitting one document into several
- Shallow and deep copying of YAML nodes while preserving `!include` tags and comments

All these operations must preserve comments, formatting, and `!include` metadata to remain compatible with `yaml_serializer` round‑trip saving. They must also integrate with `yaml_serializer`’s dirty‑tracking (`mark_dirty`, `_yaml_parent`).

The project is in early stages; breaking changes are acceptable. We need to decide on the architecture of YAML transformation capabilities and their relationship with the higher‑level `ProtoCollab` layer.

## Decision

We will create a separate package **`yaml_transformer`** that provides a complete set of YAML transformation utilities, including three‑way merge. This package will have a **linear dependency on `yaml_serializer`** and will be used by the `ProtoCollab` layer.

Additionally, we define `ProtoCollab` as a **higher‑level architectural layer** that provides a unified API for agents and users to interact with a YAML specification repository. `ProtoCollab` will use:

- `yaml_transformer` for all YAML‑specific operations.
- A **pluggable repository backend** (`RepositoryBackend` interface) for version control and file access (detailed in ADR 005).

Thus the dependency chain is:

```
ProtoCollab → yaml_transformer → yaml_serializer
```

### What `yaml_transformer` includes

#### Mutating transformations (operate on `CommentedMap`/`CommentedSeq`, call `mark_dirty`)

- `merge(docs, strategy)` – three‑way merge with conflict reporting.
- `filter(data, condition)` – keep only matching elements (dict exact match or JMESPath).
- `substitute(data, variables, syntax)` – replace variables in strings and keys.
- `rename(data, mapping)` – rename dictionary keys, preserve comments.
- `normalize(data, sort_keys, canonical_types, remove_duplicates)`.
- `patch(data, patches)` – apply JSON Patch (RFC 6902) operations.
- `set_value(data, path, value, create_parents)` – set by JSONPath.
- `delete(data, path)` – delete by JSONPath.

#### Non‑mutating utilities

- `diff(left, right)` – returns differences (based on `deepdiff`).
- `extract(data, path)` – get a subtree (returns a live reference; use `copy_node` for detachment).
- `split(data, by, path)` – split one document into several. Comments attached to split nodes can be kept in the original, moved to the new document, or copied to both. The `both` strategy duplicates comments; subsequent three‑way merge is capable of reconciling these duplicates.
- `flatten(data)` – create a deep copy without `!include` metadata (tags resolved and removed).
- `copy_node(node, mode: CopyMode = CopyMode.REFERENCE, new_root_dir: Path | None = None) -> CommentedMap | CommentedSeq`  
  Low‑level primitive that creates a copy of a YAML node according to the chosen `CopyMode`. Used internally by `TransformBuilder.copy()` and available for direct use.

#### Lazy `TransformBuilder`

- Accumulates operations without executing them.
- Applies them with:
  - `mutate()` – in‑place, marks dirty via `mark_dirty` propagation. **Not atomic**: if an operation fails midway, the document remains partially modified. For atomicity, apply changes to a copy first.
  - `copy(mode)` – creates a new document according to the chosen `CopyMode` after applying all accumulated operations.

### Copy Semantics with `!include`

Because `yaml_serializer` restricts `!include` resolution to a root directory, copying a YAML document requires careful handling of file‑system metadata (`_yaml_file`, `_yaml_include_path`). We define three copy modes available via `TransformBuilder.copy(mode)` and the low‑level `copy_node` function.

#### 1. `REFERENCE` (shallow copy)

- **Behaviour**: Creates a new root node but retains references to all child nodes (including those from `!include`). Metadata is unchanged.
- **Use case**: Temporary in‑memory structures within the same root directory.
- **Restriction**: Saving the copy to a different root directory will break `!include` paths. Use `DETACHED` or `FLATTENED` instead.
- **Dirty‑tracking**: Modifications through the copy mark the original root as dirty.

#### 2. `DETACHED` (deep copy preserving `!include` tags)

- **Behaviour**: Recursively creates new nodes, but `!include` tags are preserved (not resolved). Metadata is updated to reflect a new root directory (`new_root_dir`). Before copying, all `!include` paths are validated to lie within `new_root_dir`.
- **Metadata update**:
  - `_yaml_file` set to the new file path under `new_root_dir`.
  - `_yaml_include_path` recomputed as a relative path from the new parent.
- **Optional file copying**: If `copy_files=True`, all included files are physically copied to `new_root_dir` with relative structure preserved. Name conflicts are resolved via `yaml_transformer.merge`.
- **Use case**: Migrating a specification to a different repository while retaining modularity.

#### 3. `FLATTENED` (fully resolved, filesystem‑independent)

- **Behaviour**: Recursively replaces every `!include` node with its contents. The result is a self‑contained YAML document with no `!include` tags and no file‑system metadata.
- **Recursion control**: `max_include_depth` and cycle detection via load stack.
- **Comment preservation**: Comments from included files are preserved in the flattened tree.
- **Use case**: Passing a complete specification to an agent that lacks filesystem access; creating a distributable snapshot.

#### Validity Guarantees

| Mode       | Condition                                                                 | Failure action                               |
|------------|----------------------------------------------------------------------------|----------------------------------------------|
| `REFERENCE`| Copy is not saved to a different root directory.                           | `ValueError`                                 |
| `DETACHED` | All include paths are resolvable relative to `new_root_dir`.               | `FileNotFoundError` with the offending path  |
| `FLATTENED`| All included files are readable at copy time.                              | `IncludeError`                               |

### Three‑Way Merge (TWM)

Three‑way merge is the core conflict resolution mechanism used both directly by agents and indirectly for file‑name conflicts during `DETACHED` copy.

```python
def merge(
    base: CommentedMap | CommentedSeq,
    left: CommentedMap | CommentedSeq,
    right: CommentedMap | CommentedSeq,
    strategy: MergeStrategy = MergeStrategy.DETERMINISTIC,
) -> MergeResult:
    ...
```

- **Change detection**: Uses a hash function that **includes comments** (extended `compute_hash_with_comments` built on top of `yaml_serializer` primitives). This ensures that modifications to comments are treated as changes and can trigger conflicts.
- **`!include` handling**: Nodes with `!include` are compared by metadata (path and file hash). Content of the included file is not merged implicitly; users should flatten documents first if content merging is desired.
- **Conflict resolution strategies** (MVP):
  - `DETERMINISTIC`: Resolve using a deterministic rule, but mark the result as conflicted.
  - `FAIL_FAST`: Raise `MergeConflictError` on first conflict.
  - *Note: `MARK_CONFLICTS` (Git‑style markers) is excluded from the initial version because it produces invalid YAML and complicates round‑trip loading.*
- **Result**: `MergeResult` contains the merged document, a list of `Conflict` objects, and a flag `had_conflicts`.

TWM also serves as the foundation for reconciling duplicated comments produced by `split` with mode `both` and for resolving file name collisions when `copy_files=True` in `DETACHED` mode.

### Why not a separate `yaml_merger` only?

- A dedicated `yaml_merger` would be too narrow; agents also need filtering, substitution, patching, etc.
- Splitting into `yaml_merger` + `yaml_transformer` would force agents to depend on two packages and duplicate low‑level utilities (e.g., `copy_node`).
- A single `yaml_transformer` is more cohesive and easier to maintain.

### Why not keep everything in `yaml_serializer`?

- `yaml_serializer` stays focused on safe loading, saving, and change tracking.
- Transformation logic is complex and can evolve independently.
- Users who only need loading/saving are not forced to pull in transformation code.

## Consequences

### Positive

- Clear separation of concerns: `yaml_serializer` (core I/O), `yaml_transformer` (transformations), `ProtoCollab` (orchestration + backends).
- Multi‑agent system gets a single, powerful library for all YAML manipulations.
- Lazy evaluation (`TransformBuilder`) improves performance and allows choosing mutation/copy/deepcopy at the end.
- Pluggable repository backends (ADR 005) make `ProtoCollab` adaptable to Git, multi‑agent storage, or simple files.

### Negative

- Three packages instead of one: users who need transformations must install `yaml_transformer`; those who need full collaboration must also install `ProtoCollab`.
- Slight overhead in maintaining three sets of tests and documentation.
- `yaml_serializer` must expose additional stable API functions: `copy_node`, `propagate_dirty_up`, plus existing utilities (`canonical_repr`, `compute_hash`, `mark_dirty`, etc.).

### Mitigations

- Keep all packages in a single monorepository with a shared toolchain (Poetry workspace).
- Provide a meta‑package `protocollab` that bundles `yaml_serializer`, `yaml_transformer`, and `ProtoCollab`.
- `yaml_serializer` is already stable (v1.0.1) and the required APIs are either present or can be added in a backward‑compatible manner.

## Implementation Plan

### Phase 1: Create `yaml_transformer` package
1. Create `src/yaml_transformer/` with `pyproject.toml`, depend on `yaml_serializer >= 1.0.1`.
2. Implement core transformations (`transform.py`, `merge.py`, `diff.py`, `builder.py`).
3. Implement `TransformBuilder` with lazy execution and copy modes.
4. Write extensive tests (unit + integration with real YAML files and `!include`).
5. Release `yaml_transformer` v1.0.0.

### Phase 2: Implement `ProtoCollab` (ADR 005)
1. Define `RepositoryBackend` abstract class in new `protocollab.yaml_repository` subpackage.
2. Implement `ManualBackend`, `MultiAgentBackend`, and Git backends.
3. Build high‑level `ProtoCollab` API using `yaml_transformer`.
4. Provide factory `create_repository_backend()` in `protocollab` package.

## Alternatives Considered

- **Keep merge inside `yaml_serializer`** – rejected because it would bloat the core and not cover other needed transformations.
- **Create separate `yaml_merger` and `yaml_transformer`** – rejected due to duplication and fragmentation.
- **Use `gitpython` directly inside `ProtoCollab` without a backend abstraction** – rejected because it would hard‑code Git and prevent multi‑agent storage (addressed in ADR 005).

## References

- [ADR 003: Extract YAML Merge into a Separate Submodule](003_Separate_YAML_Merge_Submodule.md) (superseded)
- [ADR 005: ProtoCollab Architecture and Repository Abstraction](005_ProtoCollab_Architecture.md)
- [YAML Serializer README](https://github.com/protocollab-co/protocollab/tree/dev/src/yaml_serializer)
- [ruamel.yaml documentation](https://yaml.readthedocs.io/)
- [JSON Patch RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902)

---

*This ADR supersedes [ADR 003](003_Separate_YAML_Merge_Submodule.md) and establishes `yaml_transformer` as the foundation for YAML transformations in the Protocollab ecosystem.*