import os
from ruamel.yaml.comments import CommentedSeq
from yaml_serializer import utils
import yaml_serializer.serializer as core
import pytest
import tempfile
import time
from pathlib import Path
from yaml_serializer import (
    load_yaml_root,
    save_yaml_root,
    new_commented_map,
    new_commented_seq,
    add_to_dict,
    add_to_list,
    remove_from_list,
    get_node_hash,
    rename_yaml_file,
    propagate_dirty,
)
import yaml_serializer.serializer as core

# Фикстура для временной директории
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

def create_minimal_yaml(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def test_load_save_unchanged(temp_dir):
    """Тест: загрузка и сохранение без изменений не должны перезаписывать файл."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    yaml_content = """
meta:
  id: test_proto
  name: Test Protocol
  version: 1.0
kaitai:
  types: {}
endpoints: []
"""
    create_minimal_yaml(main_yaml, yaml_content)

    # Загружаем
    data = load_yaml_root(main_yaml)
    assert data['meta']['id'] == 'test_proto'

    # Хэш-файла пока нет
    hash_file = main_yaml + '.hash'
    assert not os.path.exists(hash_file)

    # Сохраняем в первый раз – файл должен быть записан (т.к. нет предыдущего хэша)
    save_yaml_root(only_if_changed=True)
    assert os.path.exists(hash_file)

    # Запоминаем время модификации main.yaml
    mtime_before = os.path.getmtime(main_yaml)

    # Сохраняем снова без изменений – файл не должен перезаписываться
    time.sleep(0.1)  # чтобы гарантировать разницу во времени, если вдруг перезапишется
    save_yaml_root(only_if_changed=True)
    mtime_after = os.path.getmtime(main_yaml)

    assert mtime_after == mtime_before, "Файл не должен был измениться"

def test_modify_and_save(temp_dir):
    """Тест: модификация данных должна приводить к перезаписи файла и обновлению хэша."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    yaml_content = """
meta:
  id: test_proto
  name: Test Protocol
  version: 1.0
kaitai:
  types: {}
endpoints: []
"""
    create_minimal_yaml(main_yaml, yaml_content)

    data = load_yaml_root(main_yaml)
    save_yaml_root(only_if_changed=True)  # создаём хэш

    hash_file = main_yaml + '.hash'
    with open(hash_file, 'r') as f:
        hash_before = f.read()

    # Модифицируем: добавляем тип в kaitai.types
    types = data['kaitai']['types']
    new_type = new_commented_map(parent=types)
    add_to_dict(new_type, 'field1', 'u4')
    add_to_dict(types, 'NewPacket', new_type)

    # Проверяем, что узел стал грязным
    assert types._yaml_dirty is True
    assert data._yaml_dirty is True  # корень тоже должен быть грязным

    # Сохраняем
    save_yaml_root(only_if_changed=True)

    # Проверяем, что файл изменился (время модификации должно обновиться)
    # Можно просто проверить, что хэш изменился
    with open(hash_file, 'r') as f:
        hash_after = f.read()
    assert hash_after != hash_before, "Хэш должен измениться после модификации"

    # Также проверим, что данные сохранились корректно – перезагрузим и проверим наличие NewPacket
    data2 = load_yaml_root(main_yaml)
    assert 'NewPacket' in data2['kaitai']['types']
    assert data2['kaitai']['types']['NewPacket']['field1'] == 'u4'

def test_include_basic(temp_dir):
    """Тест: импорт внешнего файла через !include."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    included_yaml = os.path.join(temp_dir, 'included.yaml')

    included_content = """
types:
  InnerType:
    field: u2
"""
    main_content = """
meta:
  id: include_test
  name: Include Test
  version: 1.0
kaitai: !include included.yaml
endpoints: []
"""
    create_minimal_yaml(included_yaml, included_content)
    create_minimal_yaml(main_yaml, main_content)

    data = load_yaml_root(main_yaml)

    # Проверяем, что данные из включённого файла подгрузились
    assert 'types' in data['kaitai']
    assert 'InnerType' in data['kaitai']['types']
    assert data['kaitai']['types']['InnerType']['field'] == 'u2'

    # Проверяем, что узел помечен правильным файлом (корень включённого файла)
    assert data['kaitai']._yaml_file == included_yaml
    assert data['kaitai']['types']._yaml_file == included_yaml

    # Хэш-файлы должны создаться для обоих файлов при сохранении
    save_yaml_root(only_if_changed=True)
    assert os.path.exists(main_yaml + '.hash')
    assert os.path.exists(included_yaml + '.hash')

    # Модифицируем включённый файл через родительский узел
    types_dict = data['kaitai']['types']
    new_type = new_commented_map(parent=types_dict)
    add_to_dict(new_type, 'extra', 'u8')
    add_to_dict(types_dict, 'AnotherType', new_type)

    # Проверяем, что узел стал грязным
    assert types_dict._yaml_dirty is True
    # Корень включённого файла тоже грязный (поднялись по parent)
    assert data['kaitai']._yaml_dirty is True
    # Корень главного файла НЕ грязный (нет обратной связи)
    assert data._yaml_dirty is False

    save_yaml_root(only_if_changed=True)

    # Проверим содержимое включённого файла через загрузку
    import ruamel.yaml
    yaml = ruamel.yaml.YAML()
    with open(included_yaml, 'r') as f:
        inc_data = yaml.load(f)
    assert 'AnotherType' in inc_data['types']  # структурная проверка

def test_rename_main_file(temp_dir):
    """Переименование главного файла."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    new_main = os.path.join(temp_dir, 'renamed_main.yaml')
    yaml_content = "key: value\n"
    create_minimal_yaml(main_yaml, yaml_content)

    data = load_yaml_root(main_yaml)
    assert data._yaml_file == main_yaml
    assert core._CTX._root_filename == main_yaml

    # Переименовываем
    rename_yaml_file(main_yaml, new_main)

    # Проверяем обновление внутренних структур
    assert data._yaml_file == new_main
    assert core._CTX._root_filename == new_main
    assert new_main in core._CTX._file_roots
    assert main_yaml not in core._CTX._file_roots

    # Физический файл переименован
    assert not os.path.exists(main_yaml)
    assert os.path.exists(new_main)

    # Сохраняем – хэш-файл должен создаться для нового имени
    save_yaml_root()
    assert os.path.exists(new_main + '.hash')
    assert not os.path.exists(main_yaml + '.hash')

def test_rename_included_file(temp_dir):
    """Переименование включённого файла должно обновить ссылки !include."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    inc_yaml = os.path.join(temp_dir, 'inc.yaml')
    new_inc = os.path.join(temp_dir, 'renamed_inc.yaml')

    with open(inc_yaml, 'w') as f:
        f.write("data: 42\n")
    with open(main_yaml, 'w') as f:
        f.write("include: !include inc.yaml\n")

    data = load_yaml_root(main_yaml)
    assert data['include']._yaml_file == inc_yaml

    rename_yaml_file(inc_yaml, new_inc)

    # Узел в главном файле должен указывать на новый файл
    assert data['include']._yaml_file == new_inc

    # Корень включённого файла перемещён
    assert new_inc in core._CTX._file_roots
    assert inc_yaml not in core._CTX._file_roots

    # Сохраняем – главный файл должен перезаписаться с новым путём
    save_yaml_root()
    with open(main_yaml, 'r') as f:
        content = f.read()
    # Проверяем, что путь в !include обновлён
    assert '!include renamed_inc.yaml' in content, f"Expected '!include renamed_inc.yaml' in content, got: {content}"


def test_rename_with_existing_hash(temp_dir):
    """Переименование файла, у которого уже есть .hash файл."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    new_main = os.path.join(temp_dir, 'new_main.yaml')
    create_minimal_yaml(main_yaml, "data: 1\n")

    _ = load_yaml_root(main_yaml)
    save_yaml_root()  # создаёт .hash

    assert os.path.exists(main_yaml + '.hash')
    old_hash = utils.load_hash_from_file(main_yaml)

    rename_yaml_file(main_yaml, new_main)

    # Хэш-файл должен быть переименован
    assert not os.path.exists(main_yaml + '.hash')
    assert os.path.exists(new_main + '.hash')
    new_hash = utils.load_hash_from_file(new_main)
    assert new_hash == old_hash  # содержимое не изменилось

def test_propagate_dirty_marks_parent(temp_dir):
    """propagate_dirty помечает родительские файлы, ссылающиеся на изменённый включённый файл."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    inc_yaml = os.path.join(temp_dir, 'inc.yaml')

    with open(inc_yaml, 'w') as f:
        f.write("value: 42\n")
    with open(main_yaml, 'w') as f:
        f.write("inc: !include inc.yaml\n")

    data = load_yaml_root(main_yaml)
    save_yaml_root()  # начальные хэши

    # Модифицируем включённый файл
    inc_node = data['inc']
    add_to_dict(inc_node, 'new_field', 'test')

    # Проверяем: главный файл пока не грязный
    assert data._yaml_dirty is False

    # Вызываем propagate_dirty для включённого файла
    propagate_dirty(inc_yaml)

    # Теперь главный файл должен стать грязным (его узел inc помечен и поднялся по parent)
    assert data._yaml_dirty is True

    # Сохраняем – оба файла должны перезаписаться
    save_yaml_root()

    # Перезагружаем и проверяем наличие нового поля
    data_reloaded = load_yaml_root(main_yaml)
    assert data_reloaded['inc']['new_field'] == 'test'

def test_list_modifications(temp_dir):
    """Добавление и удаление элементов в CommentedSeq."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    yaml_content = """
list:
  - first
  - second
"""
    create_minimal_yaml(main_yaml, yaml_content)

    data = load_yaml_root(main_yaml)
    lst = data['list']
    assert isinstance(lst, CommentedSeq)

    # Добавляем элемент
    new_item = new_commented_seq(parent=lst)  # для примера вложенный список
    add_to_list(lst, new_item)
    assert len(lst) == 3
    assert lst._yaml_dirty is True
    assert data._yaml_dirty is True

    # Удаляем по индексу
    remove_from_list(lst, 0)
    assert len(lst) == 2
    assert lst[0] == 'second'

def test_node_hash_changes_on_modification(temp_dir):
    """Хэш узла должен меняться после модификации."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    yaml_content = "key: value\n"
    create_minimal_yaml(main_yaml, yaml_content)

    data = load_yaml_root(main_yaml)
    original_hash = get_node_hash(data)

    add_to_dict(data, 'new', 'value2')
    new_hash = get_node_hash(data)

    assert new_hash != original_hash

    # Узел становится чистым после вызова get_node_hash?
    # get_node_hash пересчитывает и сбрасывает dirty, если узел был грязным.
    assert data._yaml_dirty is False

def test_unchanged_included_file_not_saved(temp_dir):
    """Если включённый файл не менялся, он не перезаписывается."""
    main_yaml = os.path.join(temp_dir, 'main.yaml')
    inc_yaml = os.path.join(temp_dir, 'inc.yaml')

    with open(inc_yaml, 'w') as f:
        f.write("data: 42\n")
    with open(main_yaml, 'w') as f:
        f.write("inc: !include inc.yaml\n")

    load_yaml_root(main_yaml)
    save_yaml_root()  # создаёт хэши

    mtime_inc_before = os.path.getmtime(inc_yaml)
    mtime_main_before = os.path.getmtime(main_yaml)

    time.sleep(0.1)
    # Сохраняем без изменений
    save_yaml_root(only_if_changed=True)

    mtime_inc_after = os.path.getmtime(inc_yaml)
    mtime_main_after = os.path.getmtime(main_yaml)

    assert mtime_inc_after == mtime_inc_before
    assert mtime_main_after == mtime_main_before