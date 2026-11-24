#!/bin/bash
# best-10% and next-10% stacks, E3 60 s window period (astro-science, Peter 2026-11-24). Run under
# systemd-run CPUQuota=200% MemoryMax=3G Nice=10 (astro-pipeline's cap for muppet).
cd ~/astro; P=~/astro/.venv/bin/python; B=~/tmp/best10; export PYTHONUNBUFFERED=1
scratch/best10/inputs.sh $(cat $B/e3-nights.txt)
$P scratch/best10/stack.py $B/best $B/in 2026-09-21 00:00:00 E3-window-60s $B/best10.json +$B/next10.json
$P scratch/best10/stack.py $B/next $B/in 2026-09-21 00:00:00 E3-window-60s $B/next10.json +$B/best10.json
$P scratch/best10/stack.py --combine $B/both $B/best/nights/* $B/next/nights/*
echo ALL DONE
