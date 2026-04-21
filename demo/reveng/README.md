# demo/reveng workflow

Папка содержит автоматизированный workflow для демонстрационных кейсов:

- `ip_scoped`
- `session_id`
- `tls_weak_cipher`
- `tls_sni_analysis`

## Requirements

- `pc` in `PATH` (preferred CLI entrypoint installed by this repo)
- `wireshark` in `PATH` for GUI launch
- `tshark` in `PATH` for automated assertions

Если CLI ещё не установлен:

```bash
cd ../..
pip install -e .
```

## Quick start

```bash
cd demo/reveng
./tools/generate_all.sh
./tools/test_dissectors.sh
```

Или через Makefile:

```bash
make all
```

Сгенерированные Lua-диссекторы пишутся в `results/`.

## Available scripts

```bash
./tools/fetch_samples.sh       # download public real_sample.* captures
./tools/make_samples.py        # regenerate synthetic sample.pcap fixtures
./tools/generate_all.sh        # generate Lua dissectors
./tools/test_dissectors.sh     # run tshark assertions for all cases
./tools/run_wireshark.sh ip_scoped
```

`generate_all.sh`, `test_dissectors.sh` и `run_wireshark.sh` already configure the required `DLT_USER0` mapping automatically.

## Open Wireshark

```bash
make wireshark-ip
make wireshark-session
make wireshark-tls-weak
make wireshark-tls-sni
```

## Download real pcaps

```bash
cd demo/reveng
./tools/fetch_samples.sh --force
```

Это создаёт `real_sample.*` в подпапках кейсов. Эти файлы игнорируются через `.gitignore`.

## Regenerate synthetic fixtures

```bash
cd demo/reveng
python tools/make_samples.py
```

Скрипт пересоздаёт tracked `sample.pcap` fixtures, которые используются `tshark`-тестами.

## Manual CI workflow

В репозитории есть отдельный manual-only GitHub Actions workflow:

- `.github/workflows/reveng-tshark.yml`

Он запускается только через `workflow_dispatch` и выполняет:

1. установку Poetry dependencies
2. установку `tshark`
3. генерацию Lua-диссекторов
4. запуск `./tools/test_dissectors.sh`

## Expected behavior

Используйте `expected.txt` в каждой подпапке кейса как краткую памятку по фильтрам и ожидаемым значениям.
