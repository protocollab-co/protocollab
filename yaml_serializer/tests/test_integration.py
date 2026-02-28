"""
Интеграционные тесты - сложные сценарии использования.
"""

import os
import time
import pytest
from pathlib import Path
from yaml_serializer import (
    load_yaml_root,
    save_yaml_root,
    new_commented_map,
    add_to_dict,
    add_to_list,
    rename_yaml_file,
    propagate_dirty,
)
import yaml_serializer.serializer as core


class TestComplexProtocols:
    """Тесты для сложных протоколов с множественными включениями."""
    
    def test_complex_nested_includes(self, temp_dir, create_yaml_file):
        """Сложные вложенные включения (3 уровня)."""
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


class TestModificationWorkflows:
    """Тесты рабочих процессов модификации."""
    
    def test_modify_nested_included_file(self, temp_dir, create_yaml_file):
        """Модификация вложенного включённого файла."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        
        create_yaml_file(inc_yaml, 'items:\n  - first\n')
        create_yaml_file(main_yaml, 'data: !include inc.yaml\n')
        
        data = load_yaml_root(main_yaml)
        
        # Добавляем элемент в список включённого файла
        add_to_list(data['data']['items'], 'second')
        
        save_yaml_root()
        
        # Перезагружаем и проверяем
        data2 = load_yaml_root(main_yaml)
        assert len(data2['data']['items']) == 2
        assert data2['data']['items'][1] == 'second'
    
    def test_save_only_changed_files_multiple_includes(self, temp_dir, create_yaml_file):
        """При изменении одного файла другие не пересохраняются."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        inc1_yaml = os.path.join(temp_dir, 'inc1.yaml')
        inc2_yaml = os.path.join(temp_dir, 'inc2.yaml')
        
        create_yaml_file(inc1_yaml, 'value: 1\n')
        create_yaml_file(inc2_yaml, 'value: 2\n')
        create_yaml_file(main_yaml, 'inc1: !include inc1.yaml\ninc2: !include inc2.yaml\n')
        
        data = load_yaml_root(main_yaml)
        save_yaml_root()
        
        mtime_inc2_before = os.path.getmtime(inc2_yaml)
        
        time.sleep(0.2)
        
        # Изменяем только inc1
        data['inc1']['value'] = 999
        save_yaml_root()
        
        mtime_inc2_after = os.path.getmtime(inc2_yaml)
        
        # inc2 не должен измениться
        assert mtime_inc2_after == mtime_inc2_before


class TestFileRenaming:
    """Тесты переименования файлов."""
    
    def test_rename_main_file(self, temp_dir, create_yaml_file):
        """Переименование главного файла."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        new_main = os.path.join(temp_dir, 'renamed_main.yaml')
        create_yaml_file(main_yaml, 'key: value\n')
        
        data = load_yaml_root(main_yaml)
        assert data._yaml_file == str(Path(main_yaml).resolve())
        
        rename_yaml_file(main_yaml, new_main)
        
        assert data._yaml_file == str(Path(new_main).resolve())
        assert core._CTX._root_filename == str(Path(new_main).resolve())
        assert os.path.exists(new_main)
        assert not os.path.exists(main_yaml)
    
    def test_rename_included_file(self, temp_dir, create_yaml_file):
        """Переименование включённого файла обновляет !include теги."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        new_inc = os.path.join(temp_dir, 'renamed_inc.yaml')
        
        create_yaml_file(inc_yaml, 'data: 42\n')
        create_yaml_file(main_yaml, 'include: !include inc.yaml\n')
        
        _ = load_yaml_root(main_yaml)
        rename_yaml_file(inc_yaml, new_inc)
        
        save_yaml_root()
        
        with open(main_yaml, 'r') as f:
            content = f.read()
        
        assert '!include renamed_inc.yaml' in content
    
    def test_rename_with_existing_hash(self, temp_dir, create_yaml_file):
        """Переименование файла с существующим .hash файлом."""
        from yaml_serializer import utils
        
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        new_main = os.path.join(temp_dir, 'new_main.yaml')
        create_yaml_file(main_yaml, 'data: 1\n')
        
        _ = load_yaml_root(main_yaml)
        save_yaml_root()
        
        assert os.path.exists(main_yaml + '.hash')
        old_hash = utils.load_hash_from_file(main_yaml)
        
        rename_yaml_file(main_yaml, new_main)
        
        assert not os.path.exists(main_yaml + '.hash')
        assert os.path.exists(new_main + '.hash')
        new_hash = utils.load_hash_from_file(new_main)
        assert new_hash == old_hash


class TestPropagateDirty:
    """Тесты для распространения dirty флага."""
    
    def test_propagate_dirty_marks_parent(self, temp_dir, create_yaml_file):
        """propagate_dirty помечает родительские файлы."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        
        create_yaml_file(inc_yaml, 'value: 42\n')
        create_yaml_file(main_yaml, 'inc: !include inc.yaml\n')
        
        data = load_yaml_root(main_yaml)
        save_yaml_root()
        
        # Модифицируем включённый файл
        inc_node = data['inc']
        add_to_dict(inc_node, 'new_field', 'test')
        
        # Главный файл пока не грязный
        assert data._yaml_dirty is False
        
        # Вызываем propagate_dirty
        propagate_dirty(inc_yaml)
        
        # Теперь главный файл должен стать грязным
        assert data._yaml_dirty is True
        
        save_yaml_root()
        
        # Перезагружаем и проверяем
        data_reloaded = load_yaml_root(main_yaml)
        assert data_reloaded['inc']['new_field'] == 'test'


class TestFullWorkflow:
    """Полный рабочий процесс от начала до конца."""
    
    def test_create_modify_rename_save_workflow(self, temp_dir, create_yaml_file):
        """Полный цикл: создание -> модификация -> переименование -> сохранение."""
        # 1. Создаем файлы
        main_yaml = os.path.join(temp_dir, 'protocol.yaml')
        types_yaml = os.path.join(temp_dir, 'types.yaml')
        
        create_yaml_file(types_yaml, 'Message:\n  id: u32\n')
        create_yaml_file(main_yaml, 
                        'meta:\n'
                        '  id: my_protocol\n'
                        'types: !include types.yaml\n')
        
        # 2. Загружаем
        data = load_yaml_root(main_yaml)
        assert data['types']['Message']['id'] == 'u32'
        
        # 3. Модифицируем
        add_to_dict(data['types']['Message'], 'data', 'str')
        
        # 4. Переименовываем types.yaml
        new_types_yaml = os.path.join(temp_dir, 'message_types.yaml')
        rename_yaml_file(types_yaml, new_types_yaml)
        
        # 5. Сохраняем всё
        save_yaml_root()
        
        # 6. Проверяем результат
        data2 = load_yaml_root(main_yaml)
        assert data2['types']['Message']['data'] == 'str'
        
        # Проверяем, что путь в !include обновился
        with open(main_yaml, 'r') as f:
            content = f.read()
        assert '!include message_types.yaml' in content


class TestErrorRecovery:
    """Тесты восстановления после ошибок."""
    
    def test_load_after_failed_load(self, temp_dir, create_yaml_file):
        """Успешная загрузка после неудачной попытки."""
        bad_yaml = os.path.join(temp_dir, 'bad.yaml')
        good_yaml = os.path.join(temp_dir, 'good.yaml')
        
        # Создаем файл с циклической ссылкой
        create_yaml_file(bad_yaml, 'data: !include bad.yaml\n')
        create_yaml_file(good_yaml, 'data: valid\n')
        
        # Первая загрузка должна упасть
        with pytest.raises(ValueError):
            load_yaml_root(bad_yaml)
        
        # Вторая загрузка должна работать
        data = load_yaml_root(good_yaml)
        assert data['data'] == 'valid'
