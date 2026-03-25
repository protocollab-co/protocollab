# Mock Demo

## English

This folder contains an independent queue-based demo for the generated parser, mock client, and mock server.

Generated files are written to `demo/mock/generated` and are intentionally not stored in the repository.
Only `demo/mock/generated/.gitkeep` is tracked.

### Prerequisites

- Use a Python virtual environment for the repository
- Install the project in editable mode so `python -m protocollab` works:

```bash
pip install -e .
```

### Commands

- Generate artefacts:

```bash
python demo/mock/demo.py generate
```

- Run the demo using already generated artefacts:

```bash
python demo/mock/demo.py run
```

- Regenerate and then run:

```bash
python demo/mock/demo.py run --generate
```

- Run demo tests:

```bash
python demo/mock/demo.py tests
```

- Run the full demo workflow in one command:

```bash
python demo/mock/demo.py check
```

### What `check` does

The `check` command performs three steps in order:

1. Generates a fresh Python parser, `MockClient`, and `MockServer` into `demo/mock/generated`
2. Runs the queue-based mock demo
3. Runs the demo test suite

### Notes

- The demo uses `examples/simple/ping_protocol.yaml`
- The generated runtime files are `ping_protocol_mock_client.py` and `ping_protocol_mock_server.py`
- The generated directory is cleaned before regeneration
- CI validates this workflow through the same single entry point

## Русский

Эта папка содержит независимое queue-based демо для сгенерированных парсера, mock-клиента и mock-сервера.

Сгенерированные файлы записываются в `demo/mock/generated` и намеренно не хранятся в репозитории.
В git отслеживается только `demo/mock/generated/.gitkeep`.

### Предварительные условия

- Используйте Python virtual environment в корне репозитория
- Установите проект в editable-режиме, чтобы работал `python -m protocollab`:

```bash
pip install -e .
```

### Команды

- Сгенерировать артефакты:

```bash
python demo/mock/demo.py generate
```

- Запустить демо, используя уже сгенерированные артефакты:

```bash
python demo/mock/demo.py run
```

- Перегенерировать артефакты и затем запустить демо:

```bash
python demo/mock/demo.py run --generate
```

- Запустить тесты демо:

```bash
python demo/mock/demo.py tests
```

- Выполнить весь сценарий демо одной командой:

```bash
python demo/mock/demo.py check
```

### Что делает `check`

Команда `check` последовательно выполняет три шага:

1. Генерирует свежий Python-парсер, `MockClient` и `MockServer` в `demo/mock/generated`
2. Запускает queue-based демо
3. Запускает набор тестов для демо

### Примечания

- Демо использует `examples/simple/ping_protocol.yaml`
- Сгенерированные runtime-файлы: `ping_protocol_mock_client.py` и `ping_protocol_mock_server.py`
- Перед новой генерацией каталог `generated` очищается
- CI проверяет этот сценарий через ту же единую точку входа
