# yaml_serializer

**Безопасный загрузчик/сохранитель YAML с поддержкой `!include`, отслеживанием изменений и сохранением форматирования**  
*Часть фреймворка [`protocollab`](https://github.com/yourname/protocollab)*

`yaml_serializer` — библиотека Python на основе `ruamel.yaml`, предоставляющая безопасный, готовый к продакшену способ загрузки, модификации и сохранения YAML-файлов. Это основа обработки спецификаций протоколов в `protocollab`, но может использоваться независимо в любом Python-проекте.

---

## ✨ Ключевые возможности

- 🔒 **Безопасная загрузка** — защита от path traversal, billion laughs и выполнения произвольного кода через YAML-теги
- 🔗 **Тег `!include`** — разделение больших YAML-файлов на переиспользуемые компоненты
- 📝 **Сохранение форматирования** — комментарии, кавычки и форматирование остаются неизменными при сохранении
- 🔄 **Отслеживание изменений** — автоматическое помечание dirty и обнаружение изменений на основе хэшей для эффективного сохранения
- 🧩 **Простая модификация** — вспомогательные функции для изменения YAML-структур с поддержкой родительских связей и dirty-флагов
- 🔀 **Умное переименование** — автоматическое обновление путей `!include` при переименовании файлов
- ✅ **Высокое покрытие тестами** (100%) — проверено в бою и готово к продакшену

---

## 📦 Установка

`yaml_serializer` является частью пакета `protocollab`. Установка всего фреймворка (рекомендуется):

```bash
pip install protocollab
```

Для использования только сериализатора без остальной части `protocollab`:

```bash
pip install git+https://github.com/yourname/protocollab.git
```

После установки импортируйте так:

```python
from yaml_serializer import SerializerSession
```

> **Примечание:** требуется Python 3.8 или новее

---

## 🚀 Быстрый старт

```python
from yaml_serializer import SerializerSession
from yaml_serializer.modify import add_to_dict

# Создание сессии (инкапсулирует всё состояние — потокобезопасная и удобная в тестах)
session = SerializerSession()

# Загрузка YAML-файла (все !include автоматически разрешаются)
data = session.load("path/to/file.yaml")

# Модификация структуры (родительские связи и dirty-флаги обновляются автоматически)
add_to_dict(data, "new_key", "new_value")

# Сохранение только изменённых файлов с сохранением комментариев и форматирования
session.save()
```

---

## 📁 Структура модуля

```
yaml_serializer/
├── __init__.py           # Экспорт публичного API
├── core.py               # load_protocol, save_protocol, управление файлами
├── include.py            # Конструктор !include и разрешение путей
├── modify.py             # Вспомогательные функции для безопасных модификаций
├── utils.py              # Валидация путей, hash-файлы, хэширование
├── safe_constructor.py   # Безопасный YAML конструктор, блокирует опасные теги
├── merge.py              # (TODO) Функциональность трёхстороннего слияния
├── safe_loader.py        # (Зарезервировано) Будущая реализация безопасного загрузчика
└── tests/
    ├── __init__.py
    ├── conftest.py       # Общие fixtures (temp_dir, sample data)
    ├── test_basic.py     # Smoke tests (10 тестов)
    ├── test_core.py      # Основная функциональность (10 тестов)
    ├── test_hashing.py   # Операции с хэшами (6 тестов)
    ├── test_include.py   # Директивы include (9 тестов)
    ├── test_integration.py # Интеграционные сценарии (9 тестов)
    ├── test_modify.py    # Вспомогательные функции модификации (16 тестов)
    ├── test_security.py  # Функции безопасности (17 тестов)
    ├── test_utils.py     # Утилиты (9 тестов)
    ├── test_validation.py # Стабы валидации (6 тестов)
    └── validation_stub.py # Минимальный стаб валидации для тестирования
```

---

## 📚 Примеры использования

### Работа с `!include`

**person.yaml**
```yaml
name: Alice
age: 30
```

**main.yaml**
```yaml
team:
  lead: !include person.yaml
```

```python
data = load_protocol("main.yaml")
print(data["team"]["lead"]["name"])  # выведет "Alice"
```

### Модификация вложенных структур

```python
from protocollab.yaml_serializer import load_protocol, save_protocol
from protocollab.yaml_serializer.modify import add_to_dict

data = load_protocol('protocol.yaml')

# Добавление нового поля в вложенный тип
add_to_dict(data['types']['Message'], 'timestamp', 'u64')

# Добавление нового определения типа (файл будет помечен как изменённый)
add_to_dict(data['types'], 'NewType', {'field': 'value'})

# Сохранение только изменённых файлов
save_protocol(only_if_changed=True)
```

### Безопасная загрузка с ограничениями

```python
config = {
    'max_file_size': 5 * 1024 * 1024,   # 5 МБ
    'max_include_depth': 20,              # макс. глубина вложенности
    'max_imports': 50                      # макс. количество включаемых файлов
}

data = load_protocol('protocol.yaml', config=config)
```

### Переименование файлов с автообновлением `!include`

```python
from protocollab.yaml_serializer import load_protocol, rename_protocol_file, save_protocol

data = load_protocol('main.yaml')

# Переименование включённого файла — все ссылки !include обновятся автоматически
rename_protocol_file('old_name.yaml', 'new_name.yaml')

save_protocol()
```

---

## 📖 API Reference

### Основные функции

#### `load_protocol(path: str, config: Optional[dict] = None) -> CommentedMap`
Загружает YAML-протокол с разрешением всех директив `!include`.

**Параметры:**
- `path` — путь к главному YAML-файлу
- `config` — опциональный словарь с настройками безопасности:
  - `max_file_size` — максимальный размер файла в байтах (по умолчанию 10 МБ)
  - `max_include_depth` — максимальная глубина вложенности includes (по умолчанию 50)
  - `max_imports` — максимальное количество включаемых файлов (по умолчанию 100)

#### `save_protocol(only_if_changed: bool = True)`
Сохраняет протокол и все включённые файлы обратно на диск.

**Параметры:**
- `only_if_changed` — если `True` (по умолчанию), записываются только изменённые файлы

#### `rename_protocol_file(old_path: str, new_path: str)`
Переименовывает загруженный файл и обновляет все ссылки `!include` на него.

#### `propagate_dirty(file_path: str)`
Помечает как изменённые любые узлы, ссылающиеся на данный файл. Используется внутри после модификаций, затрагивающих includes.

### Функции модификации

Все функции модификации автоматически обновляют родительские связи и dirty-флаги:

- `new_commented_map(initial: Optional[dict] = None, parent: Optional[Node] = None) -> CommentedMap`
- `new_commented_seq(initial: Optional[list] = None, parent: Optional[Node] = None) -> CommentedSeq`
- `add_to_dict(target: CommentedMap, key: str, value: Any)`
- `update_in_dict(target: CommentedMap, key: str, value: Any)`
- `remove_from_dict(target: CommentedMap, key: str)`
- `add_to_list(target: CommentedSeq, value: Any)`
- `remove_from_list(target: CommentedSeq, index: int)`
- `get_node_hash(node: Union[CommentedMap, CommentedSeq]) -> str` — возвращает хэш узла (пересчитывает при необходимости)

### Вспомогательные функции (`utils.py`)

Утилиты для работы с путями, hash-файлами и хэширование:

- `hash_file_path(yaml_path: str) -> str` — возвращает путь к hash-файлу
- `load_hash_from_file(yaml_path: str) -> str | None` — загружает сохранённый хэш
- `save_hash_to_file(yaml_path: str, hash_value: str) -> None` — сохраняет хэш в файл
- `resolve_include_path(base_file: str, include_path: str) -> str` — разрешает относительный путь включения
- `is_path_within_root(path: str, root_dir: str) -> bool` — проверяет, находится ли разрешённый путь внутри корневой директории
- `canonical_repr(data: Any) -> dict/list` — создаёт каноническое представление для хэширования
- `compute_hash(data: Any) -> str` — вычисляет SHA-256 хэш канонического представления

---

## 🛡️ Безопасность

`yaml_serializer` разработан с приоритетом безопасности, устраняя недостатки многих YAML-библиотек:

- **Ограниченные YAML-теги** — разрешён только кастомный тег `!include`; все остальные (включая опасные Python-специфичные теги) отклоняются
- **Лимит размера файла** — предотвращает атаки на истощение памяти (настраиваемый, по умолчанию 10 МБ)
- **Лимит глубины вложенности** — предотвращает переполнение стека от глубоко вложенных структур (по умолчанию 50)
- **Защита от path traversal** — `!include` может ссылаться только на файлы внутри корня проекта
- **Обнаружение циклических импортов** — предотвращает бесконечную рекурсию
- **Лимит количества импортов** — останавливает bomb-атаки с тысячами включений (по умолчанию 100)

Эти меры делают `yaml_serializer` подходящим для обработки ненадёжных YAML-файлов — ключевое преимущество перед многими альтернативами.

---

## 🧪 Тестирование и покрытие

Модуль имеет обширный набор тестов, покрывающий все критические пути.

- **Всего тестов**: 307  
- **Покрытие кода**: 100%  
- **Покрыто строк**: 100%
- **Структура**: 11 тематических тестовых модулей + `conftest.py`

Запуск тестов локально:

```bash
pytest src/yaml_serializer/tests/ --cov=yaml_serializer
```

Для более детального вывода:

```bash
pytest src/yaml_serializer/tests/ -v --cov=yaml_serializer --cov-report=term-missing
```

---

## 🔧 Настройка окружения для разработки

```bash
# Клонировать репозиторий (если ещё не сделано)
git clone https://github.com/cherninkiy/protocollab
cd protocollab

# Создать и активировать виртуальное окружение
python -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows

# Установить зависимости
pip install -r requirements.txt

# Установить пакет в режиме редактирования
pip install -e .

# Запустить тесты
pytest src/yaml_serializer/tests/
```

---

## 📄 Лицензия

`yaml_serializer` является частью `protocollab` и распространяется под лицензией **MIT**. См. файл [LICENSE](LICENSE) для деталей.

---

## 🙏 Благодарности

Создано на основе [ruamel.yaml](https://yaml.readthedocs.io/), [pydantic](https://docs.pydantic.dev/) и сообщества Python.


