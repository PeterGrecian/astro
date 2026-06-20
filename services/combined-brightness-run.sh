#!/bin/bash
# Wrapper for combined-brightness.service: refresh the multi-night combined
# brightness chart for each eclipticam camera and publish it to S3.
#
# Runs daily, independent of the deliverables pipeline, so the chart stays
# current even on cloudy / no-stack nights (when nothing else publishes).
set -uo pipefail

PY="$HOME/astro/.venv/bin/python"

# Cameras to refresh. Keep in sync with /etc/default/astro-process.
CAMERAS=(eclipticam-v1 eclipticam-v3w)

for cam in "${CAMERAS[@]}"; do
    echo "--- combined-brightness $cam"
    "$PY" "$HOME/astro/bin/combined-brightness" --camera "$cam" --publish || true
done
