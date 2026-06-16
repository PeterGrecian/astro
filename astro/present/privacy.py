"""Publication privacy crops.

privacy.json (per camera dir) is a flat crop spec, e.g.:
    {"frame_size_px": [2304, 1296], "publish_keep_top_px": 1064}

Any image published anywhere internet-reachable from a camera with
a privacy.json must be cropped to the top `publish_keep_top_px` rows
(the rest shows neighbouring windows). publish.py refuses images
without the `.privacy-ok` sidecar this module writes after cropping.
"""
from pathlib import Path

from astro.present.publish import privacy_marker


def entry_for(cfg):
    """The privacy spec for this camera, or None if unrestricted."""
    priv = getattr(cfg, "privacy", None)
    if not priv:
        return None
    # Backwards-compat: legacy eclipticam/privacy.json keyed by subcam
    # ({"v3w": {...}}). Detect the wrapper and unwrap by camera-name suffix.
    if "publish_keep_top_px" not in priv and "-" in cfg.get("name", ""):
        suffix = cfg.name.split("-", 1)[1]
        return priv.get(suffix)
    return priv


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
