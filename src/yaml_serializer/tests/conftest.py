"""
Общие фикстуры и настройки для тестов yaml_serializer.
"""

import os
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Создает временную директорию для тестов."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def create_yaml_file():
    """Фикстура для создания YAML файлов в тестах."""
    def _create_file(path, content):
        """Создает YAML файл с заданным содержимым."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    return _create_file
