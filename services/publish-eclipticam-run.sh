#!/usr/bin/env bash
# publish-eclipticam-run.sh — publish yesterday's eclipticam deliverables (both subcams).
# Triggered by publish-eclipticam.timer at 07:00 Europe/London.
set -euo pipefail

NIGHT=$(TZ=Europe/London date -d "yesterday" +%F)
REPO="$HOME/astro-unify"
LOG_TAG="publish-eclipticam[$NIGHT]"

echo "$LOG_TAG starting"
for sub in v1 v3w; do
    echo "$LOG_TAG --- $sub"
    "$REPO/bin/publish-night-cam" --camera eclipticam --subcam "$sub" --night "$NIGHT" || \
        echo "$LOG_TAG $sub FAILED (continuing)"
done
echo "$LOG_TAG done"
