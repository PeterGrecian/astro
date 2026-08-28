#!/usr/bin/env bash
set -euo pipefail
CARD="${1:-}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$DIR/_render/$(basename "$CARD" .md).png"
mkdir -p "$DIR/_render"
python3 "$DIR/render.py" "$CARD" --out "$OUT"
