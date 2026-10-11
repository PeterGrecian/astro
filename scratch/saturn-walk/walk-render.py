#!/usr/bin/env python3
"""Saturn walking against the stars: each measured night's good frames,
re-projected onto a fixed patch of sky and median-stacked, so the stars stand
still and Saturn moves. The field is sparse (brightest star within 3 deg of
the path is V 6.1, at the single-frame limit), hence the stack.

Per night (walk-nights.csv rows with ok=True) the frames used are those the
summary agreed on; each frame's own fitted pointing (walk-frames.json) maps
every sky pixel (gnomonic about the patch centre, GCRS axes) to the camera at
mid-exposure. Stars are 60 s exposures from a fixed camera, so they
are short dashes (~4 camera px). Output: walk-anim/NNN.png and walk.mp4.

Run on muppet:  cd ~/astro/scratch/saturn-walk && ~/astro/.venv/bin/python walk-render.py
"""
import csv, json, math, os, subprocess, sys
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy.ndimage import map_coordinates
from PIL import Image, ImageDraw
from astropy.coordinates import AltAz, GCRS, SkyCoord
from astropy.time import Time
import astropy.units as u

HERE = os.path.expanduser("~/astro/scratch/saturn-walk")
sys.path.insert(0, HERE)
import check3                                                    # noqa: E402
from check3 import BASE, LOC, P, model, _enu                     # noqa: E402

RA0, DEC0 = 12.4, 2.4             # patch centre (deg)
WDEG, HDEG = 8.0, 6.0             # patch size
SCALE = 1.2 / 60                  # deg per output px (camera is ~3.5'/px)
UP = 2                            # display upscale
OUT = f"{HERE}/walk-anim"


def tangent_grid():
    w, h = int(WDEG / SCALE), int(HDEG / SCALE)
    xi = (np.arange(w) - w / 2) * math.radians(SCALE) * -1      # RA increases to the left
    eta = (h / 2 - np.arange(h)) * math.radians(SCALE)
    X, Y = np.meshgrid(xi, eta)
    a0, d0 = math.radians(RA0), math.radians(DEC0)
    den = math.cos(d0) - Y * math.sin(d0)
    ra = a0 + np.arctan2(X, den)
    dec = np.arctan2(math.sin(d0) + Y * math.cos(d0), np.hypot(X, den))
    return np.degrees(ra), np.degrees(dec), w, h


def to_px(ra, dec):
    """sky (deg) -> output pixel, inverse of tangent_grid"""
    a, d = math.radians(ra) - math.radians(RA0), math.radians(dec)
    a0, d0 = 0.0, math.radians(DEC0)
    c = math.sin(d0) * math.sin(d) + math.cos(d0) * math.cos(d) * math.cos(a)
    X = math.cos(d) * math.sin(a) / c
    Y = (math.cos(d0) * math.sin(d) - math.sin(d0) * math.cos(d) * math.cos(a)) / c
    w, h = int(WDEG / SCALE), int(HDEG / SCALE)
    return (w / 2 - X / math.radians(SCALE)) * UP, (h / 2 - Y / math.radians(SCALE)) * UP


def frame_path(night, name):
    t = datetime.fromtimestamp(int(name.split(".")[0]) / 1000, timezone.utc)
    return f"{BASE}/{night}/v3w/{t:%H}/{name}"


def main():
    os.makedirs(OUT, exist_ok=True)
    nights = [r for r in csv.DictReader(open(f"{HERE}/walk-nights.csv")) if r["ok"] == "True"]
    fr = json.load(open(f"{HERE}/walk-frames.json"))
    RA, DEC, w, h = tangent_grid()
    cache = f"{HERE}/walk-stacks.npz"
    if os.path.exists(cache):
        z = np.load(cache); stacks, counts = list(z["stacks"]), list(z["counts"])
    else:
        stacks, counts = [], []
        for nr in nights:
            night = nr["night"]
            c = math.cos(math.radians(float(nr["dec"])))
            cand = [r for r in fr if r["night"] == night and r.get("sat_found") and r["n_stars"] >= 10
                    and (r.get("near_med_px") or 9) < 1.2
                    and math.hypot((r["meas_ra"] - float(nr["ra"])) * c, r["meas_dec"] - float(nr["dec"])) * 60 < 4]
            st = []
            for r in cand:
                t = datetime.fromisoformat(r["t_mid"])
                img, _ = check3.load(frame_path(night, r["frame"]))
                noise = 1.4826 * np.median(np.abs(img - np.median(img)))
                sky = SkyCoord(RA.ravel() * u.deg, DEC.ravel() * u.deg, frame=GCRS(obstime=Time(t)))
                aa = sky.transform_to(AltAz(obstime=Time(t), location=LOC, pressure=0))
                V = _enu(np.radians(aa.az.deg), np.radians(aa.alt.deg))
                cm = model(dict(P, az0=r["az0"], alt0=r["alt0"], roll=r["roll"], f=r["f"]))
                x, y = cm.project(V)
                st.append((map_coordinates(img, [y, x], order=1, cval=np.nan) / noise).reshape(h, w))
            S = np.nanmedian(np.stack(st), axis=0)
            stacks.append((S - np.nanmedian(S)).astype(np.float32)); counts.append(len(st))
            print(night, len(st), "frames", flush=True)
        np.savez_compressed(cache, stacks=np.stack(stacks), counts=np.array(counts))
    # the stars: every night stacked. Saturn sits somewhere else each night, so
    # the median across nights drops it and keeps the fixed stars.
    deep = np.nan_to_num(np.nanmedian(np.stack(stacks), axis=0))
    deep -= np.median(deep)
    sig = 1.4826 * np.median(np.abs(deep))
    yy, xx = np.mgrid[0:h, 0:w]
    track = []
    for k, nr in enumerate(nights):
        night = nr["night"]
        sx, sy = (v / UP for v in to_px(float(nr["ra"]), float(nr["dec"])))
        m = np.clip((20 - np.hypot(xx - sx, yy - sy)) / 6, 0, 1)      # that night's Saturn, soft edge
        Sn = np.nan_to_num(stacks[k]) * (sig / (1.4826 * np.nanmedian(np.abs(stacks[k]))))
        F = deep * (1 - m) + np.maximum(Sn, deep) * m
        g = np.clip((F - 1.5 * sig) / (18 * sig), 0, 1) ** 0.6
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w * UP, h * UP), Image.LANCZOS).convert("RGB")
        dr = ImageDraw.Draw(im)
        track.append(to_px(float(nr["ra"]), float(nr["dec"])))
        for (px, py) in track[:-1]:
            dr.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(255, 170, 40))
        dr.text((10, 8), f"Saturn  {night}   eclipticam", fill=(230, 230, 230))
        dr.text((10, h * UP - 20), f"stars: {sum(counts)} x 60 s over {len(nights)} nights, stacked on the sky   "
                f"Saturn: {counts[k]} frames that night   orange: earlier nights", fill=(140, 140, 147))
        im.save(f"{OUT}/{k:03d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "4", "-i", f"{OUT}/%03d.png",
                    "-vf", "tpad=stop_mode=clone:stop_duration=2,format=yuv420p", "-c:v", "libx264", "-crf", "18",
                    f"{HERE}/walk.mp4"], check=True)


if __name__ == "__main__":
    main()
