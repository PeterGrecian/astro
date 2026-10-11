#!/bin/bash
# Weighted per-night sword stacks (sword_stack_w.py) for the cross-night deep field.
cd ~/astro/scratch/orion/deep
for k in -22 -19 -18 -15 -8 -7 -4 -2 0; do
  night=$(date -d "2026-10-09 $k days" +%F)
  ref=$((1791601980645 + k * 86164091))
  echo "$night $ref"
done | xargs -P 3 -L 1 bash -c 'bigstore-run sword_stack_w.py $0 $1 1016 1053 --track 200 --out "\$BIGSTORE/eclipticam-frames/night/$0/sword-stack-w.npz" > logs/w-$0.log 2>&1; echo done $0 $(tail -1 logs/w-$0.log)'
