# astro — TODO

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

## Accurate per-frame timing (open question; affects radial smear)

- [ ] **Use real epoch_ms not frame index for angle.** fit-pole and
      fit-geometry currently assume uniform 3s frame spacing
      (`angle = omega × frame_index`). The daemon runs at-best-effort
      on a Pi 1B and intervals drift. Switch to
      `angle = sidereal_rate_per_s × (epoch_ms - epoch_0) / 1000`.
      derot-night already does this; the fitters don't.

- [ ] **Rolling shutter correction.** OV5647 reads top-to-bottom
      over the 2.9s exposure. Stars at the bottom of the frame are
      sampled ~2.9s later than stars at the top. Means each *row*
      needs its own angle offset, not just each frame:
        angle(frame_N, row_Y) =
            omega × ((epoch_ms_N - epoch_0) / 1000 + Y × T_row)
      where T_row = exposure_time / sensor_height.
      Probably accounts for some of the residual radial smear we
      see in derot outputs.

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
