#!/bin/bash
# Wrapper for storage-report.service: scan this host's astro data + disk
# capacity and report it to the DynamoDB tables behind the /astro/storage
# page. Runs periodically on each host (puppy, muppet, eclipticam).
set -uo pipefail

PY="$HOME/astro/.venv/bin/python"

"$PY" "$HOME/astro/bin/storage-report"
