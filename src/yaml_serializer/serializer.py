# yaml_serializer/serializer.py

import os
import logging
from pathlib import Path
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from . import utils
from .utils import mark_node, clear_dirty, mark_dirty, mark_includes, replace_included, update_file_attr

logger = logging.getLogger(__name__)

# Constants
INCLUDE_TAG = '!include'


# --- SerializerContext encapsulates all state ---
class SerializerContext:
    def __init__(self):
        self._file_roots = {}
        self._loaded_hashes = {}
        self._yaml_instance = None
        self._root_filename = None
        self._current_saving_file = None  # Текущий сохраняемый файл для representer
        # Глобальные переменные безопасности (устанавливаются при загрузке)
        self._root_dir = None
        self._max_file_size = None
        self._max_include_depth = None
        self._max_struct_depth = None
        self._max_imports = None
        self._loading_stack = []
        self._import_counter = 0  # счётчик обработанных импортов в текущей загрузке

    def reset(self):
        self._file_roots.clear()
        self._loaded_hashes.clear()
        self._yaml_instance = None
        self._root_filename = None
        self._current_saving_file = None
        self._root_dir = None
        self._max_file_size = None
        self._max_include_depth = None
        self._max_struct_depth = None
        self._max_imports = None
        self._loading_stack.clear()
        self._import_counter = 0

# Default global context for backward compatibility
_CTX = SerializerContext()


def create_yaml_instance(register_include_representer=False, max_depth=None, base_depth=0):
    """
    Создаёт YAML-инстанс с безопасным конструктором.
    Если register_include_representer=True, регистрирует representer для !include.
    max_depth — ограничение глубины структур.
    """
    logger.debug("Creating secure YAML instance with RestrictedSafeConstructor and !include representer, max_depth=%s", max_depth)

    from .safe_constructor import create_safe_yaml_instance
    yaml = create_safe_yaml_instance(max_depth=max_depth if max_depth is not None else 50, base_depth=base_depth)
    if register_include_representer:
        yaml.representer.add_representer(CommentedMap, include_representer)
        yaml.representer.add_representer(CommentedSeq, include_representer)
    return yaml

def include_representer(dumper, data):
    """Оставляем без изменений (отвечает только за запись)."""
    if hasattr(data, '_yaml_include_path') and hasattr(data, '_yaml_file'):
        if _CTX._current_saving_file and data._yaml_file != _CTX._current_saving_file:
            include_path = data._yaml_include_path
            logger.debug("Representing node as !include %s", include_path)
            return dumper.represent_scalar(INCLUDE_TAG, include_path)
    if isinstance(data, CommentedMap):
        return dumper.represent_dict(data)
    elif isinstance(data, CommentedSeq):
        return dumper.represent_list(data)
    # Fallback: should not be reached since representer is only registered
    # for CommentedMap and CommentedSeq, but kept as a safety net.
    return dumper.represent_data(data)  # pragma: no cover

def include_constructor(loader, node):
    """
    Конструктор для тега !include.
    Проверяет безопасность путей и лимиты.
    """
    filename = loader.construct_scalar(node)
    logger.info("Processing !include: %s", filename)

    # Проверка на превышение лимита импортов
    _CTX._import_counter += 1
    if _CTX._max_imports is not None and _CTX._import_counter > _CTX._max_imports:
        raise ValueError(f"Exceeded maximum number of imports ({_CTX._max_imports})")

    if not _CTX._loading_stack:
        raise ValueError("!include used outside of file loading context")

    current_file = _CTX._loading_stack[-1]
    # Вычисляем абсолютный путь к включаемому файлу
    included_path = utils.resolve_include_path(current_file, filename)
    logger.debug("Resolved include path: %s", included_path)

    # Безопасность: проверяем, что путь находится внутри корневой директории
    if not utils.is_path_within_root(included_path, _CTX._root_dir):
        logger.error("Attempt to include file outside root directory: %s", included_path)
        raise PermissionError(f"Include path {filename} is not allowed (outside root)")
    # Безопасность: проверка размера файла
    if _CTX._max_file_size:
        file_size = os.path.getsize(included_path)
        if file_size > _CTX._max_file_size:
            raise ValueError(f"File {included_path} exceeds size limit {_CTX._max_file_size}")
    # Безопасность: Проверка циклических импортов
    if included_path in _CTX._loading_stack:
        logger.error("Circular include detected: %s", included_path)
        raise ValueError(f"Circular include detected: {included_path}")
    # Проверка глубины включений
    if _CTX._max_include_depth and len(_CTX._loading_stack) >= _CTX._max_include_depth:
        raise ValueError(f"Exceeded maximum include depth ({_CTX._max_include_depth})")
    # Определяем текущую глобальную глубину структуры
    # Для корректного учёта: base_depth = loader._base_depth + 1
    base_depth = getattr(loader, '_base_depth', 0) + 1
    yaml_inc = create_yaml_instance(register_include_representer=False, max_depth=_CTX._max_struct_depth, base_depth=base_depth)
    if hasattr(yaml_inc, '_make_constructor'):
        yaml_inc.Constructor = yaml_inc._make_constructor(max_depth=_CTX._max_struct_depth, base_depth=base_depth)
    yaml_inc.constructor.add_constructor(INCLUDE_TAG, include_constructor)
    data = None
    try:
        _CTX._loading_stack.append(included_path)
        logger.debug("Loading included file %s", included_path)
        with open(included_path, 'r', encoding='utf-8') as f:
            data = yaml_inc.load(f)
    finally:
        _CTX._loading_stack.pop()
    if data is not None:
        mark_node(data, included_path)
        _CTX._file_roots[included_path] = data
        data._yaml_include_path = filename
        data._yaml_parent_file = current_file
        logger.debug("Marked included node with file %s, include path: %s", included_path, filename)
        saved_hash = utils.load_hash_from_file(included_path)
        _CTX._loaded_hashes[included_path] = saved_hash
        logger.debug("Loaded saved hash for included file: %s", saved_hash)
        return data

def load_yaml_root(main_yaml_path, config=None):
    logger.info("Loading root YAML from file: %s", main_yaml_path)
    config = config or {}
    main_path = str(Path(main_yaml_path).resolve())
    _CTX._root_dir = str(Path(main_path).parent)
    _CTX._max_file_size = config.get('max_file_size', 10 * 1024 * 1024)
    _CTX._max_include_depth = config.get('max_include_depth', 50)
    _CTX._max_struct_depth = config.get('max_struct_depth', 50)
    _CTX._max_imports = config.get('max_imports', 100)
    logger.debug("Security config: root_dir=%s, max_file_size=%s, max_struct_depth=%s, max_include_depth=%s, max_imports=%s", _CTX._root_dir, _CTX._max_file_size, _CTX._max_struct_depth, _CTX._max_include_depth, _CTX._max_imports)
    _CTX._yaml_instance = create_yaml_instance(register_include_representer=True, max_depth=_CTX._max_struct_depth, base_depth=0)
    _CTX._yaml_instance.constructor.add_constructor(INCLUDE_TAG, include_constructor)
    logger.debug("Added !include constructor")
    _CTX._root_filename = main_path
    _CTX._import_counter = 0
    _CTX._loaded_hashes.clear()
    _CTX._file_roots.clear()
    _CTX._loading_stack.clear()
    _CTX._loading_stack.append(main_path)
    with open(main_path, 'r', encoding='utf-8') as f:
        logger.debug("Loading YAML content from %s", main_path)
        data = _CTX._yaml_instance.load(f)
    _CTX._loading_stack.pop()
    mark_node(data, main_path)
    _CTX._file_roots[main_path] = data
    logger.debug("Root node marked with file %s", main_path)
    saved_hash = utils.load_hash_from_file(main_path)
    _CTX._loaded_hashes[main_path] = saved_hash
    logger.debug("Loaded saved hash for %s: %s", main_path, saved_hash)
    return data

def save_yaml_root(only_if_changed=True):
    if _CTX._yaml_instance is None:
        raise RuntimeError("No YAML loaded. Call load_yaml_root first.")
    logger.info("Saving root YAML (only_if_changed=%s)", only_if_changed)
    for filename, root in _CTX._file_roots.items():
        curr_hash = root._yaml_hash
        orig_hash = _CTX._loaded_hashes.get(filename)
        if only_if_changed and orig_hash is not None and curr_hash == orig_hash and not root._yaml_dirty:
            logger.debug("File %s unchanged, skipping", filename)
            continue
        logger.info("Saving file %s", filename)
        _CTX._current_saving_file = filename  # Устанавливаем текущий файл для representer
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                _CTX._yaml_instance.dump(root, f)
                f.flush()
                os.fsync(f.fileno())   # принудительная запись на диск
        finally:
            _CTX._current_saving_file = None  # Сбрасываем после сохранения
        utils.save_hash_to_file(filename, curr_hash)
        _CTX._loaded_hashes[filename] = curr_hash
        clear_dirty(root)
        logger.debug("Saved hash and cleared dirty for %s", filename)

def rename_yaml_file(old_path: str, new_path: str):
    old_abs = str(Path(old_path).resolve())
    new_abs = str(Path(new_path).resolve())
    logger.info("Renaming YAML file from %s to %s", old_abs, new_abs)
    if old_abs not in _CTX._file_roots:
        raise ValueError(f"File {old_abs} not loaded")
    # 1. Физически переименовываем файл
    Path(old_abs).rename(new_abs)
    logger.debug("Physical rename done")
    # 2. Обновляем хэш-файл
    old_hash_file = utils.hash_file_path(old_abs)
    if os.path.exists(old_hash_file):
        new_hash_file = utils.hash_file_path(new_abs)
        Path(old_hash_file).rename(new_hash_file)
        logger.debug("Hash file renamed from %s to %s", old_hash_file, new_hash_file)
    # 3. Переносим данные в глобальных структурах
    root = _CTX._file_roots.pop(old_abs)
    _CTX._file_roots[new_abs] = root
    if old_abs in _CTX._loaded_hashes:
        _CTX._loaded_hashes[new_abs] = _CTX._loaded_hashes.pop(old_abs)
    logger.debug("Updated global structures: _file_roots and _loaded_hashes")
    # 4. Обновляем атрибут _yaml_file у корня и всех потомков
    update_file_attr(root, new_abs)
    logger.debug("Updated _yaml_file attributes for root and descendants")
    # 5. Обновляем ссылки !include во всех загруженных файлах
    logger.debug("Updating !include references in other loaded files")
    for fpath, froot in _CTX._file_roots.items():
        if fpath == new_abs:
            continue
        replace_included(froot, old_abs, new_abs, logger)
        if hasattr(froot, '_yaml_dirty'):
            mark_dirty(froot)
            logger.debug("Marked root of file %s as dirty after reference update", fpath)
    # 6. Если переименовывается главный файл
    if old_abs == _CTX._root_filename:
        _CTX._root_filename = new_abs
        logger.debug("Updated main filename to %s", new_abs)

def propagate_dirty(file_path: str):
    abs_path = str(Path(file_path).resolve())
    logger.info("Propagating dirty for file %s", file_path)
    for fpath, root in _CTX._file_roots.items():
        if fpath == abs_path:
            continue
        found = mark_includes(root, abs_path, mark_dirty, logger)
        if found:
            mark_dirty(root)
            logger.debug("Marked root of file %s as dirty due to included references", fpath)


__all__ = [
    'include_representer', 'include_constructor', 'propagate_dirty',
    'load_yaml_root', 'save_yaml_root', 'rename_yaml_file',
    'create_yaml_instance', 'SerializerContext', '_CTX'
]
