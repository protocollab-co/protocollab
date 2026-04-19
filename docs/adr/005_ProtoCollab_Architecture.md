# ADR 005: ProtoCollab Architecture and Repository Abstraction

## Status

Proposed

## Date

2026-04-17

## Author

@cherninkiy

## Deciders

Protocollab maintainers

## Context

[ADR 004](004_YAML_Transformation_Library.md) established `yaml_transformer` as the foundational library for YAML transformations (merge, filter, patch, copy with `!include` awareness, etc.). Building on this, the multi‑agent system (specifier, optimizer, tester, merger, reviewer, generator) requires a **higher‑level orchestration layer** that provides a unified API for agents and users to interact with a YAML specification repository.

This layer, named **ProtoCollab**, must:

- Abstract over different storage backends (local Git, in‑memory, simple files) so that agents can work with specifications regardless of where they reside.
- Integrate `yaml_transformer` for all YAML‑specific operations (merge, diff, patching).
- Provide version control operations (commit, checkout, history) through a consistent interface.
- Support the collaborative workflow where multiple agents propose and merge changes.

The project is in early stages; breaking changes are acceptable. We need to define the architecture of ProtoCollab and the repository abstraction that underpins it.

## Decision

We will create a new subpackage **`protocollab.yaml_repository`** that defines an abstract interface `RepositoryBackend` and includes lightweight reference implementations. The ProtoCollab orchestration layer will be part of the main `protocollab` package and will depend on `yaml_transformer` and `yaml_repository`.

### Package Structure

All new modules will reside under `src/protocollab/` alongside existing CLI, loader, and generator modules:

```
src/protocollab/
├── __init__.py                     # exports ProtoCollab, create_repository_backend
├── cli/                            # existing CLI
├── loader/                         # existing loader
├── validator/                      # existing validator
├── generators/                     # existing generators
├── agent/                          # future agent implementations
└── yaml_repository/                # new subpackage
    ├── __init__.py                 # exports RepositoryBackend, ManualBackend, MultiAgentBackend
    ├── base.py                     # abstract RepositoryBackend
    ├── manual.py                   # ManualBackend
    ├── multi_agent.py              # MultiAgentBackend (in‑memory, for testing)
    ├── gitpy/                      # GitPyRepository (gitpython backend)
    │   └── __init__.py
    └── gitcli/                     # GitCliRepository (subprocess backend)
        └── __init__.py
```

**Note:** Pro backends (`github`, `sqlite`, `rag`) are **not** included in the public open‑source repository. They will be developed and distributed separately under a commercial license.

### Dependency Chain

```
protocollab
├── yaml_transformer → yaml_serializer
└── yaml_repository (core)
    ├── gitpy (optional, requires gitpython)
    └── gitcli (no extra deps)
```

### RepositoryBackend Interface

The abstract class defines the contract for versioned storage of YAML specifications.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from datetime import datetime

@dataclass
class Ref:
    name: str           # e.g., "main", "feature/xyz"
    commit_hash: str    # full SHA

@dataclass
class FileInfo:
    path: Path
    ref: Ref
    last_modified: datetime
    size: int

@dataclass
class Change:
    path: Path
    status: str         # "added", "modified", "deleted", "renamed"
    old_path: Optional[Path] = None

@dataclass
class CommitInfo:
    hash: str
    author: str
    message: str
    timestamp: datetime
    parent_hashes: List[str]
    changes: List[Change]

class RepositoryBackend(ABC):
    """Abstract interface for a versioned YAML specification store."""

    # ---- Basic file operations ----
    @abstractmethod
    def read_file(self, path: Path, ref: Optional[str] = None) -> str:
        """Read file content at given ref (HEAD if None)."""
        pass

    @abstractmethod
    def stage_file(self, path: Path, content: str) -> None:
        """Stage a file for the next commit. Does not create a commit yet."""
        pass

    @abstractmethod
    def unstage_file(self, path: Path) -> None:
        """Remove a file from the staging area."""
        pass

    @abstractmethod
    def commit(self, message: str, author: str) -> CommitInfo:
        """Create a commit from all currently staged changes."""
        pass

    @abstractmethod
    def delete_file(self, path: Path, message: str, author: str) -> CommitInfo:
        """Delete a file and commit the deletion (atomic convenience)."""
        pass

    @abstractmethod
    def exists(self, path: Path, ref: Optional[str] = None) -> bool:
        """Check if a file exists at the given ref."""
        pass

    @abstractmethod
    def list_files(self, directory: Optional[Path] = None, ref: Optional[str] = None) -> List[Path]:
        """Recursively list all YAML files under directory (root if None)."""
        pass

    # ---- Version control operations ----
    @abstractmethod
    def get_current_ref(self) -> Ref:
        """Return the current HEAD reference."""
        pass

    @abstractmethod
    def checkout(self, ref_name: str, create: bool = False) -> Ref:
        """
        Switch to a branch/tag/commit.
        If `create` is True, create a new branch named `ref_name` from current HEAD.
        """
        pass

    @abstractmethod
    def get_commit_history(
        self, ref: Optional[str] = None, path: Optional[Path] = None, max_count: int = 100
    ) -> List[CommitInfo]:
        """Retrieve commit history, optionally filtered by path."""
        pass

    @abstractmethod
    def diff(self, ref1: str, ref2: str, path: Optional[Path] = None) -> str:
        """Unified diff between two refs."""
        pass

    @abstractmethod
    def merge_base(self, ref1: str, ref2: str) -> Ref:
        """Find the best common ancestor of two refs."""
        pass

    @abstractmethod
    def get_blob(self, ref: str, path: Path) -> str:
        """Get file content exactly as stored at a commit (even if ref is a branch)."""
        pass

    @abstractmethod
    def get_root_directory(self) -> Path:
        """Absolute path to the repository root on the local filesystem."""
        pass

    @abstractmethod
    def resolve_ref(self, ref_name: str) -> Ref:
        """Convert a string name (branch, tag, SHA) to a Ref object."""
        pass
```

**Staging API**: The separation of `stage_file` / `commit` allows multiple files to be written atomically as a single commit, which is essential for agent workflows.

### Concrete Backends

| Backend | Location | Purpose | Dependencies | Notes |
|---------|----------|---------|--------------|-------|
| `ManualBackend` | `yaml_repository.manual` | Simple file system **without** versioning. Each `stage_file` + `commit` simply overwrites the file. Methods like `checkout`, `merge_base`, `diff` raise `NotImplementedError`. | None | Public, for simple local usage or testing. |
| `MultiAgentBackend` | `yaml_repository.multi_agent` | In‑memory store that fully implements versioning. Useful for testing multi‑agent collaboration without touching disk. | None | Public, for unit and integration tests. |
| `GitPyRepository` | `yaml_repository.gitpy` | Local Git repository using `gitpython` library. | `gitpython` | Public (extra `gitpy`). |
| `GitCliRepository` | `yaml_repository.gitcli` | Local Git repository using `subprocess` calls to `git`. | System Git | Public (extra `gitcli`). |

**Pro Backends**: `GitHubRepository`, `SqliteRepository`, and `RagRepository` are considered Pro features. Their source code will **not** be included in the public repository. The open‑source `protocollab` package may raise a clear error if a user attempts to instantiate them, directing them to obtain a Pro license.

### ProtoCollab High‑Level API

The `protocollab` package will expose a `ProtoCollab` class that orchestrates agent workflows:

```python
from protocollab.yaml_transformer import MergeStrategy, MergeResult

class ProtoCollab:
    def __init__(self, backend: RepositoryBackend):
        self.backend = backend

    def merge_refs(self, ref1: str, ref2: str, strategy: MergeStrategy) -> MergeResult:
        """Three‑way merge of two references using yaml_transformer."""
        base_ref = self.backend.merge_base(ref1, ref2)
        base_doc = self._load_spec(base_ref.commit_hash)
        left_doc = self._load_spec(ref1)
        right_doc = self._load_spec(ref2)
        return merge(base_doc, left_doc, right_doc, strategy)

    def apply_patch(self, ref: str, patches: List[Dict], message: str, author: str) -> CommitInfo:
        """Apply a JSON Patch to a spec and commit."""
        ...

    def checkout_branch(self, branch_name: str, create: bool = True) -> Ref:
        ...

    # … other convenience methods
```

Agents (specifier, optimizer, etc.) will use this API instead of directly manipulating files.

### Integration with `yaml_transformer`

ProtoCollab relies on `yaml_transformer` for:

- Three‑way merge (`merge`)
- Diffing (`diff`)
- Applying JSON Patches (`patch`)
- Copying documents between backends (e.g., flattening for agent consumption)

The `MultiAgentBackend` may also use `yaml_transformer` internally to simulate merge conflicts for testing.

### Factory Function

A factory will be provided in `protocollab` to instantiate the appropriate backend:

```python
def create_repository_backend(backend_type: str, **kwargs) -> RepositoryBackend:
    """
    Create a repository backend.

    backend_type may be:
        "manual"  → ManualBackend(root_path)
        "multi_agent" → MultiAgentBackend()
        "gitpy"   → GitPyRepository(repo_path)
        "gitcli"  → GitCliRepository(repo_path)

    Pro backends ('github', 'sqlite', 'rag') are not available in Community Edition.
    """
```

## Consequences

### Positive

- **Separation of concerns**: Storage logic is decoupled from YAML transformations and agent orchestration.
- **Pluggability**: New backends (e.g., S3, etcd) can be added without modifying core ProtoCollab.
- **Testability**: `MultiAgentBackend` enables fast, isolated tests of agent collaboration.
- **Clear open‑source boundaries**: Pro features are kept out of the public repository, reducing legal and maintenance complexity.

### Negative

- `ManualBackend` violates the full `RepositoryBackend` contract (throws `NotImplementedError`). This is a conscious trade‑off for simplicity; users who need full versioning should use a Git backend.
- Some backends (especially `GitCliRepository`) require careful handling of subprocess output and error conditions.
- The staging API introduces more complexity than a simple `write_file`, but it is necessary for atomic multi‑file commits.

### Mitigations

- Keep the core `RepositoryBackend` interface minimal and stable.
- Document clearly which methods are not supported by `ManualBackend`.
- Use `extras` in `pyproject.toml` to make optional dependencies explicit.

## Implementation Plan

### Phase 1: Core `yaml_repository` Subpackage
1. Create `src/protocollab/yaml_repository/` with `base.py`, `manual.py`, and `multi_agent.py`.
2. Write comprehensive unit tests using `MultiAgentBackend`.
3. Ensure compatibility with `yaml_serializer`'s `root_dir` validation.
4. Release as part of `protocollab` core.

### Phase 2: Git Backends
1. Implement `GitPyRepository` in `yaml_repository/gitpy/`.
2. Implement `GitCliRepository` in `yaml_repository/gitcli/`.
3. Add `gitpython` as an optional extra.
4. Test against real Git repositories.

### Phase 3: ProtoCollab Orchestration Layer
1. Develop `ProtoCollab` class in `protocollab/collab.py`.
2. Integrate with `yaml_transformer`.
3. Add CLI commands for agent‑driven workflows (e.g., `pc agent run`).

### Phase 4: Pro Backends (Separate Timeline)
1. Develop `GitHubRepository`, `SqliteRepository`, and `RagRepository` in a private repository.
2. Distribute under a commercial license.

## Alternatives Considered

- **Embedding repository logic directly in `ProtoCollab`** – rejected because it would hard‑code assumptions about storage and make testing difficult.
- **Single `write_file` that always creates a commit** – rejected because multi‑file changes are common in agent workflows and should be atomic.
- **Using `pygit2` instead of `gitpython`** – `pygit2` is a lower‑level binding; `gitpython` provides a more Pythonic API and is sufficient for our needs.
- **Including Pro backends in the open‑source repository with license checks** – rejected due to maintenance overhead and legal clarity; a clean separation is preferred.

## References

- [ADR 004: YAML Transformation Library and ProtoCollab Architecture](004_YAML_Transformation_Library.md)
- [GitPython Documentation](https://gitpython.readthedocs.io/)
- [GitHub REST API Documentation](https://docs.github.com/en/rest)
