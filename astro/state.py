"""Day/night/dusk/dawn state — stage 1 of the 4-stage pipeline.

Reads brightness.csv (written by stage 2) + sun altitude (from
location.json) to decide the camera's current mode. Writes the
decision and its inputs to state.json at
<frames_root>/<YYYY>/<MM>/<DD>/<camera>/state.json.

Decision-source tiers (degrades gracefully if primary signal missing):

    brightness    — recent brightness.csv row within plausible range
    sun_altitude  — no brightness; use sun altitude from location.json
    default_day   — no location either; fall back to safe day capture

state.json records decision_source + degraded_reasons so stage 2 can
pick conservative day-mode parameters when running blind, and stage 3
can choose whether to process or wait.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .brightness_log import BrightnessRow, latest as latest_brightness
from .nightdir import night_of, night_path

# Defaults — overridable per camera via camera.json["state"].
DEFAULTS = {
    # Below this sun altitude (deg), it is "night" for the purpose of the
    # sun_altitude fallback. -12 = nautical twilight; safe enough that we
    # never point a sensor at the sun.
    "sun_altitude_night_deg": -12.0,
    # Above this sun altitude (deg), it is "day".
    "sun_altitude_day_deg": -6.0,    # civil twilight
    # Brightness-based transition thresholds (stops above pedestal).
    "brightness_night_stops": 6.0,    # below this = night
    "brightness_day_stops": 10.0,     # above this = day
    # Hysteresis ticks before committing a transition (stops flapping).
    "hold_ticks": 3,
    # Max age of a brightness row before we treat it as stale and fall back.
    "stale_brightness_after_s": 600,
}


@dataclass
class State:
    camera: str
    host: str
    night: str
    mode: str                      # "day" | "night" | "dusk" | "dawn"
    transitioned_at_utc: str
    previous_mode: str | None
    decision_source: str           # "brightness" | "sun_altitude" | "default_day"
    degraded_reasons: list[str]
    latest_brightness: dict | None
    sun_altitude_deg: float | None
    written_at_utc: str
    pending_process: dict          # {dusk_window_complete, dawn_window_complete}

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def state_path(frames_root: Path, camera: str,
               when: datetime | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    return Path(frames_root) / night_path(night_of(when)) / camera / "state.json"


def load_state(frames_root: Path, camera: str,
               when: datetime | None = None) -> State | None:
    p = state_path(frames_root, camera, when)
    if not p.exists():
        return None
    return State(**json.loads(p.read_text()))


def write_state(frames_root: Path, state: State,
                when: datetime | None = None) -> Path:
    p = state_path(frames_root, state.camera, when)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state.to_json())
    return p


def sun_altitude_deg(lat: float, lon: float,
                     when: datetime | None = None) -> float:
    """Sun altitude in degrees at (lat, lon) at UTC `when`. Uses ephem."""
    import ephem
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = (when or datetime.now(timezone.utc)).strftime("%Y/%m/%d %H:%M:%S")
    obs.pressure = 0  # ignore atmospheric refraction; we don't need 0.01 deg
    sun = ephem.Sun(obs)
    return float(sun.alt) * 180.0 / 3.141592653589793


def _mode_from_brightness(stops: float, params: dict,
                          previous: str | None) -> str:
    """Classify brightness with hysteresis-friendly thresholds.

    Returns "day", "night", or "dusk"/"dawn" in the in-between band.
    The caller applies hold_ticks before committing a transition.
    """
    if stops <= params["brightness_night_stops"]:
        return "night"
    if stops >= params["brightness_day_stops"]:
        return "day"
    # In-between: dusk if we were brighter, dawn if we were darker.
    if previous in ("day", "dusk"):
        return "dusk"
    return "dawn"


def _mode_from_sun(alt_deg: float, params: dict,
                   previous: str | None = None) -> str:
    if alt_deg <= params["sun_altitude_night_deg"]:
        return "night"
    if alt_deg >= params["sun_altitude_day_deg"]:
        return "day"
    # In the twilight band the sun is always below the horizon, so altitude
    # alone can't tell dusk from dawn — use the trajectory implied by the
    # previous mode: leaving day -> dusk; leaving night -> dawn.
    if previous in ("day", "dusk"):
        return "dusk"
    return "dawn"


def decide(camera: str, host: str, cfg_state: dict | None,
           location: dict | None, frames_root: Path,
           previous: State | None = None,
           when: datetime | None = None) -> State:
    """Compute the current State for one camera.

    Inputs:
      cfg_state — overrides for DEFAULTS, from camera.json["state"]
      location  — contents of location.json (needs "lat", "lon")
      previous  — last written state (for hysteresis + previous_mode)

    Output: a fresh State ready to write_state().
    """
    when = when or datetime.now(timezone.utc)
    params = {**DEFAULTS, **(cfg_state or {})}
    night = night_of(when)
    reasons: list[str] = []

    # --- tier 1: brightness ---
    br = latest_brightness(frames_root, camera, when=when)
    br_fresh = br is not None and (
        when - br.utc <= timedelta(seconds=params["stale_brightness_after_s"]))
    if br is not None and not br_fresh:
        age = int((when - br.utc).total_seconds())
        reasons.append(f"brightness_stale_{age}s")
    elif br is None:
        reasons.append("no_brightness_yet")

    # --- tier 2: sun altitude (also recorded even when brightness wins) ---
    sun_alt: float | None = None
    if location and "lat_deg" in location and "lon_deg" in location:
        sun_alt = sun_altitude_deg(
            location["lat_deg"], location["lon_deg"], when)
    else:
        reasons.append("no_location_json")

    # --- pick a decision source ---
    if br_fresh:
        source = "brightness"
        mode = _mode_from_brightness(
            br.stops_above_pedestal, params,
            previous.mode if previous else None)
    elif sun_alt is not None:
        source = "sun_altitude"
        mode = _mode_from_sun(sun_alt, params,
                              previous.mode if previous else None)
    else:
        source = "default_day"
        mode = "day"

    # --- hysteresis (only meaningful when previous mode disagrees) ---
    if previous and previous.mode != mode:
        # We don't keep a multi-tick counter here yet — the daemon loop
        # owns that. For now we emit the candidate; the daemon decides
        # whether to commit by counting consecutive disagreements.
        pass

    transitioned = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    if previous and previous.mode == mode:
        transitioned = previous.transitioned_at_utc

    latest_b = None
    if br is not None:
        latest_b = {
            "stops_above_pedestal": br.stops_above_pedestal,
            "per_s": br.per_s,
            "ts_utc": br.utc_iso,
        }

    pending = (previous.pending_process if previous else {
        "dusk_window_complete": False,
        "dawn_window_complete": False,
    })
    # Transition into night marks dusk window complete; into day marks dawn.
    # Morning can arrive via dawn or (if the band was mislabelled) dusk, so
    # accept any not-from-day path into day as a completed dawn window.
    if previous and previous.mode != mode:
        if mode == "night":
            pending = {**pending, "dusk_window_complete": True}
        elif mode == "day" and previous.mode in ("night", "dawn", "dusk"):
            pending = {**pending, "dawn_window_complete": True}

    return State(
        camera=camera,
        host=host,
        night=night,
        mode=mode,
        transitioned_at_utc=transitioned,
        previous_mode=previous.mode if previous else None,
        decision_source=source,
        degraded_reasons=reasons,
        latest_brightness=latest_b,
        sun_altitude_deg=sun_alt,
        written_at_utc=when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        pending_process=pending,
    )
