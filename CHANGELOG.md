# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-03-25

### Changed

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

### Added

- **`protocollab/loader/__init__.py`**: Added `get_global_loader()` to expose the
  module-level `ProtocolLoader` for inspection and cache management, and
  `configure_global(max_cache_size)` to reconfigure the shared cache at runtime.
  Module docstring expanded with hybrid-design guide, usage examples, and thread-safety
  warning ([`ffeae03`]).

- **`protocollab/loader/cache/memory_cache.py`**: `MemoryCache` now supports a
  `max_size` bound with LRU eviction and per-instance cache statistics (`hits`,
  `misses`, `evictions`) ([`ffeae03`]).

- **`yaml_serializer/tests/test_session.py`**: New test module covering
  `SerializerSession` lifecycle, `clear()`/`reset()`, config override,
  `propagate_dirty()` with multiple parents, rename across directories, and
  thread-safety scenarios ([`6035012`]).

- **`docs/adr/001_Replace_Loader_Global_State.md`**: ADR 001 — documents the decision
  to replace global state with explicit sessions in `yaml_serializer` and the
  hybrid-design pattern for `protocollab.loader` ([`52b0e22`]).

### Security

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

- **`protocollab/tests/`**: `FieldDef` instances in tests are now constructed via
  `FieldDef.model_validate({"id": …, "type": …, "if": …})` instead of direct keyword
  arguments. Using keyword arguments bypassed Pydantic's alias mapping (`if` → `if_expr`,
  `repeat` → `repeat_expr`), causing tests to silently exercise incorrect code paths
  ([`2b84714`]).

### Added

- **`protocollab/loader/base_loader.py`**: Added `assert isinstance(result, dict)` after
  `canonical_repr()` to surface unexpected return types early ([`86433a2`]).

- **`protocollab/tests/test_generators.py`**: Added `assert spec is not None` and
  `assert spec.loader is not None` guards in `_import_module()` to produce clear error
  messages instead of confusing `AttributeError`s ([`86433a2`]).

- **`yaml_serializer/serializer.py`**: Added `assert _CTX._yaml_instance is not None`
  after YAML instance construction ([`86433a2`]).

- **`.gitignore`**: Added `pyrightconfig.json` to ignore list.
