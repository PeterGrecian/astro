#!/bin/bash
# Wrapper for canon-nightly.service: deliver last night's EOS 2000D capture.
#
# Runs post-dawn on MUPPET, where the CR2s land and where all four stages now
# run (compute follows the data — see canon/camera.json processing_notes).
#
# Idempotent by construction: eos-cr2-to-fits skips frames it has already
# converted, and nightly-cam/publish-night-cam rewrite their outputs, so a
# re-run after a failure is safe and a Persistent=true catch-up run is safe.
#
# Exits 0 when a night simply has no capture — that is normal (cloud, no
# session), not a failure, and must not mark the unit failed.
set -uo pipefail

REPO="$HOME/astro"
PY=python3
[ -x "$REPO/.venv/bin/python" ] && PY="$REPO/.venv/bin/python"

# Night defaults to the last completed noon-rollover night, which post-dawn is
# the one that just ended. Override with NIGHT=YYYY-MM-DD for a backfill.
NIGHT="${NIGHT:-}"
ARGS=()
[ -n "$NIGHT" ] && ARGS+=(--night "$NIGHT")

echo "=== canon-nightly-run $(date -u +%FT%TZ) on $(hostname -s) ==="
bash "$REPO/bin/canon-nightly" "${ARGS[@]}"
rc=$?
echo "=== canon-nightly-run exit $rc ==="
exit $rc
