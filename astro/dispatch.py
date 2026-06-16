"""Stage 3 dispatcher — twice-daily processing trigger.

Reads each assigned camera's state.json on NFS; when stage 1 sets
`pending_process.dawn_window_complete` (or dusk) true, invokes the
deliverables pipeline for the just-finished window and resets the
flag.

The deliverables pipeline itself is unchanged — we shell out to
`bin/publish-night-cam --camera <cam> --night <YYYY-MM-DD>`. This
module is the testable core that decides *when* to run it; the
daemon at bin/astro-process is a thin loop around `tick_once()`.

Module name "dispatch" (not "process") avoids the clash with the
existing astro.process subpackage (bayer / brightness / derot / ...).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import CameraConfig
from .nightdir import night_of
from .state import load_state, state_path


# Match the daemon's per-camera CameraLoop in bin/astro-state: writes
# pending_process via decide() in astro.state.
PENDING_FLAGS = ("dusk_window_complete", "dawn_window_complete")


def _publish_cmd(repo_root: Path, camera: str, night: str) -> list[str]:
    return [str(repo_root / "bin" / "publish-night-cam"),
            "--camera", camera, "--night", night]


def _reset_pending(state_path_: Path, flag: str, log: logging.Logger) -> None:
    """Set pending_process[flag] = False after handling it."""
    try:
        data = json.loads(state_path_.read_text())
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f"reset: cannot read {state_path_}: {e}")
        return
    pending = dict(data.get("pending_process") or {})
    if not pending.get(flag):
        return
    pending[flag] = False
    data["pending_process"] = pending
    data["written_at_utc"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    try:
        state_path_.write_text(json.dumps(data, indent=2))
    except OSError as e:
        log.warning(f"reset: cannot write {state_path_}: {e}")


def run_for_camera(camera: str, night: str, repo_root: Path,
                   log: logging.Logger,
                   dry_run: bool = False) -> int:
    """Invoke publish-night-cam for one (camera, night). Returns rc."""
    cmd = _publish_cmd(repo_root, camera, night)
    log.info(f"[{camera}/{night}] running: {' '.join(cmd)}")
    if dry_run:
        log.info(f"[{camera}/{night}] dry-run: would invoke")
        return 0
    try:
        result = subprocess.run(cmd, check=False)
    except OSError as e:
        log.error(f"[{camera}/{night}] subprocess failed to start: {e}")
        return -1
    rc = result.returncode
    if rc == 0:
        log.info(f"[{camera}/{night}] publish-night-cam OK")
    else:
        log.warning(f"[{camera}/{night}] publish-night-cam rc={rc}")
    return rc


def tick_once(cameras: Iterable[str], repo_root: Path,
              log: logging.Logger, dry_run: bool = False) -> list[tuple[str, str, int]]:
    """One pass: for each camera, read its current state.json; if a
    pending flag is set, fire the deliverables and clear the flag.

    Returns a list of (camera, night, rc) for every run attempted.
    """
    fired: list[tuple[str, str, int]] = []
    when = datetime.now(timezone.utc)
    for camera in cameras:
        try:
            cfg = CameraConfig.load(camera)
        except FileNotFoundError as e:
            log.warning(f"[{camera}] skip: {e}")
            continue
        state = load_state(cfg.frames_root, camera, when=when)
        if state is None:
            # Cold start: no state.json for tonight yet. Nothing to do.
            continue
        pending = state.pending_process or {}
        for flag in PENDING_FLAGS:
            if not pending.get(flag):
                continue
            # Process the night that the just-completed window belongs to.
            # state.night is "the night-of when stage 1 last wrote", which
            # is "today's night" by noon-rollover — same answer.
            night = state.night
            rc = run_for_camera(camera, night, repo_root, log, dry_run=dry_run)
            if rc == 0 and not dry_run:
                sp = state_path(cfg.frames_root, camera, when=when)
                _reset_pending(sp, flag, log)
            fired.append((camera, night, rc))
    return fired
