#!/usr/bin/env sh
set -eu

echo "[pc-check] Probing existing 'pc' command in PATH..."
if command -v pc >/dev/null 2>&1; then
  echo "[pc-check] Found: $(command -v pc)"
else
  echo "[pc-check] No 'pc' command found before install."
fi

echo "[pc-check] Probing Python module fallback..."
if python -m protocollab --help >/dev/null 2>&1; then
  echo "[pc-check] OK: 'python -m protocollab --help' works."
else
  echo "[pc-check] FAIL: fallback module invocation failed." >&2
  exit 1
fi

echo "[pc-check] Probe complete."
