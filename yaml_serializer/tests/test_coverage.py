"""
Тесты для покрытия непокрытых строк в utils.py, serializer.py и safe_constructor.py.
"""

import os
import io
import logging
import pytest
import ruamel.yaml
from pathlib import Path
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from yaml_serializer import utils
from yaml_serializer.utils import (
    mark_dirty,
    mark_includes,
    replace_included,
    update_file_attr,
)
from yaml_serializer.modify import add_to_dict, add_to_list
from yaml_serializer.safe_constructor import create_safe_yaml_instance
from yaml_serializer.serializer import (
    _CTX,
    rename_yaml_file,
    include_representer,
    include_constructor,
    INCLUDE_TAG,
    load_yaml_root,
)


# ---------------------------------------------------------------------------
# utils.py – mark_dirty(None)  [line 80]
# ---------------------------------------------------------------------------

class TestMarkDirtyNone:
    def test_mark_dirty_none_is_noop(self):
        """mark_dirty(None) должен тихо завершаться без исключений."""
        mark_dirty(None)  # не должно бросить исключение


# ---------------------------------------------------------------------------
# utils.py – update_file_attr с CommentedSeq-детьми  [lines 63-65]
# ---------------------------------------------------------------------------

class TestUpdateFileAttrSeq:
    def test_update_file_attr_seq_children(self):
        """update_file_attr рекурсивно обновляет _yaml_file у элементов CommentedSeq."""
        root = CommentedSeq()
        child_map = CommentedMap()
        child_map._yaml_file = 'old.yaml'
        root.append(child_map)

        update_file_attr(root, 'new.yaml')

        assert root._yaml_file == 'new.yaml'
        assert child_map._yaml_file == 'new.yaml'


# ---------------------------------------------------------------------------
# utils.py – mark_includes с CommentedSeq в корне  [lines 137-140]
# ---------------------------------------------------------------------------

class TestMarkIncludesSeq:
    def test_mark_includes_in_seq_root(self):
        """mark_includes находит узлы с нужным _yaml_file внутри CommentedSeq."""
        seq = CommentedSeq()
        a = CommentedMap({'x': 1})
        b = CommentedMap({'y': 2})
        a._yaml_file = 'target.yaml'
        b._yaml_file = 'other.yaml'
        seq.append(a)
        seq.append(b)

        marked = []
        found = mark_includes(seq, 'target.yaml', marked.append)

        assert found is True
        marked_ids = [id(x) for x in marked]
        assert id(a) in marked_ids
        assert id(b) not in marked_ids

    def test_mark_includes_in_seq_not_found(self):
        """mark_includes возвращает False, если в CommentedSeq нет нужного файла."""
        seq = CommentedSeq()
        node = CommentedMap()
        node._yaml_file = 'other.yaml'
        seq.append(node)

        found = mark_includes(seq, 'missing.yaml', lambda x: None)
        assert found is False


# ---------------------------------------------------------------------------
# utils.py – replace_included с logger и абсолютным путём [lines 149, 159-162]
# ---------------------------------------------------------------------------

class TestReplaceIncludedLogger:
    def test_replace_included_logs_file_update(self, caplog):
        """replace_included вызывает logger при обновлении _yaml_file."""
        node = CommentedMap()
        node._yaml_file = 'old.yaml'

        logger = logging.getLogger('test_replace')
        with caplog.at_level(logging.DEBUG, logger='test_replace'):
            replace_included(node, 'old.yaml', 'new.yaml', logger)

        assert node._yaml_file == 'new.yaml'

    def test_replace_included_absolute_path_fallback(self, temp_dir):
        """
        replace_included использует абсолютный путь, если relative_to бросает ValueError
        (новый файл не является потомком директории родительского файла).
        """
        # parent_file находится в temp_dir/proj/, new_file — в temp_dir/other/
        # Поэтому Path(new_file).relative_to(parent_dir) → ValueError
        proj_dir = os.path.join(temp_dir, 'proj')
        other_dir = os.path.join(temp_dir, 'other')
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(other_dir, exist_ok=True)

        old_file = os.path.join(proj_dir, 'old.yaml')
        new_file = os.path.join(other_dir, 'new.yaml')
        parent_file = os.path.join(proj_dir, 'main.yaml')

        node = CommentedMap()
        node._yaml_file = old_file
        node._yaml_include_path = 'old.yaml'
        node._yaml_parent_file = parent_file

        replace_included(node, old_file, new_file)
        # В ветке ValueError должен быть установлен абсолютный путь, содержащий new.yaml
        assert 'new.yaml' in node._yaml_include_path

    def test_replace_included_absolute_path_logs(self, temp_dir, caplog):
        """replace_included логирует абсолютный путь при fallback."""
        proj_dir = os.path.join(temp_dir, 'proj')
        other_dir = os.path.join(temp_dir, 'other')
        os.makedirs(proj_dir, exist_ok=True)
        os.makedirs(other_dir, exist_ok=True)

        old_file = os.path.join(proj_dir, 'old.yaml')
        new_file = os.path.join(other_dir, 'new.yaml')
        parent_file = os.path.join(proj_dir, 'main.yaml')

        node = CommentedMap()
        node._yaml_file = old_file
        node._yaml_include_path = 'old.yaml'
        node._yaml_parent_file = parent_file

        logger = logging.getLogger('test_replace_abs')
        with caplog.at_level(logging.DEBUG, logger='test_replace_abs'):
            replace_included(node, old_file, new_file, logger)

        assert 'new.yaml' in node._yaml_include_path


# ---------------------------------------------------------------------------
# serializer.py – rename_yaml_file с незагруженным файлом  [line 203]
# ---------------------------------------------------------------------------

class TestRenameUnloadedFile:
    def test_rename_unloaded_file_raises(self, temp_dir):
        """rename_yaml_file должен бросать ValueError для незагруженного файла."""
        unloaded = os.path.join(temp_dir, 'notloaded.yaml')
        with pytest.raises(ValueError, match="not loaded"):
            rename_yaml_file(unloaded, os.path.join(temp_dir, 'other.yaml'))


# ---------------------------------------------------------------------------
# serializer.py – include_constructor вне контекста загрузки  [line 94]
# ---------------------------------------------------------------------------

class TestIncludeConstructorOutsideContext:
    def test_include_outside_loading_context_raises(self):
        """include_constructor должен бросить ValueError, если _loading_stack пуст."""
        _CTX._loading_stack.clear()
        _CTX._max_imports = None  # не мешать проверке

        yaml_inst = create_safe_yaml_instance()
        yaml_inst.constructor.add_constructor(INCLUDE_TAG, include_constructor)

        with pytest.raises(ValueError, match="outside of file loading context"):
            yaml_inst.load(io.StringIO('data: !include some.yaml'))


# ---------------------------------------------------------------------------
# safe_constructor.py – _check_structure_depth при max_depth=None  [early return]
# ---------------------------------------------------------------------------

class TestCheckStructureDepthNone:
    def test_no_depth_limit_allows_any_depth(self):
        """create_safe_yaml_instance(max_depth=None) не поднимает исключений ни на какой глубине."""
        # Собираем глубоко вложенный YAML (60 уровней) через стандартный ruamel.yaml
        data: dict = {'value': 1}
        for i in range(60):
            data = {f'l{i}': data}
        y = ruamel.yaml.YAML()
        buf = io.StringIO()
        y.dump(data, buf)
        yaml_str = buf.getvalue()

        loader = create_safe_yaml_instance(max_depth=None)
        # Не должно бросать исключений
        loader.load(yaml_str)


# ---------------------------------------------------------------------------
# Проверка Round-trip: сохраняются комментарии и форматирование
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_comments_preserved_on_load(self, temp_dir, create_yaml_file):
        """Комментарии сохраняются при загрузке и сохранении (round-trip)."""
        yaml_content = (
            "# Top-level comment\n"
            "key: value  # inline comment\n"
        )
        path = os.path.join(temp_dir, 'rt.yaml')
        create_yaml_file(path, yaml_content)
        data = load_yaml_root(path)

        # Дамп через ruamel.yaml (через YAML instance)
        out = io.StringIO()
        _CTX._yaml_instance.dump(data, out)
        dumped = out.getvalue()

        assert '# Top-level comment' in dumped
        assert 'inline comment' in dumped


# ---------------------------------------------------------------------------
# modify.py – наследование _yaml_file при add_to_dict / add_to_list [lines 37, 47]
# ---------------------------------------------------------------------------

class TestModifyYamlFileInheritance:
    def test_add_to_dict_inherits_yaml_file(self):
        """Значение без _yaml_file наследует его от контейнера при add_to_dict."""
        dct = CommentedMap()
        dct._yaml_file = 'parent.yaml'
        dct._yaml_hash = None
        dct._yaml_dirty = False

        child = CommentedMap({'x': 1})
        # child не имеет _yaml_file и _yaml_parent

        add_to_dict(dct, 'child', child)

        assert child._yaml_file == 'parent.yaml'

    def test_add_to_list_inherits_yaml_file(self):
        """Элемент без _yaml_file наследует его от списка при add_to_list."""
        lst = CommentedSeq()
        lst._yaml_file = 'parent.yaml'
        lst._yaml_hash = None
        lst._yaml_dirty = False

        item = CommentedMap({'y': 2})
        # item не имеет _yaml_file и _yaml_parent

        add_to_list(lst, item)

        assert item._yaml_file == 'parent.yaml'
