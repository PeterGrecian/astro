"""Experiment metadata + S3 upload.

Experiments are one-off processings of a night's data, distinct from
deliverables (which run every night). They sit at:

    s3://<bucket>/<prefix>/<night>/experiments/<name>/

with a meta.json carrying:
    name, description, args, repo, commit, run_at_utc

The website lists experiments by S3-listing the experiments/ subdir
per night, so this module does not touch the deliverables' summary.json.

Each experiment is one CLI invocation of bin/astro-experiment. The
experiment kinds themselves live in astro.experiments_impl.* — one
module per kind, exposing a `run(camera, night, work_dir, **params)`
function that produces files in work_dir and returns a description
string.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

from .nightdir import night_path


REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_commit(repo_root: Path | None = None) -> dict:
    """Return {'repo': 'astro', 'commit': '<short>', 'dirty': bool}.
    Run via subprocess so it works without git-python."""
    root = repo_root or REPO_ROOT
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"
    try:
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0
    except FileNotFoundError:
        dirty = False
    name = root.name
    return {"repo": name, "commit": commit, "dirty": dirty}


@dataclass
class ExperimentMeta:
    name: str                # short slug, e.g. "mci-60fps"
    kind: str                # implementation key, e.g. "mci"
    camera: str
    night: str               # YYYY-MM-DD
    description: str
    args: dict               # the CLI args / params used
    repo: str
    commit: str
    dirty: bool
    run_at_utc: str
    artefacts: list[str] = field(default_factory=list)  # uploaded filenames

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def s3_prefix_for(cfg, night: str, experiment_name: str) -> str:
    """Canonical experiment prefix: <s3-prefix>/<night>/experiments/<name>/."""
    prefix = cfg.s3["prefix"].strip("/")
    return f"{prefix}/{night}/experiments/{experiment_name}"


def upload_experiment(cfg, meta: ExperimentMeta, work_dir: Path,
                      dry_run: bool = False) -> list[str]:
    """Upload every file in work_dir to S3 under the experiment prefix,
    plus a meta.json built from meta. Returns the list of S3 keys.

    Privacy: experiments inherit the camera's publication crop rule.
    Each image file in work_dir must have a privacy-ok sidecar if the
    camera has a privacy config — same rule as publish_night.
    """
    from .present.publish import check_privacy

    files = sorted(p for p in work_dir.iterdir()
                   if p.is_file() and not p.name.endswith(".privacy-ok"))
    blocked = check_privacy(cfg, files)
    if blocked:
        names = ", ".join(f.name for f in blocked)
        raise PermissionError(
            f"{cfg.name}: experiment '{meta.name}' refusing to upload "
            f"images without privacy-ok markers: {names}")

    meta.artefacts = [f.name for f in files] + ["meta.json"]
    meta_local = work_dir / "meta.json"
    meta_local.write_text(meta.to_json())
    files = files + [meta_local]

    bucket = cfg.s3["bucket"]
    prefix = s3_prefix_for(cfg, meta.night, meta.name)
    uploads = [(f, f"{prefix}/{f.name}") for f in files]

    if dry_run:
        print(f"would upload {len(uploads)} files to s3://{bucket}/")
        for local, key in uploads:
            print(f"  {local} -> {key}")
        return [key for _, key in uploads]

    import boto3
    from .present.publish import CONTENT_TYPES
    s3 = boto3.client("s3")
    for local, key in uploads:
        ctype = CONTENT_TYPES.get(local.suffix, "application/octet-stream")
        s3.upload_file(str(local), bucket, key,
                       ExtraArgs={"ContentType": ctype})
        print(f"uploaded s3://{bucket}/{key}")
    return [key for _, key in uploads]


def make_meta(name: str, kind: str, camera: str, night: str,
              description: str, args: dict) -> ExperimentMeta:
    rc = repo_commit()
    return ExperimentMeta(
        name=name, kind=kind, camera=camera, night=night,
        description=description, args=args,
        repo=rc["repo"], commit=rc["commit"], dirty=rc["dirty"],
        run_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
