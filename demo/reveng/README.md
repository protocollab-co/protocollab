# protocollab — демонстрация реверс-инжиниринга

Эта папка содержит самодостаточное демо для четырёх кейсов
реверс-инжиниринга сетевых протоколов с помощью **protocollab ≥ 0.1.0**.

Каждый кейс включает:
- YAML-спецификацию протокола,
- синтетический дамп (`sample.pcap`) — включён в репозиторий, работает сразу,
- опционально: реальный публичный дамп (`real_sample.pcap` / `real_sample.pcapng`) — скачивается командой `make fetch-samples` (не включён в репозиторий),
- описание ожидаемого поведения (`expected.txt`).

---

## Кейсы

### 1. `ip_scoped` — классификация IP-адресов по области видимости

Разбирает минимальный IPv4-подобный кадр и вычисляет поля `src_scope` /
`dst_scope` со значениями `"lan"`, `"nat"` или `"inet"`.  
Позволяет фильтровать пакеты по типу источника/назначения прямо в
Wireshark.

### 2. `session_id` — симметричный идентификатор сессии

Читает src_ip, dst_ip и service_port и вычисляет симметричный ключ сессии
через XOR (`src_ip ^ dst_ip`). Для пакетов A→B и B→A ключ одинаков, что
позволяет группировать двусторонний трафик одним Wireshark-фильтром.

### 3. `tls_weak_cipher` — обнаружение слабых TLS-шифров

Разбирает упрощённый заголовок ClientHello и поднимает флаг
`has_weak_cipher`, если предложенный шифр входит в список известно
небезопасных (RC4 и т.д.). Полезно для быстрого аудита трафика.

### 4. `tls_sni_analysis` — анализ SNI и обнаружение аномалий

Читает поле SNI из упрощённого ClientHello и классифицирует имя хоста
по длине: `"Short"`, `"Medium"` или `"Long/Anomaly"`. Аномально длинные
имена (> 20 символов) сигнализируют о возможном DNS-туннелировании или
DGA-трафике.

---

## Требования

| Компонент | Минимальная версия |
|-----------|-------------------|
| protocollab | **≥ 0.1.0** |
| Python | ≥ 3.10 |
| Wireshark | ≥ 4.0 (для Lua 5.4) |

Установка protocollab (из корня репозитория):

```bash
pip install -e .
# или через Poetry:
poetry install
```

---

## Генерация диссекторов

```bash
cd demo/reveng
make all
# или вручную:
./tools/generate_all.sh
```

Сгенерированные `.lua`-файлы появятся в папке `results/`.

---

## Запуск Wireshark

### Через Makefile

```bash
make wireshark-ip         # ip_scoped
make wireshark-session    # session_id
make wireshark-tls-weak   # tls_weak_cipher
make wireshark-tls-sni    # tls_sni_analysis
```

### Вручную

```bash
wireshark -r ip_scoped/sample.pcap       -X lua_script:results/ip_scoped.lua
wireshark -r session_id/sample.pcap      -X lua_script:results/session_demo.lua
wireshark -r tls_weak_cipher/sample.pcap -X lua_script:results/tls_weak_cipher.lua
wireshark -r tls_sni_analysis/sample.pcap -X lua_script:results/tls_sni_analysis.lua
```

> **Совет.** Если Wireshark не применяет диссектор автоматически,
> щёлкните правой кнопкой по пакету → *Decode As…* → выберите
> соответствующий протокол.

---

## Автоматические тесты (tshark)

Скрипт `tools/test_dissectors.sh` запускает tshark против каждого
синтетического `sample.pcap` с соответствующим Lua-диссектором и проверяет:

- **значения полей** (строки, например `src_scope`, `sni_category`) — совпадают
  с ожидаемыми для каждого пакета;
- **счётчики фильтров** — количество пакетов, соответствующих каждому
  display-filter из `expected.txt`, совпадает с ожидаемым;
- **симметрию сессий** — ключ сессии одинаков для пакетов A→B и B→A.

### Запуск

```bash
cd demo/reveng
make test          # генерирует диссекторы (если нужно) и запускает тесты
# или напрямую:
./tools/test_dissectors.sh
```

### Вывод при успехе

```
==> ip_scoped
  PASS  src_scope per-frame  (5 frame(s), field: ip_scoped.src_scope)
  PASS  dst_scope per-frame  (5 frame(s), field: ip_scoped.dst_scope)
  PASS  src_scope=="lan"  → 2  (filter: ip_scoped.src_scope == "lan"  →  2 frame(s))
  ...
Results:  24 passed  0 failed  0 skipped
```

### Требования

| Компонент | Минимальная версия |
|-----------|-------------------|
| tshark | ≥ 3.0 (часть пакета Wireshark) |

```bash
# Ubuntu/Debian
sudo apt-get install tshark
# macOS
brew install wireshark
# Fedora/RHEL
sudo dnf install wireshark-cli
```

Если tshark не установлен, скрипт сообщает об этом и завершается с кодом 0
(тесты пропущены), не ломая CI.

---

## Проверка фильтров

Для каждого кейса смотрите файл `expected.txt` с конкретными
display-фильтрами и ожидаемым набором пакетов.

| Кейс | Файл |
|------|------|
| ip_scoped | [ip_scoped/expected.txt](ip_scoped/expected.txt) |
| session_id | [session_id/expected.txt](session_id/expected.txt) |
| tls_weak_cipher | [tls_weak_cipher/expected.txt](tls_weak_cipher/expected.txt) |
| tls_sni_analysis | [tls_sni_analysis/expected.txt](tls_sni_analysis/expected.txt) |

---

## Структура папки

```
demo/reveng/
├── README.md
├── Makefile
├── .gitignore
├── ip_scoped/
│   ├── ip_scoped.yaml        ← спецификация протокола
│   ├── sample.pcap           ← 5 синтетических пакетов (в git)
│   ├── real_sample.pcap      ← реальный дамп (скачивается, не в git)
│   └── expected.txt          ← описание фильтров и ожидаемый вывод
├── session_id/
│   ├── session_id.yaml
│   ├── sample.pcap           ← 4 пакета (2 двунаправленных потока, в git)
│   ├── real_sample.pcap      ← реальный дамп (не в git)
│   └── expected.txt
├── tls_weak_cipher/
│   ├── tls_handshake_mini.yaml  ← справочная спецификация
│   ├── tls_weak_cipher.yaml     ← рабочая спецификация
│   ├── sample.pcap              ← 2 пакета: слабый и нормальный шифр (в git)
│   ├── real_sample.pcapng       ← реальный TLS-дамп (не в git)
│   └── expected.txt
├── tls_sni_analysis/
│   ├── tls_handshake_mini.yaml  ← справочная спецификация
│   ├── tls_sni_analysis.yaml    ← рабочая спецификация
│   ├── sample.pcap              ← 3 пакета с разными SNI (в git)
│   ├── real_sample.pcapng       ← реальный TLS-дамп (не в git)
│   └── expected.txt
├── tools/
│   ├── generate_all.sh       ← генерирует все диссекторы
│   ├── run_wireshark.sh      ← открывает Wireshark для кейса
│   ├── test_dissectors.sh    ← автоматические тshark-тесты
│   ├── fetch_samples.sh      ← скачивает реальные pcap из публичных источников
│   └── make_samples.py       ← пересоздаёт синтетические sample.pcap
└── results/                  ← сюда пишутся .lua (не в git)
```

---

## Реальные примеры трафика

Кроме синтетических `sample.pcap` (которые точно соответствуют спецификации и
включены в репозиторий), можно скачать настоящие захваты из публичных
источников для более реалистичного тестирования.

### Скачать одной командой

```bash
cd demo/reveng
make fetch-samples
```

Скрипт скачивает:

| Файл | Источник | Кейсы |
|------|----------|-------|
| `ip_scoped/real_sample.pcap` | Wireshark SampleCaptures — `ipv4frags.pcap` | ip_scoped, session_id |
| `tls_weak_cipher/real_sample.pcapng` | Lekensteyn/wireshark-notes — `imap-ssl.pcapng` | tls_weak_cipher, tls_sni_analysis |

Если автоматическая загрузка недоступна, скачайте файлы вручную:

```bash
# IPv4 дамп (ip_scoped и session_id):
curl -L -o ip_scoped/real_sample.pcap \
  "https://wiki.wireshark.org/SampleCaptures?action=AttachFile&do=get&target=ipv4frags.pcap"
cp ip_scoped/real_sample.pcap session_id/real_sample.pcap

# TLS дамп (tls_weak_cipher и tls_sni_analysis):
curl -L -o tls_weak_cipher/real_sample.pcapng \
  "https://github.com/Lekensteyn/wireshark-notes/raw/master/tls/imap-ssl.pcapng"
cp tls_weak_cipher/real_sample.pcapng tls_sni_analysis/real_sample.pcapng
```

### Открыть реальный дамп в Wireshark

```bash
# С диссектором (после make all):
wireshark -r ip_scoped/real_sample.pcap        -X lua_script:results/ip_scoped.lua
wireshark -r tls_weak_cipher/real_sample.pcapng -X lua_script:results/tls_weak_cipher.lua

# Без диссектора (нативный Wireshark TLS-разбор):
wireshark -r tls_weak_cipher/real_sample.pcapng
```

> **Примечание.** Синтетические `sample.pcap` разработаны специально под
> поля YAML-спецификаций (custom DLT_USER0 frames). Реальные дампы содержат
> настоящие Ethernet/IP/TCP-кадры: Wireshark-диссектор применяется к ним
> как пользовательский overlay и читает первые N байт полезной нагрузки.
> Результат полезен для изучения принципов работы, а не как продакшн-парсер.

---

## Воспроизведение синтетических дампов

Файлы `sample.pcap` включены в репозиторий и всегда актуальны.
При необходимости пересоздать их:

```bash
make make-samples
# или вручную:
python tools/make_samples.py
```

Скрипт `tools/make_samples.py` использует только стандартную библиотеку
Python и полностью воспроизводит каждый пакет по спецификации.
