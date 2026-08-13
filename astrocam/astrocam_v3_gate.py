#!/usr/bin/env python3
"""astrocam-v3-gate — sun-altitude day/night gate for the v3 night daemon.

One tick: compute sun altitude (shared astro.state.sun_altitude_deg, the
same function eclipticam uses), decide night vs day from astrocam's
camera.json["state"] thresholds, and start/stop astrocam-v3-night.service
accordingly. Mirrors eclipticam's capture.py ensure_v3w_streaming_*()
pattern, keyed off SUN ALTITUDE only.

Why sun-altitude, not brightness: the imx708 pedestal is STALE (imx219
value) so per-frame "stops above pedestal" misclassifies daylight as dark.
eclipticam-v3w deliberately gates on sun altitude for exactly this reason
(brightness is confused by headlights/moon/AE wobble/cloud); altitude is a
hard physical signal. Revisit once the imx708 pedestal is remeasured.

Run every minute from astrocam-v3-gate.timer. The uploader runs
continuously regardless (draining whatever the daemon wrote).
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from astro.config import CameraConfig
from astro.state import sun_altitude_deg

NIGHT_SERVICE = "astrocam-v3-night.service"
COVER_SCRIPT = HERE / "cover.py"
# The gate is stateless and ticks every minute, but a servo is not idempotent
# the way `systemctl start` is: re-commanding it each tick would buzz the SG90
# 60x/hour for no reason. So the cover's last commanded position is persisted
# here and we move ONLY on a change.
COVER_STATE_FILE = Path("/var/lib/astrocam/cover.json")

# Defaults if camera.json omits them. Night below -10 matches astrocam's
# configured sun_altitude_night_deg and eclipticam-v3w. Day threshold a
# touch higher gives a small hysteresis band so the boundary doesn't flap.
DEFAULT_NIGHT_DEG = -10.0
DEFAULT_DAY_DEG = -8.0


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
        # --no-block: the night daemon can take up to TimeoutStopSec (90s)
        # to finish an in-flight 60s exposure on stop; don't let a blocking
        # start/stop outlive this oneshot tick. systemd owns the drain.
        _systemctl("start", "--no-block", unit)


def ensure_stopped(unit: str):
    if _is_active(unit):
        logging.info(f"stopping {unit}")
        _systemctl("stop", "--no-block", unit)


def _read_cover_position() -> str | None:
    """Last position we commanded, or None if unknown (first run / bad file)."""
    try:
        return json.loads(COVER_STATE_FILE.read_text()).get("position")
    except (OSError, ValueError):
        return None


def _write_cover_position(position: str):
    try:
        COVER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COVER_STATE_FILE.write_text(json.dumps({"position": position}))
    except OSError as e:
        logging.error(f"cover state write failed: {e}")


def ensure_cover(position: str):
    """Drive the cover to `position` if it isn't already there.

    Never raises: a stuck servo must not stop the gate from managing the
    night service (an uncovered lens is a lost day of flats, a dead gate is
    a lost night of data). Only records the new position if the command
    actually succeeded, so a failure retries on the next tick.
    """
    if _read_cover_position() == position:
        return
    logging.info(f"cover -> {position}")
    try:
        subprocess.run([sys.executable, str(COVER_SCRIPT), position],
                       capture_output=True, text=True, timeout=30, check=True)
    except Exception as e:
        logging.error(f"cover {position} FAILED: {e}")
        return
    _write_cover_position(position)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = CameraConfig.load("astrocam")
    st = cfg.get("state") or {}
    night_deg = float(st.get("sun_altitude_night_deg", DEFAULT_NIGHT_DEG))
    day_deg = float(st.get("sun_altitude_day_deg", DEFAULT_DAY_DEG))

    loc = cfg.location or {}
    if "lat_deg" not in loc or "lon_deg" not in loc:
        # No location -> safest is DAY (never point the sensor at the sun in
        # a way that pins frames all day). Stop the night daemon.
        logging.warning("no location.json lat/lon; defaulting to day (stop)")
        ensure_stopped(NIGHT_SERVICE)
        ensure_cover("closed")
        return 0

    alt = sun_altitude_deg(loc["lat_deg"], loc["lon_deg"])

    # Asymmetric thresholds give natural hysteresis: enter night below
    # night_deg, return to day above day_deg, hold state in between (which
    # here means: don't actively flip — we key purely off the two edges).
    if alt <= night_deg:
        logging.info(f"sun_alt={alt:.2f} <= {night_deg} -> night")
        ensure_cover("open")
        ensure_running(NIGHT_SERVICE)
    elif alt >= day_deg:
        logging.info(f"sun_alt={alt:.2f} >= {day_deg} -> day")
        ensure_stopped(NIGHT_SERVICE)
        ensure_cover("closed")
    else:
        # In the band: leave the service in whatever state it's in.
        logging.info(f"sun_alt={alt:.2f} in ({night_deg},{day_deg}) band; "
                     f"holding {'running' if _is_active(NIGHT_SERVICE) else 'stopped'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
