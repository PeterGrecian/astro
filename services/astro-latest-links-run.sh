#!/bin/bash
# Wrapper for astro-latest-links.service: repoint the per-camera `latest`
# symlinks at today's data on puppy's NFS shares. Each camera's link lands
# in its own frames_root (astro-latest-links anchors it there), so the one
# invocation covers both the eclipticam and astrocam shares.
set -uo pipefail

"$HOME/astro/.venv/bin/python" "$HOME/astro/bin/astro-latest-links" \
    --camera eclipticam-v3w \
    --camera eclipticam-v1 \
    --camera astrocam
