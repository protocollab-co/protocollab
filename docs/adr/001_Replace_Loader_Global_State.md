# ADR 001: Replace Global State with Explicit Sessions and Enhance Loader Hybrid Design

## Status
Accepted

## Context
The `yaml_serializer` module currently uses a global `_CTX` context to hold all loaded files, configuration, and parsing state. This design leads to:

- **Lack of thread-safety** – concurrent operations corrupt the context.
- **No isolation** – different parts of an application cannot load independent YAML trees without interference.
- **Unbounded memory growth** – all loaded files remain in memory forever.
- **Testing difficulties** – tests must reset the global state manually.
- **Inflexibility** – cannot use different security limits for different loads.

The `protocollab.loader` module already follows a hybrid approach: a global default loader with `MemoryCache` for convenience, plus the ability to create isolated instances. However, it has its own shortcomings:

- The global loader is not publicly accessible, so cache clearing or inspection is impossible.
- `MemoryCache` lacks size limits – it can grow indefinitely.
- Thread-safety is not documented, and the default loader is not safe for concurrent use.
- No simple way to reconfigure the global loader (e.g., to increase cache size or change security limits) without re‑implementing.

We need to address these issues to make both libraries production‑ready, especially for long‑running services and multi‑threaded environments.

## Decision

### 1. yaml_serializer: Explicit Session Pattern
We will replace the global `_CTX` with an explicit `SerializerSession` class that encapsulates all state and operations.

- **`SerializerSession`** will have methods `load`, `save`, `rename`, `propagate_dirty`, and `clear`. Its constructor accepts a configuration dict.
- The old top‑level functions (`load_yaml_root`, `save_yaml_root`, etc.) are **removed** as a breaking change. Since the library has not yet reached a stable release (v1.0), a clean break is preferred over maintaining deprecated wrappers.
- All internal helpers (e.g., `include_constructor`, `include_representer`) will be refactored to accept a session reference (stored on the YAML instance) rather than relying on `_CTX`.
- This design ensures:
  - **Isolation**: different sessions do not interfere.
  - **Thread‑safety**: sessions are not shared by default; each thread can create its own.
  - **Resource control**: sessions can be discarded, releasing memory.
  - **Flexibility**: different security limits per session.

### 2. protocollab.loader: Enhanced Hybrid Design
We will keep the hybrid model but address the weaknesses:

- **Expose global loader**: add `get_global_loader()` to return the default `ProtocolLoader` instance.
- **Cache size limits**: extend `MemoryCache` to accept `max_size` (number of entries) and implement LRU eviction using `OrderedDict`. The global loader’s cache can be configured via a new `configure_global(max_cache_size, config)` function.
- **Thread‑safety documentation**: explicitly warn that the global loader is not thread‑safe; recommend using separate `ProtocolLoader` instances for concurrent workloads.
- **Configurable global loader**: provide `configure_global()` to re‑initialize the global loader with new settings without breaking existing code that expects `_default_loader`.

These improvements maintain the convenience of a one‑liner for simple scripts while giving advanced users the control they need.

## Consequences

### Positive
- **Thread‑safety**: both libraries can be safely used in multi‑threaded applications by creating per‑thread sessions/loaders.
- **Memory control**: caches can be bounded, preventing unbounded growth.
- **Isolation**: multiple independent workloads can coexist without interference.
- **Testability**: unit tests can create fresh sessions/loaders without cross‑test contamination.
- **Flexibility**: different parts of an application can use different security settings or caching strategies.
- **Backward compatibility (loader)**: existing code using the default `protocollab.loader` API continues to work, while advanced users gain explicit access to the shared loader configuration.

### Negative
- **Migration effort (serializer)**: users of `yaml_serializer` must update code that called the removed top-level functions to use `SerializerSession` before upgrading.
- **Slightly more code** in some use cases (explicit session creation), but the convenience of the global loader remains for simple scenarios.
- **Potential confusion** about whether to use global or explicit instance; documentation will clearly explain the trade‑offs.

## Related Issues
- `yaml_serializer` global context → prevents reuse in server environments.
- `protocollab.loader` memory leak and missing cache control.

## Implementation Plan
The two refactorings will be implemented in separate branch:
- `refactor/remove-global-context`

Documentation will be updated to reflect the new APIs and recommendations.
