# protocollab — демонстрация реверс-инжиниринга

Эта папка содержит самодостаточное демо для четырёх кейсов
реверс-инжиниринга сетевых протоколов с помощью **protocollab ≥ 0.1.0**.

Каждый кейс включает:
- YAML-спецификацию протокола,
- небольшой бинарный дамп (`sample.pcap`),
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
│   ├── sample.pcap           ← 5 демо-пакетов
│   └── expected.txt          ← описание фильтров и ожидаемый вывод
├── session_id/
│   ├── session_id.yaml
│   ├── sample.pcap           ← 4 пакета (2 двунаправленных потока)
│   └── expected.txt
├── tls_weak_cipher/
│   ├── tls_handshake_mini.yaml  ← справочная спецификация
│   ├── tls_weak_cipher.yaml     ← рабочая спецификация
│   ├── sample.pcap              ← 2 пакета: слабый и нормальный шифр
│   └── expected.txt
├── tls_sni_analysis/
│   ├── tls_handshake_mini.yaml  ← справочная спецификация
│   ├── tls_sni_analysis.yaml    ← рабочая спецификация
│   ├── sample.pcap              ← 3 пакета с разными SNI
│   └── expected.txt
├── tools/
│   ├── generate_all.sh       ← генерирует все диссекторы
│   └── run_wireshark.sh      ← открывает Wireshark для кейса
└── results/                  ← сюда пишутся .lua (не в git)
```

---

## Самостоятельная генерация PCAP-дампов

Дампы уже включены в репозиторий. При необходимости пересоздать их
самостоятельно используйте следующие команды Python (требуется только
стандартная библиотека):

```python
import struct

def pcap_header(link_type=147):  # DLT_USER0
    return struct.pack("<IHHiIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, link_type)

def pcap_packet(ts_sec, data):
    return struct.pack("<IIII", ts_sec, 0, len(data), len(data)) + data

# ip_scoped: version(u1) + src_ip(u4 BE) + dst_ip(u4 BE) + payload_size(u2 BE)
with open("ip_scoped/sample.pcap", "wb") as f:
    f.write(pcap_header())
    packets = [
        struct.pack(">BIIH", 1, 0xC0A80101, 0x08080808, 64),  # LAN->inet
        struct.pack(">BIIH", 1, 0x64400001, 0x08080808, 64),  # NAT->inet
        struct.pack(">BIIH", 1, 0x08080808, 0xC0A80101, 64),  # inet->LAN
        struct.pack(">BIIH", 1, 0xC0A80101, 0x0A000001, 64),  # LAN->LAN
        struct.pack(">BIIH", 1, 0x08080808, 0x64400001, 64),  # inet->NAT
    ]
    for i, pkt in enumerate(packets):
        f.write(pcap_packet(i + 1, pkt))
```

Аналогичные скрипты для остальных кейсов смотрите в комментариях к
соответствующим YAML-файлам.
