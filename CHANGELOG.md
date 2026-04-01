# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-04-01

### Added

- **`src/jsonschema_validator/`**: Introduced a standalone pluggable JSON Schema
  validation facade as described by ADR 002. The package now provides a backend-
  agnostic public API, `ValidatorFactory`, `SchemaValidationError`, backend
  discovery helpers, and independent tests/docs so validation logic can evolve
  outside `protocollab.*` internals while remaining reusable from them.

- **`src/yaml_serializer/tests/test_public_api.py`**: Added explicit stability
  and metadata-integrity coverage for the advanced-use public API exposed from
  `yaml_serializer.utils`, including export boundaries and invariants for
  `_yaml_file`, `_yaml_parent`, and `_yaml_include_path`.

- **`src/jsonschema_validator/backends/`**: Added three backend adapters with
  explicit policy boundaries:
  - `jsonschema` as the compatibility-oriented safe fallback
  - `jsonscreamer` as the preferred safe backend in `auto` mode when installed
  - `fastjsonschema` as the performance-oriented backend requiring explicit opt-in

- **`pyproject.toml`**: Added optional Poetry extras for JSON Schema backend
  selection: `validator-jsonscreamer` and `validator-fastjsonschema`.

- **`docs/adr/002_Pluggable_JSON_Schema_Validator.md`** and
  **`docs/adr/002_Pluggable_JSON_Schema_Validator_RU.md`**: ADR 002 is now
  reflected by the implemented package structure, backend policy, and packaging
  approach used in the repository.

### Changed

- **`src/protocollab/validator/`**: Replaced direct `jsonschema` coupling with the
  new `jsonschema_validator` facade so backend selection, error normalization, and
  backend-specific tradeoffs are encapsulated behind a reusable validation layer.

- **`src/protocollab` CLI and validation flow**: Validation now preserves the
  existing user-facing dot-notation error paths such as `meta.id` and
  `seq[0].type` while delegating backend-specific error mapping to the facade.

- **`.github/workflows/ci.yml`**, **`pyproject.toml`**, **`setup.py`**,
  **`README.md`**, **`README_ru.md`**, demo READMEs, and module READMEs:
  repository packaging and documentation were aligned around Poetry, optional
  validator extras, the standalone `jsonschema_validator` package, and the
  current Apache 2.0 licensing layout.

- **`README.md`** and **`README_ru.md`**: Root documentation now reflects the
  current architecture (`yaml_serializer`, `jsonschema_validator`, and
  `protocollab`), includes language-switch links between English and Russian,
  points to the external `protocollab-specs` repository, and describes coverage
  as 100% for the critical modules rather than a single submodule.

- **`yaml_serializer/serializer.py`**: Replaced the module-level `SerializerContext`
  singleton and free functions (`load_yaml_root`, `save_yaml_root`, `rename_yaml_file`,
  `propagate_dirty`) with an explicit `SerializerSession` class. Each session owns its
  own YAML instance, loading stack, dirty tracking, and file-root registry — eliminating
  shared mutable state and making concurrent use of multiple sessions safe
  ([`d8394b9`]).

- **`yaml_serializer/__init__.py`**: Public API now exports `SerializerSession` instead
  of the removed free functions ([`ff0aaf1`]).

- **`yaml_serializer/utils.py`**, **`yaml_serializer/safe_constructor.py`**,
  **`yaml_serializer/merge.py`**: All remaining Russian docstrings and comments
  translated to English ([`141eef5`]).

- **`src/yaml_serializer/utils.py`**, **`src/yaml_serializer/README.md`**, and
  **`src/yaml_serializer/README_ru.md`**: Phase 0 of ADR 003 is now implemented.
  The placeholder `merge.py` was removed, a stable advanced-use API was defined
  for `yaml_serializer.utils`, internal helpers were renamed with a leading `_`,
  and both English and Russian package READMEs now document the public API
  stability boundary for future `yaml_merger` integration.

- **`src/yaml_serializer/pyproject.toml`** and
  **`src/jsonschema_validator/pyproject.toml`**: Added standalone package
  manifests with independent versioning so `yaml_serializer` and
  `jsonschema_validator` can be built and released separately as `1.0.0`
  packages while remaining part of the monorepo.

- **`protocollab/loader/__init__.py`**: Added `get_global_loader()` to expose the
  module-level `ProtocolLoader` for inspection and cache management, and
  `configure_global(max_cache_size)` to reconfigure the shared cache at runtime.
  Module docstring expanded with hybrid-design guide, usage examples, and thread-safety
  warning ([`ffeae03`]).

- **`src/protocollab/loader/base_loader.py`** and
  **`src/protocollab/validator/schema_validator.py`**: Internal integration now
  prefers the package-root public APIs of `yaml_serializer` and
  `jsonschema_validator`, reducing coupling to internal implementation modules
  before separate package releases.

- **`protocollab/loader/cache/memory_cache.py`**: `MemoryCache` now supports a
  `max_size` bound with LRU eviction ([`ffeae03`]).

- **`yaml_serializer/tests/test_session.py`**: New test module covering
  `SerializerSession` lifecycle, `clear()`/`reset()`, config override,
  `propagate_dirty()` with multiple parents, rename across directories, and
  thread-safety scenarios ([`6035012`]).

- **`docs/adr/001_Replace_Loader_Global_State.md`**: ADR 001 — documents the decision
  to replace global state with explicit sessions in `yaml_serializer` and the
  hybrid-design pattern for `protocollab.loader` ([`52b0e22`]).

- **`src/jsonschema_validator/tests/`**: Added backend-specific and integration
  coverage for factory selection, cache behaviour, normalized error paths,
  schema-path formatting, optional dependency handling, and backend probing.

### Security

- **`src/jsonschema_validator` backend policy**: `auto` mode remains safe for
  untrusted-schema workflows by excluding `fastjsonschema` from automatic
  selection. `fastjsonschema` remains available only through explicit opt-in
  because it relies on generated code and `exec`.

- **`yaml_serializer/utils.py`**: `is_path_within_root()` no longer accepts `None` as
  `root_dir`. Previously, `None` silently bypassed path validation and allowed any path
  to pass — a potential path-traversal vulnerability. The parameter is now typed `str`
  and raises `TypeError` when `None` is passed ([`e80b398`]).

- **`yaml_serializer/safe_constructor.py`**: `max_depth` in `RestrictedSafeConstructor`
  and `create_safe_yaml_instance()` must now be a **positive integer**. Passing `None`
  (the old default) would have disabled the nesting-depth guard entirely, leaving the
  parser open to "billion-laughs"-style deeply-nested payloads. A `ValueError` is now
  raised for `None`, zero, or any negative value ([`f4b1f89`]).

### Fixed

- **`src/jsonschema_validator/backends/fastjsonschema_backend.py`**: Validation now
  collects a complete error set through the compatibility fallback instead of
  surfacing only the first backend-native error. Validator caching and fallback
  reuse paths are also covered by tests.

- **`src/jsonschema_validator/backends/jsonscreamer_backend.py`** and
  **`src/protocollab/tests/test_validator.py`**: Schema-path normalization and
  assertions were aligned so user-visible errors remain backend-agnostic while
  preserving compatible dot-notation paths.

- **`protocollab/tests/`**: `FieldDef` instances in tests are now constructed via
  `FieldDef.model_validate({"id": …, "type": …, "if": …})` instead of direct keyword
  arguments. Using keyword arguments bypassed Pydantic's alias mapping (`if` → `if_expr`,
  `repeat` → `repeat_expr`), causing tests to silently exercise incorrect code paths
  ([`2b84714`]).

- **`protocollab/loader/base_loader.py`**: Added `assert isinstance(result, dict)` after
  `canonical_repr()` to surface unexpected return types early ([`86433a2`]).

- **`protocollab/tests/test_generators.py`**: Added `assert spec is not None` and
  `assert spec.loader is not None` guards in `_import_module()` to produce clear error
  messages instead of confusing `AttributeError`s ([`86433a2`]).

- **`yaml_serializer/serializer.py`**: Added `assert _CTX._yaml_instance is not None`
  after YAML instance construction ([`86433a2`]).

- **`.gitignore`**: Added `pyrightconfig.json` to ignore list.
