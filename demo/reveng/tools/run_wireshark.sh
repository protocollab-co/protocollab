#!/usr/bin/env bash
# run_wireshark.sh – open Wireshark for a specific demo case.
#
# Usage:  ./tools/run_wireshark.sh <case_name>
#
# <case_name> is one of:
#   ip_scoped
#   session_id
#   tls_weak_cipher
#   tls_sni_analysis
#
# Prerequisites:
#   • Run generate_all.sh first so that results/<case>.lua exists.
#   • Wireshark must be in PATH.

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEMO_DIR"

CASE="${1:-}"

if [ -z "$CASE" ]; then
    echo "Usage: $0 {ip_scoped|session_id|tls_weak_cipher|tls_sni_analysis}" >&2
    exit 1
fi

PCAP="${CASE}/sample.pcap"
LUA="results/${CASE}.lua"

if [ ! -f "$PCAP" ]; then
    echo "ERROR: PCAP file not found: $PCAP" >&2
    exit 1
fi

if [ ! -f "$LUA" ]; then
    echo "ERROR: Lua dissector not found: $LUA" >&2
    echo "       Run ./tools/generate_all.sh first." >&2
    exit 1
fi

echo "==> Opening Wireshark for case '${CASE}' …"
echo "    PCAP : ${PCAP}"
echo "    Lua  : ${LUA}"
echo ""
echo "    TIP: In Wireshark, right-click a packet → Decode As… and select"
echo "    the '${CASE}' dissector if frames are not decoded automatically."
echo ""

wireshark -r "$PCAP" -X "lua_script:${LUA}"
