# L2 Demo

## English

This folder contains an independent Scapy-based Layer 2 demo for the generated parser, L2 runtime, and Wireshark dissector.

Generated files are written to `demo/l2/generated` and are intentionally not stored in the repository.
Only `demo/l2/generated/.gitkeep` is tracked.

### Prerequisites

- Use the repository Poetry environment
- Install the project and the optional L2 demo dependency from the repository root:

```bash
poetry install --extras "demo-l2"
```

- The live L2 demo requires a real network interface and permissions suitable for Scapy raw Ethernet traffic

### Commands

- Generate artefacts:

```bash
python demo/l2/demo.py generate
```

- Run the live L2 demo on a specific interface:

```bash
python demo/l2/demo.py run --iface eth0
```

- Regenerate and then run:

```bash
python demo/l2/demo.py run --generate --iface eth0
```

- Run demo tests:

```bash
python demo/l2/demo.py tests
```

- Run the full demo workflow without live traffic:

```bash
python demo/l2/demo.py check
```

- Run the full demo workflow including the live Scapy exchange:

```bash
python demo/l2/demo.py check --iface eth0
```

### What `check` does

The `check` command always performs these steps:

1. Generates a fresh Python parser, `L2ScapyClient`, `L2ScapyServer`, and Wireshark Lua dissector into `demo/l2/generated`
2. Runs the demo test suite

If `--iface` is provided, it also runs a live Scapy Layer 2 ping/pong exchange.

### Notes

- The demo uses `examples/simple/ping_protocol.yaml`
- The generated runtime files are `ping_protocol_l2_client.py` and `ping_protocol_l2_server.py`
- The generated dissector file is `demo/l2/generated/ping_protocol.lua`
- The generated directory is cleaned before regeneration
- This demo is intentionally not part of CI because it depends on a real interface and raw-packet privileges

### Wireshark

- Load `demo/l2/generated/ping_protocol.lua` into Wireshark after running `generate` or `check`
- Capture traffic on the same interface passed via `--iface`
- If Wireshark does not decode frames automatically, use `Decode As...` for EtherType `0x88B5`

## Русский

Эта папка содержит независимое Scapy-based Layer 2 демо для сгенерированных парсера, L2 runtime и Wireshark-диссектора.

Сгенерированные файлы записываются в `demo/l2/generated` и намеренно не хранятся в репозитории.
В git отслеживается только `demo/l2/generated/.gitkeep`.

### Предварительные условия

- Используйте Poetry-окружение репозитория
- Установите проект и optional зависимость для L2 demo из корня репозитория:

```bash
poetry install --extras "demo-l2"
```

- Для живого L2-демо нужен реальный сетевой интерфейс и права, достаточные для raw Ethernet трафика через Scapy

### Команды

- Сгенерировать артефакты:

```bash
python demo/l2/demo.py generate
```

- Запустить живое L2-демо на конкретном интерфейсе:

```bash
python demo/l2/demo.py run --iface eth0
```

- Перегенерировать артефакты и затем запустить демо:

```bash
python demo/l2/demo.py run --generate --iface eth0
```

- Запустить тесты демо:

```bash
python demo/l2/demo.py tests
```

- Выполнить полный сценарий без живого L2-обмена:

```bash
python demo/l2/demo.py check
```

- Выполнить полный сценарий вместе с живым Scapy-обменом:

```bash
python demo/l2/demo.py check --iface eth0
```

### Что делает `check`

Команда `check` всегда делает следующее:

1. Генерирует свежий Python-парсер, `L2ScapyClient`, `L2ScapyServer` и Wireshark Lua-диссектор в `demo/l2/generated`
2. Запускает набор тестов для демо

Если передан `--iface`, команда также запускает живой Layer 2 ping/pong обмен через Scapy.

### Примечания

- Демо использует `examples/simple/ping_protocol.yaml`
- Сгенерированные runtime-файлы: `ping_protocol_l2_client.py` и `ping_protocol_l2_server.py`
- Сгенерированный файл диссектора: `demo/l2/generated/ping_protocol.lua`
- Перед новой генерацией каталог `generated` очищается
- Это демо намеренно не входит в CI, потому что зависит от реального интерфейса и прав на raw пакеты

### Wireshark

- Подключите `demo/l2/generated/ping_protocol.lua` в Wireshark после `generate` или `check`
- Захватывайте трафик на том же интерфейсе, который передаётся через `--iface`
- Если Wireshark не декодирует кадры автоматически, используйте `Decode As...` для EtherType `0x88B5`