#!/bin/bash
case="$1"
if [ -z "$case" ]; then
    echo "Usage: $0 {ip_scoped|session_id|tls_weak_cipher|tls_sni_analysis}"
    exit 1
fi
case_dir="$case"
lua_script="results/${case}.lua"
if [ ! -f "$lua_script" ]; then
    echo "Dissector not found. Run ./tools/generate_all.sh first."
    exit 1
fi
wireshark -r "$case_dir/sample.pcap" -X lua_script:"$lua_script"
