# Drift-scan architecture: cadences and storage

Written 2026-06-05.

## The insight

Plate-solve residuals are dominated not by pole drift in time, but
by **distortion-model error as stars traverse the sensor**. The
trigger to close a derotation-accumulation stack is the per-star
residual at the frame edges crossing a threshold — not a wall-clock
timer.

This makes the whole instrument essentially a **drift-scan survey
camera**, with a fixed distortion field through which the sky
moves at a known rate. Long-term value is in the integrated
star-position dataset against which the lens itself gets
characterised — not just the sky.

## Three cadences

The pipeline runs at three nested rates:

**Capture cadence — seconds.**
Short exposures (1–2 s) keep single-frame trailing sub-pixel.
On-Pi: capture → bin2 → warp by current best-WCS → += into
in-flight float32 stack. Pi 4 / Pi 5 both have abundant CPU
headroom (warp <100 ms, accumulate <60 ms; see derot benchmarks).

**Derot-accumulate cadence — ~100×.**
~100 subs per stack ≈ 100 s of integration, ≈ 20 px star motion
near frame center, ≈ a band across the distortion field whose
edges are still within residual threshold. Stack closes when
residual exceeds threshold; closed stack written to disk with its
time-tagged WCS. Output: ~hundreds of stacks per night.

**Global-solve / refinement cadence — slow, once a night or rarer.**
Probably needs NFS + puppy because it's a batch fit over the
archive. Refits the distortion model from all star-position
measurements across recent nights. Doesn't run in the hot loop;
runs after upload. As the distortion model improves, historical
raw subs can be **retrospectively re-warped + re-stacked** with
the better model.

The exact cadence of (3) is unknown. Will calibrate from experience.

## Storage outlook

- 12 nights of starcam-style raw capture currently = ~360 GB
  (~30 GB/night). Sustainable on puppy short-term, not forever.
- New pipeline stores derot-accumulated stacks instead of raws,
  with raws kept only for some retention window for retrospective
  re-derotation.
- Naive accumulated-stack size: similar bytes to one raw frame
  per stack × ~hundreds of stacks/night = same order of magnitude
  as raw capture. Decimation needed.
- Decimation options to think about:
  - **Sub-window decimation** — only keep the central useful
    region of each stack (distortion-clean), not the full sensor.
  - **Bit-depth decimation** — float32 → uint16 once the noise
    floor justifies it.
  - **Temporal decimation** — keep only some stacks (best seeing,
    say, by residual-quality).
  - **Raw-to-FITS Rice compression** — already in pipeline,
    ~2.5× saving over raw .npy.

The retention question (how long to keep raws for retrospective
re-derot) is the load-bearing one. Rolling 3 months feels right
as a starting heuristic; revisit after the global solve has
converged enough that further retrospective gains are small.

## Why retrospective re-derot matters

Each night's frames are derotated by *that night's best
distortion model*. As the model improves over weeks, old frames
were derotated with a worse model than we now have. Reprocessing
them with the current model gives strictly better stacks.

So the archive becomes more valuable over time, not less. The
historical data is the calibration source *and* the re-derotation
target. This argues for keeping raws longer than a strict
operational requirement would suggest.

## Implications for puppy / NFS

- Capture-side pipeline runs on the Pi, no NFS in the hot loop.
- Closed stacks ship to puppy via existing uploader pattern.
- Global solve runs on puppy with NFS-read access to all
  cameras' archives.
- Retrospective re-derot is also a puppy job (CPU + data both
  live there).

The split is clean: Pis do the time-critical pipeline; puppy does
the slow batch science.

## Open questions

- Residual threshold for closing a stack — empirical. Likely
  something like "RMS residual on bright-star subset >0.5 px after
  warp." Need real data to calibrate.
- Distortion model form — polynomial (SIP) is the obvious starting
  point. May need additional terms for thermal / mechanical
  effects once the residual gets that small.
- How many stacks per night does this actually produce? If
  hundreds, storage planning needs sharpening. If a dozen, the
  picture is rosier.
- Going back through existing 12 days of raws to re-derot under
  this model is feasible (raw frames already on puppy). Decide
  whether to do that now or after the live pipeline is shaking
  out.
