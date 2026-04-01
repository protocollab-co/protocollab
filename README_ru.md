# protocollab

[English version](README.md)

> Опиши один раз. Сгенерируй всё.

`protocollab` — open-source фреймворк для описания, валидации и генерации реализаций сетевых и бинарных протоколов из человекочитаемых YAML-спецификаций.

Одна `.yaml`-спецификация позволяет получить Python-парсеры, Wireshark-диссекторы, mock runtime, Scapy Layer 2 demo, TCP Layer 3 demo, тестовые наборы и документацию из одного источника правды.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#состояние-проекта)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20critical__modules-brightgreen)](#состояние-проекта)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#установка)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Зачем protocollab?

Большинство инструментов сериализации ориентированы на данные или RPC. `protocollab` ориентирован на протокол как на главный артефакт: вокруг спецификации строятся валидация, генерация, demo-сценарии и сопутствующий tooling.

| Возможность | Protobuf / Thrift | Kaitai Struct | protocollab |
|---|---|---|---|
| Protocol-first workflow | Нет | Частично | Да |
| Генерация Wireshark-диссекторов | Нет | Да | Да |
| Генерация Python-парсеров | Да | Да | Да |
| Валидация через JSON Schema | Нет | Нет | Да |
| Защищённый YAML loader | Нет | Нет | Да |
| Готовые demo runtime | Нет | Нет | Да |
| Roadmap для stateful-протоколов | Ограниченно | Нет | Планируется |

---

## Что Входит

- Безопасный YAML-формат для описания протоколов
- CLI-команды для загрузки, валидации и генерации артефактов из спецификации
- Отдельный пакет `yaml_serializer` для защищённой обработки YAML
- Отдельный пакет `jsonschema_validator` для подключаемой валидации JSON Schema
- Генераторы Python-парсеров, Wireshark Lua-диссекторов, mock runtime, L2 Scapy runtime и L3 socket runtime
- Demo workflow, которые проверяют полный путь от спецификации до готовых артефактов

---

## Репозиторий Спецификаций

Community-driven репозиторий спецификаций доступен здесь: [protocollab-specs](https://github.com/cherninkiy/protocollab-specs).

Репозиторий `protocollab-specs` — это центральная курируемая коллекция YAML-описаний протоколов, совместимых с `protocollab`. Каждую спецификацию можно валидировать, версионировать и использовать для генерации парсеров, Wireshark-диссекторов и тестовых наборов.

Используйте `protocollab`, когда нужен сам фреймворк и генераторы. Используйте `protocollab-specs`, когда нужен каталог переиспользуемых спецификаций, поддерживаемый сообществом.

---

## Быстрый Старт

### Установка

```bash
git clone https://github.com/cherninkiy/protocollab
cd protocollab

poetry install

# Optional backend-ы JSON Schema для полного validator test suite
poetry install --extras "validator-jsonscreamer validator-fastjsonschema"
```

`protocollab` использует Poetry для управления зависимостями. Основные и optional зависимости описаны в `pyproject.toml`.

Тесты optional backend-ов в `src/jsonschema_validator/tests/` автоматически пропускаются, если соответствующие extras не установлены.

### Написать Спецификацию

```yaml
meta:
  id: ping_protocol
  endian: le
  title: Ping Protocol
  description: Simple ICMP-like ping/pong protocol

seq:
  - id: type_id
    type: u1
    doc: Тип сообщения (0 = запрос, 1 = ответ)
  - id: sequence_number
    type: u4
    doc: Порядковый номер, переполнение при 2^32
  - id: payload_size
    type: u2
    doc: Размер полезной нагрузки после заголовка, в байтах
```

### Загрузить и Провалидировать

```bash
protocollab load examples/simple/ping_protocol.yaml --output-format json
protocollab validate examples/simple/ping_protocol.yaml
protocollab validate examples/simple/ping_protocol.yaml --strict
```

### Сгенерировать Артефакты

```bash
protocollab generate python examples/simple/ping_protocol.yaml --output build/
protocollab generate wireshark examples/simple/ping_protocol.yaml --output build/
protocollab generate mock-client examples/simple/ping_protocol.yaml --output build/
protocollab generate mock-server examples/simple/ping_protocol.yaml --output build/
protocollab generate l2-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l2-server examples/simple/ping_protocol.yaml --output build/
protocollab generate l3-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l3-server examples/simple/ping_protocol.yaml --output build/
```

### Использовать Сгенерированный Парсер

```python
import io

from build.ping_protocol_parser import PingProtocol

data = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x40, 0x00])
proto = PingProtocol.parse(io.BytesIO(data))
print(proto.type_id, proto.sequence_number, proto.payload_size)
```

---

## Замечания По Спецификациям

Через `instances:` можно объявлять виртуальные поля Wireshark, если запись содержит выражение `value:` и блок `wireshark:`.

- Используйте `wireshark.type: bool` вместе с `filter-only: true` для shortcut-полей вроде `myproto.lan`
- Используйте `wireshark.type: string` для summary-полей вроде `myproto.scope == "lan"`

Актуальные примеры:

- `examples/simple/ip_scoped_packet.yaml` для одного поля `scope`
- `examples/simple/ip_scoped_frame.yaml` для раздельных фильтров `src_scope` и `dst_scope`

---

## Состояние Проекта

Критические модули сейчас имеют полное покрытие, а основные CLI- и generator-workflow уже реализованы.

| Область | Статус | Примечания |
|---|---|---|
| `yaml_serializer` | Stable | Безопасный YAML loader, `!include`, сохранение форматирования, 100% покрытие |
| `jsonschema_validator` | Stable | Подключаемые backend-ы, единая модель ошибок, безопасный auto mode, 100% покрытие |
| `protocollab.loader` | Available | Безопасная загрузка, кэширование, интеграция через session-based API |
| `protocollab.validator` | Available | Базовая и строгая валидация схем через facade backend selection |
| `protocollab.generators` | Available | Генераторы Python, Wireshark, mock, L2 и L3 |
| CLI | Available | Команды `load`, `validate`, `generate` |
| Demo workflow | Available | `demo/mock`, `demo/l2`, `demo/l3` |

---

## Demo Workflows

В репозитории есть три demo entrypoint для одной и той же спецификации `examples/simple/ping_protocol.yaml`.

- `demo/mock` генерирует парсер и queue-based runtime `MockClient` и `MockServer`
- `demo/l2` генерирует парсер, `L2ScapyClient`, `L2ScapyServer` и Wireshark Lua-диссектор
- `demo/l3` генерирует парсер, `L3SocketClient`, `L3SocketServer` и Wireshark Lua-диссектор

Команды для проверки:

- `python demo/mock/demo.py check`
- `python demo/l2/demo.py check`
- `python demo/l3/demo.py check`

Команды для живых transport demo:

- `python demo/l2/demo.py run --iface <name>`
- `python demo/l3/demo.py run`

---

## Структура Репозитория

```text
src/
|-- yaml_serializer/          # Безопасная загрузка YAML и round-trip сохранение
|-- jsonschema_validator/     # Подключаемый фасад для валидации JSON Schema
`-- protocollab/              # CLI, loader, validator, generator, utilities

demo/
|-- mock/                     # Queue-based generated runtime demo
|-- l2/                       # Scapy Layer 2 generated runtime demo
`-- l3/                       # TCP Layer 3 generated runtime demo

examples/
|-- simple/                   # Однофайловые описания протоколов
`-- with_includes/            # Многофайловые примеры с !include

docs/
`-- adr/                      # Architecture decision records
```

Высокоуровневая цепочка зависимостей:

```text
CLI
|-- protocollab.loader      -> yaml_serializer
|-- protocollab.validator   -> jsonschema_validator
`-- protocollab.generators  -> Jinja2 templates
```

---

## Технологический Стек

| Область | Инструмент |
|---|---|
| Язык | Python 3.10+ |
| YAML processing | ruamel.yaml |
| CLI | Click 8.x |
| Валидация схем | jsonschema, jsonscreamer, fastjsonschema |
| Шаблоны | Jinja2 3.x |
| Модели | Pydantic v2 |
| Сборка | Poetry |
| Тестирование | pytest, pytest-cov |

---

## Запуск Тестов

```bash
poetry run pytest src/ -q
poetry run pytest src/yaml_serializer/tests/ --cov=yaml_serializer --cov-report=term-missing
poetry run pytest src/jsonschema_validator/tests/ --cov=jsonschema_validator --cov-report=term-missing
poetry run pytest src/protocollab/tests/ --cov=protocollab --cov-report=term-missing
```

---

## Roadmap

### Ближайшие Шаги

- Примитивные и пользовательские типы в `protocollab.core`
- Разрешение импортов между файлами
- Безопасный движок выражений без `eval`
- Семантическая валидация
- Ранняя поддержка генерации C++

### Дальше

- Stateful-протоколы с flat FSM в Community Edition
- Hierarchical statecharts в Pro
- Дополнительные генераторы для C++, Rust и Java
- Генерация тестов и фаззинг
- Система плагинов и enterprise-интеграции

---

## Community Edition vs Pro

| Возможность | Community | Pro | Enterprise |
|---|---|---|---|
| Генерация Python и Lua | Да | Да | Да |
| Mock, L2 и L3 demo runtime | Да | Да | Да |
| Базовая и строгая валидация схем | Да | Да | Да |
| Flat FSM | Планируется | Да | Да |
| Генераторы C++, Rust, Java | Нет | Да | Да |
| Hierarchical statecharts | Нет | Да | Да |
| Генерация тестов и фаззинг | Нет | Да | Да |
| Кастомные генераторы и CI/CD actions | Нет | Нет | Да |

---

## Участие В Разработке

Вклад приветствуется. Перед открытием pull request ознакомьтесь с [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

1. Сделайте fork репозитория.
2. Создайте feature-ветку от `dev`.
3. Добавьте или обновите тесты под свои изменения.
4. Запустите релевантный локальный test suite.
5. Откройте pull request в `dev`.

Ветка разработки: [github.com/cherninkiy/protocollab/tree/dev](https://github.com/cherninkiy/protocollab/tree/dev)

---

## Лицензия

[Apache 2.0](LICENSE)
