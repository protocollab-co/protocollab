"""
Тесты для модуля core.py - основные функции загрузки и сохранения.
"""

import os
import time
import pytest
from yaml_serializer import (
    load_yaml_root,
    save_yaml_root,
    new_commented_map,
    add_to_dict,
)
import yaml_serializer.serializer as core


class TestLoadProtocol:
    """Тесты для функции load_yaml_root."""
    
    def test_load_simple_protocol(self, temp_dir, create_yaml_file):
        """Загрузка простого протокола."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        content = """
meta:
  id: test_proto
  version: "1.0"
kaitai:
  types: {}
endpoints: []
"""
        create_yaml_file(main_yaml, content)
        
        data = load_yaml_root(main_yaml)
        assert data['meta']['id'] == 'test_proto'
        assert hasattr(data, '_yaml_file')
        assert hasattr(data, '_yaml_hash')
    
    def test_load_nonexistent_file(self):
        """Загрузка несуществующего файла должна вызвать FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_yaml_root('nonexistent_file.yaml')
    
    def test_load_with_config(self, temp_dir, create_yaml_file):
        """Загрузка с параметрами конфигурации."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: value\n')
        
        config = {
            'max_file_size': 1024,
            'max_include_depth': 10,
            'max_imports': 50
        }
        
        data = load_yaml_root(main_yaml, config=config)
        assert data['data'] == 'value'
        
        # Проверяем, что глобальные переменные установлены
        assert core._CTX._max_file_size == 1024
        assert core._CTX._max_include_depth == 10
        assert core._CTX._max_imports == 50


class TestSaveProtocol:
    """Тесты для функции save_yaml_root."""
    
    def test_save_without_loading(self):
        """save_yaml_root без предварительной загрузки должен вызвать ошибку."""
        core._CTX._yaml_instance = None
        
        with pytest.raises(RuntimeError, match="No YAML loaded"):
            save_yaml_root()
    
    def test_save_unchanged_protocol(self, temp_dir, create_yaml_file):
        """Сохранение без изменений не должно перезаписывать файл."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        content = "key: value\n"
        create_yaml_file(main_yaml, content)
        
        _ = load_yaml_root(main_yaml)
        save_yaml_root(only_if_changed=True)
        
        mtime_before = os.path.getmtime(main_yaml)
        time.sleep(0.1)
        
        save_yaml_root(only_if_changed=True)
        mtime_after = os.path.getmtime(main_yaml)
        
        assert mtime_after == mtime_before
    
    def test_save_modified_protocol(self, temp_dir, create_yaml_file):
        """Сохранение изменённого протокола должно обновить файл."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: {}\n')
        
        data = load_yaml_root(main_yaml)
        save_yaml_root(only_if_changed=True)
        
        # Модифицируем
        add_to_dict(data['data'], 'new_key', 'new_value')
        
        save_yaml_root(only_if_changed=True)
        
        # Перезагружаем и проверяем
        data2 = load_yaml_root(main_yaml)
        assert data2['data']['new_key'] == 'new_value'


class TestHashTracking:
    """Тесты отслеживания хэшей файлов."""
    
    def test_hash_file_created_on_save(self, temp_dir, create_yaml_file):
        """При сохранении должен создаваться .hash файл."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: value\n')
        
        _ = load_yaml_root(main_yaml)
        hash_file = main_yaml + '.hash'
        
        assert not os.path.exists(hash_file)
        
        save_yaml_root()
        
        assert os.path.exists(hash_file)
    
    def test_hash_changes_after_modification(self, temp_dir, create_yaml_file):
        """Хэш должен изменяться после модификации."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: {}\n')
        
        data = load_yaml_root(main_yaml)
        save_yaml_root()
        
        hash_file = main_yaml + '.hash'
        with open(hash_file, 'r') as f:
            hash_before = f.read()
        
        # Модифицируем
        add_to_dict(data['data'], 'key', 'value')
        save_yaml_root()
        
        with open(hash_file, 'r') as f:
            hash_after = f.read()
        
        assert hash_after != hash_before


class TestFileRootTracking:
    """Тесты отслеживания корней файлов."""
    
    def test_main_file_registered(self, temp_dir, create_yaml_file):
        """Главный файл должен быть зарегистрирован в _file_roots."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: value\n')
        
        from pathlib import Path
        data = load_yaml_root(main_yaml)
        
        main_abs = str(Path(main_yaml).resolve())
        assert main_abs in core._CTX._file_roots
        assert core._CTX._file_roots[main_abs] is data
    
    def test_file_roots_cleared_on_new_load(self, temp_dir, create_yaml_file):
        """_file_roots должен очищаться при новой загрузке."""
        file1 = os.path.join(temp_dir, 'file1.yaml')
        file2 = os.path.join(temp_dir, 'file2.yaml')
        
        create_yaml_file(file1, 'data: 1\n')
        create_yaml_file(file2, 'data: 2\n')
        
        load_yaml_root(file1)
        
        load_yaml_root(file2)
        roots_count_2 = len(core._CTX._file_roots)
        
        # После второй загрузки должен остаться только один файл
        assert roots_count_2 == 1
