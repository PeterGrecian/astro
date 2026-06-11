"""Publication privacy crops.

privacy.json (per camera dir) maps subcam -> crop spec, e.g. eclipticam:
    {"v3w": {"frame_size_px": [2304, 1296], "publish_keep_top_px": 1064}}

Any v3w-derived image published anywhere internet-reachable must be
cropped to the top `publish_keep_top_px` rows (the rest shows
neighbouring windows). publish.py refuses images without the
`.privacy-ok` sidecar this module writes after cropping.
"""
from pathlib import Path

from astro.present.publish import privacy_marker


def entry_for(cfg, subcam: str | None = None):
    """The privacy spec for this camera/subcam, or None if unrestricted."""
    priv = getattr(cfg, "privacy", None)
    if not priv:
        return None
    if subcam is None and "-" in cfg.get("name", ""):
        subcam = cfg.name.split("-", 1)[1]
    return priv.get(subcam) if subcam else None


def crop_for_publication(img, spec):
    """Apply a privacy spec to an image array. Scales the crop if the
    image is a different resolution than the spec's frame_size_px (e.g.
    binned or full-res variants of the same field)."""
    if spec is None:
        return img
    keep = spec["publish_keep_top_px"]
    spec_h = spec["frame_size_px"][1]
    h = img.shape[0]
    if h != spec_h:
        keep = int(round(keep * h / spec_h))
    return img[:keep]


def mark_ok(path: Path):
    """Record that `path` was produced through the publication crop."""
    privacy_marker(path).touch()
