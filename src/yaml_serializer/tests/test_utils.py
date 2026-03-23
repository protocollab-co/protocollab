"""
Тесты для модуля utils.py - вспомогательные функции.
"""

import os
import pytest
from pathlib import Path
from yaml_serializer import utils


class TestHashFileOperations:
    """Тесты для работы с hash-файлами."""
    
    def test_hash_file_path(self, temp_dir):
        """hash_file_path должен добавлять расширение .hash."""
        yaml_path = os.path.join(temp_dir, 'test.yaml')
        hash_path = utils.hash_file_path(yaml_path)
        assert hash_path == yaml_path + '.hash'
    
    def test_save_and_load_hash(self, temp_dir):
        """Сохранение и загрузка hash-файла."""
        yaml_path = os.path.join(temp_dir, 'test.yaml')
        test_hash = 'abc123def456'
        
        utils.save_hash_to_file(yaml_path, test_hash)
        loaded_hash = utils.load_hash_from_file(yaml_path)
        
        assert loaded_hash == test_hash
    
    def test_load_hash_nonexistent_file(self, temp_dir):
        """Загрузка несуществующего hash-файла должна вернуть None."""
        yaml_path = os.path.join(temp_dir, 'nonexistent.yaml')
        hash_value = utils.load_hash_from_file(yaml_path)
        assert hash_value is None


class TestResolveIncludePath:
    """Тесты для функции resolve_include_path."""
    
    def test_resolve_relative_path(self, temp_dir):
        """Разрешение относительного пути."""
        base_file = os.path.join(temp_dir, 'main.yaml')
        include_path = 'subdir/include.yaml'
        
        resolved = utils.resolve_include_path(base_file, include_path)
        expected = str((Path(temp_dir) / 'subdir' / 'include.yaml').resolve())
        
        assert resolved == expected
    
    def test_resolve_parent_path(self, temp_dir):
        """Разрешение пути с ../"""
        subdir = os.path.join(temp_dir, 'subdir')
        os.makedirs(subdir, exist_ok=True)
        
        base_file = os.path.join(subdir, 'main.yaml')
        include_path = '../include.yaml'
        
        resolved = utils.resolve_include_path(base_file, include_path)
        expected = str((Path(temp_dir) / 'include.yaml').resolve())
        
        assert resolved == expected


class TestIsPathWithinRoot:
    """Тесты для функции is_path_within_root."""
    
    def test_path_within_root(self, temp_dir):
        """Путь внутри корневой директории должен быть разрешен."""
        root_dir = temp_dir
        inner_path = os.path.join(temp_dir, 'subdir', 'file.yaml')
        
        assert utils.is_path_within_root(inner_path, root_dir) is True
    
    def test_path_outside_root(self, temp_dir):
        """Путь вне корневой директории должен быть заблокирован."""
        root_dir = os.path.join(temp_dir, 'restricted')
        os.makedirs(root_dir, exist_ok=True)
        
        outside_path = os.path.join(temp_dir, 'outside.yaml')
        
        assert utils.is_path_within_root(outside_path, root_dir) is False
    
    def test_none_root_raises_error(self, temp_dir):
        """Передача None в root_dir должна вызывать ошибку, так как root_dir обязателен."""
        any_path = os.path.join(temp_dir, 'any.yaml')
        with pytest.raises(TypeError, match="argument should be a str or an os.PathLike object"):
            utils.is_path_within_root(any_path, None)
    
    def test_path_traversal_attack(self, temp_dir):
        """Защита от path traversal атак."""
        root_dir = os.path.join(temp_dir, 'safe')
        os.makedirs(root_dir, exist_ok=True)
        
        # Попытка выйти за пределы через ../../../
        malicious_path = os.path.join(root_dir, '..', '..', '..', 'etc', 'passwd')
        
        # Должно заблокировать
        assert utils.is_path_within_root(malicious_path, root_dir) is False
