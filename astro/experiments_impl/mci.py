"""mci — motion-compensated frame interpolation via ffmpeg minterpolate.

Takes an input mp4 (the night's deliverable or any other source) and
produces a smoothed output at a higher framerate.

Args:
  input: required. Either a deliverable filename (e.g. "sweep-colour.mp4"
         — pulled from the night's S3 deliverable prefix), an
         http(s):// URL, or an absolute local path.
  fps: target output framerate (default 60).
  mc_mode: minterpolate mc_mode (default "aobmc"; alternatives "obmc").
  mi_mode: minterpolate mi_mode (default "mci"; alternatives "blend",
           "dup").
  out_name: name of the produced mp4 (default "<experiment-name>.mp4").

Star fields have weak texture and global rotational motion that
minterpolate's translational flow model can't represent well. This
experiment is most useful on the cloud-y nights and on rendered
sweeps where the "scene" is windowed averages — i.e. mostly clouds.
"""
from __future__ import annotations

import shutil
import subprocess
import urllib.parse
from pathlib import Path


def _fetch_input(spec: str, cfg, night: str, work_dir: Path) -> Path:
    """Resolve `spec` to a local mp4 path inside work_dir."""
    if spec.startswith("http://") or spec.startswith("https://"):
        local = work_dir / "input.mp4"
        subprocess.check_call(["curl", "-fL", "-o", str(local), spec])
        return local
    p = Path(spec)
    if p.is_absolute() and p.exists():
        # Local file; copy in so the work_dir is self-contained.
        local = work_dir / p.name
        shutil.copy2(p, local)
        return local
    # Treat as a deliverable filename in the night's S3 prefix.
    import boto3
    bucket = cfg.s3["bucket"]
    prefix = cfg.s3["prefix"].strip("/")
    key = f"{prefix}/{night}/{spec}"
    local = work_dir / spec
    s3 = boto3.client("s3")
    s3.download_file(bucket, key, str(local))
    return local


def run(cfg, night: str, name: str, work_dir: Path, **params) -> str:
    """Run the mci experiment. Returns a short description string for meta."""
    input_spec = params.get("input")
    if not input_spec:
        raise ValueError("mci requires --param input=<filename|url|path>")
    fps = int(params.get("fps", 60))
    mc_mode = params.get("mc_mode", "aobmc")
    mi_mode = params.get("mi_mode", "mci")
    out_name = params.get("out_name", f"{name}.mp4")

    input_path = _fetch_input(input_spec, cfg, night, work_dir)
    out_path = work_dir / out_name
    vf = f"minterpolate=fps={fps}:mi_mode={mi_mode}:mc_mode={mc_mode}"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-i", str(input_path),
           "-vf", vf,
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart",
           str(out_path)]
    print(f"ffmpeg: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    # Privacy: if the input was a deliverable mp4 that already passed
    # the privacy crop, the smoothed output inherits the crop. Mark
    # the output OK so upload doesn't refuse it.
    if getattr(cfg, "privacy", None):
        out_path.with_name(out_path.name + ".privacy-ok").touch()

    return (f"minterpolate fps={fps} mi_mode={mi_mode} mc_mode={mc_mode} "
            f"on {input_spec}")
