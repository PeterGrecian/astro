#!/bin/bash
# Wrapper for plot-brightness.service: scan last night's skycam brightness
# first, then render the all-nights plot with skycam overlaid as the
# starcam-vs-skycam confirmation curve.
set -euo pipefail

source "$HOME/astro/.venv/bin/activate"

# scan-skycam-brightness picks "last completed night" itself; its default
# output is ~/tmp/skycam-<night>.csv. Mirror that path here so we can pass
# the file to plot-brightness without parsing stdout.
NIGHT="$("$HOME/super/bin/night-dir")"
SKY_CSV="$HOME/tmp/skycam-$NIGHT.csv"

"$HOME/astro/bin/scan-skycam-brightness" --night "$NIGHT" --out "$SKY_CSV" || true

SKY_ARGS=()
if [[ -s "$SKY_CSV" ]]; then
    SKY_ARGS=(--skycam "$SKY_CSV")
fi

"$HOME/astro/bin/plot-brightness" "$HOME/starcam-frames/night/" \
    "${SKY_ARGS[@]}" \
    --out "$HOME/starcam-frames/brightness.png"
