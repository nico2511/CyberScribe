#!/usr/bin/env bash
# Capture Tk overlay states under Xvfb for PR proof (Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${CYBERSCRIBE_SCREENSHOTS:-/opt/cursor/artifacts/overlay-states-tk}"
mkdir -p "$OUT"
export CYBERSCRIBE_SCREENSHOTS="$OUT"
xvfb-run -a python3 "$ROOT/scripts/render_overlay_screenshots.py"
echo "Saved Tk captures under $OUT"