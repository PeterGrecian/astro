#!/usr/bin/env python3
"""Keep only the frames where something other than sky is in view; discard the rest.

    plane_catch.py [--out DIR] [--shutter 2000] [--gain 1.0] [--fps 15]

MJPEG, not h264, so every frame stands alone and can be kept or dropped by
itself. Each frame is decoded at quarter scale and compared with a running model
of the sky. A change that is small, local and sharp starts an event, which saves
the frames from --pre seconds before it until --post seconds after the last hit:

    <out>/<UTC date>/<UTC start>/<epoch_ms>.jpg      full-size frames, as encoded
    <out>/events.csv                                 one line per event

Slow change (cloud, the light) is absorbed by the model and high-pass filter, so
a thing that stays put becomes sky. Pixels that keep firing (a branch in the wind)
are masked. Exposure is pinned, as in plane_hunt.sh: AE blows the sky out.
"""
import argparse
import collections
import io
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ni


class Detector:
    """Per-frame change against the sky model. All sizes in quarter-scale pixels."""

    def __init__(self, k=6.0, floor=4.0, min_area=3, max_frac=0.2, alpha=0.05, hp=25):
        self.k, self.floor, self.min_area = k, floor, min_area
        self.max_frac, self.alpha, self.hp = max_frac, alpha, hp
        self.bg = self.hot = None
        self.warm = 0

    def reset(self, g):
        self.bg, self.warm = g.copy(), 0

    def update(self, g):
        """Return the blobs as (area, x0, y0, x1, y1, peak), or None for a scene change."""
        if self.bg is None:
            self.reset(g)
            self.hot = np.zeros(g.shape, np.float32)
            return []
        d = g - self.bg
        d -= ni.uniform_filter(d, self.hp)
        sigma = 1.4826 * np.median(np.abs(d[::4, ::4]))
        mask = np.abs(d) > max(self.k * sigma, self.floor)
        self.hot += (mask - self.hot) * 0.02
        self.warm += 1
        if self.warm <= 15:
            self.bg += (g - self.bg) * 0.2
            return []
        if mask.mean() > self.max_frac:
            self.reset(g)
            return None
        self.bg += (g - self.bg) * np.where(mask, self.alpha / 10, self.alpha)
        mask &= self.hot < 0.2
        if not mask.any():
            return []
        lab, n = ni.label(mask, structure=np.ones((3, 3)))
        blobs = []
        for i, sl in enumerate(ni.find_objects(lab), 1):
            area = int((lab[sl] == i).sum())
            if area >= self.min_area:
                blobs.append((area, sl[1].start, sl[0].start, sl[1].stop, sl[0].stop,
                              float(np.abs(d[sl][lab[sl] == i]).max())))
        return blobs


def quarter(jpeg):
    im = Image.open(io.BytesIO(jpeg))
    im.draft("L", (im.width // 4, im.height // 4))
    return np.asarray(im.convert("L"), np.float32)


def split_jpegs(stream, chunk=262144):
    """Yield whole JPEGs from a concatenated MJPEG stream."""
    buf = bytearray()
    while True:
        data = stream.read1(chunk)
        if not data:
            return
        buf += data
        while True:
            cut = buf.find(b"\xff\xd9\xff\xd8")
            if cut < 0:
                break
            yield bytes(buf[:cut + 2])
            del buf[:cut + 2]


def writer(q, stats):
    while True:
        path, jpeg = q.get()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(jpeg)
            tmp.rename(path)
            stats["bytes"] += len(jpeg)
        except OSError as e:
            stats["write_err"] += 1
            print(f"write failed: {e}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=Path("/mnt/muppet/bigstore/xoverpi-frames/planecatch"))
    ap.add_argument("--width", type=int, default=2028)
    ap.add_argument("--height", type=int, default=1520)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--shutter", type=int, default=2000)
    ap.add_argument("--gain", type=float, default=1.0)
    ap.add_argument("--pre", type=float, default=1.0)
    ap.add_argument("--post", type=float, default=1.0)
    ap.add_argument("--max-event", type=float, default=60.0, help="seconds; then re-arm")
    ap.add_argument("--quota-gb", type=float, default=20.0, help="stop saving past this")
    a = ap.parse_args()

    cmd = ["rpicam-vid", "-n", "-t", "0", "--codec", "mjpeg", "--width", str(a.width),
           "--height", str(a.height), "--framerate", str(a.fps), "--shutter", str(a.shutter),
           "--gain", str(a.gain), "--awbgains", "1,1", "-o", "-"]
    cam = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    a.out.mkdir(parents=True, exist_ok=True)
    log = (a.out / "events.csv").open("a", buffering=1)
    stats = {"bytes": 0, "write_err": 0}
    q = queue.Queue(maxsize=int(a.fps * 30))
    threading.Thread(target=writer, args=(q, stats), daemon=True).start()

    det = Detector()
    pre = collections.deque(maxlen=max(1, int(a.pre * a.fps)))
    event = None            # dict while saving
    n = last_report = kept = dropped = changes = 0
    started = time.time()

    def keep(t, jpeg):
        nonlocal kept, dropped
        path = event["dir"] / f"{int(t * 1000)}.jpg"
        try:
            q.put_nowait((path, jpeg))
            kept += 1
            event["frames"] += 1
        except queue.Full:
            dropped += 1

    for jpeg in split_jpegs(cam.stdout):
        t = time.time()
        n += 1
        g = quarter(jpeg)
        blobs = det.update(g)
        if blobs is None:
            changes += 1
            blobs = []
        if event:
            keep(t, jpeg)
            if blobs:
                event["last"] = t
                event["hits"] += 1
                big = max(blobs)
                event["area"] = max(event["area"], big[0])
                event["box"] = big[1:5]
            if t - event["last"] > a.post or t - event["start"] > a.max_event:
                log.write(f'{event["name"]},{event["frames"]},{event["hits"]},{event["area"]},'
                          f'{" ".join(map(str, event["box"]))}\n')
                print(f'event {event["name"]}: {event["frames"]} frames, {event["hits"]} hits, '
                      f'peak area {event["area"]}', flush=True)
                event = None
        elif blobs and stats["bytes"] < a.quota_gb * 1e9:
            now = datetime.fromtimestamp(t, timezone.utc)
            big = max(blobs)
            event = {"name": now.strftime("%Y%m%dT%H%M%SZ"), "start": t, "last": t, "frames": 0,
                     "hits": 1, "area": big[0], "box": big[1:5],
                     "dir": a.out / now.strftime("%Y-%m-%d") / now.strftime("%Y%m%dT%H%M%SZ")}
            for pt, pj in pre:
                keep(pt, pj)
            keep(t, jpeg)
        else:
            pre.append((t, jpeg))
        if t - last_report >= 60:
            last_report = t
            print(f"{n / (t - started):.1f} fps  sky {g.mean():.0f}  kept {kept}  dropped {dropped}  "
                  f"scene changes {changes}  {stats['bytes'] / 1e6:.0f} MB  "
                  f"masked {(det.hot > 0.2).mean() * 100 if det.hot is not None else 0:.2f}%  "
                  f"write errors {stats['write_err']}", flush=True)
    sys.exit(f"camera stream ended, exit {cam.wait()}")


if __name__ == "__main__":
    main()
