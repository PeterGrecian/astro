#!/bin/bash
# Rerun of run.sh with the glow-fit gate off (MAXR=1e9), q <= 1.2, reference glow model for failed fits
# and the nearest night's ring map (astro-science, 2026-11-24). Keeps the inputs that already exist.
cd ~/astro; P=~/astro/.venv/bin/python; B=~/tmp/best10; export PYTHONUNBUFFERED=1 MAXR=1e9 QMAX=1.2
for n in $(cat $B/e3-nights.txt); do [[ -s $B/in/$n/align.npy ]] || trash $B/in/$n/align.log 2>/dev/null; done
scratch/best10/inputs.sh $(cat $B/e3-nights.txt)
for d in best next both; do [[ -e $B/$d ]] && trash $B/$d; done
$P scratch/best10/stack.py $B/best $B/in 2026-09-21 00:00:00 E3-window-60s $B/best10.json +$B/next10.json
$P scratch/best10/stack.py $B/next $B/in 2026-09-21 00:00:00 E3-window-60s $B/next10.json +$B/best10.json
$P scratch/best10/stack.py --combine $B/both $B/best/nights/* $B/next/nights/*
echo ALL DONE
