"""
Тесты для mark_includes и replace_included из include.py
"""
import pytest
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from yaml_serializer.utils import mark_includes, replace_included

def make_tree():
    # root -> a (from file1), b (from file2)
    root = CommentedMap()
    a = CommentedMap()
    b = CommentedMap()
    a._yaml_file = 'file1.yaml'
    b._yaml_file = 'file2.yaml'
    root['a'] = a
    root['b'] = b
    return root, a, b

def test_mark_includes_marks_correct_nodes():
    root, a, b = make_tree()
    marked = []
    def mark_dirty(node):
        marked.append(node)
    found = mark_includes(root, 'file1.yaml', mark_dirty)
    assert found is True
    marked_ids = [id(x) for x in marked]
    assert id(a) in marked_ids
    assert id(b) not in marked_ids
    # Проверяем что не находит несуществующий файл
    marked.clear()
    found2 = mark_includes(root, 'notfound.yaml', mark_dirty)
    assert found2 is False
    assert marked == []

def test_replace_included_updates_yaml_file_and_path():
    root, a, b = make_tree()
    # Добавим include path и parent file
    a._yaml_include_path = 'old.yaml'
    a._yaml_parent_file = 'parent.yaml'
    # Меняем file1.yaml на file3.yaml
    replace_included(root, 'file1.yaml', 'file3.yaml')
    assert a._yaml_file == 'file3.yaml'
    assert b._yaml_file == 'file2.yaml'
    # _yaml_include_path должен обновиться на относительный путь
    assert isinstance(a._yaml_include_path, str)
    assert 'file3.yaml' in a._yaml_include_path or a._yaml_include_path.endswith('file3.yaml')

def test_replace_included_handles_nested_structures():
    root = CommentedMap()
    seq = CommentedSeq()
    a = CommentedMap()
    a._yaml_file = 'file1.yaml'
    seq.append(a)
    root['seq'] = seq
    replace_included(root, 'file1.yaml', 'fileX.yaml')
    assert a._yaml_file == 'fileX.yaml'
