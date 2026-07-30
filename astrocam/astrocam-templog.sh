#!/usr/bin/env bash
# Dirty CPU-temperature logger for astrocam (the only outdoor camera).
# One line per tick: UTC ISO8601, cpu_temp_C. Appended to a CSV on root.
# Driven by astrocam-templog.timer (every 2 min). Keeps the file bounded by
# rotating at ~1 MB (~30k rows ≈ weeks) so it never fills the 89%-full root.
set -euo pipefail

CSV="${ASTROCAM_TEMPLOG:-$HOME/astrocam-templog.csv}"
MAXBYTES=1048576   # 1 MB rotate threshold

now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# thermal_zone0 is cpu-thermal in milli-degrees C
raw="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo '')"
if [[ -z "$raw" ]]; then temp=""; else temp="$(awk "BEGIN{printf \"%.1f\", $raw/1000}")"; fi

# header if new file
if [[ ! -f "$CSV" ]]; then echo "utc,cpu_temp_c" > "$CSV"; fi
echo "${now},${temp}" >> "$CSV"

# rotate if too big (keep one .1 backup, overwrite older)
if [[ -f "$CSV" ]] && [[ "$(stat -c%s "$CSV")" -gt "$MAXBYTES" ]]; then
  mv -f "$CSV" "${CSV}.1"
  echo "utc,cpu_temp_c" > "$CSV"
fi
