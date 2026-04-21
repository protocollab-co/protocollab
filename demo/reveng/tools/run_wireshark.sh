#!/bin/bash
case="$1"
if [ -z "$case" ]; then
    echo "Usage: $0 {ip_scoped|session_id|tls_weak_cipher|tls_sni_analysis}"
    exit 1
fi
case_dir="$case"
case "$case" in
    ip_scoped) lua_script="results/ip_scoped.lua" ;;
    session_id) lua_script="results/session_demo.lua" ;;
    tls_weak_cipher) lua_script="results/tls_weak_cipher.lua" ;;
    tls_sni_analysis) lua_script="results/tls_sni_analysis.lua" ;;
    *)
        echo "Usage: $0 {ip_scoped|session_id|tls_weak_cipher|tls_sni_analysis}"
        exit 1
        ;;
esac
if [ ! -f "$lua_script" ]; then
    echo "Dissector not found. Run ./tools/generate_all.sh first."
    exit 1
fi
proto_name=$(basename "$lua_script" .lua)
wireshark -o "uat:user_dlts:\"User 0 (DLT=147)\",\"${proto_name}\",\"0\",\"\",\"0\",\"\"" -r "$case_dir/sample.pcap" -X lua_script:"$lua_script"
