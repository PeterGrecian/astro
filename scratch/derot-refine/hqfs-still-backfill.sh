#!/usr/bin/env bash
# Re-run night-still (plate solve, star counts, colours) for hqfs nights and
# publish just those products, then the all-nights composite. On muppet.
cd ~/astro; PY=.venv/bin/python; R=/mnt/bigstore/astro-data/xoverpi-frames/night
for n in "$@"; do
  nd=$R/$n; echo "=== $n"
  mkdir -p $nd/.old-still && mv $nd/night-still.jpg $nd/night-still.json $nd/.old-still/ 2>/dev/null
  $PY bin/night-still --camera xoverpi --night $n 2>&1 | grep -E "solved|solve failed|star counts|colours|done|Gaia" 
  if [[ -s $nd/night-still.jpg ]]; then
    ~/super/bin/trash $nd/.old-still >/dev/null 2>&1 || true
  else
    mv $nd/.old-still/* $nd/ 2>/dev/null; rmdir $nd/.old-still; continue
  fi
  $PY bin/annotate-night-still $nd/night-still.jpg $nd/night-still-annotated.jpg --geometry $nd/night-still.json >/dev/null
  $PY bin/annotate-night-still $nd/night-still.jpg $nd/night-still-annotated-dark.jpg --geometry $nd/night-still.json --surround "#404040" >/dev/null
  $PY - "$n" "$nd" <<'PYEOF'
import sys; sys.path.insert(0, ".")
from pathlib import Path
from astro.config import CameraConfig
from astro.present.publish import publish_night
cfg = CameraConfig.load("xoverpi"); nd = Path(sys.argv[2])
names = ["night-still.jpg", "night-still.json", "night-still-annotated.jpg", "night-still-annotated-dark.jpg",
         "star-counts.png", "star-counts.json", "star-colours.png", "star-colours.json", "star-crops.jpg"]
publish_night(cfg, sys.argv[1], [nd / x for x in names if (nd / x).exists()])
PYEOF
done
echo "=== composite"; $PY bin/night-still-composite --camera xoverpi --publish 2>&1 | tail -12
