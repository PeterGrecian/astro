# The hierarchical vector field — brightest-first camera→sidereal-space mapping

**One static per-camera map, `pixel → true sky direction`, built brightest-first
in layers: the pole star and bright anchors pin it, fainter stars read off it,
and time densifies it. The new framing: this same field IS the camera→sidereal-
space resampling map the static accumulator co-adds through.** Identification and
accumulation are two uses of one object.

Drafted 2026-08-03 (astro-science), consolidating the framing that was split
across `design/zenith-quests.md` (the bright-anchor bridge + time densification)
and `worklog/2026-07-05.md` (the 3-layer schema, "lens interpolates / sensor
accumulates"). The method itself is Peter's (2026-07-05, 2026-07-25); this doc
names it and states the accumulator connection.

## The method — hierarchical, brightest-first

Don't plate-solve each star independently — most are too faint to anchor a solve.
Instead build **one smooth field over the fixed sensor** and work down the
magnitude ladder:

1. **Pole star / brightest anchors first.** The brightest, most-anchored points
   seed the geometry. On astrocam the brightest detection *is* Polaris — the
   natural seed near the pole where distortion is ~zero (see
   `design/standing-plate-solve.md`, `camera-geometry.md`, and TODO "orientation
   lock — near-pole outward"). Bright, catalogued stars plate-solve where faint
   ones can't.
2. **The bright grid IS the vector field.** `solve-field --tweak-order 3` → a
   **SIP-distortion WCS** = `pixel → true sky direction`, distortion and all.
   Because the camera is *fixed*, this field is **static per camera** — measured
   once, refined per night. (The distortion component also shows directly as the
   per-tile effective-pole map — see `per-tile-effective-pole.md`: `tile_pole −
   global_pole` at each tile centroid *is* the distortion vector field.)
3. **Read faint detections off the field.** The field is smooth and dense, so the
   sky coordinate of *any* (x,y) is known — including a blob too faint to solve
   alone. **Relative position to nearby bright stars does the work**: the faint
   star sits at a known offset within a locally-known distortion field.
4. **Local deep cross-match.** Predicted coordinate + tight error box → match
   against a fainter catalogue tier (Gaia DR3, mag ~20) at that spot — a 1-star
   local match, not a blind global solve. **The bright stars bridge to the dark
   ones**; this is the key to "identify 10,000."

The ordering is coarse→fine in magnitude: work down from mag 1 step by step,
each brighter layer tightening the field the next-fainter layer reads off.

## The layers — vector fields and models, split by timescale

Three layers, each with its own update rule (`worklog/2026-07-05.md`):

| Layer | Content | Update rule | Timescale |
|---|---|---|---|
| **Detections** | raw source tables (x, y, flux, time); the field shows *directly* here (drift angle rotates +11°→−0.4° across x, length 14→33 px top→bottom) | append | per-frame |
| **Per-frame / per-night params** | pole, roll, sidereal velocity, k1/k2 | fit per night | per-night |
| **Residual maps per epoch** | distortion = residual after k1/k2 on an 8-px grid (~0.75 MB); sensitivity = per-pixel gain (uint8) + smooth colour map | accumulate / interpolate | per-`(POSINDEX, MOVEID)` epoch |

The load-bearing distinction: **the lens map interpolates; the sensor map
accumulates.** Distortion is smooth → interpolate between bright anchors. Sensor
gain/colour is per-pixel → build up sample-by-sample as anchors sweep each pixel.

**Epoch scope.** The field is valid over exactly one **move epoch** — the same
`(POSINDEX, MOVEID)` (see `camera-moved-signal.md`). A generation swap or a
re-aim starts a fresh field solve; all fields land on the *same* sidereal sphere,
so a re-aim re-solves the map without forking the science product.

## Time densifies the field (why frames from different times matter)

The camera is fixed but the sky drifts, so a bright anchor **sweeps through every
region of the sensor over weeks** (`zenith-quests.md`). Two consequences:

1. **The field densifies.** Anchors trace dense tracks; the field goes from
   "anchored at dozens of positions" to "anchored almost everywhere a bright star
   has *ever* been." A faint star *between* tonight's bright stars gets pinned on
   some *other* night when a different bright anchor drifts into its neighbourhood.
2. **Persistence = identity.** A real faint source sits at the same sky
   coordinate every night; its field-predicted (x,y) tracks the sidereal drift
   exactly under many *different* anchoring configurations. A hot pixel, cosmic
   ray, or satellite does not. Identity is confirmed from **cross-time
   consistency**, not one frame's geometry — working "down from mag 1 to
   something deep" in *time* as well as space.

This drives the retention rule (per-frame source tables kept forever; raw pixels
freed after a rolling window) and the **local catalogue** (`SC-000001`…): mint an
ID when a detection persists, Gaia cross-match as an *attribute, not a gate*, so
persistent-but-unmatched sources stay real — the "see vs identify" gap turned
into records.

## The new aspect — the field IS the camera→sidereal-space accumulation map

This is what ties the hierarchical field to the strand's thrust (the sidereal-
space static accumulator; see STATE "the thrust" + "accumulation theory").

The accumulator's whole premise is a **camera→sphere resampling**: de-rotate every
frame into a fixed sidereal frame and co-add, so stars stop being streaks and
become points that accumulate. STATE says plainly that this resampling is
*load-bearing* — feed it undersampled/aliased data or a wrong geometry and the
error bakes into the accumulator permanently.

**That resampling map is exactly this hierarchical vector field.** `pixel → true
sky direction` is the camera→sphere projection; there is not a separate
"identification field" and "accumulation map" — they are one object used two ways:

- **for identification:** evaluate the field at a detection → predicted sky coord
  → local catalogue match.
- **for accumulation:** evaluate the field at *every* pixel → where that pixel's
  light lands on the sphere → drizzle it there.

Consequences of recognising them as one field:

- **Brightest-first solves the accumulator's geometry prerequisite.** STATE's
  gating item ("pole + plate scale from a clear imx708 night, then RA/Dec naming
  + the accumulator") is the *first two layers* of this method — pole star +
  bright-anchor SIP fit. Building the field IS finding the resampling geometry.
- **The static field is why per-night resampling is cheap.** The camera is fixed,
  so the map is measured once per epoch and only *refined* per night (drift,
  refocus). The accumulator doesn't re-derive geometry each night; it reuses the
  standing field. Per-night marginal cost stays ≈ 0, matching the accumulation-
  capacity numbers in STATE.
- **Time densification and deep accumulation are the same sweep.** The bright
  anchors sweeping every pixel (which densifies the identification field) is the
  same sidereal drift that sweeps each sky point across R/G/B pixels for the
  drift-demosaic accumulator. One motion; the field it builds serves both the
  "identify" tables and the "see" stack.
- **Drizzle, not interpolation, through the field.** Resampling camera→sphere on
  undersampled data must be drizzle-style (STATE): the field gives each pixel's
  sub-pixel sphere position; drizzle rains it onto the finer sky grid. The field
  is the coordinate map; drizzle is how signal crosses it.

**In one line:** the hierarchical bright-anchored vector field and the static
accumulator's camera→sidereal-space map are the same object. Build it brightest-
first, densify it over time, and it simultaneously names the faint stars and tells
the accumulator where every pixel's light belongs on the sphere.

## Status / what it needs

- **Method: proven in pieces, not yet assembled end-to-end.** Near-pole/optical-
  axis solve works (astrocam plate-solved 2026-07-02, Tycho-2 idx 19); the SIP
  field is what `standing-plate-solve.md`'s `astro-solve` produces per night; the
  per-tile pole map gives the distortion field. Missing: the layered assembly
  (bright anchors → field → faint read-off → local catalogue) as a standing loop,
  and validation that the SIP field extrapolates faithfully into the faint regime
  (test on medium stars that can self-solve AND sit near the faint floor).
- **Blocked on the same prerequisite as the accumulator:** a clean bright-anchor
  solve on a real imx708 clear night (astrocam geometry still STALE from the
  imx219 era; the 2026-07-02 solve stalled extending outward on candidate quality
  — foreground/glow cells, needs occlusion masking first).
- **Deps present:** `solve-field` + Tycho-2 on puppy; `bin/{solve-detections,
  fit-pole,fit-geometry,derot-patches,find-candidates}`; `pipeline-night` (the
  known-good center-out bootstrap); a deep catalogue tier (Gaia DR3) for the
  faint cross-match.

## See also
- `design/standing-plate-solve.md` — the per-night `astro-solve` that produces the SIP field this method layers on.
- `design/per-tile-effective-pole.md` — the distortion component as an explicit vector field (per-tile effective poles).
- `design/camera-moved-signal.md` — the epoch boundary over which one field is valid.
- `design/zenith-quests.md` — the bright-anchor bridge + time-densification + local catalogue (source of the identification half).
- `worklog/2026-07-05.md` — the 3-layer schema and "lens interpolates / sensor accumulates".
- STATE.md (astro-science) — "the thrust" (sidereal-space static accumulator) + "accumulation theory" this field feeds.
