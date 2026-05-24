#!/usr/bin/env bash
# todo.sh — operator cheat-sheet for the astro pipeline.
#
# This file isn't meant to be executed as a whole. It collects the
# commands you'd type to drive the pipeline. Copy/paste lines as
# needed.
#
# Conventions:
#   - All processing runs on puppy (it has the .fits.fz frames).
#   - From pip, ssh in to run things; outputs land under
#     ~/starcam-frames/night/<night>/ and are visible from pip via
#     the /mnt/puppy NFS mount.

set -e
echo "this file is a cheat-sheet, not a script — open it and copy lines."
exit 1

# ----- one-shot: process another night --------------------------------
# Reads every HH/ in the night dir, processes darkest hours first.
# Seed pole from a previous night for faster convergence.
ssh peter@192.168.4.138 'source ~/astro/activate && \
    pipeline-night /home/peter/starcam-frames/night/2026-05-22 \
        --pole-x 905 --pole-y -20'

# Same, but backgrounded (returns immediately):
ssh peter@192.168.4.138 'nohup bash -c "source ~/astro/activate && \
    pipeline-night /home/peter/starcam-frames/night/2026-05-22 \
    > /home/peter/starcam-frames/night/2026-05-22/run.log 2>&1" &'

# ----- process a single hour ------------------------------------------
ssh peter@192.168.4.138 'source ~/astro/activate && \
    pipeline-hour /home/peter/starcam-frames/night/2026-05-22/02 \
        --pole-x 905 --pole-y -20'

# Re-run a finished hour, ignoring cached outputs:
ssh peter@192.168.4.138 'source ~/astro/activate && \
    pipeline-hour /home/peter/starcam-frames/night/2026-05-22/02 --force'

# ----- monitor progress -----------------------------------------------
ssh peter@192.168.4.138 'tail -80 /home/peter/starcam-frames/night/2026-05-22/pipeline.log && \
    echo --- && cat /home/peter/starcam-frames/night/2026-05-22/pipeline-poles.csv'

# Currently running python jobs on puppy:
ssh peter@192.168.4.138 'ps -eo etime,pcpu,args --sort=-pcpu | grep python | head'

# ----- exploration: fit lens distortion -------------------------------
# Slow — best run after pipeline-night finishes. Tries pole + omega
# + radial distortion (k1, k2) jointly.
ssh peter@192.168.4.138 'source ~/astro/activate && \
    fit-geometry /home/peter/starcam-frames/night/2026-05-23/02b'

# ----- view results from pip -----------------------------------------
# View final derot stack for an hour:
splay /mnt/puppy/starcam-frames/night/2026-05-23/02b/final/

# Flick through binned frames with a hot-pixel mask:
splay /mnt/puppy/starcam-frames/night/2026-05-23/02b \
    -m /mnt/puppy/starcam-frames/night/2026-05-23/02b/hot-pixels-starcam-4pct.fits.fz \
    --highlight

# Per-candidate derotated patches mosaic:
xdg-open /mnt/puppy/starcam-frames/night/2026-05-23/02b/final/mosaic.jpg

# ----- alternate processing routes -----------------------------------
# bin 1 (raw) instead of bin 2 — skips bin-frames; pole coords double.
# Worse SNR (Bayer signal split) but full resolution.
# Currently you'd have to run the inner tools by hand:
ssh peter@192.168.4.138 'source ~/astro/activate && \
    scan-brightness /home/peter/starcam-frames/night/2026-05-23/02 && \
    sum-frames      /home/peter/starcam-frames/night/2026-05-23/02 && \
    hot-pixel-mask  /home/peter/starcam-frames/night/2026-05-23/02/sum.fits.fz --sweep \
        --out-dir /home/peter/starcam-frames/night/2026-05-23/02 && \
    find-candidates /home/peter/starcam-frames/night/2026-05-23/02 --grid 200 \
        --mask /home/peter/starcam-frames/night/2026-05-23/02/hot-pixels-starcam-4pct.fits.fz && \
    derot-patches   /home/peter/starcam-frames/night/2026-05-23/02 \
        --pole-x 1810 --pole-y 100 --patch 100 --top 20'

# ----- ideas / TODO ---------------------------------------------------
# - Bin-2 on the camera (Pi 1B side). Would halve our .npy throughput
#   over NFS — currently 80 GB/night becomes 20 GB/night. Change
#   gardencam/starcam_night_daemon.py: capture full-res, sum-bin 2x2
#   into uint16 (peak ~4092 fits comfortably), save 1296x972 .npy.
#   Cost: lose the option to revisit bin 1 from the same night. Best
#   only after we're sure bin 2 is what we want long-term — keep
#   raw for now.
#
# - Per-night daily systemd timer for pipeline-night (yesterday's
#   night, fires 06:00 BST after to-fits-sweep is quiet).
#
# - Catalog match (HYG) to convert peak-ADU per candidate into
#   magnitude. Tells us our limiting magnitude.
#
# - fit-pole-geometric: use star drift vectors only (no derot) with
#   the same (k1, k2) distortion model. Cross-check against fit-pole.
