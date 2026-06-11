"""Upload a night's deliverables to S3 for the website.

Key contract (unify-cameras): s3://<bucket>/<prefix>/<night>/<name>
with bucket/prefix from camera.json "s3" — e.g.
s3://astro-berrylands-eu-west-1/astrocam/nights/2026-06-09/summary.json.
Objects are private; the Lambda renderer presigns URLs (same pattern as
the existing starcam pages).

Privacy guard: for cameras with a privacy config (eclipticam), every
image must carry a `<file>.privacy-ok` sidecar, written by
astro.present.privacy when the publication crop is applied. Uploads of
unmarked images are refused — this is a hard requirement, not a warning.
"""
from pathlib import Path

CONTENT_TYPES = {
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".yaml": "application/x-yaml",
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def privacy_marker(path: Path) -> Path:
    return path.with_name(path.name + ".privacy-ok")


def check_privacy(cfg, files):
    """Return the subset of `files` that may NOT be published for this
    camera (images without a privacy-ok sidecar). Empty if cfg has no
    privacy config."""
    if not getattr(cfg, "privacy", None):
        return []
    return [f for f in files
            if f.suffix.lower() in IMAGE_SUFFIXES
            and not privacy_marker(f).exists()]


def publish_night(cfg, night: str, files, dry_run: bool = False,
                  extra: dict | None = None):
    """Upload `files` (list of local Paths) under <prefix>/<night>/.
    `extra` maps local Path -> absolute S3 key for assets outside the
    night prefix (e.g. an always-current dashboard hero).
    Returns the list of S3 keys written (or that would be written)."""
    blocked = check_privacy(cfg, list(files) + list((extra or {})))
    if blocked:
        names = ", ".join(f.name for f in blocked)
        raise PermissionError(
            f"{cfg.name}: refusing to publish images without privacy-ok "
            f"markers: {names}. Apply the publication crop "
            f"(astro.present.privacy) first.")

    bucket = cfg.s3["bucket"]
    prefix = cfg.s3["prefix"].strip("/")
    uploads = [(f, f"{prefix}/{night}/{f.name}") for f in files]
    uploads += [(f, key) for f, key in (extra or {}).items()]

    if dry_run:
        print(f"would upload {len(uploads)} files to s3://{bucket}/")
        for local, key in uploads:
            print(f"  {local} -> {key}")
        return [key for _, key in uploads]

    import boto3
    s3 = boto3.client("s3")
    for local, key in uploads:
        ctype = CONTENT_TYPES.get(local.suffix, "application/octet-stream")
        s3.upload_file(str(local), bucket, key,
                       ExtraArgs={"ContentType": ctype})
        print(f"uploaded s3://{bucket}/{key}")
    return [key for _, key in uploads]
