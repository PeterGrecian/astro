# astro — TODO

rain detector.  suggested that 10k pull up from GPIO and tinned veroboard.  

periodically review the relationship between these repos:
astro - image processing for astronomy
Berrylands/gardencam - raspberry pi camera routines.  might need rehoming
super/services - asynchronous file transfer using local ramfs
Berrylands shoud have servo sg90.  maybe generic servo stuff is super?
generic camera super? 
Berrylands is sprawling and I could have a focused pi repo pilib or piservices

the temporal resolution of 3 second frames is probably overkill.  There's probably an order of magnetude saving in bandwidth which can be achieved.  
there are still some breakthroughs to be had.   think how scruffy the skycam videos were for ages.  maybe a month to get smooth reliable output.  I have 1/4 TBy of data and have many stars I can pull from it.  still quite a way to go on the clouds.

some more stereo video?  stereo video with one camera.



info in journal for pipeline-night is better than pipeline.log
pipeline-night could be renamed starfinder-daily or something  starcatcher


Live work list. Move items to DECISIONS.md once they crystallise
into a load-bearing choice; delete done items.


storage comments:
moved 2026-05-20 to muppet
moving 2026-05-22 
still 100G free there, will need to do the experiment: can we derive stars from 6s fits - or 12s?  can we finish a pipeline and get just the deliverables?  
pip has 100G.  we are, with care going to make it to the break in the weather Thursday night lasting at least 1 week.  just 2 more nights.  going to make it!

**WATCH ~/.trash — it warps the free-space picture.** Trashed data
still occupies disk until the GC sweeps it; `df` "Avail" only tells
the truth once trash is accounted for. I emptied ~/.trash recently,
so the current reading is real: pip 121G free, trash empty (2026-05-28).
Always check `du -sh ~/.trash` alongside `df -h ~` before judging headroom.

need the real catalog to do magnetude estimates.

fitz 5G per hour 30G per night, bin2 1.4G/10G 6 or 7 hours currently  total 40G.  bin2 is derived.
100 avalible - 100 on muppet too  100 on pip.  the old desktop
fitz thinning 3s -> 6s
delete fitz for every other night - ones which are "done".  I have a week to sort it all.  2 weeks at 6s and so on.

## Foundations
aliases    cdd - chdir to day dir - part of astro/activate.  splay is broken by latter.  maybe $CDD=that dir

dashboard - camera state, brightness trend, storage, stars found

brightness.csv generated for wrong hour on hourly trigger - revise whole real time analysis pipeline
bin-frames should be part of the same pipeline .  step by step automate it all until its all stars
oiiotool looks interesting.  siril is hidious.  splay is capable of doing it better.
- [ ] `notes/tooling.md` — install commands + cheat-sheet for solve-field, oiiotool, djv. (Siril dropped — splay is better.)
- [ ] `notes/pi4-feasibility.md` — can a £35 Pi4 do FITS + plate solve + derot? RAM/CPU budget. Estimate vs £45 model.

## Utilities (bin/, no astro- prefix)

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

**Verified 2026-05-31:** measured on 2026-05-30/01 (1025 intervals,
1008 within ±50 ms after trimming sat-skip gaps): mean 2999.6 ms,
**std 0.49 ms** — down from 103 ms pre-fix. Min 2999, max 3000.

- [ ] Switch fitters to use real epoch_ms (cumulative drift
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

## Transparent/diffuse cover → starcam self-sufficient for brightness (idea, 2026-05-28)

**Goal: make starcam independent of skycam for brightness
measurement while the cover is closed.** Today the cover is opaque
white, so with it closed starcam is blind and we must lean on skycam
for the dusk/darkness brightness signal. Replace the opaque cover
with a **transparent (possibly diffuse) cover** so that closed
starcam still reads total downwelling sky flux — an integrated
brightness measure of its own, no skycam dependency.

A diffuse-transparent cover acts as a white screen that passes light:
starcam sees the integrated sky flux that bounces/transmits through
the cover. That removes the [[project-cover-brightness-calibration]]
coupling where the close/open decision relies on skycam — starcam
can drive its own cover from its own closed-cover reading.

Value of the diffuse path isn't sharper discrimination — diffuse
transmission smears out the spatial cloud structure the open view
shows directly — but it's a robust, structureless integrated-flux
baseline: no saturation from a bright star/moon/streetlight in
frame, no AE chasing a hot spot. Still useful to difference against
the open/skycam views for **cloudy vs. clear** at dusk (cloudy dusk
is brighter and decays slower than clear at the same solar
depression).

First sample (2026-05-28, daytime): AE pinned shutter to 1/100 s,
ISO 155, mean 223/255 (near saturation). So the raw mean is useless
while AE is running — need either fixed exposure/gain capture, or
back out AE via `mean / (exposure × gain)`.

Open questions / risks:
- **Transparency vs. how much light to let in.** A transparent cover
  reads dusk well but admits more daylight — pick the diffuse/tint
  level so closed starcam stays unsaturated by day yet sees enough at
  low sky brightness. The angle-dependent-opacity idea below is the
  refinement that squares this circle.
- **Direct-sunlight concern is cumulative degradation, not
  burnout.** No focusing optics: the wide OV5647 lens (53.5°×41.4°,
  f=3.6 mm) spreads the 0.5° solar disc over a few pixels, not a
  focused point, so catastrophic sensor death is unlikely. The real,
  documented OV5647 failure mode is **thermal**: repeated direct sun
  raises dark current and burns in hot pixels / a faint spot where
  the sun tracks — exactly what hurts an astronomy sensor's dark
  frames. Mitigation: never leave the cover open across the sun's
  daytime arc (existing timers already keep it closed 07:00–20:30).
  The **angle-dependent-opacity cover** idea targets this directly:
  opaque toward the daytime solar arc, more translucent toward the
  zenith / low-sun dusk directions — lets dusk light in without
  exposing the sensor to midday sun, so the closed window can relax.
- Empirical test still owed: log AE-corrected closed-cover flux
  through one clear and one cloudy dusk and see if the curves
  separate. Check what `cover-watch` already logs first.

**Today's coupling (to be removed by the transparent cover).** The
brightness *decision* already runs on starcam (cover-controller,
cover-watch, cover-open-when-dark all live and execute there), so the
*logic* is in the right place. But the *data* it reads —
`~/skycam-frames/` — is an NFS mount from puppy, so starcam still
depends on puppy + the network path for every brightness read. That's
the coupling that broke on 2026-05-27 when puppy's IP changed (see
[[project-puppy-starcam-ethernet-migration]]). With a transparent
cover, starcam reads downwelling flux through its own closed cover
and the skycam-NFS dependency drops entirely — logic AND data become
local to starcam, and the cross-host fragility goes away.

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
