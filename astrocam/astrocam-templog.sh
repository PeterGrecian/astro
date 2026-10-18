#!/usr/bin/env bash
# Dirty CPU-temperature logger for astrocam (the only outdoor camera).
# One line per tick: UTC ISO8601, cpu_temp_C, and the DHT22 inside the box
# (box_temp_c, box_rh_pct; empty if absent or a read fails). Appended to a
# CSV on root. The DHT22 is on GPIO4 via the kernel dht11 overlay
# (config.txt dtoverlay=dht11,gpiopin=4), read from IIO sysfs. The bus is
# single-wire and timing-fragile, so reads fail now and then; retry.
# Driven by astrocam-templog.timer (every 2 min). Keeps the file bounded by
# rotating at ~1 MB (~30k rows ≈ weeks) so it never fills the 89%-full root.
set -euo pipefail

CSV="${ASTROCAM_TEMPLOG:-$HOME/astrocam-templog.csv}"
MAXBYTES=1048576   # 1 MB rotate threshold

now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# thermal_zone0 is cpu-thermal in milli-degrees C
raw="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo '')"
if [[ -z "$raw" ]]; then temp=""; else temp="$(awk "BEGIN{printf \"%.1f\", $raw/1000}")"; fi

# DHT22: IIO reports milli-degC and milli-percent.
dht_read() {
  local f="/sys/bus/iio/devices/iio:device0/$1" v i
  for i in 1 2 3; do
    v="$(cat "$f" 2>/dev/null)" && [[ -n "$v" ]] && { awk "BEGIN{printf \"%.1f\", $v/1000}"; return; }
    sleep 2
  done
}
box_t="$(dht_read in_temp_input || true)"
box_rh="$(dht_read in_humidityrelative_input || true)"

HEADER="utc,cpu_temp_c,box_temp_c,box_rh_pct"
# header if new file; start a fresh file if it has the old two-column header
if [[ -f "$CSV" ]] && [[ "$(head -1 "$CSV")" != "$HEADER" ]]; then mv -f "$CSV" "${CSV}.1"; fi
if [[ ! -f "$CSV" ]]; then echo "$HEADER" > "$CSV"; fi
echo "${now},${temp},${box_t},${box_rh}" >> "$CSV"

# rotate if too big (keep one .1 backup, overwrite older)
if [[ -f "$CSV" ]] && [[ "$(stat -c%s "$CSV")" -gt "$MAXBYTES" ]]; then
  mv -f "$CSV" "${CSV}.1"
  echo "$HEADER" > "$CSV"
fi
