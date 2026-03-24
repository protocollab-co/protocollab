"""
Shared fixtures and configuration for yaml_serializer tests.
"""

import pytest
import tempfile


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def create_yaml_file():
    """Return a factory function that writes YAML files for tests."""

    def _create_file(path, content):
        """Write *content* to *path* with UTF-8 encoding."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    return _create_file
