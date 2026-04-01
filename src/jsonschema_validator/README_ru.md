# jsonschema_validator

**Подключаемый фасад для валидации JSON Schema с единым форматом ошибок и безопасным выбором backend**  
*Часть фреймворка [`protocollab`](https://github.com/cherninkiy/protocollab).* 

`jsonschema_validator` — небольшая Python-библиотека, которая выравнивает работу с несколькими движками JSON Schema. Она даёт единый factory, единую модель ошибки и единый API для валидации, при этом позволяет выбрать между совместимостью, безопасностью и производительностью.

---

## Ключевые возможности

- Единый API валидации через `ValidatorFactory`
- Единая модель ошибок через `SchemaValidationError`
- Безопасный режим `auto`, который предпочитает `jsonscreamer` и откатывается к `jsonschema`
- Явная поддержка `fastjsonschema`, когда нужна максимальная производительность
- Единый формат путей ошибок: `(root)`, `meta.id`, `seq[0].type`
- Полное покрытие тестами для всего модуля и backend-реализаций

---

## Установка

Установка standalone-пакета:

```bash
pip install jsonschema-validator
```

Если нужен весь фреймворк вместе с CLI и генераторами:

```bash
pip install protocollab
```

Установка standalone-пакета с предпочтительным дополнительным backend `jsonscreamer`:

```bash
pip install "jsonschema-validator[jsonscreamer]"
```

Установка с дополнительным backend `fastjsonschema`:

```bash
pip install "jsonschema-validator[fastjsonschema]"
```

Для разработки из текущего репозитория можно либо установить весь monorepo из
корня, либо поставить этот пакет в editable-режиме:

```bash
pip install -e "src/jsonschema_validator[jsonscreamer,fastjsonschema]"
```

После установки импортируйте так:

```python
from jsonschema_validator import ValidatorFactory, SchemaValidationError
```

> Примечание: `jsonschema_validator` требует Python 3.10 или новее.

---

## Быстрый старт

```python
from jsonschema_validator import ValidatorFactory

schema = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
}

data = {"name": 42, "age": -1}

validator = ValidatorFactory.create(backend="auto")
errors = validator.validate(schema, data)

for error in errors:
    print(error.path, error.message, error.schema_path)
```

Пример вывода:

```text
name 42 is not of type 'string' properties/name/type
age -1 is less than the minimum of 0 properties/age/minimum
```

---

## Структура модуля

```text
jsonschema_validator/
|-- __init__.py                     # Экспорт публичного API
|-- factory.py                      # Выбор backend и создание экземпляров
|-- models.py                       # Dataclass SchemaValidationError
|-- backends/
|   |-- base.py                     # Абстрактный интерфейс валидатора
|   |-- jsonschema_backend.py       # Backend с упором на совместимость
|   |-- jsonscreamer_backend.py     # Предпочтительный безопасный backend для auto
|   `-- fastjsonschema_backend.py   # Явно подключаемый быстрый backend
|-- tests/                          # Тесты backend-логики, factory и моделей
`-- LICENSE                         # Локальная копия лицензии Apache 2.0
```

---

## Выбор backend

### `backend="auto"`

Это режим по умолчанию и рекомендуемый вариант.

- Предпочитает `jsonscreamer`, если он установлен
- Откатывается к `jsonschema`, если `jsonscreamer` недоступен
- Никогда не выбирает `fastjsonschema` автоматически

### `backend="jsonschema"`

Подходит, когда нужна максимально предсказуемая Draft 7-совместимая валидация.

### `backend="jsonscreamer"`

Подходит, когда вы хотите явно использовать предпочтительный безопасный backend.

### `backend="fastjsonschema"`

Используйте только тогда, когда осознанно нужен более быстрый backend.

```python
validator = ValidatorFactory.create(backend="fastjsonschema")
```

---

## API Reference

### `ValidatorFactory`

```python
from jsonschema_validator import ValidatorFactory
```

#### `ValidatorFactory.create(backend: str = "auto", cache: bool = True)`

Создаёт экземпляр валидатора для выбранного backend.

- `backend="auto"` выбирает самый безопасный доступный backend
- `backend="jsonschema"` принудительно использует backend `jsonschema`
- `backend="jsonscreamer"` принудительно использует backend `jsonscreamer`
- `backend="fastjsonschema"` принудительно использует backend `fastjsonschema`
- `cache=True` включает кэширование валидаторов внутри backend

### `available_backends() -> list[str]`

Возвращает имена backend-ов, которые можно создать в текущем окружении.

```python
from jsonschema_validator import available_backends

print(available_backends())
```

### `SchemaValidationError`

```python
from jsonschema_validator import SchemaValidationError
```

Нормализованный результат валидации со следующими полями:

- `path`: путь в валидируемых данных, например `meta.id` или `seq[0].type`
- `message`: читаемое текстовое описание ошибки валидации
- `schema_path`: путь внутри JSON Schema, если backend его предоставляет

---

## Стабильность публичного API

Стабильная публичная API для `jsonschema_validator 1.0.0` ограничена корневым
API пакета, экспортируемым через `jsonschema_validator.__all__`:

- `ValidatorFactory`
- `BackendNotAvailableError`
- `SchemaValidationError`
- `available_backends`

Внутренние backend-модули в `jsonschema_validator.backends` считаются деталями
реализации и могут развиваться независимо, пока корневой API пакета остаётся
обратно совместимым в рамках ветки `1.x`.

---

## Пример обработки ошибок

```python
from jsonschema_validator import ValidatorFactory

schema = {
    "type": "object",
    "required": ["meta"],
    "properties": {
        "meta": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z_][a-z0-9_]*$"}
            },
        }
    },
}

data = {"meta": {"id": "InvalidName"}}

validator = ValidatorFactory.create(backend="jsonschema")
errors = validator.validate(schema, data)

assert errors[0].path == "meta.id"
assert errors[0].schema_path.endswith("pattern")
```

---

## Замечания по безопасности

- режим `auto` намеренно исключает `fastjsonschema`
- `fastjsonschema` подключается только явно, так как использует сгенерированный код и `exec`
- когда безопасность и предсказуемость важнее скорости, предпочитайте `auto`, `jsonscreamer` или `jsonschema`

---

## Тестирование и покрытие

Модуль содержит тесты для:

- специфики валидации каждого backend
- нормализации `path` и `schema_path`
- обработки опциональных зависимостей
- ошибок factory и probing backend-ов
- поведения кэша backend-ов

Локальный запуск тестов из директории пакета:

```bash
pytest tests/ --cov=jsonschema_validator
```

Для подробного отчёта по покрытию:

```bash
pytest tests/ --cov=jsonschema_validator --cov-report=term-missing
```

Текущее покрытие: 100% для `jsonschema_validator`.

---

## Заметки для разработки

- пакет ориентирован на поведение JSON Schema Draft 7 через поддерживаемые backend-ы
- доступность backend-ов зависит от установленных optional dependency
- фасад скрывает backend-specific форматы ошибок и типы исключений от вызывающего кода

---

## Лицензия

`jsonschema_validator` распространяется по лицензии Apache License 2.0.

- Локальная лицензия пакета: `LICENSE`
- Лицензия репозитория: `../../LICENSE`