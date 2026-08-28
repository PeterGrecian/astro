#!/usr/bin/env bash
# Front Matter CMS action: rebuild this card's preview into transients/_render/.
# FM calls: bash <script> <projectPath> <filePath>
set -euo pipefail
proj="$1"; card="$2"
mkdir -p "$proj/transients/_render"
out="$proj/transients/_render/$(basename "${card%.md}").png"
"$proj/.venv/bin/python" "$proj/transients/render.py" "$card" --out "$out"
