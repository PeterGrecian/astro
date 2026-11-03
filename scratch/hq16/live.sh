#!/bin/bash
# Live focus loop for HQ16: fit blur discs on each new frame as it reaches eclipticam's SSD.
# Run on muppet (has the astro venv and disc.py as ~/tmp/hq16-disc.py). One line per frame
# to stdout and ~/tmp/hq16-live.log:
#   UTC frame-time  n-discs  D binned px (p16-p84)  defocus um
# Usage: hq16-live.sh [night]   (default: today's UTC date; before 12 UTC use yesterday)
ECL=peter@192.168.0.68
NIGHT=${1:-$(date -u +%F)}
SRC=/mnt/ssd/eclipticam-frames/night/$NIGHT/hq16
WORK=$HOME/tmp/hq16-live1
LOG=$HOME/tmp/hq16-live.log
last=""
echo "# live HQ16 disc fit, night $NIGHT, started $(date -u +%T) UTC" | tee -a "$LOG"
while true; do
  f=$(ssh -o BatchMode=yes $ECL "ls $SRC/*/*.fits.fz 2>/dev/null | tail -1")
  if [ -n "$f" ] && [ "$f" != "$last" ]; then
    last=$f
    rm -rf "$WORK"; mkdir -p "$WORK/eclipticam-frames/night/$NIGHT/hq16/00"
    scp -q $ECL:"$f" "$WORK/eclipticam-frames/night/$NIGHT/hq16/00/" || continue
    ms=$(basename "$f" .fits.fz)
    t=$(date -u -d @$((ms/1000)) +%T)
    out=$(BIGSTORE=$WORK NIGHT=$NIGHT HOURS=00 ~/astro/.venv/bin/python ~/tmp/hq16-disc.py 2>&1)
    n=$(echo "$out" | grep -o "[0-9]* kept" | grep -o "[0-9]*")
    D=$(echo "$out" | grep "D binned px" | awk '{print $5, "(" $7 "-" $9 ")"}')
    dl=$(echo "$out" | grep "defocus um" | awk '{print $5}')
    echo "$(date -u +%T) frame $t  n=${n:-0}  D=${D:--} px  defocus=${dl:--} um" | tee -a "$LOG"
  fi
  sleep 10
done
