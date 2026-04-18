#!/usr/bin/env bash
# fetch_samples.sh – download real public pcap files into each demo case.
#
# Usage:  ./tools/fetch_samples.sh [--force]
#
# Files written (never committed – listed in .gitignore):
#   ip_scoped/real_sample.pcap
#   session_id/real_sample.pcap
#   tls_weak_cipher/real_sample.pcapng
#   tls_sni_analysis/real_sample.pcapng
#
# Sources (all public-domain / CC0 Wireshark sample captures):
#   IPv4 fragments  – Wireshark SampleCaptures wiki
#   TLS ClientHello – Lekensteyn / wireshark-notes (imap-ssl.pcapng)
#
# If a URL is unreachable the script prints a manual-download hint and
# continues so that the other cases are not blocked.

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEMO_DIR"

FORCE="${1:-}"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

try_download() {
    local label="$1"
    local url="$2"
    local dest="$3"

    if [ -f "$dest" ] && [ "$FORCE" != "--force" ]; then
        echo "  already exists: $dest  (skip; use --force to re-download)"
        return 0
    fi

    echo "  downloading $label …"
    if curl -fsSL --max-time 30 -o "$dest" "$url" 2>/dev/null; then
        local size
        size=$(wc -c < "$dest")
        echo "  saved ${size} bytes → $dest"
    else
        echo "  WARNING: download failed for $label"
        echo "           URL: $url"
        echo "           Please download manually and save as: $dest"
        # Don't leave an empty/broken file
        [ -f "$dest" ] && rm -f "$dest"
        return 0  # non-fatal; continue with remaining cases
    fi
}

# ---------------------------------------------------------------------------
# 1. ip_scoped — IPv4 fragmentation capture
#    Contains a mix of public, private and multicast addresses – ideal for
#    testing src_scope / dst_scope classification.
# ---------------------------------------------------------------------------

echo ""
echo "==> Case: ip_scoped"
try_download \
    "ipv4frags.pcap (Wireshark SampleCaptures)" \
    "https://wiki.wireshark.org/SampleCaptures?action=AttachFile&do=get&target=ipv4frags.pcap" \
    "ip_scoped/real_sample.pcap"

# Fallback: capture from a well-known Wireshark samples mirror
if [ ! -f "ip_scoped/real_sample.pcap" ]; then
    try_download \
        "ipv4frags.pcap (alternate mirror)" \
        "https://github.com/wireshark/wireshark/raw/master/test/captures/ipv4frags.pcap" \
        "ip_scoped/real_sample.pcap"
fi

# ---------------------------------------------------------------------------
# 2. session_id — same IPv4 file: it contains bidirectional flows, which is
#    perfect for verifying that session_key is symmetric (A→B == B→A).
# ---------------------------------------------------------------------------

echo ""
echo "==> Case: session_id"
if [ -f "ip_scoped/real_sample.pcap" ]; then
    cp "ip_scoped/real_sample.pcap" "session_id/real_sample.pcap"
    echo "  copied ip_scoped/real_sample.pcap → session_id/real_sample.pcap"
else
    echo "  WARNING: ip_scoped/real_sample.pcap not available;"
    echo "           session_id/real_sample.pcap was not created."
    echo "           Re-run after downloading ip_scoped/real_sample.pcap."
fi

# ---------------------------------------------------------------------------
# 3. tls_weak_cipher — TLS capture with multiple cipher suites
# ---------------------------------------------------------------------------

echo ""
echo "==> Case: tls_weak_cipher"
try_download \
    "imap-ssl.pcapng (Lekensteyn / wireshark-notes)" \
    "https://github.com/Lekensteyn/wireshark-notes/raw/master/tls/imap-ssl.pcapng" \
    "tls_weak_cipher/real_sample.pcapng"

if [ ! -f "tls_weak_cipher/real_sample.pcapng" ]; then
    try_download \
        "http2-16-ssl.pcapng (Lekensteyn / wireshark-notes)" \
        "https://github.com/Lekensteyn/wireshark-notes/raw/master/tls/http2-16-ssl.pcapng" \
        "tls_weak_cipher/real_sample.pcapng"
fi

# ---------------------------------------------------------------------------
# 4. tls_sni_analysis — same TLS file: SNI fields are present in ClientHello
# ---------------------------------------------------------------------------

echo ""
echo "==> Case: tls_sni_analysis"
if [ -f "tls_weak_cipher/real_sample.pcapng" ]; then
    cp "tls_weak_cipher/real_sample.pcapng" "tls_sni_analysis/real_sample.pcapng"
    echo "  copied tls_weak_cipher/real_sample.pcapng → tls_sni_analysis/real_sample.pcapng"
else
    echo "  WARNING: tls_weak_cipher/real_sample.pcapng not available;"
    echo "           tls_sni_analysis/real_sample.pcapng was not created."
    echo "           Re-run after downloading tls_weak_cipher/real_sample.pcapng."
fi

# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

echo ""
echo "==> Done.  Real sample files:"
for f in \
    "ip_scoped/real_sample.pcap" \
    "session_id/real_sample.pcap" \
    "tls_weak_cipher/real_sample.pcapng" \
    "tls_sni_analysis/real_sample.pcapng"
do
    if [ -f "$f" ]; then
        size=$(wc -c < "$f")
        echo "  [OK]   $f  (${size} bytes)"
    else
        echo "  [MISS] $f"
    fi
done
echo ""
echo "NOTE: Real sample files are listed in .gitignore and are not committed."
echo "      Synthetic demo files (sample.pcap) remain unchanged."
echo "      To open Wireshark with a real capture, run:"
echo "        wireshark -r ip_scoped/real_sample.pcap"
