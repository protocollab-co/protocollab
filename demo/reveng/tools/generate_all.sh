#!/bin/bash
set -e
cd "$(dirname "$0")/.."
mkdir -p results
CLI_BIN=""
if command -v pc >/dev/null 2>&1; then
	CLI_BIN="pc"
elif command -v protocollab >/dev/null 2>&1; then
	CLI_BIN="protocollab"
else
	echo "Neither 'pc' nor 'protocollab' was found in PATH." >&2
	exit 127
fi

register_user0() {
	local lua_path="$1"
	local proto_var="$2"
	printf '\nDissectorTable.get("wtap_encap"):add(147, %s)\n' "$proto_var" >> "$lua_path"
}

"$CLI_BIN" generate wireshark ip_scoped/ip_scoped.yaml -o results/
register_user0 results/ip_scoped.lua proto_ip_scoped

"$CLI_BIN" generate wireshark session_id/session_id.yaml -o results/
register_user0 results/session_demo.lua proto_session_demo

"$CLI_BIN" generate wireshark tls_weak_cipher/tls_weak_cipher.yaml -o results/
register_user0 results/tls_weak_cipher.lua proto_tls_weak_cipher

"$CLI_BIN" generate wireshark tls_sni_analysis/tls_sni_analysis.yaml -o results/
register_user0 results/tls_sni_analysis.lua proto_tls_sni_analysis

echo "Generated dissectors into results/"
