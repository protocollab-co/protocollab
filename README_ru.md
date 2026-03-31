# `protocollab`

> **Опиши один раз. Сгенерируй всё.**

`protocollab` — это open-source фреймворк для объявления, валидации и генерации реализаций **сетевых и бинарных протоколов** из человекочитаемых YAML-спецификаций.

Напишите один `.yaml`-файл → получите Python-парсеры, Wireshark-диссекторы, mock-, Scapy L2- и TCP L3-runtime для демо, тестовые наборы и документацию — всё из единого источника правды.

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#текущее-состояние)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20yaml__serializer-brightgreen)](#текущее-состояние)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#установка)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## Зачем `protocollab`?

Большинство инструментов сериализации (Protobuf, Thrift, FlatBuffers) ориентированы **на данные** или **на RPC**. `protocollab` ориентирован **на протокол**:

| Возможность | Protobuf / Thrift | Kaitai Struct | `protocollab` |
|---|---|---|---|
| Протоколы с состоянием (FSM) | Нет | Нет | Планируется (CE: плоский, Pro: иерархический) |
| Генерация Wireshark-диссекторов | Нет | Да | Да |
| Встроенная защита загрузчика | Нет | Нет | Да — многоуровневый загрузчик |
| Валидация спецификаций (JSON Schema) | Нет | Нет | Да |
| Генерация Python-парсеров | Да | Да | Да |
| Open-source сообщество | Да | Да | Да |

---

## Для кого?

- **Разработчики протоколов** — embedded, телеком, IoT, fintech
- **QA-инженеры** — автоматически сгенерированные тест-сьюты для проверки протоколов
- **Сетевые аналитики** — генерация Wireshark-диссекторов из спецификаций
- **Инженеры по данным** — структурированное извлечение данных из бинарных форматов (roadmap)

---

## Быстрый старт

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/cherninkiy/protocollab
cd protocollab

# 2. Создать и активировать окружение (необязательно, но рекомендуется)
python -m venv venv
source venv/bin/activate      # Linux / macOS
# venv\Scripts\activate       # Windows

# 3. Установить основные зависимости
pip install -r requirements.txt

# 4. Установить пакет в режиме разработки (редактируемый режим)
pip install -e .
```

> **Примечание:** Для разработки требуется установить дополнительные зависимости:
>
>     pip install -r requirements-dev.txt


Через `instances:` можно также объявлять виртуальные Wireshark-поля, если у
записи есть выражение `value:` и блок `wireshark:`. Используйте
`wireshark.type: bool` вместе с `filter-only: true` для shortcut-полей вроде
`myproto.lan`, а `wireshark.type: string` для summary-полей вроде
`myproto.scope == "lan"`.

В каталоге examples есть оба варианта: `examples/simple/ip_scoped_packet.yaml`
для одного поля `scope` и `examples/simple/ip_scoped_frame.yaml` для раздельных
фильтров `src_scope` / `dst_scope`.

### Написать спецификацию

```yaml
# examples/simple/ping_protocol.yaml
meta:
  id: ping_protocol
  endian: le
  title: "Ping Protocol"
  description: "Simple ICMP-like ping/pong protocol"

seq:
  - id: type_id
    type: u1
    doc: "Тип сообщения (0 = запрос, 1 = ответ)"
  - id: sequence_number
    type: u4
    doc: "Порядковый номер, переполнение при 2^32"
  - id: payload_size
    type: u2
    doc: "Размер полезной нагрузки после заголовка, в байтах"
```

### Загрузить и валидировать

```bash
# Загрузить и просмотреть (вывод в JSON или YAML)
protocollab load examples/simple/ping_protocol.yaml --output-format json

# Валидация по базовой схеме
protocollab validate examples/simple/ping_protocol.yaml

# Строгая валидация (без неизвестных полей)
protocollab validate examples/simple/ping_protocol.yaml --strict
```

### Сгенерировать код

```bash
# Python dataclass-парсер
protocollab generate python examples/simple/ping_protocol.yaml --output build/

# Wireshark Lua-диссектор
protocollab generate wireshark examples/simple/ping_protocol.yaml --output build/

# Mock runtime на очередях
protocollab generate mock-client examples/simple/ping_protocol.yaml --output build/
protocollab generate mock-server examples/simple/ping_protocol.yaml --output build/

# TCP L3 socket runtime
protocollab generate l3-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l3-server examples/simple/ping_protocol.yaml --output build/

# Scapy L2 runtime
protocollab generate l2-client examples/simple/ping_protocol.yaml --output build/
protocollab generate l2-server examples/simple/ping_protocol.yaml --output build/
```

```python
# Использование сгенерированного парсера
from build.ping_protocol_parser import PingProtocol
import io

data = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x40, 0x00])
proto = PingProtocol.parse(io.BytesIO(data))
print(proto.type_id, proto.sequence_number, proto.payload_size)
```

---

## Текущее состояние

**Фаза 1 завершена.** Набор тестов проходит.

| Компонент | Статус | Примечания |
|---|---|---|
| `yaml_serializer` | ✅ 100% покрытие | Защищённый YAML-загрузчик: `!include`, лимиты глубины/размера, защита от path traversal и Billion Laughs |
| `protocollab.loader` | ✅ | `load_protocol()`, `get_global_loader()`, `configure_global()`, `ProtocolLoader`, LRU `MemoryCache` |
| `protocollab.validator` | ✅ | JSON Schema Draft 7, схемы `base` и `strict` |
| `protocollab.generators` | ✅ | Python-парсер, Wireshark-диссектор, mock client/server, L2 Scapy client/server, L3 socket client/server, Jinja2 |
| CLI `protocollab load` | ✅ | `--output-format json\|yaml`, `--no-cache`, флаги безопасности |
| CLI `protocollab validate` | ✅ | `--strict`, `--schema`, коды выхода 0/1/2/3 |
| CLI `protocollab generate` | ✅ | `generate python\|wireshark\|mock-client\|mock-server\|l2-client\|l2-server\|l3-client\|l3-server FILE -o DIR`, коды выхода 0/1/2/4 |
| Примеры | ✅ | `examples/simple/` — ping-протокол, Ethernet-фрейм |
| Демо-сценарии | ✅ | `demo/mock` для очередей, `demo/l2` для Scapy L2, `demo/l3` для TCP + Wireshark |
| Тесты — `yaml_serializer` | ✅ | 100% покрытие |
| Тесты — `protocollab` | ✅ | loader, cache, utils, CLI, validator, generators |
| **Набор тестов** | ✅ | Все проходят |

## Демо-сценарии

В репозитории есть три demo entrypoint для одной и той же спецификации `examples/simple/ping_protocol.yaml`:

- `demo/mock` генерирует парсер и queue-based runtime `MockClient` / `MockServer`, а полный сценарий проверяется командой `python demo/mock/demo.py check`
- `demo/l2` — это рабочее Scapy Layer 2 демо: оно генерирует парсер, `L2ScapyClient` / `L2ScapyServer` и Wireshark Lua-диссектор; локальная проверка выполняется через `python demo/l2/demo.py check`, а живой обмен запускается командой `python demo/l2/demo.py run --iface <name>`
- `demo/l3` генерирует парсер, TCP runtime `L3SocketClient` / `L3SocketServer` и Wireshark Lua-диссектор, а полный сценарий проверяется командой `python demo/l3/demo.py check`

**Рабочие transport demo:** `demo/l2` покрывает живой Scapy-based Layer 2 обмен, а `demo/l3` покрывает localhost TCP обмен и разбор в Wireshark.

**Защищённый YAML-загрузчик**: модуль `yaml_serializer` защищён от распространённых атак: защита от YAML bombs (Billion Laughs-style расширение алиасов/якорей YAML), path traversal в `!include`, ограничения глубины рекурсии и размера файлов. Это обеспечивает безопасную обработку недоверенных спецификаций.

### Фаза 2 (в разработке)
- Система типов: примитивные и пользовательские типы (`protocollab.core`)
- Разрешение импортов между файлами
- Движок выражений (безопасный, без `eval`)
- Семантическая валидация
- Генерация кода на C++ (превью)

### Фаза 3+ (roadmap)
- Протоколы с состоянием — плоский FSM (Community), иерархические statecharts (Pro)
- Генераторы для C++ / Rust / Java (Pro)
- Автоматическая генерация тестов и фаззинг (Pro)
- Система плагинов (Enterprise)

---

## Архитектура

```
src/
├── yaml_serializer/          # Защищённый YAML-загрузчик (подмодуль)
│   ├── serializer.py         # SerializerSession — основной API
│   ├── safe_constructor.py   # Ограничения безопасности
│   ├── utils.py              # canonical_repr, is_path_within_root, ...
│   ├── merge.py              # Слияние деревьев !include
│   └── modify.py             # Мутации структуры
│
└── protocollab/              # Основной пакет
    ├── main.py               # CLI (Click): load | validate | generate
    ├── exceptions.py         # FileLoadError (выход 1), YAMLParseError (выход 2)
    ├── loader/               # load_protocol(), get_global_loader(), configure_global(), LRU MemoryCache
    ├── validator/            # validate_protocol() + JSON Schema
    │   └── schemas/
    │       ├── base.schema.json      # разрешающая, совместимая с KSY
    │       └── protocol.schema.json  # строгая (additionalProperties: false)
    ├── generators/           # generate() + parser/dissector/mock/L2/L3 generators
    │   └── templates/
    │       ├── python/parser.py.j2
    │       ├── python/mock_client.py.j2
    │       ├── python/mock_server.py.j2
    │       ├── python/l2_client.py.j2
    │       ├── python/l2_server.py.j2
    │       ├── python/l3_client.py.j2
    │       ├── python/l3_server.py.j2
    │       └── lua/dissector.lua.j2
    └── utils/                # resolve_path, to_json, to_yaml, print_data

  demo/
  ├── mock/                     # демо со сгенерированным queue-based runtime
  ├── l2/                       # демо со сгенерированным Scapy L2 runtime
  └── l3/                       # демо со сгенерированным TCP runtime и Wireshark

examples/
├── simple/                   # ping_protocol.yaml, ethernet_frame.yaml
└── with_includes/            # base_types.yaml, tcp_like.yaml
```

**Цепочка зависимостей:**
```
CLI (main.py)
 └─ protocollab.loader     ──→ yaml_serializer.serializer
 └─ protocollab.validator  ──→ jsonschema.Draft7Validator
 └─ protocollab.generators ──→ jinja2.Environment
```

---

## Стек технологий

| Область | Инструмент |
|---|---|
| Язык | Python 3.10+ |
| YAML-парсер | ruamel.yaml |
| CLI | Click 8.x |
| Валидация схем | jsonschema 4.x (Draft 7) |
| Генерация кода | Jinja2 3.x |
| Модели данных | Pydantic v2 |
| Сборка | pyproject.toml (Poetry) + setup.py |
| Тестирование | pytest + pytest-cov |

---

## Запуск тестов

```bash
# Все тесты с покрытием
pytest src/ -q

# Только yaml_serializer (100% покрытие)
pytest src/yaml_serializer/tests/ --cov=yaml_serializer --cov-report=term-missing

# Только protocollab
pytest src/protocollab/tests/ --cov=protocollab --cov-report=term-missing
```

---

## Community Edition vs Pro

| | Community (этот репозиторий) | Pro | Enterprise |
|---|---|---|---|
| Генерация Python + Lua | ✅ | ✅ | ✅ |
| Mock, L2 и L3 demo runtime | ✅ | ✅ | ✅ |
| Валидация базовой и строгой схемами | ✅ | ✅ | ✅ |
| Плоский FSM (≤10 состояний) | Планируется | ✅ | ✅ |
| Генерация C++ / Rust / Java | — | ✅ | ✅ |
| Иерархические statecharts | — | ✅ | ✅ |
| Генерация тестов + фаззинг | — | ✅ | ✅ |
| CI/CD actions, кастомные генераторы | — | — | ✅ |

---

## Участие в разработке

Вклад приветствуется! Пожалуйста, прочитайте [CONTRIBUTING.md](CONTRIBUTING.md) и следуйте нашему [Кодексу поведения](CODE_OF_CONDUCT.md).

1. Сделайте fork репозитория
2. Создайте ветку для своей фичи от `dev`: `git checkout -b feature/my-feature`
3. Напишите тесты для новой функциональности
4. Запустите полный тест-сьют: `pytest src/ -q`
5. Откройте Pull Request в ветку `dev`

Ветка разработки: `dev` · Remote: [github.com/cherninkiy/protocollab/tree/dev](https://github.com/cherninkiy/protocollab/tree/dev)

---

## Вдохновение

- [Kaitai Struct](https://kaitai.io/) — декларативное описание бинарных форматов
- [OpenAPI](https://www.openapis.org/) — specification-first дизайн API
- [Protocol Buffers](https://protobuf.dev/) — строгая типизация и генерация кода
- [Scapy](https://scapy.net/) — конструирование и тестирование протоколов
- [Harel statecharts](https://www.sciencedirect.com/science/article/pii/0167642387900359) — формализм реактивных систем

---

## Лицензия

[Apache 2.0](LICENSE)
