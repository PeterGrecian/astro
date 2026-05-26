# astro — TODO
obviously, sort out the capture pipeline.
and also the day pipeline.  i guess it's step by step

pigpiod uses a lot of cpu unnecesarily.  

Live work list. Move items to DECISIONS.md once they crystallise
into a load-bearing choice; delete done items.

rotating disk as lens cover toy motor.  start working on enclosure 2

storage comments:
fitz 5G per hour 30G per night, bin2 1.4G/10G 6 or 7 hours currently  total 40G.  bin2 is derived.
100 avalible - 100 on muppet too  100 on pip.  the old desktop
fitz thinning 3s -> 6s
delete fitz for every other night - ones which are "done".  I have a week to sort it all.  2 weeks at 6s and so on.

## Foundations
aliases    cdd - chdir to day dir - part of astro/activate.  splay is broken by latter.  maybe $CDD=that dir

dashboard - camera state, brightness trend, storage, stars found

brightness.csv generated for wrong hour on hourly trigger - revise whole real time analysis pipeline
bin-frames should be part of the same pipeline .  step by step automate it all until its all stars
plot-brightness usage message inacurate.  $ plot-brigtness * in the nights dir works
oiiotool looks interesting.  siril is hidious.  splay is capable of doing it better.
- [ ] `notes/tooling.md` — install commands + cheat-sheet for solve-field, oiiotool, djv. (Siril dropped — splay is better.)
- [ ] `notes/pi4-feasibility.md` — can a £35 Pi4 do FITS + plate solve + derot? RAM/CPU budget. Estimate vs £45 model.

## Utilities (bin/, no astro- prefix)

- [ ] `gc-status` — human readout of `file-garbage-collector` on puppy: free space, target, what would be next to go.
- [ ] `platesolve` — wraps `solve-field` with our defaults; writes SIP into header. (Decision pending — Peter prefers parametric fit over catalog; revisit if we want magnitudes.)

## Pipeline

- [ ] Hot-pixel mask v2 from derot stack — real stars are points, hot pixels trace arcs. Far more selective than thresholding the raw sum (which currently misclassifies bright stars).
- [ ] Dark master per (gain, exposure) — capture procedure documented; subtraction step in `to-fits` or a separate `subtract-dark`?
- [ ] Cloud / sky-quality flag per frame — `notes/sky-quality.md`. Std-dev signal, mean/median ratio, centre-vs-edge. (Partial: scan-brightness mean already used for sky-threshold gating in pipeline-night.)
- [ ] Compress retention plan — keep raws for N days, FITS for M, accumulators forever.

## Aspirational (cameras)

- [ ] Decide camera identifier convention (`back`, `front`, `sky`, `experimental`). Reflect in path layout: `~/<cam>-frames/night/<night-dir>/HH/`.
- [ ] Per-camera config: gain, exposure, lens, sensor, Bayer pattern.

## Accurate per-frame timing

**Current state (2026-05-25):** filename epoch_ms is **noisier than
the actual sensor cadence** because the daemon stamps with
`time.time_ns()` *after* the Python loop receives the frame — that
stamp jitters ±100 ms (measured stddev 103 ms over 1199 intervals).
Sensor itself is rock-steady at the requested cadence. So:

- Fitters (fit-pole, fit-geometry) keep using `frame_index × 3 s` —
  that's *more* accurate than the recorded timestamps.
- derot-night uses `(epoch_ms - epoch_0)` from filenames; affects
  it less because the jitter is unbiased and we're summing many
  frames at each pixel.

**Fix in flight (2026-05-25):** changed
`Berrylands/gardencam/starcam_night_daemon.py` to use libcamera's
`SensorTimestamp` (CLOCK_BOOTTIME ns, set at exposure end) instead
of wall-clock `time.time_ns()`. Converted to wall-clock epoch via
one-time offset captured at process start. Frames captured AFTER
this fix is deployed should have ms-accurate, jitter-free
filenames.

**To verify after deployment:**
- [ ] Re-measure interval std on a fresh hour (`ls *.fits.fz |
      awk` one-liner). Should drop from ~103 ms to ~1 ms.
- [ ] Then switch fitters to use real epoch_ms (cumulative drift
      ~0.14 px at 300 frames would vanish).

**Rolling shutter:** OV5647 readout time is 66.7 ms top-to-bottom,
NOT exposure time. So row-to-row sample-time difference is half
that — ~33 ms. At sidereal rate, sub-pixel even at corners of our
binned image. Skip the per-row correction; it's below INTER_LINEAR
precision.

## Day-mode sky-mask process (deferred until rain sensor + 2nd camera)

A daily noon cycle on each camera that derives a fresh sky mask
from blue-sky daytime frames. NOT interleaved with night capture
— a standalone day-mode process.

Cycle (oneshot wrapper, e.g. `sky-mask-cycle.sh` on starcam):
  1. Check rain sensor. **Abort if wet** (don't expose the lens).
  2. Stop day-mode capture (whatever's running for skycam etc.).
  3. Cover OPEN (servo to +60°).
  4. Grab N daytime frames at low exposure/gain.
  5. Process with chromakey (against blue-sky colour) AND
     brightness key (dark = foreground). Combine: anything failing
     either test is masked.
  6. Cover CLOSED (back to -60°, weather-safe).
  7. Restart day-mode capture.
  8. Output: ~/astro/calib/sky-mask-<camera>-<YYYY-MM-DD>.fits.fz

Cadence: daily noon if dry. Catches slow foreground changes
(tree growth) and camera-position drift without manual
intervention. Mask filename is dated so pipeline-night's
auto-pick logic uses the most-recent-≤-night.

Round-trip with existing cover timers:
- 07:00  cover-close.timer → cover closed all morning
- 12:00  sky-mask-cycle (if dry) → briefly open, mask, close
- 12:00..20:30  cover closed (weather + sun protection)
- 20:30  cover-open.timer → open for night capture
- 21:00  starcam-capture night window begins

Pre-reqs:
- Rain sensor on starcam (GPIO input).
- bin/auto-sky-mask (exists) needs chromakey added; currently
  only does brightness threshold (mean − k·std). Blue-sky
  chromakey would catch white house bricks that brightness
  thresholding alone misses.
- Per-camera: 2nd camera (south-facing, arriving soon) gets its
  own sky-mask-cycle on its own host with its own --camera id.

## Seasonal note (2026-05-25)

- 4 weeks to summer solstice (2026-06-21).
- At 51.4°N, **astronomical twilight doesn't end** around the
  solstice — the sun stays within 18° of the horizon all night.
- Effect on this pipeline:
  - Mean per-hour sky brightness rises through June.
  - sky-threshold gate (default 100 ADU) will skip more hours
    each night, eventually skipping the whole night by mid-June.
  - Cumulative stars detected per night will fall, then recover
    after solstice.
- Don't read "we're losing stars" as a regression — it's the sun.
- Maybe expose `--sky-threshold` more prominently or vary it
  seasonally if we want to keep pulling whatever signal we can.

## Wandering-star (planet) discriminator — Tombaugh blink

After two nights have a sharp per-night `final/derot.fits.fz` at
identical pole + distortion, **subtract** them. Stars cancel
(same pixel). Planets, asteroids, comets leave a `+star` at
tonight's pixel and a `-star` at last night's pixel: classic
blink-comparator signature.

Implementation sketch:
- `derot-diff <night-A> <night-B>` → writes
  `<B>/diff-vs-<A>.fits.fz` (signed int32 = B - A).
- Optional `--abs` for absolute-value variant where moving
  objects appear as paired-bright-blob signatures.
- `find-candidates` on the abs-diff stack with high threshold:
  the only pixels above sky-noise floor are planet
  positions (or hot pixels we didn't catch, or cosmic rays).
- For Neptune/Uranus specifically: compute predicted nightly
  motion from JPL Horizons ephemeris, derotate-stack the diff
  along that motion vector across many nights — moving-object
  SNR √N improvement, all sky cancels.

Uranus (mag +5.6, Nov opposition 2026-11-21): per-night derot
should already show it; diff-vs-yesterday should make it
unmistakable. Neptune (mag +7.8) needs both stacking AND diff.

## Neptune in November (target)

- Neptune opposition: late Sep / early Oct 2026; observable through
  Nov with peak brightness ~mag +7.8 (point source for our pixel
  scale ~70 arcsec/binned-px).
- Estimated SNR budget: ~28 hours of derotated stacking (~4
  good nights × ~7 dark hours) gets us 5–6× our current single-
  hour SNR — enough to pull mag +7.8 from sky background.
- Requirements:
  1. Per-night `final/derot.fits.fz` must be sharp (good pole +
     distortion fit). Residual smear squared compounds across
     nights.
  2. Multi-night derot stacker (`derot-week`-style) that derotates
     using `omega × (epoch_ms - epoch_0)` across nights.
  3. Planet-aware motion model: Neptune drifts ~1 arcmin/day
     against the star background. After sidereal derotation the
     planet smears. Either compute its ephemeris (real
     ra/dec known from JPL Horizons) and apply per-night
     position correction, or detect the moving spot directly.
  4. Camera survives the winter (warm + dry; cover working).

## Multi-night stacking (deferred — let the per-night pipeline mature first)

- [ ] `derot-week` — extension of `derot-night` that walks multiple
      night dirs, derotates by `omega × (epoch_ms - epoch_0) / 3000`
      so frames from different nights stack onto a common rotated
      reference. Stars near the pole stack perfectly; stars away
      from the pole accumulate only when above the horizon.
- [ ] **Lens distortion dominates atmospheric refraction** — when
      we start pulling refraction signal out of multi-night stacks
      it'll be a big deal, but first the per-frame distortion model
      (k1, k2 from `fit-geometry`) needs to be solidly fitting. The
      residual after a good distortion fit will be where we look
      for refraction effects.
- [ ] **Camera position drifts sometimes, possibly with
      temperature.** Within one night the pole moves <30 binned px
      (see pipeline-poles.csv across hours). Between nights it can
      jump (we've seen ~50 px shifts after physical repositioning).
      Multi-night stacks need a per-night pole, not a global one.
      A `fit-pole-multinight` would estimate per-night pole + a
      single shared distortion (k1, k2 are sensor properties).

## Disposable scratch

- Old per-`/tmp/` scripts (streak_window.py, streak_clean.py, streak_lum.py, run_streaks.sh) — port the useful patterns into `bin/` if needed, don't ressurrect the originals. They were /tmp violations; lesson logged.
