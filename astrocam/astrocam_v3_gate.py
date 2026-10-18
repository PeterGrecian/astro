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
import urllib.request
import urllib.error
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
# Durable record of every cover move and every cloud verdict change, so
# "did it close for cloud at 02:00?" is answerable after the journal has
# rotated. utc,event,position,reason,detail.
COVER_LOG = Path("/var/lib/astrocam/cover-log.csv")
# Last good open-meteo answer: a 503 reuses it rather than reading as dry.
WEATHER_CACHE = Path("/var/lib/astrocam/weather.json")
WEATHER_STALE_S = 1800
# Cloud verdict persisted between ticks (the gate itself is stateless).
CLOUD_STATE = Path("/var/lib/astrocam/cloud.json")
# The night daemon's per-frame environment log (epoch_ms = END of exposure,
# column 2; frame mean, column 8). Local SD, so the cloud decision never
# waits on NFS. NOT the buffer's brightness.csv: the uploader drains that,
# so on 10-18 the verdict saw zero frames all night.
LOCAL_BRIGHTNESS = Path("/var/lib/astrocam-storage/env/frame-env.csv")
# camera.json "cloud_gate" overrides these. mode "shadow" logs what it would
# do and never moves the cover; "live" moves it; "off" skips it. Thresholds
# are the median frame mean above black_level over the window, for the
# night's sub length: 10-17 (15 s) read 6.4-10 clear and dark, ~22 in a
# brighter clear spell, and 76-120 on streetlit overcast nights.
CLOUD_DEFAULTS = {"mode": "shadow", "window_min": 10,
                  "close_above_black": 30.0, "open_above_black": 16.0}

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


def _log_cover(event: str, position: str, reason: str, detail: str = ""):
    """Append one row to the durable cover log. Never raises."""
    from datetime import datetime, timezone
    try:
        new = not COVER_LOG.exists()
        with COVER_LOG.open("a") as fh:
            if new:
                fh.write("utc,event,position,reason,detail\n")
            utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(f"{utc},{event},{position},{reason},{detail}\n")
    except OSError as e:
        logging.error(f"cover log write failed: {e}")


def ensure_cover(position: str, reason: str = "", detail: str = ""):
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
    _log_cover("move", position, reason, detail)


def is_raining(lat: float, lon: float) -> bool:
    """open-meteo's current weather code says rain (>= 50). A failed fetch
    reuses the last good answer for up to WEATHER_STALE_S, then reads as
    RAIN: the lens is exposed, so an unknown sky closes the cover."""
    import time
    try:
        raining = _fetch_raining(lat, lon)
    except Exception as e:
        try:
            c = json.loads(WEATHER_CACHE.read_text())
            age = time.time() - float(c["t"])
            if age < WEATHER_STALE_S:
                logging.warning(f"weather fetch failed ({e}); using cached "
                                f"raining={c['raining']} from {age:.0f} s ago")
                return bool(c["raining"])
        except (OSError, ValueError, KeyError):
            pass
        logging.error(f"weather fetch failed ({e}) and no fresh cache; "
                      "treating as RAIN")
        return True
    try:
        WEATHER_CACHE.write_text(json.dumps({"t": time.time(), "raining": raining}))
    except OSError as e:
        logging.error(f"weather cache write failed: {e}")
    return raining


def cloud_verdict(black_level: float, gate: dict) -> tuple[str, float, int]:
    """("cloudy"|"clear"|"unsure", median above black, n frames) over the
    last window_min minutes of the night daemon's local brightness rows."""
    import statistics
    import time
    since_ms = (time.time() - 60 * float(gate["window_min"])) * 1000
    vals = []
    try:
        with LOCAL_BRIGHTNESS.open() as fh:
            next(fh, None)
            for line in fh:
                f = line.split(",")
                try:
                    if int(f[1]) >= since_ms:
                        vals.append(float(f[7]) - black_level)
                except (ValueError, IndexError):
                    continue
    except OSError:
        return "unsure", float("nan"), 0
    # Need most of the window's frames, not one or two after a restart.
    if len(vals) < 3:
        return "unsure", float("nan"), len(vals)
    med = statistics.median(vals)
    if med > float(gate["close_above_black"]):
        return "cloudy", med, len(vals)
    if med < float(gate["open_above_black"]):
        return "clear", med, len(vals)
    return "unsure", med, len(vals)


def cloud_state(black_level: float, gate: dict) -> str:
    """Hysteresis over cloud_verdict: "unsure" holds the previous state.
    Logs every change. Returns "cloudy" or "clear"."""
    verdict, med, n = cloud_verdict(black_level, gate)
    try:
        prev = json.loads(CLOUD_STATE.read_text()).get("state", "clear")
    except (OSError, ValueError):
        prev = "clear"
    state = prev if verdict == "unsure" else verdict
    logging.info(f"cloud: verdict={verdict} median_above_black={med:.2f} "
                 f"n={n} state={state} mode={gate['mode']}")
    if state != prev:
        _log_cover("cloud", "closed" if state == "cloudy" else "open",
                   f"{gate['mode']}:{state}", f"median={med:.2f} n={n}")
        try:
            CLOUD_STATE.write_text(json.dumps({"state": state}))
        except OSError as e:
            logging.error(f"cloud state write failed: {e}")
    return state


def _fetch_raining(lat: float, lon: float) -> bool:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    req = urllib.request.Request(url, headers={'User-Agent': 'astro-gate/1.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode())
        return data["current_weather"]["weathercode"] >= 50


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = CameraConfig.load("astrocam")
    st = cfg.get("state") or {}
    night_deg = float(st.get("sun_altitude_night_deg", DEFAULT_NIGHT_DEG))
    day_deg = float(st.get("sun_altitude_day_deg", DEFAULT_DAY_DEG))

    gate = {**CLOUD_DEFAULTS, **(cfg.get("cloud_gate") or {})}
    black_level = float(cfg.get("black_level") or 64)

    loc = cfg.location or {}
    if "lat_deg" not in loc or "lon_deg" not in loc:
        # No location -> safest is DAY (never point the sensor at the sun in
        # a way that pins frames all day). Stop the night daemon.
        logging.warning("no location.json lat/lon; defaulting to day (stop)")
        ensure_stopped(NIGHT_SERVICE)
        ensure_cover("closed", "no-location")
        return 0

    alt = sun_altitude_deg(loc["lat_deg"], loc["lon_deg"])
    raining = is_raining(loc["lat_deg"], loc["lon_deg"])

    # Asymmetric thresholds give natural hysteresis: enter night below
    # night_deg, return to day above day_deg, hold state in between (which
    # here means: don't actively flip — we key purely off the two edges).
    if alt <= night_deg:
        if raining:
            # The cover is transparent from 2026-10-18: rain closes it and
            # capture carries on through it (COVER=closed on those frames).
            logging.info(f"sun_alt={alt:.2f} <= {night_deg} but RAINING -> closing, capture continues")
            ensure_running(NIGHT_SERVICE)
            ensure_cover("closed", "rain")
        else:
            logging.info(f"sun_alt={alt:.2f} <= {night_deg} and dry -> night")
            ensure_running(NIGHT_SERVICE)
            # The cover is transparent from 2026-10-18, so capture runs on
            # under a closed cover and the same frames say when to reopen.
            cloudy = (gate["mode"] != "off"
                      and cloud_state(black_level, gate) == "cloudy")
            if cloudy and gate["mode"] == "live":
                ensure_cover("closed", "cloud")
            else:
                ensure_cover("open", "night")
    elif alt >= day_deg:
        logging.info(f"sun_alt={alt:.2f} >= {day_deg} -> day")
        ensure_stopped(NIGHT_SERVICE)
        ensure_cover("closed", "day")
        try:
            CLOUD_STATE.unlink()   # each night starts from "clear"
        except OSError:
            pass
    else:
        # In the band: leave the service in whatever state it's in, unless it's raining
        if raining and _is_active(NIGHT_SERVICE):
            logging.info(f"sun_alt={alt:.2f} in band but RAINING -> closing, capture continues")
            ensure_cover("closed", "rain")
        else:
            logging.info(f"sun_alt={alt:.2f} in ({night_deg},{day_deg}) band; "
                         f"holding {'running' if _is_active(NIGHT_SERVICE) else 'stopped'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
