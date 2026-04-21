# demo/reveng workflow

Папка содержит автоматизированный workflow для демонстрационных кейсов:

- `ip_scoped`
- `session_id`
- `tls_weak_cipher`
- `tls_sni_analysis`

## Требования

- `protocollab` в `PATH`
- `wireshark` в `PATH`

Если `protocollab` не установлен:

```bash
cd ../..
pip install -e .
```

## Быстрый старт

```bash
cd demo/reveng
make all
```

Команда создаст Lua-диссекторы в `results/`.

## Открытие Wireshark

```bash
make wireshark-ip
make wireshark-session
make wireshark-tls-weak
make wireshark-tls-sni
```

## Загрузка реальных pcap

```bash
cd demo/reveng
curl -L -o ip_scoped/sample.pcap "https://wiki.wireshark.org/SampleCaptures?action=raw&download=ipv4frags.pcap"
cp ip_scoped/sample.pcap session_id/sample.pcap

curl -L -o tls_weak_cipher/sample.pcap "https://github.com/Lekensteyn/wireshark-notes/raw/master/tls/http2-16-ssl.pcapng" || \
curl -L -o tls_weak_cipher/sample.pcap "https://raw.githubusercontent.com/Lekensteyn/wireshark-notes/master/tls/http2-16-ssl.pcapng" || \
curl -L -o tls_weak_cipher/sample.pcap "https://github.com/Lekensteyn/wireshark-notes/raw/master/tls/imap-ssl.pcapng"

cp tls_weak_cipher/sample.pcap tls_sni_analysis/sample.pcap
```

## Проверка ожидаемого поведения

Используйте `expected.txt` в каждой подпапке кейса.
