#!/bin/bash
# One-step cubic resampling: each night's frames straight onto the 10-09 grid (affines from weighted-affines.json).
cd ~/astro/scratch/orion/deep
for k in -22 -19 -18 -15 -8 -7 -4 -2 0; do
  night=$(date -d "2026-10-09 $k days" +%F)
  echo "$night $((1791601980645 + k * 86164091))"
done | xargs -P 3 -L 1 bash -c 'pre=$(python3 -c "import json,sys;print(\",\".join(\"%.9g\" % v for r in json.load(open(\"weighted-affines.json\"))[sys.argv[1]] for v in r))" $0)
  bigstore-run sword_stack_w.py $0 $1 1016 1053 --track 200 --pre="$pre" --out "\$BIGSTORE/eclipticam-frames/night/$0/sword-stack-1s.npz" > logs/1s-$0.log 2>&1; echo done $0 $(tail -1 logs/1s-$0.log)'
