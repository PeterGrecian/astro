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

# Temporary: SSH to starcam and harvest cover open/close events from the
# systemd journal for the night window (noon-noon, London). Permanent fix
# pending: starcam_night_daemon writes cover.csv into the night frame dir.
COVER_CSV="$HOME/tmp/cover-$NIGHT.csv"
START_ISO="${NIGHT}T11:00:00Z"
END_ISO="$(date -u -d "$NIGHT + 1 day 12:00" +%Y-%m-%dT%H:%M:%SZ)"
echo "iso_utc,state" > "$COVER_CSV"
# journalctl -o json gives __REALTIME_TIMESTAMP in microseconds since epoch,
# which dodges all year/timezone parsing ambiguity. python3 -c (on puppy)
# turns each match into iso_utc,state.
ssh -o ConnectTimeout=10 -o BatchMode=yes peter@starcam.local \
    "sudo -n journalctl --since '$START_ISO' --until '$END_ISO' -o json --no-pager 2>/dev/null \
     | grep -F 'cover now '" 2>/dev/null \
    | python3 -c '
import json, sys, datetime
for line in sys.stdin:
    try:
        rec = json.loads(line)
    except Exception:
        continue
    msg = rec.get("MESSAGE", "")
    parts = msg.split("cover now ", 1)
    if len(parts) != 2:
        continue
    state = parts[1].split()[0].rstrip(":,.")
    if state not in ("open", "closed"):
        continue
    ts_us = int(rec["__REALTIME_TIMESTAMP"])
    iso = datetime.datetime.utcfromtimestamp(ts_us / 1e6).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{iso},{state}")
' >> "$COVER_CSV" || true

COVER_ARGS=()
if [[ "$(wc -l < "$COVER_CSV")" -gt 1 ]]; then
    COVER_ARGS=(--cover "$COVER_CSV")
fi

"$HOME/astro/bin/plot-brightness" "$HOME/starcam-frames/night/" \
    "${SKY_ARGS[@]}" \
    "${COVER_ARGS[@]}" \
    --out "$HOME/starcam-frames/brightness.png"
