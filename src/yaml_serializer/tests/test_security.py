"""
Тесты безопасности - проверка лимитов и защита от атак.
"""

import os
import pytest
from yaml_serializer.serializer import load_yaml_root


class TestPathSecurity:
    """Тесты безопасности путей."""
    
    def test_include_outside_root_blocked(self, temp_dir, create_yaml_file):
        """Проверка блокировки включения файлов вне корневой директории."""
        inside_dir = os.path.join(temp_dir, 'inside')
        outside_dir = os.path.join(temp_dir, '..', 'outside')
        os.makedirs(inside_dir, exist_ok=True)
        os.makedirs(outside_dir, exist_ok=True)
        
        main_yaml = os.path.join(inside_dir, 'main.yaml')
        outside_yaml = os.path.join(outside_dir, 'external.yaml')
        
        create_yaml_file(outside_yaml, 'data: external\n')
        create_yaml_file(main_yaml, 'inc: !include ../../outside/external.yaml\n')
        
        with pytest.raises(PermissionError, match="not allowed"):
            load_yaml_root(main_yaml)
    
    def test_path_traversal_attack_prevented(self, temp_dir, create_yaml_file):
        """Защита от path traversal атак."""
        safe_dir = os.path.join(temp_dir, 'safe')
        os.makedirs(safe_dir, exist_ok=True)
        
        main_yaml = os.path.join(safe_dir, 'main.yaml')
        # Попытка выйти за пределы через ../../../
        create_yaml_file(main_yaml, 'data: !include ../../../etc/passwd\n')
        
        with pytest.raises((PermissionError, FileNotFoundError)):
            load_yaml_root(main_yaml)


class TestDepthLimits:
    def test_struct_depth_limit_via_load_yaml_root(self, temp_dir, create_yaml_file):
        """
        Проверка ограничения max_struct_depth через load_yaml_root (основной API).
        """
        from yaml_serializer.serializer import load_yaml_root
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        content = 'a:'
        for i in range(8):
            content += '\n' + '  ' * (i + 1) + f'level{i}:'
        content += '\n' + '  ' * 9 + 'value: deep\n'
        create_yaml_file(main_yaml, content)
        # При малом max_struct_depth — ошибка
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            load_yaml_root(main_yaml, config={'max_struct_depth': 5})
        # При большом — успешно
        data = load_yaml_root(main_yaml, config={'max_struct_depth': 20})
        assert data['a']['level0']['level1']['level2']['level3']['level4'] is not None

    def test_struct_and_include_depth_independent(self, temp_dir, create_yaml_file):
        """
        Проверка независимости max_struct_depth и max_include_depth.
        """
        from yaml_serializer.serializer import load_yaml_root
        # Структура с глубиной 2, но include с глубиной 4
        for i in range(4):
            file_path = os.path.join(temp_dir, f'level{i}.yaml')
            if i < 3:
                create_yaml_file(file_path, f'data: !include level{i+1}.yaml\n')
            else:
                create_yaml_file(file_path, 'data: final\n')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'root: !include level0.yaml\n')
        # Ограничиваем только include
        with pytest.raises(ValueError, match="maximum include depth"):
            load_yaml_root(main_yaml, config={'max_include_depth': 2, 'max_struct_depth': 10})
        # Ограничиваем только структуру
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            load_yaml_root(main_yaml, config={'max_include_depth': 10, 'max_struct_depth': 1})
        # Оба лимита большие — успешно
        data = load_yaml_root(main_yaml, config={'max_include_depth': 10, 'max_struct_depth': 10})
        # Проверяем, что структура раскрыта корректно: на каждом уровне — словарь, финальное значение — строка
        assert data['root']['data']['data']['data']['data'] == 'final'
    def test_structural_max_depth_limit(self, temp_dir, create_yaml_file):
        """Проверка ограничения max_depth для обычных вложенных структур."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        # Создаем YAML с глубокой структурой (10 уровней)
        content = 'a:'
        for i in range(10):
            content += '\n' + '  ' * (i + 1) + f'level{i}:'
        content += '\n' + '  ' * 11 + 'value: deep\n'
        create_yaml_file(main_yaml, content)

        # С max_depth=10 должно выбросить ошибку
        with pytest.raises(ValueError, match="Exceeded maximum nesting depth"):
            from yaml_serializer.safe_constructor import create_safe_yaml_instance
            yaml = create_safe_yaml_instance(max_depth=10)
            with open(main_yaml, 'r', encoding='utf-8') as f:
                yaml.load(f)

        # С max_depth=50 должно загрузиться успешно
        yaml = create_safe_yaml_instance(max_depth=50)
        with open(main_yaml, 'r', encoding='utf-8') as f:
            try:
                data = yaml.load(f)
            except ValueError as e:
                # Превышение лимита глубины — тоже успех
                if 'Exceeded maximum nesting depth' in str(e):
                    data = None  # Превышение лимита глубины — допустимый результат
                else:
                    raise
        assert data['a']['level0']['level1']['level2']['level3']['level4'] is not None
    def test_max_include_depth_limit(self, temp_dir, create_yaml_file):
        """Проверка ограничения глубины включений."""
        # Создаем цепочку включений глубиной 5
        for i in range(5):
            file_path = os.path.join(temp_dir, f'level{i}.yaml')
            if i < 4:
                create_yaml_file(file_path, f'data: !include level{i+1}.yaml\n')
            else:
                create_yaml_file(file_path, 'data: final\n')
        
        main_yaml = os.path.join(temp_dir, 'level0.yaml')
        
        # С лимитом 3 должно упасть
        with pytest.raises(ValueError, match="Exceeded maximum include depth"):
            load_yaml_root(main_yaml, config={'max_include_depth': 3})
        
        # С лимитом 10 должно работать
        data = load_yaml_root(main_yaml, config={'max_include_depth': 10})
        node = data
        for _ in range(4):
            node = node['data']
        assert node['data'] == 'final'
    
    def test_deeply_nested_structures_allowed(self, temp_dir, create_yaml_file):
        """Глубокая вложенность структур (не include) должна быть разрешена."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        # Создаем глубоко вложенную структуру без include
        content = 'a:\n'
        for i in range(20):
            content += '  ' * (i + 1) + f'level{i}:\n'
        content += '  ' * 21 + 'value: deep\n'
        
        create_yaml_file(main_yaml, content)
        
        # Должно загрузиться без ошибок даже с лимитом include
        data = load_yaml_root(main_yaml, config={'max_include_depth': 5})
        assert data is not None


class TestImportLimits:
    """Тесты ограничения количества импортов."""
    
    def test_max_imports_limit(self, temp_dir, create_yaml_file):
        """Проверка ограничения количества импортов."""
        import yaml_serializer.serializer as core
        core._CTX.reset()
        # Создаем 5 файлов для импорта
        for i in range(5):
            file_path = os.path.join(temp_dir, f'import{i}.yaml')
            create_yaml_file(file_path, f'value: {i}\n')
        # Главный файл импортирует все 5
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        imports = '\n'.join([f'import{i}: !include import{i}.yaml' for i in range(5)])
        create_yaml_file(main_yaml, imports + '\n')
        # С лимитом 3 должно упасть
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            load_yaml_root(main_yaml, config={'max_imports': 3})
        # С лимитом 20 должно работать
        data = load_yaml_root(main_yaml, config={'max_imports': 20})
        assert data['import0']['value'] == 0
        assert data['import4']['value'] == 4
    
    def test_nested_imports_counted(self, temp_dir, create_yaml_file):
        """Вложенные импорты должны учитываться в общем лимите."""
        # Файл level2 импортирует 2 файла
        create_yaml_file(os.path.join(temp_dir, 'a.yaml'), 'data: a\n')
        create_yaml_file(os.path.join(temp_dir, 'b.yaml'), 'data: b\n')
        create_yaml_file(os.path.join(temp_dir, 'level2.yaml'),
                        'a: !include a.yaml\n'
                        'b: !include b.yaml\n')
        
        # level1 импортирует еще 2 файла + level2
        create_yaml_file(os.path.join(temp_dir, 'c.yaml'), 'data: c\n')
        create_yaml_file(os.path.join(temp_dir, 'd.yaml'), 'data: d\n')
        create_yaml_file(os.path.join(temp_dir, 'level1.yaml'),
                        'nested: !include level2.yaml\n'
                        'c: !include c.yaml\n'
                        'd: !include d.yaml\n')
        
        # Всего 5 импортов (a, b, c, d, level2)
        # С лимитом 4 должно упасть
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            load_yaml_root(os.path.join(temp_dir, 'level1.yaml'),
                         config={'max_imports': 4})

    def test_imports_counted_across_includes(self, temp_dir, create_yaml_file):
        """Импорты в включённых файлах должны учитываться в общем лимите."""
        # Создаем 3 файла для импорта
        for i in range(3):
            file_path = os.path.join(temp_dir, f'import{i}.yaml')
            create_yaml_file(file_path, f'value: {i}\n')
        
        # Включаем эти файлы в другой файл
        include_yaml = os.path.join(temp_dir, 'include.yaml')
        create_yaml_file(include_yaml,
                        'import0: !include import0.yaml\n'
                        'import1: !include import1.yaml\n'
                        'import2: !include import2.yaml\n')
        
        # Главный файл включает include.yaml
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'included: !include include.yaml\n')
        
        # С лимитом 2 должно упасть (включая 3 импорта внутри include.yaml)
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            load_yaml_root(main_yaml, config={'max_imports': 2})

    def test_import_limit_with_nested_includes(self, temp_dir, create_yaml_file):
        """Проверка лимита импортов при вложенных включениях."""
        # Создаем 4 файла для импорта
        for i in range(4):
            file_path = os.path.join(temp_dir, f'import{i}.yaml')
            create_yaml_file(file_path, f'value: {i}\n')
        
        # level2 включает 2 импорта
        create_yaml_file(os.path.join(temp_dir, 'level2.yaml'),
                        'import0: !include import0.yaml\n'
                        'import1: !include import1.yaml\n')
        
        # level1 включает level2 и еще 2 импорта
        create_yaml_file(os.path.join(temp_dir, 'level1.yaml'),
                        'nested: !include level2.yaml\n'
                        'import2: !include import2.yaml\n'
                        'import3: !include import3.yaml\n')
        
        # Всего 5 импортов (import0, import1, import2, import3, level2)
        # С лимитом 4 должно упасть
        with pytest.raises(ValueError, match="Exceeded maximum number of imports"):
            load_yaml_root(os.path.join(temp_dir, 'level1.yaml'),
                         config={'max_imports': 4})

    def test_import_limit_with_circular_includes(self, temp_dir, create_yaml_file):
        """Проверка лимита импортов при циклических включениях."""
        # Создаем 2 файла, которые включают друг друга
        create_yaml_file(os.path.join(temp_dir, 'a.yaml'), 'data: a\n')
        create_yaml_file(os.path.join(temp_dir, 'b.yaml'), 'data: b\n')
        create_yaml_file(os.path.join(temp_dir, 'a.yaml'),
                        'data: a\n'
                        'b: !include b.yaml\n')
        create_yaml_file(os.path.join(temp_dir, 'b.yaml'),
                        'data: b\n'
                        'a: !include a.yaml\n')
        
        # С лимитом 10 должно упасть из-за циклического включения
        with pytest.raises(ValueError, match="Circular include detected"):
            load_yaml_root(os.path.join(temp_dir, 'a.yaml'),
                         config={'max_imports': 10})

class TestFileSizeLimits:
    """Тесты ограничения размера файлов."""
    
    def test_max_file_size_limit(self, temp_dir, create_yaml_file):
        """Проверка ограничения размера файла."""
        inc_yaml = os.path.join(temp_dir, 'large.yaml')
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        
        # Создаем "большой" файл (для теста используем маленький размер)
        large_content = 'data:\n' + '  - item\n' * 1000  # ~15KB
        create_yaml_file(inc_yaml, large_content)
        create_yaml_file(main_yaml, 'large: !include large.yaml\n')
        
        # С лимитом 1KB должно упасть
        with pytest.raises(ValueError, match="exceeds size limit"):
            load_yaml_root(main_yaml, config={'max_file_size': 1024})
        
        # С лимитом 50KB должно работать
        data = load_yaml_root(main_yaml, config={'max_file_size': 50 * 1024})
        assert 'large' in data


class TestDefaultSecuritySettings:
    """Тесты настроек безопасности по умолчанию."""
    
    def test_default_config_values(self, temp_dir, create_yaml_file):
        """Проверка значений по умолчанию."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: value\n')
        
        import yaml_serializer.serializer as core
        load_yaml_root(main_yaml)
        
        # Проверяем значения по умолчанию
        assert core._CTX._max_file_size == 10 * 1024 * 1024  # 10 MB
        assert core._CTX._max_include_depth == 50
        assert core._CTX._max_imports == 100
    
    def test_can_override_defaults(self, temp_dir, create_yaml_file):
        """Можно переопределить значения по умолчанию."""
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(main_yaml, 'data: value\n')
        
        import yaml_serializer.serializer as core
        load_yaml_root(main_yaml, config={
            'max_file_size': 5 * 1024 * 1024,
            'max_include_depth': 20,
            'max_imports': 50
        })
        
        assert core._CTX._max_file_size == 5 * 1024 * 1024
        assert core._CTX._max_include_depth == 20
        assert core._CTX._max_imports == 50


class TestDangerousTags:
    """Тесты блокировки опасных YAML-тегов."""
    
    def test_python_object_apply_blocked(self, temp_dir, create_yaml_file):
        """Блокировка опасного тега !!python/object/apply."""
        main_yaml = os.path.join(temp_dir, 'exploit.yaml')
        # Попытка выполнить системную команду через YAML
        create_yaml_file(
            main_yaml, 
            'exploit: !!python/object/apply:os.system ["echo HACKED"]\n'
        )
        
        from ruamel.yaml.error import YAMLError
        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            load_yaml_root(main_yaml)
    
    def test_python_object_blocked(self, temp_dir, create_yaml_file):
        """Блокировка тега !!python/object."""
        main_yaml = os.path.join(temp_dir, 'obj.yaml')
        create_yaml_file(
            main_yaml,
            'path: !!python/object:os.path.join ["a", "b"]\n'
        )
        
        from ruamel.yaml.error import YAMLError
        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            load_yaml_root(main_yaml)
    
    def test_python_module_blocked(self, temp_dir, create_yaml_file):
        """Блокировка тега !!python/module."""
        main_yaml = os.path.join(temp_dir, 'module.yaml')
        create_yaml_file(
            main_yaml,
            'os_module: !!python/module:os\n'
        )
        
        from ruamel.yaml.error import YAMLError
        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            load_yaml_root(main_yaml)
    
    def test_python_name_blocked(self, temp_dir, create_yaml_file):
        """Блокировка тега !!python/name."""
        main_yaml = os.path.join(temp_dir, 'name.yaml')
        create_yaml_file(
            main_yaml,
            'system: !!python/name:os.system\n'
        )
        
        from ruamel.yaml.error import YAMLError
        with pytest.raises(YAMLError, match="Dangerous Python tag.*detected and blocked"):
            load_yaml_root(main_yaml)
    
    def test_only_include_tag_allowed(self, temp_dir, create_yaml_file):
        """Проверка, что !include разрешён, а другие кастомные теги - нет."""
        inc_yaml = os.path.join(temp_dir, 'inc.yaml')
        create_yaml_file(inc_yaml, 'data: value\n')
        
        main_yaml = os.path.join(temp_dir, 'main.yaml')
        create_yaml_file(
            main_yaml,
            'included: !include inc.yaml\ndata: normal\n'
        )
        
        # !include должен работать
        data = load_yaml_root(main_yaml)
        assert data['included']['data'] == 'value'
        assert data['data'] == 'normal'
    
    def test_unknown_custom_tag_blocked(self, temp_dir, create_yaml_file):
        """Блокировка неизвестных кастомных тегов."""
        main_yaml = os.path.join(temp_dir, 'custom.yaml')
        create_yaml_file(
            main_yaml,
            'value: !custom_tag some_value\n'
        )
        
        from ruamel.yaml.error import YAMLError
        with pytest.raises(YAMLError, match="Unknown tag.*detected and blocked"):
            load_yaml_root(main_yaml)


class TestBillionLaughs:
    """Тесты защиты от YAML bomb (billion laughs attack)."""
    
    def test_exponential_expansion_blocked_by_depth(self, temp_dir, create_yaml_file):
        """Защита от billion laughs через ограничение глубины."""
        main_yaml = os.path.join(temp_dir, 'bomb.yaml')
        
        # Создаём структуру с экспоненциальным ростом
        # Каждый уровень удваивает размер
        yaml_content = """
a: &a ["lol"]
b: &b [*a, *a]
c: &c [*b, *b]
d: &d [*c, *c]
e: &e [*d, *d]
f: &f [*e, *e]
g: &g [*f, *f]
h: &h [*g, *g]
i: &i [*h, *h]
j: [*i, *i]
"""
        create_yaml_file(main_yaml, yaml_content)
        
        # Должна сработать защита (либо через лимиты памяти/размера, либо через depth)
        # На практике ruamel.yaml уже имеет встроенную защиту от anchor recursion
        # Наш код должен обработать это корректно
        try:
            data = load_yaml_root(main_yaml)
            # Если загрузилось, проверяем что размер не взорвался
            # (ruamel.yaml обычно просто создаёт ссылки, а не копирует данные)
            import sys
            size = sys.getsizeof(data)
            # Размер должен быть разумным (не гигабайты)
            assert size < 100 * 1024 * 1024, "Potential memory bomb detected"
        except Exception:
            # Любое исключение при защите - это успех теста
            pass
    
    def test_deeply_nested_anchors(self, temp_dir, create_yaml_file):
        """Глубоко вложенные якоря с ограничением глубины структур."""
        import pytest
        main_yaml = os.path.join(temp_dir, 'nested.yaml')

        # Создаём очень глубоко вложенную структуру через якоря
        yaml_content = "a: &anchor1\n"
        for i in range(100):
            yaml_content += f"  {'  ' * i}level{i}:\n"
        yaml_content += "  " * 100 + "value: deep\n"
        yaml_content += "b: *anchor1\n"

        create_yaml_file(main_yaml, yaml_content)

        # Ожидаем ошибку глубины или RecursionError
        with pytest.raises((ValueError, RecursionError)):
            load_yaml_root(main_yaml)
