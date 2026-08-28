#!/usr/bin/env bash
# Front Matter CMS action: publish this card to the live gallery.
# Deliberately NOT a dry run — the button says publish. FM shows the output.
set -euo pipefail
proj="$1"; card="$2"
"$proj/.venv/bin/python" "$proj/transients/publish.py" "$card" --publish
