"""Resolve where a (camera, night)'s data physically lives — across
multiple storage roots and across layouts (old/new split).

The point: callers ask "where is eclipticam-v3w for 2026-06-12?" and get
back the directory that actually holds it *right now*, without knowing
whether it's in the legacy `night/<date>/<subcam>` tree, the canonical
`YYYY/MM/DD/<camera>` tree, or a cold-archive root added later. Data can
move for storage/archival reasons — register a new root in the camera's
`frames_roots` and resolution keeps working; nothing computes a fixed path.

This complements astro.frames (which lists the *frames* once you know the
layout): locate answers the prior question of *which root + layout* holds
the night at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .nightdir import night_of, night_path


# Layout -> how to form the night's data dir under a given root. Mirrors
# astro.frames; kept here as a pure (root, camera, night) -> Path map so a
# single night can be probed across every layout without a config commit.
def _canonical_dir(root: Path, camera: str, night: str) -> Path:
    return root / night_path(night) / camera


def _percam_dir(root: Path, camera: str, night: str) -> Path:
    # Legacy pre-split eclipticam: night/<date>/<subcam>, subcam = the bit
    # after the first '-' (eclipticam-v3w -> v3w).
    subcam = camera.split("-", 1)[1] if "-" in camera else camera
    return root / "night" / night / subcam


def _flat_dir(root: Path, camera: str, night: str) -> Path:
    # astrocam-style: deliverables sit at <root>/<night>.
    return root / night


# Order matters: probe the modern layout first, then legacy fallbacks.
_LAYOUT_DIRS = [
    ("canonical", _canonical_dir),
    ("percam", _percam_dir),
    ("flat", _flat_dir),
]


@dataclass
class Located:
    camera: str
    night: str
    root: Path
    layout: str
    path: Path     # the resolved night directory (exists)


def resolve(cfg, night: str | None = None) -> Located | None:
    """Find where `cfg`'s `night` data lives. `night` defaults to the
    current noon-rollover night ("today"). Returns None if no root/layout
    holds it. Probes cfg.search_roots x layouts in priority order; the
    camera's configured night_layout is tried first so the common case is
    one stat."""
    night = night or night_of()
    camera = cfg.name
    preferred = getattr(cfg, "night_layout", None)

    # Try the camera's declared layout first, then the rest.
    layouts = list(_LAYOUT_DIRS)
    layouts.sort(key=lambda lt: lt[0] != preferred)

    for root in cfg.search_roots:
        for layout, dirfn in layouts:
            d = dirfn(root, camera, night)
            if d.is_dir():
                return Located(camera=camera, night=night, root=root,
                               layout=layout, path=d)
    return None


def list_nights(cfg) -> list[tuple[str, "Located"]]:
    """Every night that resolves for `cfg`, newest first, each tagged with
    where it lives. Discovers candidate night dates across all roots and
    layouts, then resolves each through resolve() so a night present in more
    than one place picks the SAME (highest-priority) location that resolve()
    would — keeping `today` and `latest` consistent."""
    camera = cfg.name
    subcam = camera.split("-", 1)[1] if "-" in camera else camera
    candidate_nights: set[str] = set()
    for root in cfg.search_roots:
        # canonical: root/YYYY/MM/DD/<camera>
        for cam_dir in root.glob("[0-9][0-9][0-9][0-9]/[0-1][0-9]/[0-3][0-9]/"
                                 + camera):
            candidate_nights.add("-".join(cam_dir.parts[-4:-1]))
        # percam: root/night/<date>/<subcam>
        for sc_dir in root.glob(f"night/[0-9]*-[0-9]*-[0-9]*/{subcam}"):
            candidate_nights.add(sc_dir.parts[-2])
        # flat: root/<date> (astrocam-style deliverables dir)
        for d in root.glob("[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]"):
            if d.is_dir():
                candidate_nights.add(d.name)

    out: list[tuple[str, Located]] = []
    for night in sorted(candidate_nights, reverse=True):
        loc = resolve(cfg, night)
        if loc is not None:
            out.append((night, loc))
    return out
