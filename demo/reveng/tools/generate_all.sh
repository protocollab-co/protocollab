#!/usr/bin/env bash
# generate_all.sh – generate all Wireshark Lua dissectors for the demo cases.
#
# Usage:  ./tools/generate_all.sh
#         Run from demo/reveng/ or any location; the script always operates
#         relative to its own parent directory.

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEMO_DIR"

echo "==> Creating results/ directory …"
mkdir -p results

echo "==> Generating ip_scoped dissector …"
protocollab generate wireshark ip_scoped/ip_scoped.yaml -o results/

echo "==> Generating session_id dissector …"
protocollab generate wireshark session_id/session_id.yaml -o results/

echo "==> Generating tls_weak_cipher dissector …"
protocollab generate wireshark tls_weak_cipher/tls_weak_cipher.yaml -o results/

echo "==> Generating tls_sni_analysis dissector …"
protocollab generate wireshark tls_sni_analysis/tls_sni_analysis.yaml -o results/

echo ""
echo "Done!  Generated Lua dissectors:"
ls -1 results/*.lua 2>/dev/null || echo "  (none found – check errors above)"
