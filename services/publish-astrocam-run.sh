#!/usr/bin/env bash
# publish-astrocam-run.sh — publish yesterday's astrocam deliverables.
# Triggered by publish-astrocam.timer at 07:00 Europe/London.
set -euo pipefail

NIGHT=$(TZ=Europe/London date -d "yesterday" +%F)
REPO="$HOME/astro"
LOG_TAG="publish-astrocam[$NIGHT]"

echo "$LOG_TAG starting"
"$REPO/bin/publish-night-cam" --camera astrocam --night "$NIGHT" || \
    echo "$LOG_TAG FAILED (continuing)"
echo "$LOG_TAG done"
