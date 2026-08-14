# polefit — find the celestial pole from a night's max stack

**Two stages, because each is good at a different thing: the ARCS find POLARIS,
and POLARIS finds the POLE.** Peter, 2026-08-14.

A night's `max.jpg` / `max.fits.fz` is a star-trail image: every star draws an
arc of a circle centred on the celestial pole. Getting the pole out of it is the
single cheapest calibration the estate has — no frame reads, no plate solve, one
small file per night — and it feeds the map (`design/accumulation-bucket-
refinement.md`), the camera-moved signal, and every per-epoch geometry question.

## The algorithm

```
stage 1   ARCS  ->  POLARIS      coarse consensus centre from many long arcs,
                                 then take the brightest arc within ~30 px of it
stage 2   POLARIS ->  POLE       fit a circle to Polaris's OWN arc; its centre
                                 IS the pole
```

**Why this split and not one global fit.** The long outer arcs have huge radius
and small angular sweep, so their curvature barely constrains a centre — fits
wander. Polaris is the opposite: radius ~0.75° (≈18 px at astrocam's scale,
half-res) sweeping ~138° in one night. Short radius + large sweep is the
well-conditioned case for a circle fit.

Measured on astrocam 2026-08-12 (matched-moving-star sharpness of a 20-frame
de-rotated stack — higher is tighter, single frame = 4.452 is the ceiling):

| Pole source | Sharpness |
|---|---|
| plain sum, no de-rotation | 1.358 |
| whole-image gradient fit (1232, 916) | 1.884 |
| **Polaris arc circle-fit (1392, 978)** | **2.549** |

Stage 1 alone is not good enough to *be* the answer — it is good enough to
*locate Polaris*, which is all it is asked to do.

## Why it is trustworthy

- **Deterministic.** No RNG, no random seeding. Same input, same output.
- **Stage 2 has no free parameters.** Stage 1's threshold need only be good
  enough to find a region; the precise answer comes from stage 2, which tunes
  nothing. This matters: `bin/arc-walk`'s pole moves ~90 px with threshold
  choice — further than a real camera shift would.
- **It self-checks.** The fitted radius must come out ≈ the known Polaris–NCP
  separation (0.7525° in 2026) at the image's plate scale. If it does not, the
  arc is not Polaris and the fit is rejected rather than silently returned. This
  caught a real error during development: a too-tight crop captured only a 20 px
  fragment of the arc, giving radius 10.9 px (vs 18.1 expected) and a centre
  90 px wrong. **Angular sweep matters more than pixel count.**

## Known limits / to do

- **Polaris saturates** in the published JPEG (clipped at 255), fattening the arc
  and degrading the ridge. Fitting from the **FITS** max stack should tighten the
  1.65 px residual and avoids the JPEG's 2× downsampling. Not yet tested.
- **Pole out of view** — eclipticam (pole ~88.6° off-axis) and any far-pole
  camera have no Polaris and no closed arcs. Trails there are near-straight
  segments and the pole is a distant intersection. `bin/fit-distortion-trails`
  already handles that limit for distortion; the pole equivalent is the planned
  extension. Note the estate also has `design/pole-from-sun-moon.md` as an
  independent route for such cameras.
- **Per-epoch use.** Pole position is per camera *and per epoch* (an epoch
  boundary is a camera/lens/mount change). Epoch 1 and 2 frames differ in
  resolution (3280×2464 vs 4608×2592), so compare in **fractional frame
  coordinates or angle from frame centre**, never raw pixels.

## Relationship to the existing pole tools

The estate already has nine; this subproject is meant to gather the max-stack
route, not add a tenth in isolation:

| Tool | Role |
|---|---|
| `bin/arc-walk` | stage-1-style consensus from arc bisectors; threshold-sensitive |
| `bin/fit-pole` | maximises derot patch sharpness over candidate poles; needs `find-candidates` over full frames first (expensive) |
| `bin/fit-distortion-trails` | the FAR-pole limit (eclipticam) — trail bowing for distortion |
| `bin/separate-trails` | splits merged parallel trails; needed for the far-pole case |
| `bin/annotate-pole` | writes a DS9 region file of named stars given a pole |
| `bin/fit-tile-pole*`, `fit-per-star-poles` | per-tile effective poles = the distortion field |

## Samples

`samples/` holds real max stacks as fixtures so the fitter can be developed and
regression-tested without touching the archive. Each sample carries a
`.expected.json` with the accepted answer and how it was derived.
