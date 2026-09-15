#!/bin/bash
# Build a 6s max-hold video for every completed plane-hunt hour that lacks one.
# "Completed" = not the current UTC hour, so we never process a file still open.
set -u
DIR=/mnt/bigstore/astro-data/xoverpi-frames/planehunt
OUT=$DIR/video
NOW=$(date -u +%Y%m%dT%H0000Z)
mkdir -p "$OUT"
for f in "$DIR"/*.h264; do
    [ -e "$f" ] || continue
    b=$(basename "$f" .h264)
    [ "$b" = "$NOW" ] && continue
    [ -e "$OUT/$b.mp4" ] && continue
    echo "building $b"
    /usr/bin/python3 /home/peter/astro/bin/xoverpi-planevid "$f" -o "$OUT/$b.mp4"
done
