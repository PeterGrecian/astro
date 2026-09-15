#!/bin/bash
# xoverpi plane hunt — hourly h264 segments straight to muppet's bigstore.
#
# Why video and not the FITS sub pipeline: a plane crosses the 0.69 deg field in
# 1-2 s. At the FITS path's measured 1.46 s cadence we would catch it in about
# one frame, and at the ~6 ms daylight exposure it moves ~1 px in that frame -
# a dot, not a streak. Seeing a streak needs MANY samples across the transit,
# which means the sensor's own frame rate (46 fps binned) and hardware h264,
# not Rice-compressed stills.
#
# One file per UTC hour so the deliverable lines up with the capture.
set -u
OUT=${XOVER_PLANE_OUT:-/mnt/muppet/bigstore/xoverpi-frames/planehunt}
FPS=${XOVER_PLANE_FPS:-30}
W=${XOVER_PLANE_W:-1296}
H=${XOVER_PLANE_H:-972}
# Exposure is PINNED, not auto. Left on AE, rpicam-vid chose an exposure that
# blew the sky to white (measured 2026-09-15), and a plane against a saturated
# background is invisible. Probed against real overcast: 2000 us gives sky mean
# 70/255 with max 119, so the sky sits low-mid grey and there is ample headroom
# above it for a sunlit aircraft. Re-probe if the weather or aim changes.
SHUTTER=${XOVER_PLANE_SHUTTER:-2000}
GAIN=${XOVER_PLANE_GAIN:-1.0}

mkdir -p "$OUT"
while true; do
    now=$(date -u +%Y%m%dT%H0000Z)
    # Run until the top of the next hour, so files are whole clock hours.
    secs=$(( 3600 - ($(date -u +%s) % 3600) ))
    echo "$(date -u +%FT%TZ) starting ${secs}s segment -> $OUT/$now.h264"
    rpicam-vid -n -t $((secs * 1000)) \
        --width "$W" --height "$H" --framerate "$FPS" \
        --shutter "$SHUTTER" --gain "$GAIN" --awbgains 1,1 \
        --codec h264 -o "$OUT/$now.h264" 2>&1 | grep -viE "^\[|INFO" || true
done
