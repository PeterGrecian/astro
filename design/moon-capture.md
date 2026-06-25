# Moon capture subsystem — design

Peter's design (2026-06-24/25). One short-exposure-in-stream mechanism
serves FOUR purposes: phases timelapse, precise net tracking, moon
removal from long exposures, and focus testing.

## The problem

The moon is the only thing of interest in v3w's daytime sky (occasionally
Venus). But neither capture mode images it well:
- **Night (55 s):** moon saturates → a bloomed white blob. Centroid is
  noisy (~30-90 px scatter, x-vs-az corr only 0.17) AND streetlights /
  double-glazing ghosts also saturate, so a whole-frame "brightest blob"
  detector finds the wrong object. **55 s frames CANNOT track the moon
  precisely** (measured 2026-06-24 on 12 night frames).
- **Day (auto-exposure):** moon faint against bright sky, marginal to
  detect (resid ~2 over local bg).

A SHORT exposure on the moon gives a clean, properly-exposed disc.
Validated live 2026-06-24: at ~8 ms (gain 1, lens 3.15) the low/hazy
gibbous moon shows the terminator + phase, not saturated. Exposure must
ADAPT (a high full moon wants shorter; auto-meter on the moon or
phase+altitude aware). The moon is ~20 px on the 102° ultra-wide lens —
small but the phase is clear.

## Capture: vary exposure IN-STREAM (no reconfigure, no slack needed)

The night daemon (astro/capture/streaming.py) is now a CONTINUOUS stream:
55 s exposures back-to-back, ~100 ms readout between (>99 % duty cycle).
The old per-tick model's ~5 s slack is gone. BUT picamera2 exposure is
per-frame controllable via `cam.set_controls({ExposureTime, FrameDuration
Limits})` mid-stream (already used at startup; the code already drops the
first frame after a control change for the 1-2 frame apply latency).

So the moon HDR bracket is interleaved IN the stream:
1. normal: ExposureTime = 55 s (faint stars)
2. every Nth cycle: set_controls to 10 ms → grab frame; 1 ms → grab;
   0.1 ms → grab  (an HDR bracket covering crescent..full)
3. set_controls back to 55 s → resume star frames
Cost: ~12 ms exposures + ~3×100 ms readout ≈ 0.3 s per bracket — a
fraction of one 55 s cycle, NOT a whole frame. Duty cycle stays ~99.5 %.
(Peter's "use the dead 5 s" was for the old per-tick model; in-stream
exposure change is the better fit for the continuous stream.)

DAY mode: omit the 55 s entirely — just the short bracket (day frames are
moon-only images anyway).

## Why we need the moon position (two uses)

1. **Remove the moon from the long exposure** — for brightness/sky-quality
   calcs the saturated moon contaminates the frame mean; knowing its
   pixel lets us mask it. (Needs only rough position.)
2. **Crop the HDR moon** — extract a properly-exposed moon postage-stamp
   for the phases timelapse + precise tracking.

## Two tracking states — gated by a `camera_moved` boolean

The camera is a cardboard mount; it WILL get bumped. So:
- **camera_moved = False (normal): FINE-TRACK.** Pointing known
  (ephemeris + the moon-net fit + last position). Predict the moon pixel,
  search a SMALL box, centroid the short-exposure disc precisely. Fast,
  foreground/ghost-immune.
- **camera_moved = True: FIND-THE-MOON.** Pointing unknown (bump /
  remount). Search the whole frame / re-acquire, re-seed the net fit,
  clear the flag. = re-calibration trigger.

How to set camera_moved: detect a step change in where the moon (or a
bright reference) lands vs prediction; or a manual flag after touching
the rig. TBD.

## What this serves (one mechanism, four uses)

- **Phases timelapse** — the properly-exposed HDR moon disc, a few/night
  over a lunar month → crop+register(centre the disc)+timelapse.
- **Precise net tracking** — sharp short-exposure disc → clean net points
  (vs the noisy 55 s blob). Extends the moon-net into night.
- **Moon removal** — mask the moon out of the 55 s brightness calc.
- **Focus testing** — the moon is a true-infinity sharp-edged target.
  Validated 2026-06-25: lens sweep on the moon peaks at 3.15 (65/67/73 →
  **83** → 73/61), confirming 3.15 = astronomical infinity. A periodic
  moon focus-sweep could catch temperature focus-drift automatically.

## Build order (next session, when the moon's up to test)

1. Verify in-stream exposure change works (set_controls mid-stream,
   confirm short frame is properly exposed) — the feasibility crux.
2. moon HDR bracket interleaved every N cycles (night) / standalone (day).
3. moon-track on the short frames (precise) — extend the net.
4. camera_moved boolean + fine-track vs find-the-moon dispatch.
5. crop+register+timelapse pipeline for the phases video.
6. moon-removal mask for brightness.
