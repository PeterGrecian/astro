#!/bin/bash
# Per-night derot inputs for the best-10% stacks (astro-science, Peter 2026-11-24), mirroring
# publish-night-cam's glow + refine + align, plus the clipped ring residual. Written to
# $OUT/<night>/, never to the bigstore night dirs (pipeline-owned). Usage: inputs.sh <night> ...
cd ~/astro; P=~/astro/.venv/bin/python; OUT=${OUT:-$HOME/tmp/best10/in}; J=${J:-2}; MAXR=${MAXR:-1.5}   # glow-fit gate; 1e9 = off (blocks are already star-count selected)
REFGLOW=${REFGLOW:-$OUT/2026-09-21/skyglow-model.npz}   # used when a night's own fit fails
export DEROT_CAMERA=astrocam BIGSTORE=/mnt/bigstore/astro-data
SEED0=$(ls ~/astro/astrocam/cammodel-*.json | sort | tail -1)
for N in "$@"; do
  D=$OUT/$N; mkdir -p $D; t0=$(date +%s); echo "=== $N"
  [[ -s $D/skyglow-cube.npz ]] || nice -n 15 $P bin/skyglow-model cube astrocam $N -o $D/skyglow-cube.npz -j $J > $D/cube.log 2>&1 || { echo "$N cube FAILED"; continue; }
  [[ -s $D/skyglow-model.npz ]] || nice -n 15 $P bin/skyglow-model fit $D/skyglow-cube.npz -o $D/skyglow-model.npz > $D/fit.log 2>&1 || { [[ -s $REFGLOW ]] && cp $REFGLOW $D/skyglow-model.npz && echo "$N own fit failed: using reference glow model" || { echo "$N fit FAILED"; continue; }; }
  G=$D/skyglow-model.npz; C=$D/skyglow-cammodel.json
  if [[ ! -s $C ]]; then
    ct=$($P bin/derot-sky clean $N --glow $G --max-ratio $MAXR --times 6 --times-out /dev/fd/3 3>&1 >/dev/null 2>/dev/null | tr '\n' ' ')
    prev=$(ls $OUT/*/skyglow-cammodel.json 2>/dev/null | awk -v n="$OUT/$N/" '$0 < n' | sort | tail -1)
    for seed in $prev $SEED0; do for t in 23:00:00 00:00:00 22:30:00 01:00:00 $ct; do
      nice -n 15 $P bin/derot-sky refine $seed $N $t --glow $G -o $C.try >> $D/refine.log 2>&1 \
        && $P -c "import json,sys; p=json.load(open('$C.try')); sys.exit(not (p['refine_n'] >= 50 and p['refine_median_px'] < 1.5))" \
        && mv $C.try $C && break 2
    done; done
    [[ -s $C ]] || { echo "$N refine FAILED"; continue; }
  fi
  [[ -s $D/align.npy ]] || nice -n 15 $P bin/derot-sky align $C $N --glow $G --max-ratio $MAXR -j $J -o $D/align.npy > $D/align.log 2>&1 || echo "$N align failed (stacking unaligned)"
  if [[ $MAXR == 1.5 && ! -s $D/resid.npy ]]; then   # gate off: no clean set for a ring map; stack.py borrows the nearest night's
    nice -n 15 $P bin/derot-sky residual $N --glow $G --stat clipped --channel sum -o $D/resid.npy > $D/resid.log 2>&1 || echo "$N residual failed"
  fi
  echo "$N done in $(( ($(date +%s) - t0) / 60 )) min: $(python3 -c "import json;p=json.load(open('$C'));print('refine', p['refine_n'], 'stars', round(p['refine_median_px'],2), 'px')")"
done
