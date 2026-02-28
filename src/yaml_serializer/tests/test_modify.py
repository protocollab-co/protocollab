"""
Тесты для модуля modify.py - модификация YAML структур.
"""

import pytest
from yaml_serializer import (
    new_commented_map,
    new_commented_seq,
    add_to_dict,
    add_to_list,
    update_in_dict,
    remove_from_dict,
    remove_from_list,
    get_node_hash,
)


class TestNewCommented:
    """Тесты для создания новых узлов."""
    
    def test_new_commented_map_empty(self):
        """Создание пустого CommentedMap."""
        dct = new_commented_map()
        assert len(dct) == 0
        assert dct._yaml_dirty is True
    
    def test_new_commented_map_with_initial_data(self):
        """new_commented_map с начальными данными."""
        initial = [('key1', 'val1'), ('key2', 'val2')]
        dct = new_commented_map(initial=initial)
        assert dct['key1'] == 'val1'
        assert dct['key2'] == 'val2'
        assert dct._yaml_dirty is True
    
    def test_new_commented_seq_empty(self):
        """Создание пустого CommentedSeq."""
        seq = new_commented_seq()
        assert len(seq) == 0
        assert seq._yaml_dirty is True
    
    def test_new_commented_seq_with_initial_data(self):
        """new_commented_seq с начальными данными."""
        initial = ['item1', 'item2', 'item3']
        seq = new_commented_seq(initial=initial)
        assert len(seq) == 3
        assert seq[0] == 'item1'
        assert seq._yaml_dirty is True


class TestDictOperations:
    """Тесты для операций со словарями."""
    
    def test_add_to_dict_simple_value(self):
        """Добавление простого значения в словарь."""
        dct = new_commented_map()
        dct._yaml_dirty = False
        
        add_to_dict(dct, 'key', 'value')
        
        assert dct['key'] == 'value'
        assert dct._yaml_dirty is True
    
    def test_add_to_dict_with_commented_value(self):
        """add_to_dict с CommentedMap в качестве значения."""
        parent = new_commented_map()
        child = new_commented_map({'nested': 'value'})
        add_to_dict(parent, 'child', child)
        
        assert parent['child']['nested'] == 'value'
        assert hasattr(child, '_yaml_parent')
        assert child._yaml_parent is parent
    
    def test_add_to_dict_else_branch(self):
        """Проверяет ветку else в add_to_dict: value не CommentedMap/Seq."""
        from yaml_serializer.modify import add_to_dict, new_commented_map
        dct = new_commented_map()
        dct._yaml_dirty = False
        add_to_dict(dct, 'simple', 123)
        assert dct['simple'] == 123
        assert dct._yaml_dirty is True
    
    def test_update_in_dict_existing_key(self):
        """update_in_dict должен обновлять существующий ключ."""
        dct = new_commented_map({'key': 'old_value'})
        update_in_dict(dct, 'key', 'new_value')
        assert dct['key'] == 'new_value'
        assert dct._yaml_dirty is True
    
    def test_update_in_dict_new_key(self):
        """update_in_dict должен добавлять новый ключ, если его нет."""
        dct = new_commented_map({'existing': 'value'})
        update_in_dict(dct, 'new_key', 'new_value')
        assert dct['new_key'] == 'new_value'
        assert 'existing' in dct
    
    def test_remove_from_dict_existing_key(self):
        """remove_from_dict должен удалять существующий ключ."""
        dct = new_commented_map({'key1': 'val1', 'key2': 'val2'})
        remove_from_dict(dct, 'key1')
        assert 'key1' not in dct
        assert 'key2' in dct
        assert dct._yaml_dirty is True
    
    def test_remove_from_dict_nonexistent_key(self):
        """remove_from_dict не должен ничего делать для несуществующего ключа."""
        dct = new_commented_map({'key1': 'val1'})
        # Не должно вызывать исключение
        remove_from_dict(dct, 'nonexistent')
        assert 'key1' in dct


class TestListOperations:
    """Тесты для операций со списками."""
    
    def test_add_to_list_simple_value(self):
        """Добавление простого значения в список."""
        lst = new_commented_seq()
        lst._yaml_dirty = False
        
        add_to_list(lst, 'item')
        
        assert len(lst) == 1
        assert lst[0] == 'item'
        assert lst._yaml_dirty is True
    
    def test_add_to_list_with_commented_item(self):
        """add_to_list с CommentedMap в качестве элемента."""
        lst = new_commented_seq()
        item = new_commented_map({'key': 'value'})
        add_to_list(lst, item)
        
        assert len(lst) == 1
        assert hasattr(item, '_yaml_parent')
        assert item._yaml_parent is lst
    
    def test_remove_from_list(self):
        """Удаление элемента из списка по индексу."""
        lst = new_commented_seq(['first', 'second', 'third'])
        remove_from_list(lst, 0)
        
        assert len(lst) == 2
        assert lst[0] == 'second'
        assert lst._yaml_dirty is True


class TestNodeHash:
    """Тесты для функции get_node_hash."""
    
    def test_recalculates_when_dirty(self):
        """get_node_hash должен пересчитывать хэш для грязных узлов."""
        node = new_commented_map({'key': 'value'})
        node._yaml_dirty = True
        
        hash1 = get_node_hash(node)
        assert node._yaml_dirty is False
        
        # Изменяем и снова получаем хэш
        node['key'] = 'new_value'
        node._yaml_dirty = True
        hash2 = get_node_hash(node)
        
        assert hash1 != hash2
    
    def test_returns_cached_hash_for_clean_node(self):
        """get_node_hash должен возвращать кэшированный хэш для чистого узла."""
        node = new_commented_map({'key': 'value'})
        hash1 = get_node_hash(node)
        
        # Второй вызов должен вернуть тот же хэш без пересчета
        node._yaml_dirty = False
        hash2 = get_node_hash(node)
        
        assert hash1 == hash2


@pytest.mark.parametrize("operation", [
    lambda d: add_to_dict(d, 'new_key', 'new_value'),
    lambda d: update_in_dict(d, 'key', 'updated'),
    lambda d: add_to_dict(d, 'another', 123),
])
def test_dict_operations_mark_dirty(operation):
    """Все операции словаря должны помечать узел как dirty."""
    dct = new_commented_map({'key': 'value'})
    dct._yaml_dirty = False
    
    operation(dct)
    
    assert dct._yaml_dirty is True
