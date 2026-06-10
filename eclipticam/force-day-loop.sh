#!/bin/bash
# Force day-mode JPG captures every 5 min on both cameras.
# Use while the brightness-based day/night discriminator is unreliable.
# Run as: ~/astro/eclipticam/force-day-loop.sh  (stop the systemd timer first)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3
SCRIPT="$HERE/force-day-one.py"
INTERVAL_S=${INTERVAL_S:-300}

while true; do
    "$PY" "$SCRIPT" || echo "tick FAILED" >&2
    sleep "$INTERVAL_S"
done
