"""
Тесты для модуля include.py - работа с директивой !include.
"""

import os
import pytest
from pathlib import Path
from yaml_serializer.serializer import load_yaml_root


class TestBasicInclude:
    """Базовые тесты для функций включения."""
    
    def test_include_with_nested_directory(self, temp_dir, create_yaml_file):
        """Включение файла из вложенной директории."""
        subdir = os.path.join(temp_dir, 'subdir')
        os.makedirs(subdir)
        
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        nested_yaml = os.path.join(subdir, 'nested.yaml')
        
        create_yaml_file(nested_yaml, 'value: 42\n')
        create_yaml_file(main_yaml, 'data: !include subdir/nested.yaml\n')
        
        data = load_yaml_root(main_yaml)
        assert data['data']['value'] == 42
        assert data['data']._yaml_file == str(Path(nested_yaml).resolve())
    
    def test_include_with_relative_path(self, temp_dir, create_yaml_file):
        """Относительные пути должны разрешаться относительно базового файла."""
        dir1 = os.path.join(temp_dir, 'subdir1')
        dir2 = os.path.join(temp_dir, 'subdir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        inc_yaml = os.path.join(dir2, 'include.yaml')
        
        create_yaml_file(inc_yaml, 'data: test\n')
        relative_path = os.path.relpath(inc_yaml, temp_dir).replace('\\', '/')
        create_yaml_file(main_yaml, f'inc: !include {relative_path}\n')
        
        data = load_yaml_root(main_yaml)
        assert data['inc']['data'] == 'test'
    
    def test_multiple_includes_in_one_file(self, temp_dir, create_yaml_file):
        """Несколько включений в одном файле."""
        inc1_yaml = os.path.join(temp_dir, 'inc1.yaml')
        inc2_yaml = os.path.join(temp_dir, 'inc2.yaml')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        
        create_yaml_file(inc1_yaml, 'value: 1\n')
        create_yaml_file(inc2_yaml, 'value: 2\n')
        create_yaml_file(main_yaml, 
                        'first: !include inc1.yaml\n'
                        'second: !include inc2.yaml\n')
        
        data = load_yaml_root(main_yaml)
        assert data['first']['value'] == 1
        assert data['second']['value'] == 2


class TestNestedIncludes:
    """Тесты для вложенных включений."""
    
    def test_nested_include_chain(self, temp_dir, create_yaml_file):
        """Цепочка вложенных включений (level1 -> level2 -> level3)."""
        level3_yaml = os.path.join(temp_dir, 'level3.yaml')
        level2_yaml = os.path.join(temp_dir, 'level2.yaml')
        level1_yaml = os.path.join(temp_dir, 'level1.yaml')
        
        create_yaml_file(level3_yaml, 'value: 3\n')
        create_yaml_file(level2_yaml, 'level3: !include level3.yaml\nvalue: 2\n')
        create_yaml_file(level1_yaml, 'level2: !include level2.yaml\nvalue: 1\n')
        
        data = load_yaml_root(level1_yaml)
        assert data['value'] == 1
        assert data['level2']['value'] == 2
        assert data['level2']['level3']['value'] == 3
    
    def test_include_in_list(self, temp_dir, create_yaml_file):
        """Включение файлов в списке."""
        item1_yaml = os.path.join(temp_dir, 'item1.yaml')
        item2_yaml = os.path.join(temp_dir, 'item2.yaml')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        
        create_yaml_file(item1_yaml, 'name: first\n')
        create_yaml_file(item2_yaml, 'name: second\n')
        create_yaml_file(main_yaml, 
                        'items:\n'
                        '  - !include item1.yaml\n'
                        '  - !include item2.yaml\n')
        
        data = load_yaml_root(main_yaml)
        assert data['items'][0]['name'] == 'first'
        assert data['items'][1]['name'] == 'second'


class TestIncludeErrorHandling:
    """Тесты обработки ошибок при включении."""
    
    def test_circular_include_detection(self, temp_dir, create_yaml_file):
        """Обнаружение циклических включений."""
        file_a = os.path.join(temp_dir, 'a.yaml')
        file_b = os.path.join(temp_dir, 'b.yaml')
        
        create_yaml_file(file_a, 'data: !include b.yaml\n')
        create_yaml_file(file_b, 'data: !include a.yaml\n')
        
        with pytest.raises(ValueError, match="Circular include detected"):
            load_yaml_root(file_a)
    
    def test_nonexistent_include_file(self, temp_dir, create_yaml_file):
        """Попытка включить несуществующий файл."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: !include nonexistent.yaml\n')
        
        with pytest.raises(FileNotFoundError):
            load_yaml_root(main_yaml)


class TestIncludeMetadata:
    """Тесты для метаданных включённых узлов."""
    
    def test_included_node_has_file_attribute(self, temp_dir, create_yaml_file):
        """Включённые узлы должны иметь атрибут _yaml_file."""
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        
        create_yaml_file(inc_yaml, 'data: value\n')
        create_yaml_file(main_yaml, 'inc: !include inc.yaml\n')
        
        data = load_yaml_root(main_yaml)
        assert hasattr(data['inc'], '_yaml_file')
        assert data['inc']._yaml_file == str(Path(inc_yaml).resolve())
    
    def test_included_node_has_include_path(self, temp_dir, create_yaml_file):
        """Включённые узлы должны сохранять оригинальный путь включения."""
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        
        create_yaml_file(inc_yaml, 'data: value\n')
        create_yaml_file(main_yaml, 'inc: !include inc.yaml\n')
        
        data = load_yaml_root(main_yaml)
        assert hasattr(data['inc'], '_yaml_include_path')
        assert data['inc']._yaml_include_path == 'inc.yaml'
