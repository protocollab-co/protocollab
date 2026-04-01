# yaml_serializer

**Безопасный загрузчик/сохранитель YAML с поддержкой `!include`, отслеживанием изменений и сохранением форматирования**  
*Часть фреймворка [`protocollab`](https://github.com/cherninkiy/protocollab)*

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

Установка standalone-пакета:

```bash
pip install yaml-serializer
```

Если нужен весь фреймворк вместе с CLI и генераторами:

```bash
pip install protocollab
```

Для разработки прямо из этого репозитория можно либо установить весь monorepo
из корня, либо поставить этот пакет в editable-режиме:

```bash
pip install -e src/yaml_serializer
```

После установки импортируйте так:

```python
from yaml_serializer import SerializerSession
```

> **Примечание:** требуется Python 3.10 или новее

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
├── serializer.py         # SerializerSession, загрузка, сохранение, переименование
├── safe_constructor.py   # Безопасный YAML-конструктор и лимиты безопасности
├── modify.py             # Вспомогательные функции для модификации YAML-дерева
├── utils.py              # Проверка путей, хэширование, include-хелперы, dirty-tracking
└── tests/                # Набор тестов для загрузки, includes, безопасности и session API
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
from yaml_serializer import SerializerSession

session = SerializerSession()
data = session.load("main.yaml")
print(data["team"]["lead"]["name"])  # выведет "Alice"
```

### Модификация вложенных структур

```python
from yaml_serializer import SerializerSession
from yaml_serializer.modify import add_to_dict

session = SerializerSession()
data = session.load('protocol.yaml')

# Добавление нового поля в вложенный тип
add_to_dict(data['types']['Message'], 'timestamp', 'u64')

# Добавление нового определения типа (файл будет помечен как изменённый)
add_to_dict(data['types'], 'NewType', {'field': 'value'})

# Сохранение только изменённых файлов
session.save(only_if_changed=True)
```

### Безопасная загрузка с ограничениями

```python
from yaml_serializer import SerializerSession

config = {
    'max_file_size': 5 * 1024 * 1024,   # 5 МБ
    'max_struct_depth': 20,               # макс. глубина YAML-структуры (по умолчанию 50)
    'max_include_depth': 20,              # макс. глубина вложенности
    'max_imports': 50                      # макс. количество включаемых файлов
}

session = SerializerSession(config)
data = session.load('protocol.yaml')

# Переопределение лимитов для конкретного вызова load
data = session.load('protocol.yaml', config={'max_imports': 10})
```

### Переименование файлов с автообновлением `!include`

```python
from yaml_serializer import SerializerSession

session = SerializerSession()
session.load('main.yaml')

# Переименование включённого файла — все ссылки !include обновятся автоматически
session.rename('old_name.yaml', 'new_name.yaml')

session.save()
```

---

## 📖 API Reference

### `SerializerSession` (основной API)

```python
from yaml_serializer import SerializerSession
```

Каждый экземпляр полностью независим: его можно безопасно использовать в
параллельных тестах, в разных потоках и для нескольких несвязанных наборов YAML.

#### `SerializerSession(config: Optional[dict] = None)`
Создаёт session с опциональной конфигурацией по умолчанию.

| Ключ | Значение по умолчанию | Описание |
|------|------------------------|----------|
| `max_file_size` | 10 МБ | Максимальный размер файла в байтах |
| `max_struct_depth` | 50 | Максимальная глубина YAML-структуры |
| `max_include_depth` | 50 | Максимальная глубина цепочки `!include` |
| `max_imports` | 100 | Максимальное число include-операций |

#### `session.load(path: str, config: Optional[dict] = None) -> CommentedMap`
Загружает `path` и разрешает все директивы `!include`. Параметр `config`
позволяет переопределить конфигурацию session для конкретного вызова.

#### `session.save(only_if_changed: bool = True)`
Сохраняет изменённые файлы обратно на диск. По умолчанию пропускает файлы,
контент которых не изменился.

#### `session.rename(old_path: str, new_path: str)`
Переименовывает загруженный файл и обновляет все ссылки `!include` на него.

#### `session.propagate_dirty(file_path: str)`
Помечает как dirty все файлы, которые ссылаются на `file_path` через `!include`.

#### `session.clear()`
Сбрасывает загруженное состояние session, сохраняя её конфигурацию по умолчанию.

### Функции модификации

Публичные helper-функции, экспортируемые `yaml_serializer`, автоматически
обновляют родительские связи и dirty-флаги:

- `new_commented_map(initial: Optional[dict] = None, parent: Optional[Node] = None) -> CommentedMap`
- `new_commented_seq(initial: Optional[list] = None, parent: Optional[Node] = None) -> CommentedSeq`
- `add_to_dict(target: CommentedMap, key: str, value: Any)`
- `update_in_dict(target: CommentedMap, key: str, value: Any)`
- `remove_from_dict(target: CommentedMap, key: str)`
- `add_to_list(target: CommentedSeq, value: Any)`
- `remove_from_list(target: CommentedSeq, index: int)`
- `get_node_hash(node: Union[CommentedMap, CommentedSeq]) -> str` — возвращает хэш узла (пересчитывает при необходимости)

Модули `safe_constructor.py` и большая часть внутренностей `serializer.py`
считаются низкоуровневыми деталями реализации. Для обычного использования
ориентируйтесь на `SerializerSession` и публично экспортируемые helper-функции.

---

## 🛡️ Стабильность публичного API

Следующие функции из `yaml_serializer.utils` входят в стабильную advanced-use
API для `yaml_serializer 1.0.0` и покрываются гарантиями обратной
совместимости в ветке `yaml_serializer 1.x`:

- `canonical_repr`
- `compute_hash`
- `resolve_include_path`
- `is_path_within_root`
- `mark_node`
- `mark_dirty`
- `clear_dirty`
- `update_file_attr`
- `replace_included`
- `mark_includes`

Эти функции экспортируются через `yaml_serializer.utils.__all__` и помечены в
исходном коде метаданными `_stable_api`.

Хелперы с префиксом `_` являются внутренними деталями реализации и могут
изменяться без предварительного уведомления.

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

- **Набор тестов**: покрывает все критические пути  
- **Покрытие кода**: 100%  
- **Покрыто строк**: 100%
- **Структура**: тематические тестовые модули + `conftest.py`

Локальный запуск тестов из директории пакета:

```bash
pytest tests/ --cov=yaml_serializer
```

Для более детального вывода:

```bash
pytest tests/ -v --cov=yaml_serializer --cov-report=term-missing
```

---

## 🔧 Настройка окружения для разработки

```bash
# Клонировать репозиторий (если ещё не сделано)
git clone https://github.com/cherninkiy/protocollab
cd protocollab/src/yaml_serializer

# Установить пакет в editable-режиме
pip install -e .

# Запустить тесты
pytest tests/
```

---

## 📄 Лицензия

`yaml_serializer` распространяется по лицензии **Apache License 2.0**. Локальная
копия доступна в файле [LICENSE](LICENSE), а канонический текст лицензии проекта
также находится в корне репозитория: [../../LICENSE](../../LICENSE).

---

## 🙏 Благодарности

Создано на основе [ruamel.yaml](https://yaml.readthedocs.io/), [pydantic](https://docs.pydantic.dev/) и сообщества Python.


