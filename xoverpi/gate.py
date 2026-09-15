#!/usr/bin/env python3
"""xoverpi-gate — sun-altitude day/night gate for the xoverpi capture daemon.

One tick: compute sun altitude (shared astro.state.sun_altitude_deg, the same
function astrocam and eclipticam use), decide night vs day from xoverpi's
camera.json["state"] thresholds, and start/stop xoverpi-capture.service.
Run every minute from xoverpi-gate.timer.

Why this exists: without it, nothing starts capture at dusk. `systemctl enable`
only starts a unit at BOOT, so an enabled capture unit would come up in daylight
and exit on its saturation guard within a frame or two. The night of 2026-09-14
was lost to exactly this gap - the unit was installed and correct, and captured
nothing, because nobody was there to type `start`.

Why sun altitude and not frame brightness: altitude is a hard physical signal,
while brightness is confused by headlights, moon, AE wobble and cloud. This
follows eclipticam-v3w and astrocam rather than inventing a third convention.

Simpler than astrocam's gate in two ways, both deliberate:
  * NO COVER. astrocam drives an SG90 lens cover and must persist its last
    commanded position to avoid buzzing the servo every tick. The FirstScope
    has no cover - it is carried out and set up by hand - so there is no
    actuator to manage and no state to persist. This gate is fully stateless.
  * NO RAIN CHECK. astrocam's gate stops capture and closes the cover when
    open-meteo reports rain, which protects hardware. Here there is no cover to
    close, so a rain check could only ever STOP a session that is running -
    losing data without protecting anything - and it would add an external HTTP
    dependency to the one thing that must not fail. The scope is not left out.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.config import CameraConfig          # noqa: E402
from astro.state import sun_altitude_deg       # noqa: E402

CAPTURE_SERVICE = "xoverpi-capture.service"
DEFAULT_NIGHT_DEG = -12.0
DEFAULT_DAY_DEG = -10.0


def _systemctl(*args):
    """Best-effort systemctl; never raises."""
    try:
        return subprocess.run(["systemctl", *args],
                              capture_output=True, text=True, timeout=10)
    except Exception as e:
        logging.error(f"systemctl {' '.join(args)}: {e}")
        return None


def _is_active(unit: str) -> bool:
    r = _systemctl("is-active", "--quiet", unit)
    return r is not None and r.returncode == 0


def ensure_running(unit: str):
    if not _is_active(unit):
        logging.info(f"starting {unit}")
        _systemctl("start", "--no-block", unit)


def ensure_stopped(unit: str):
    if _is_active(unit):
        logging.info(f"stopping {unit}")
        _systemctl("stop", "--no-block", unit)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = CameraConfig.load("xoverpi")
    st = cfg.get("state") or {}
    night_deg = float(st.get("sun_altitude_night_deg", DEFAULT_NIGHT_DEG))
    day_deg = float(st.get("sun_altitude_day_deg", DEFAULT_DAY_DEG))

    loc = cfg.location or {}
    if "lat_deg" not in loc or "lon_deg" not in loc:
        # No location -> safest is DAY. A gate that cannot tell the time of day
        # must not be the thing that leaves capture running into sunlight.
        logging.warning("no location.json lat/lon; defaulting to day (stop)")
        ensure_stopped(CAPTURE_SERVICE)
        return 0

    alt = sun_altitude_deg(loc["lat_deg"], loc["lon_deg"])

    # Asymmetric thresholds give hysteresis: enter night below night_deg,
    # return to day above day_deg, hold whatever we are doing in between.
    if alt <= night_deg:
        logging.info(f"sun_alt={alt:.2f} <= {night_deg} -> night")
        ensure_running(CAPTURE_SERVICE)
    elif alt >= day_deg:
        logging.info(f"sun_alt={alt:.2f} >= {day_deg} -> day")
        ensure_stopped(CAPTURE_SERVICE)
    else:
        logging.info(f"sun_alt={alt:.2f} in ({night_deg},{day_deg}) band; "
                     f"holding {'running' if _is_active(CAPTURE_SERVICE) else 'stopped'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
