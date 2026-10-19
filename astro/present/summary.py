"""Per-night summary.json — the single document the website Lambda reads.

Schema (v2, camera-parametric — distinct from starcam's pipeline-night
summary.yaml, which stays untouched until Phase 4):

{
  "schema": 2,
  "camera": "astrocam",
  "night": "2026-06-09",
  "generated_utc": "...",
  "n_frames": 974,
  "first_frame_utc": "...", "last_frame_utc": "...",
  "hours": [{"hh": "23", "n_frames": 360, "mean_brightness": 31.2}, ...],
  "badpix": {"n_hot": ..., "n_cold": ..., "bad_pct": ...},
  "derot": {"pole_xy": [x, y], "pole_source": "prior|fit|solved",
            "window_utc": [start, end], "n_frames": N,
            # sensitivity yardstick (from derot-select / plate solve):
            "n_sources": N,          # registered point sources in the stack
            "limiting_mag": V,       # ~limiting V mag (anchored, e.g. Polaris)
            "best_window_frames": N, # winning interval length
            "k1": k1, "k2": k2       # fitted distortion (null if unfitted)
            } | null,
  "outputs": {"max_jpg": "max.jpg", "derot_jpg": "derot.jpg",
              "brightness_png": "brightness.png", ...}
}
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def build(camera: str, night: str, rows, badpix: dict | None,
          derot: dict | None, outputs: dict) -> dict:
    """rows = brightness rows (astro.process.brightness.measure)."""
    hours = {}
    for r in rows:
        t = datetime.fromisoformat(r[1])
        hh = f"{t.hour:02d}"
        hours.setdefault(hh, []).append(float(r[3]))
    # Chronological within the noon-rollover night: 12..23 then 00..11.
    order = [f"{h:02d}" for h in list(range(12, 24)) + list(range(0, 12))]
    hour_list = [{"hh": hh,
                  "n_frames": len(hours[hh]),
                  "mean_brightness": round(sum(hours[hh]) / len(hours[hh]), 3)}
                 for hh in order if hh in hours]
    env_temps = []
    env_rhs = []
    for r in rows:
        if isinstance(r, dict):
            bt = r.get("box_temp_c")
            brh = r.get("box_rh_pct")
        else:
            bt = r[9] if len(r) > 9 else None
            brh = r[10] if len(r) > 10 else None
        if bt not in (None, ""):
            try:
                env_temps.append(float(bt))
            except ValueError:
                pass
        if brh not in (None, ""):
            try:
                env_rhs.append(float(brh))
            except ValueError:
                pass

    env = None
    if env_temps or env_rhs:
        env = {}
        if env_temps:
            env["box_temp_min"] = round(min(env_temps), 1)
            env["box_temp_max"] = round(max(env_temps), 1)
        if env_rhs:
            env["box_rh_min"] = round(min(env_rhs), 1)
            env["box_rh_max"] = round(max(env_rhs), 1)

    summary = {
        "schema": 2,
        "camera": camera,
        "night": night,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_frames": len(rows),
        "first_frame_utc": rows[0][1] if rows else None,
        "last_frame_utc": rows[-1][1] if rows else None,
        "hours": hour_list,
        "badpix": badpix,
        "derot": derot,
        "env": env,
        "outputs": outputs,
    }
    return summary


def write(summary: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=False)
