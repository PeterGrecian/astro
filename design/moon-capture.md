# Moon capture subsystem — design

Peter's design (2026-06-24/25). The moon is a Swiss-army calibration
object serving FOUR purposes: phases timelapse, precise net tracking,
moon removal from long exposures, and focus testing.

## CHOSEN DIRECTION (2026-06-25): v1 as a COMPLEMENT to v3w

Two cameras share the eclipticam Pi: v3w (IMX708 Wide, 102°, the
faint-star camera, continuous 55s stream) and v1 (OV5647, narrower FOV,
currently day-only). They are roughly co-pointed (verified: a midday
frame from each shows the same sun + rooftops; v1 is narrower and badly
double-glazing-ghosted). Rather than juggle v3w's stream, use v1 to image
the moon:

- **v1 images the moon at its OWN short exposure**, day AND night,
  WITHOUT interrupting v3w's continuous faint-star stream. (v1 has a 3s
  exposure ceiling — irrelevant for the bright moon; this is exactly the
  "sun/moon-pointing" role CLAUDE.md already earmarked v1 for.)
- **The daytime moon (when BOTH cameras see it — rarer in winter's short
  days) gives a monthly chance to derive/refresh the v1<->v3w transform**:
  the moon imaged in both at the same instant = matched points -> the
  one-off inter-camera mapping (plate scale, distortion, pointing offset).
- The transform maps v1's moon pixel into v3w's frame for moon-removal,
  the net, etc. v1 carries the moon-tracking load; v3w stays uninterrupted.

Complementary, each camera doing what it's good at. The in-stream-bracket
approach below remains the FALLBACK if v1 proves unusable (ghosting,
overlap too small, can't re-enable at night).

OPEN: (a) re-enable v1 at night (currently switched off in capture.py —
"v1 day-only, night JPG is just noise"); give it a short-exposure moon
mode. (b) v1 double-glazing ghosting — may swamp a small faint moon;
test. (c) measure the v1<->v3w overlap + transform from existing
simultaneous day frames. (d) v1 also needs its own moon focus / lens
position.

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
