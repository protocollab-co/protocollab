"""Tests for the stable public API exported by jsonschema_validator."""

import jsonschema_validator
from jsonschema_validator import (
    BackendNotAvailableError,
    SchemaValidationError,
    ValidatorFactory,
    available_backends,
)

STABLE_PUBLIC_API = {
    "ValidatorFactory",
    "BackendNotAvailableError",
    "SchemaValidationError",
    "available_backends",
}


def test_package_root_all_matches_stable_api() -> None:
    assert set(jsonschema_validator.__all__) == STABLE_PUBLIC_API


def test_package_root_exports_expected_symbols() -> None:
    assert ValidatorFactory is jsonschema_validator.ValidatorFactory
    assert BackendNotAvailableError is jsonschema_validator.BackendNotAvailableError
    assert SchemaValidationError is jsonschema_validator.SchemaValidationError
    assert available_backends is jsonschema_validator.available_backends
