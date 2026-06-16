#!/usr/bin/env bash
# publish-eclipticam-run.sh — publish yesterday's eclipticam deliverables (both cameras).
# Triggered by publish-eclipticam.timer at 07:00 Europe/London.
set -euo pipefail

NIGHT=$(TZ=Europe/London date -d "yesterday" +%F)
REPO="$HOME/astro"
LOG_TAG="publish-eclipticam[$NIGHT]"

echo "$LOG_TAG starting"
for cam in eclipticam-v1 eclipticam-v3w; do
    echo "$LOG_TAG --- $cam"
    "$REPO/bin/publish-night-cam" --camera "$cam" --night "$NIGHT" || \
        echo "$LOG_TAG $cam FAILED (continuing)"
done
echo "$LOG_TAG done"
