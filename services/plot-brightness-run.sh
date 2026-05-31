#!/bin/bash
# Wrapper for plot-brightness.service: scan last night's skycam brightness
# first, then render the all-nights plot with skycam overlaid as the
# starcam-vs-skycam confirmation curve.
set -euo pipefail

source "$HOME/astro/.venv/bin/activate"

# Pick the most recently *completed* night: night-dir of "24h ago". Using
# night-dir of "now" returns the current observing night, which during the
# day has no frames yet (timer runs at 05:00 — yesterday's night just
# ended). Subtracting 24h dodges the noon edge case either side.
NIGHT="$("$HOME/super/bin/night-dir" "$(date -u -d '24 hours ago' +%s)")"
SKY_CSV="$HOME/tmp/skycam-$NIGHT.csv"

"$HOME/astro/bin/scan-skycam-brightness" --night "$NIGHT" --out "$SKY_CSV" || true

SKY_ARGS=()
if [[ -s "$SKY_CSV" ]]; then
    SKY_ARGS=(--skycam "$SKY_CSV")
fi

"$HOME/astro/bin/plot-brightness" "$HOME/starcam-frames/night/" \
    "${SKY_ARGS[@]}" \
    --out "$HOME/starcam-frames/brightness.png"
