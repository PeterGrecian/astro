#!/usr/bin/env bash
# Refine every failing v3w night as publish-night-cam would (same frame times,
# same acceptance), with the night's glow model unless degenerate, then 10-29's.
cd ~/tmp/derot-backfill/tree; export DEROT_CAMERA=eclipticam-v3w
one () {
  N=$1; D=~/eclipticam-frames/night/$N; G=$D/skyglow-model.npz
  nb=$(python3 -c "import numpy as np;print(np.load('$G')['sky'].sum())")
  [ "$nb" -lt 800 ] && G=~/eclipticam-frames/night/2026-10-29/skyglow-model.npz
  T=$(~/astro/.venv/bin/python bin/derot-sky clean $N --glow $D/skyglow-model.npz --times 6 2>/dev/null | grep -E '^[0-9]{2}:' | tr '\n' ' ')
  for t in ${TIMES:-23:00:00 00:00:00 22:30:00 01:00:00 02:00:00} $T; do
    out=$(~/astro/.venv/bin/python bin/derot-sky refine eclipticam-v3w/cammodel-2026-10-29.json $N $t --glow $G -o ~/tmp/derot-backfill/r-$N.json 2>&1)
    ok=$(python3 -c "import json,sys; p=json.load(open('/home/peter/tmp/derot-backfill/r-$N.json')); print(p['refine_n'], round(p['refine_median_px'],2), 'OK' if p['refine_n']>=50 and p['refine_median_px']<1.5 else 'no')" 2>/dev/null)
    echo "$N $t glowblocks=$nb $(echo "$out" | grep -o 'coarse: .*') | $ok"
    [[ "$ok" == *OK ]] && break
    rm -f ~/tmp/derot-backfill/r-$N.json
  done
}
export -f one
printf '%s\n' "$@" | xargs -P 4 -I{} bash -c 'one {}'
