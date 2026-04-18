#!/usr/bin/env bash
# test_dissectors.sh – automated tshark tests for all demo/reveng Lua dissectors.
#
# For each of the four demo cases the script:
#   1. Reads field values from sample.pcap using tshark + the generated Lua
#      dissector and verifies they match the values described in expected.txt.
#   2. Counts the frames matched by representative Wireshark display filters
#      and verifies the counts against the expected numbers.
#
# Usage:
#   ./tools/test_dissectors.sh
#   Run from demo/reveng/ or any location; the script always operates
#   relative to its own parent directory.
#
# Prerequisites:
#   tshark ≥ 3.0 must be in PATH (part of the Wireshark package).
#   If tshark is not found, all tests are reported as skipped and the
#   script exits with code 0 so CI pipelines are not broken.
#   Run ./tools/generate_all.sh first – or let this script do it for you.
#
# Exit code: 0 all tests passed (or skipped), 1 at least one assertion failed.

set -uo pipefail

DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEMO_DIR"

# ─── terminal colours (disabled when not a tty) ───────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m'
    BOLD='\033[1m'   RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BOLD='' RESET=''
fi

# ─── counters ─────────────────────────────────────────────────────────────────
PASS=0; FAIL=0; SKIP=0

_pass() { echo -e "  ${GREEN}PASS${RESET}  $*"; ((PASS++)) || true; }
_fail() { echo -e "  ${RED}FAIL${RESET}  $*"; ((FAIL++)) || true; }
_skip() { echo -e "  ${YELLOW}SKIP${RESET}  $*"; ((SKIP++)) || true; }

# ─── prerequisite: tshark ─────────────────────────────────────────────────────
echo -e "\n${BOLD}==> Checking prerequisites${RESET}"

if ! command -v tshark &>/dev/null; then
    _skip "tshark not found in PATH – install Wireshark and re-run"
    echo ""
    echo "To install on common platforms:"
    echo "  Ubuntu/Debian : sudo apt-get install tshark"
    echo "  macOS (brew)  : brew install wireshark"
    echo "  Fedora/RHEL   : sudo dnf install wireshark-cli"
    echo ""
    echo "All tshark tests skipped."
    exit 0
fi

TSHARK_VER=$(tshark --version 2>&1 | head -1)
echo "    tshark : ${TSHARK_VER}"

# ─── prerequisite: Lua dissectors ─────────────────────────────────────────────
NEED_GEN=0
for lua in results/ip_scoped.lua results/session_demo.lua \
           results/tls_weak_cipher.lua results/tls_sni_analysis.lua; do
    [ -f "$lua" ] || NEED_GEN=1
done

if [ "$NEED_GEN" -eq 1 ]; then
    echo -e "\n${BOLD}==> Generating Lua dissectors …${RESET}"
    if ! ./tools/generate_all.sh; then
        echo -e "${RED}ERROR: generate_all.sh failed; cannot run tests.${RESET}"
        exit 1
    fi
fi

echo ""

# ─── helpers ──────────────────────────────────────────────────────────────────

# _tshark_fields <pcap> <lua> <field> ...
# Runs tshark and outputs one value per frame for the requested field(s).
_tshark_fields() {
    local pcap="$1" lua="$2"; shift 2
    tshark -r "$pcap" -X "lua_script:${lua}" -T fields "$@" 2>/dev/null
}

# assert_values <label> <pcap> <lua> <field> <expected_val> [<expected_val> …]
# Reads the named field from every frame and compares with the expected list.
assert_values() {
    local label="$1" pcap="$2" lua="$3" field="$4"
    shift 4
    local expected=("$@")

    mapfile -t actual < <(_tshark_fields "$pcap" "$lua" -e "$field")

    if [ "${#actual[@]}" -ne "${#expected[@]}" ]; then
        _fail "${label}: expected ${#expected[@]} value(s) but got ${#actual[@]} (field: ${field})"
        return
    fi

    local ok=1
    for i in "${!expected[@]}"; do
        if [ "${actual[$i]}" != "${expected[$i]}" ]; then
            _fail "${label} [pkt $((i+1))]: field '${field}' expected='${expected[$i]}' got='${actual[$i]}'"
            ok=0
        fi
    done
    [ "$ok" -eq 1 ] && _pass "${label}  (${#expected[@]} frame(s), field: ${field})"
}

# assert_count <label> <pcap> <lua> <display_filter> <expected_count>
# Counts frames that match the display filter and compares with expected.
assert_count() {
    local label="$1" pcap="$2" lua="$3" filter="$4" expected="$5"

    local count
    count=$(tshark -r "$pcap" -X "lua_script:${lua}" -Y "$filter" 2>/dev/null \
            | wc -l | tr -d ' ')

    if [ "$count" -eq "$expected" ]; then
        _pass "${label}  (filter: ${filter}  →  ${count} frame(s))"
    else
        _fail "${label}: filter '${filter}' expected ${expected} frame(s), got ${count}"
    fi
}

# ─── Case 1: ip_scoped ────────────────────────────────────────────────────────
#
# Packet layout (11 bytes, DLT_USER0):
#   version[1]  src_ip[4 BE]  dst_ip[4 BE]  payload_size[2 BE]
#
# Packets:
#   #1  src=192.168.1.1  dst=8.8.8.8      (LAN  -> inet)
#   #2  src=100.64.0.1   dst=8.8.8.8      (NAT  -> inet)
#   #3  src=8.8.8.8      dst=192.168.1.1  (inet -> LAN)
#   #4  src=192.168.1.1  dst=10.0.0.1     (LAN  -> LAN)
#   #5  src=8.8.8.8      dst=100.64.0.1   (inet -> NAT)

echo -e "${BOLD}==> ip_scoped${RESET}"
PCAP="ip_scoped/sample.pcap"
LUA="results/ip_scoped.lua"

assert_values "src_scope per-frame" "$PCAP" "$LUA" \
    "ip_scoped.src_scope" \
    "lan" "nat" "inet" "lan" "inet"

assert_values "dst_scope per-frame" "$PCAP" "$LUA" \
    "ip_scoped.dst_scope" \
    "inet" "inet" "lan" "lan" "nat"

assert_count 'src_scope=="lan"  → 2' "$PCAP" "$LUA" 'ip_scoped.src_scope == "lan"'  2
assert_count 'src_scope=="nat"  → 1' "$PCAP" "$LUA" 'ip_scoped.src_scope == "nat"'  1
assert_count 'src_scope=="inet" → 2' "$PCAP" "$LUA" 'ip_scoped.src_scope == "inet"' 2
assert_count 'dst_scope=="lan"  → 2' "$PCAP" "$LUA" 'ip_scoped.dst_scope == "lan"'  2
assert_count 'dst_scope=="nat"  → 1' "$PCAP" "$LUA" 'ip_scoped.dst_scope == "nat"'  1
assert_count 'dst_scope=="inet" → 2' "$PCAP" "$LUA" 'ip_scoped.dst_scope == "inet"' 2

# filter-only bool fields: src_lan, src_nat, dst_lan, dst_nat
assert_count 'src_lan  → 2'  "$PCAP" "$LUA" 'ip_scoped.src_lan'  2
assert_count 'src_nat  → 1'  "$PCAP" "$LUA" 'ip_scoped.src_nat'  1
assert_count 'dst_lan  → 2'  "$PCAP" "$LUA" 'ip_scoped.dst_lan'  2
assert_count 'dst_nat  → 1'  "$PCAP" "$LUA" 'ip_scoped.dst_nat'  1

# ─── Case 2: session_id ───────────────────────────────────────────────────────
#
# Packet layout (10 bytes, DLT_USER0):
#   src_ip[4 BE]  dst_ip[4 BE]  service_port[2 BE]
#
# Packets:
#   #1  src=192.168.1.1  dst=192.168.1.2  port=1234  (A→B)   key=3^1234=1233
#   #2  src=192.168.1.2  dst=192.168.1.1  port=1234  (B→A)   key=3^1234=1233
#   #3  src=10.0.0.1     dst=10.0.0.2     port=80    (C→D)   key=3^80=83
#   #4  src=10.0.0.2     dst=10.0.0.1     port=80    (D→C)   key=3^80=83

echo ""
echo -e "${BOLD}==> session_id${RESET}"
PCAP="session_id/sample.pcap"
LUA="results/session_demo.lua"

assert_values "session_with_service per-frame" "$PCAP" "$LUA" \
    "session_demo.session_with_service" \
    "1233" "1233" "83" "83"

assert_count 'session_with_service=="1233" → 2' "$PCAP" "$LUA" \
    'session_demo.session_with_service == "1233"' 2

assert_count 'session_with_service=="83"   → 2' "$PCAP" "$LUA" \
    'session_demo.session_with_service == "83"' 2

# Symmetry check: both directions of the same flow must have equal keys
# (implicitly covered by the two assertions above, but stated explicitly)
SWS=$(  _tshark_fields "$PCAP" "$LUA" -e "session_demo.session_with_service" )
PKT1=$(echo "$SWS" | sed -n '1p')
PKT2=$(echo "$SWS" | sed -n '2p')
PKT3=$(echo "$SWS" | sed -n '3p')
PKT4=$(echo "$SWS" | sed -n '4p')

if [ "$PKT1" = "$PKT2" ]; then
    _pass "session symmetry: pkt#1 == pkt#2  (A→B and B→A same key)"
else
    _fail "session symmetry: pkt#1='${PKT1}' != pkt#2='${PKT2}' (expected equal)"
fi

if [ "$PKT3" = "$PKT4" ]; then
    _pass "session symmetry: pkt#3 == pkt#4  (C→D and D→C same key)"
else
    _fail "session symmetry: pkt#3='${PKT3}' != pkt#4='${PKT4}' (expected equal)"
fi

if [ "$PKT1" != "$PKT3" ]; then
    _pass "session isolation: flow A-B and flow C-D have different keys"
else
    _fail "session isolation: flow A-B and flow C-D have the same key (expected different)"
fi

# ─── Case 3: tls_weak_cipher ──────────────────────────────────────────────────
#
# Packet layout (5 bytes, DLT_USER0):
#   handshake_type[1]  tls_version[2 BE]  cipher_suite[2 BE]
#
# Packets:
#   #1  type=0x01  version=0x0303  cipher=0x0005  (TLS 1.2, RC4-SHA  → WEAK)
#   #2  type=0x01  version=0x0303  cipher=0x002F  (TLS 1.2, AES-128  → OK)

echo ""
echo -e "${BOLD}==> tls_weak_cipher${RESET}"
PCAP="tls_weak_cipher/sample.pcap"
LUA="results/tls_weak_cipher.lua"

# Total decoded frames
TOTAL=$(tshark -r "$PCAP" -X "lua_script:${LUA}" 2>/dev/null | wc -l | tr -d ' ')
if [ "$TOTAL" -eq 2 ]; then
    _pass "total decoded frames = 2"
else
    _fail "expected 2 decoded frames, got ${TOTAL}"
fi

# has_weak_cipher filter counts
assert_count 'has_weak_cipher → 1 frame (RC4 packet)'  "$PCAP" "$LUA" \
    'tls_weak_cipher.has_weak_cipher' 1

assert_count 'not has_weak_cipher → 1 frame (AES packet)' "$PCAP" "$LUA" \
    'not tls_weak_cipher.has_weak_cipher' 1

# is_client_hello: both packets are ClientHello (type=0x01)
assert_count 'is_client_hello → 2 frames' "$PCAP" "$LUA" \
    'tls_weak_cipher.is_client_hello' 2

# ─── Case 4: tls_sni_analysis ─────────────────────────────────────────────────
#
# Packet layout (36 bytes, DLT_USER0):
#   handshake_type[1]  tls_version[2 BE]  sni_length[1]  sni_name[32, null-padded]
#
# Packets:
#   #1  sni_length=14  "cloudflare.com"   → Medium
#   #2  sni_length=11  "netflix.com"      → Medium
#   #3  sni_length=39  anomalous name     → Long/Anomaly

echo ""
echo -e "${BOLD}==> tls_sni_analysis${RESET}"
PCAP="tls_sni_analysis/sample.pcap"
LUA="results/tls_sni_analysis.lua"

assert_values "sni_category per-frame" "$PCAP" "$LUA" \
    "tls_sni_analysis.sni_category" \
    "Medium" "Medium" "Long/Anomaly"

assert_count 'sni_category=="Medium"       → 2' "$PCAP" "$LUA" \
    'tls_sni_analysis.sni_category == "Medium"' 2

assert_count 'sni_category=="Long/Anomaly" → 1' "$PCAP" "$LUA" \
    'tls_sni_analysis.sni_category == "Long/Anomaly"' 1

# is_anomaly bool: only packet #3
assert_count 'is_anomaly → 1 frame (long SNI)'      "$PCAP" "$LUA" \
    'tls_sni_analysis.is_anomaly' 1

assert_count 'not is_anomaly → 2 frames (short SNI)' "$PCAP" "$LUA" \
    'not tls_sni_analysis.is_anomaly' 2

# ─── summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Results:${RESET}  ${GREEN}${PASS} passed${RESET}  ${RED}${FAIL} failed${RESET}  ${YELLOW}${SKIP} skipped${RESET}"
echo ""

[ "$FAIL" -eq 0 ]
