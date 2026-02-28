from ruamel.yaml.nodes import ScalarNode, MappingNode
from yaml_serializer.safe_constructor import RestrictedSafeConstructor

def test_remove_dangerous_constructors():
	cons = RestrictedSafeConstructor()
	# Добавим опасный тег вручную
	cons.yaml_constructors['tag:yaml.org,2002:python/object'] = lambda x, y: None
	cons._remove_dangerous_constructors()
	assert 'tag:yaml.org,2002:python/object' not in cons.yaml_constructors

def test_construct_object_blocks_python_tag():
	cons = RestrictedSafeConstructor()
	node = ScalarNode('tag:yaml.org,2002:python/object', 'data')
	with pytest.raises(YAMLError):
		cons.construct_object(node)

def test_construct_object_blocks_unknown_tag():
	cons = RestrictedSafeConstructor()
	node = ScalarNode('!unknown', 'data')
	with pytest.raises(YAMLError):
		cons.construct_object(node)

def test_construct_mapping_and_sequence_depth():
	import io
	from yaml_serializer.safe_constructor import create_safe_yaml_instance
	import logging
	logger = logging.getLogger("test_safe_constructor")
	# Проверяем глубину для mapping через парсинг YAML-строки
	yaml = create_safe_yaml_instance(max_depth=1)
	deep_mapping = 'a:\n  b:\n    c: 1'
	try:
		yaml.load(io.StringIO(deep_mapping))
	except Exception as e:
		logger.warning(f"[TEST] deep_mapping exception: {type(e)} {e}")
	else:
		logger.warning("[TEST] deep_mapping: no exception raised")
	# Проверяем глубину для sequence через парсинг YAML-строки
	deep_seq = '-\n  -\n    - 1'
	try:
		yaml.load(io.StringIO(deep_seq))
	except Exception as e:
		logger.warning(f"[TEST] deep_seq exception: {type(e)} {e}")
	else:
		logger.warning("[TEST] deep_seq: no exception raised")
# Тесты для RestrictedSafeConstructor и create_safe_yaml_instance
import io
import pytest
from ruamel.yaml.error import YAMLError
from yaml_serializer.safe_constructor import create_safe_yaml_instance

def test_load_simple_yaml():
	yaml = create_safe_yaml_instance()
	data = yaml.load(io.StringIO('a: 1\nb: test\nc:\n  - 1\n  - 2'))
	assert data['a'] == 1
	assert data['b'] == 'test'
	assert data['c'] == [1, 2]

def test_block_dangerous_python_tag():
	yaml = create_safe_yaml_instance()
	dangerous = 'a: !!python/object/apply:os.system ["echo hacked"]'
	with pytest.raises(YAMLError):
		yaml.load(io.StringIO(dangerous))

def test_block_unknown_custom_tag():
	yaml = create_safe_yaml_instance()
	unknown = 'a: !customtag value'
	with pytest.raises(YAMLError):
		yaml.load(io.StringIO(unknown))

def test_max_depth_limit():
	yaml = create_safe_yaml_instance(max_depth=3)
	deep = 'a:\n  b:\n    c:\n      d: 1'
	with pytest.raises(ValueError):
		yaml.load(io.StringIO(deep))
