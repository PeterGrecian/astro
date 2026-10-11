#!/bin/bash
# Per-night sword stacks for the cross-night deep field. Ref = the instant the sword sits at its 10-09 pixel.
cd ~/astro/bin
for k in -22 -19 -18 -15 -8 -7 -4 -2; do
  night=$(date -d "2026-10-09 $k days" +%F)
  ref=$((1791601980645 + k * 86164091))
  echo "$night $ref"
done | xargs -P 3 -L 1 bash -c 'bigstore-run sword-stack-draft.py $0 $1 1016 1053 --track 200 --sky-max 95 > ~/astro/scratch/orion/deep/logs/$0.log 2>&1; echo done $0 $(tail -1 ~/astro/scratch/orion/deep/logs/$0.log)'
