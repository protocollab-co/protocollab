#!/bin/bash
set -e
cd "$(dirname "$0")/.."
mkdir -p results
for spec in ip_scoped/ip_scoped.yaml session_id/session_id.yaml tls_weak_cipher/tls_weak.yaml tls_sni_analysis/tls_sni.yaml; do
	proto_id=$(basename $(dirname $spec))
	protocollab generate wireshark "$spec" -o "results/${proto_id}.lua"
done
echo "Generated dissectors into results/"
