"""Locate a night's frames for any camera, per its night_layout.

Layouts (camera.json "night_layout"):
  canonical   <frames_root>/YYYY/MM/DD/<camera>/{day,night}/HH/HH-MM-SS.fits.fz
              (DECISIONS.md 2026-06-16 canonical layout). Camera name is
              taken from cfg.name.
  flat        <frames_root>/YYYY-MM-DD/HH/*.fits.fz, UTC date dirs;
              night membership decided by DATE-OBS within the
              noon-rollover window (astrocam, pre-migration).
  percam      <frames_root>/night/<night-date>/<cam>/HH/*.fits.fz,
              already night-keyed (legacy eclipticam pre-split).
  starcam-npy <frames_root>/night/<night-date>/HH/*.{npy,fits.fz},
              night-keyed, epoch-ms filenames (decommissioned starcam).

Returns a sorted list of (utc_datetime, path).
"""
import glob
from datetime import datetime, timezone
from pathlib import Path

from astropy.io import fits

from astro.nightdir import night_path, night_window

# Derived outputs that share the frame dirs but are not frames.
_SKIP_SUBSTRINGS = (".derot.", "/max.fits", "/min.fits", "/sum.fits")


def _date_obs(path: Path):
    try:
        with fits.open(path) as hdul:
            return datetime.fromisoformat(hdul[1].header["DATE-OBS"])
    except (OSError, KeyError, ValueError, IndexError):
        return None


def _epoch_ms_time(path: Path):
    name = path.name.split(".", 1)[0]
    try:
        v = int(name)
    except ValueError:
        return None
    if v < 10**12:  # not a 13-digit epoch-ms
        return None
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc)


def list_night_frames(cfg, night: str, ext: str = "*.fits.fz"):
    """All raw frames of `night` for camera config `cfg`, time-sorted."""
    layout = cfg.night_layout
    root = cfg.frames_root
    keep = []

    if layout == "canonical":
        base = root / night_path(night) / cfg.name / "night"
        for hour_dir in sorted(base.glob("[0-2][0-9]")):
            for f in sorted(hour_dir.glob(ext)):
                if any(s in str(f) for s in _SKIP_SUBSTRINGS):
                    continue
                t = _date_obs(f)
                if t is not None:
                    keep.append((t, f))

    elif layout == "flat":
        start, end = night_window(night)
        for day in (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")):
            for hour in range(24):
                pat = str(root / day / f"{hour:02d}" / ext)
                for f in glob.glob(pat):
                    if any(s in f for s in _SKIP_SUBSTRINGS):
                        continue
                    t = _date_obs(Path(f))
                    if t is not None and start <= t < end:
                        keep.append((t, Path(f)))

    elif layout == "percam":
        # Legacy: pre-split eclipticam writes to night/<night>/<v1|v3w>/HH.
        # New code paths (post-split) should use "canonical".
        subcam = cfg.name.split("-", 1)[1] if "-" in cfg.name else cfg.name
        base = root / "night" / night / subcam
        for hour_dir in sorted(base.glob("[0-2][0-9]")):
            if hour_dir.name.endswith("b"):
                continue
            for f in sorted(hour_dir.glob(ext)):
                if any(s in str(f) for s in _SKIP_SUBSTRINGS):
                    continue
                t = _date_obs(f)
                if t is not None:
                    keep.append((t, f))

    elif layout == "starcam-npy":
        base = root / "night" / night
        for hour_dir in sorted(base.glob("[0-2][0-9]")):
            for f in sorted(hour_dir.glob(ext)):
                if any(s in str(f) for s in _SKIP_SUBSTRINGS):
                    continue
                t = _epoch_ms_time(f) or _date_obs(f)
                if t is not None:
                    keep.append((t, f))

    else:
        raise ValueError(f"{cfg.name}: unknown night_layout {layout!r}")

    keep.sort()
    return keep


def night_output_dir(cfg, night: str) -> Path:
    """Where a night's derived artefacts live (next to the data)."""
    if cfg.night_layout == "canonical":
        return cfg.frames_root / night_path(night) / cfg.name
    if cfg.night_layout == "flat":
        return cfg.frames_root / night
    return cfg.frames_root / "night" / night
