# L3 Demo

## English

This folder contains an independent TCP-based demo for the generated parser, L3 socket runtime, and Wireshark dissector.

Generated files are written to `demo/l3/generated` and are intentionally not stored in the repository.
Only `demo/l3/generated/.gitkeep` is tracked.

### Prerequisites

- Use the repository Poetry environment
- Install dependencies from the repository root:

```bash
poetry install
```

### Commands

- Generate artefacts:

```bash
python demo/l3/demo.py generate
```

- Run the TCP demo using already generated artefacts:

```bash
python demo/l3/demo.py run
```

- Regenerate and then run:

```bash
python demo/l3/demo.py run --generate
```

- Run demo tests:

```bash
python demo/l3/demo.py tests
```

- Run the full demo workflow in one command:

```bash
python demo/l3/demo.py check
```

### What `check` does

The `check` command performs three steps in order:

1. Generates a fresh Python parser, `L3SocketClient`, `L3SocketServer`, and Wireshark Lua dissector into `demo/l3/generated`
2. Runs a localhost TCP ping/pong exchange using the generated parser
3. Runs the demo test suite

### Notes

- The demo uses `examples/simple/ping_protocol.yaml`
- The generated runtime files are `ping_protocol_l3_client.py` and `ping_protocol_l3_server.py`
- The generated dissector file is `demo/l3/generated/ping_protocol.lua`
- The generated directory is cleaned before regeneration
- CI validates this workflow through the same single entry point

### Wireshark

- Capture the localhost TCP exchange in Wireshark and load the generated Lua file
- If Wireshark does not decode the stream automatically, use `Decode As...` for the demo TCP port

## Русский

Эта папка содержит независимое TCP-демо для сгенерированных парсера, L3 socket runtime и Wireshark-диссектора.

Сгенерированные файлы записываются в `demo/l3/generated` и намеренно не хранятся в репозитории.
В git отслеживается только `demo/l3/generated/.gitkeep`.

### Предварительные условия

- Используйте Poetry-окружение репозитория
- Установите зависимости из корня репозитория:

```bash
poetry install
```

### Команды

- Сгенерировать артефакты:

```bash
python demo/l3/demo.py generate
```

- Запустить TCP-демо, используя уже сгенерированные артефакты:

```bash
python demo/l3/demo.py run
```

- Перегенерировать артефакты и затем запустить демо:

```bash
python demo/l3/demo.py run --generate
```

- Запустить тесты демо:

```bash
python demo/l3/demo.py tests
```

- Выполнить весь сценарий демо одной командой:

```bash
python demo/l3/demo.py check
```

### Что делает `check`

Команда `check` последовательно выполняет три шага:

1. Генерирует свежий Python-парсер, `L3SocketClient`, `L3SocketServer` и Wireshark Lua-диссектор в `demo/l3/generated`
2. Запускает localhost TCP ping/pong обмен с использованием сгенерированного парсера
3. Запускает набор тестов для демо

### Примечания

- Демо использует `examples/simple/ping_protocol.yaml`
- Сгенерированные runtime-файлы: `ping_protocol_l3_client.py` и `ping_protocol_l3_server.py`
- Сгенерированный файл диссектора: `demo/l3/generated/ping_protocol.lua`
- Перед новой генерацией каталог `generated` очищается
- CI проверяет этот сценарий через ту же единую точку входа

### Wireshark

- Захватите localhost TCP обмен в Wireshark и подключите сгенерированный Lua-файл
- Если Wireshark не распознает поток автоматически, используйте `Decode As...` для TCP-порта демо