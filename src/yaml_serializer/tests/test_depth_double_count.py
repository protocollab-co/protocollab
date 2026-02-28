# tests/test_depth_double_count.py
"""
Тесты для проверки корректности ограничения глубины вложенности в RestrictedSafeConstructor.
Выявляют проблему двойного учёта глубины, из-за которой фактический лимит оказывается в два раза меньше заданного.
"""

import pytest
import ruamel.yaml
from io import StringIO

from yaml_serializer.safe_constructor import create_safe_yaml_instance


# ----------------------------------------------------------------------
# Вспомогательные функции для генерации YAML-строк с заданной глубиной
# ----------------------------------------------------------------------

def nested_mapping(depth: int, value=1):
    """Создаёт вложенный словарь глубины depth (количество уровней маппингов)."""
    result = value
    for i in range(depth):
        result = {f"level{i}": result}
    return result


def nested_sequence(depth: int, value=1):
    """Создаёт вложенный список глубины depth (количество уровней последовательностей)."""
    result = value
    for i in range(depth):
        result = [result]
    return result


def to_yaml(data) -> str:
    """Преобразует объект в YAML-строку (без использования нашей библиотеки)."""
    yaml = ruamel.yaml.YAML()
    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


# ----------------------------------------------------------------------
# Тесты для маппингов
# ----------------------------------------------------------------------

@pytest.mark.parametrize("depth", range(1, 51))
def test_mapping_depth_within_limit(depth):
    """
    Для глубин от 1 до max_depth (50) исключение возникать не должно.
    Если тест падает на каком-то значении depth <= 50, это указывает на проблему двойного учёта.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_mapping(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Mapping depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_mapping_depth_exceeds_limit(depth):
    """
    При глубине > max_depth должно возникать ValueError.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_mapping(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Тесты для последовательностей
# ----------------------------------------------------------------------

@pytest.mark.parametrize("depth", range(1, 51))
def test_sequence_depth_within_limit(depth):
    """
    Аналогично для последовательностей.
    """
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_sequence(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Sequence depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_sequence_depth_exceeds_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = nested_sequence(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Комбинированные структуры (маппинг + последовательность)
# ----------------------------------------------------------------------

def mixed_structure(depth: int):
    """Чередует маппинг и последовательность для создания глубины depth."""
    result = 1
    for i in range(depth):
        if i % 2 == 0:
            result = [result]
        else:
            result = {f"level{i}": result}
    return result


@pytest.mark.parametrize("depth", range(1, 51))
def test_mixed_depth_within_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = mixed_structure(depth)
    yaml_str = to_yaml(data)

    try:
        loader.load(yaml_str)
    except ValueError as e:
        pytest.fail(f"Mixed structure depth {depth} raised exception unexpectedly: {e}")


@pytest.mark.parametrize("depth", [51, 55, 60])
def test_mixed_depth_exceeds_limit(depth):
    loader = create_safe_yaml_instance(max_depth=50)
    data = mixed_structure(depth)
    yaml_str = to_yaml(data)

    with pytest.raises(ValueError, match="Exceeded maximum nesting depth of 50"):
        loader.load(yaml_str)


# ----------------------------------------------------------------------
# Тест, специально нацеленный на выявление двойного учёта
# ----------------------------------------------------------------------

def test_double_counting_manifestation():
    """
    Проверяет отсутствие двойного учёта глубины.
    При max_depth=50 глубина 26 должна быть допустима (без двойного учёта 26 != 52).
    Если этот тест падает (исключение для 26 возникает), значит двойной учёт присутствует.
    """
    # Используем отдельный инстанс для каждого load, чтобы _depth сбрасывался
    loader_25 = create_safe_yaml_instance(max_depth=50)
    data_25 = nested_mapping(25)
    yaml_25 = to_yaml(data_25)
    try:
        loader_25.load(yaml_25)
    except ValueError:
        pytest.fail("Depth 25 raised exception, but should be allowed.")

    # Глубина 26 – должна быть допустима (двойного учёта нет: 26 <= 50)
    loader_26 = create_safe_yaml_instance(max_depth=50)
    data_26 = nested_mapping(26)
    yaml_26 = to_yaml(data_26)
    try:
        loader_26.load(yaml_26)
    except ValueError:
        pytest.fail("Depth 26 raised exception, double counting is still present (2*26=52 > 50).")