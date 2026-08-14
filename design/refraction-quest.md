# Refraction quest — measure the atmosphere as a static vector field

**Detect atmospheric refraction as a SECOND static distortion field, separable
from the lens by its weather dependence, and use it to measure temperature and
pressure from starlight alone.** Begun 2026-08-14 (astro-science), from the
map/vector-field work.

Peter: *"the asymmetry of the field wrt the lens/image will show the static
atmospheric distortion. that would be cool."*

## The insight that makes it tractable

**Because the camera never moves, every pixel looks at a FIXED ALTITUDE
forever.** So refraction — which depends on altitude — is *static in image
space*, exactly like lens distortion. It does **not** sweep through the frame as
the sky rotates. The star moves through the refraction field; the field itself
sits still.

**This is NOT new to the estate** — `atmospheric-model-residuals.md` (2026-08-03)
already records it: *"for a FIXED camera, each pixel always sees the same
altitude, so refraction is a static function of (x,y) — captured in the vector
field"*. What this quest adds is the **separation strategy** (below) and the
inversion to weather measurement. (The framing it corrects was mine, in
conversation on 2026-08-14, not the estate's.)

So the mapping decomposes as:

```
map = R(t) ∘ [ F_lens(x,y)  +  k(T,P) · F_refr(x,y) ]
```

| Term | Fixed in | Varies with |
|---|---|---|
| `F_lens` | image space | **nothing** (per epoch) |
| `R(t)` | — | time only, known rate |
| `F_refr` | image space | **nothing** — its SHAPE is pure geometry |
| `k(T,P)` | — | weather: temperature, pressure |

**The time-variable part collapses to a single scalar `k`, not a field.** That is
what makes this a quest rather than a wish: fitting one number per night against
a field whose shape is known a priori is well conditioned, and a modest number of
bright stars can do it.

## Why the two static fields separate

A single night cannot distinguish them — both are static in image space, so they
sum into one effective field. The separation is **temporal**:

- `F_lens` is **invariant across all nights** of an epoch;
- `k·F_refr` **breathes with the weather**.

So stack many nights: the part that never changes is the lens, the part that
varies is refraction. **This is a strong argument for the accumulate-across-
nights design over per-night solves** — the separation is impossible without a
long baseline, and free with one.

The second discriminator is **anisotropy**, which is Peter's "asymmetry" point:
refraction compresses the field **only in the altitude direction**, not in
azimuth. Lens distortion is (to first order) radially symmetric about the
optical centre. Two different symmetry centres and two different symmetries —
the same asymmetry argument that made the radial-normal pole trick work.

## Expected signal — this is not marginal

At **51.39°N**, refraction at the horizon is ~34′, falling as roughly
tan(zenith distance):

Computed with the Bennett formula, and converted at astrocam's 75″/px:

| Altitude | Refraction | Pixels |
|---|---|---|
| 10° | 5.39′ | 4.3 |
| 20° | 2.70′ | 2.2 |
| 26° | 2.03′ | 1.6 |
| 45° | 0.99′ | 0.8 |
| 60° | 0.57′ | 0.5 |
| 76° | 0.25′ | 0.2 |

astrocam's field spans ~50°, so if it is pointed near the pole (alt ≈ 51°) the
frame covers roughly **26°–76° altitude**, where refraction runs ~2′ down to
~15″ — a **factor of ~8 across one frame**. At 0.0208°/px = 75″/px that is
**1.6 px to 0.2 px**, i.e. a 1.4 px differential across the field.

That is small but not hopeless: it is a **coherent, smooth, predictable-shaped**
signal measurable over thousands of stars and hundreds of nights, not a per-star
detection. Weather changes it by ~3% for a 10 hPa pressure swing and ~1% per 3°C
— so the *variation* being chased is a few hundredths of a pixel per night,
reachable only via the accumulator's sub-pixel regime (STATE: centroids ~0.1 px
per frame, systematics-limited at 0.14 px).

**Honest assessment: this is a late-stage quest.** It needs the map's sub-pixel
astrometry working and the lens field already solved. It is listed now because
the *design* must keep the terms separable from the start — not because it is
attemptable this month.

## Quest stages

**Stage 1 — bound it.** Fit a single static field per epoch and show the
residuals are not white: look for a coherent component aligned with the altitude
gradient rather than with the optical centre. Success = a detected anisotropy,
even without calibration.

**Stage 2 — separate lens from atmosphere.** With ≥2 epochs or many nights,
show the residual field has an invariant part and a varying part. Success =
`k` measurably differs between nights.

**Stage 3 — calibrate against ground truth.** Correlate fitted `k` with recorded
temperature and pressure. The estate already logs weather via home-automation,
and the Pi fleet has sensors. Success = a significant correlation.

**Stage 4 — the prize: starlight as a barometer.** Invert it — predict pressure
from the fitted field. Success = agreement with a real barometer to a few hPa.

## Degeneracies to design around

- **`k` vs plate scale.** Refraction compresses radially in *altitude*; a scale
  error compresses *uniformly*. They separate only with good azimuthal coverage —
  build that into the star selection rather than assuming it.
- **`k` vs pole error.** A pole offset also produces a coherent directional
  residual. Distinguish by shape: refraction grows toward the horizon
  non-linearly (tan z), a pole error is a constant offset.
- **Focus breathing.** `LENSPOS` is recorded in every frame header, so this is a
  *measurable covariate*, not a nuisance — fit plate scale against LENSPOS and
  either find a dependence or bound it. Do this BEFORE claiming refraction, since
  both perturb scale.
- **The camera must genuinely not move.** The whole premise is a fixed altitude
  per pixel. The `polefit` per-night pole survey is the check — and
  `camera-moved-signal.md` treats a move as an epoch boundary.

## Why it is worth doing

Peter: *"I would be thrilled if we detect atmospheric distortion, as a function
of weather especially."* Beyond the thrill, it is a genuinely novel use of an
urban all-night archive: a fixed camera staring at the same sky for a year is an
unusually good refraction instrument, because everything else in the system is
held still. It needs no extra hardware, and it turns the estate's biggest
nuisance — a bright, turbulent, low-altitude urban sky — into the measurand.

## See also
- `accumulation-bucket-refinement.md` — the map; the accumulate-across-nights
  design this depends on.
- `hierarchical-vector-field.md` — the lens field this must be separated from.
- `zenith-quests.md` — the quest convention; those target the ZENITH precisely
  because refraction is near zero there. This quest is their complement.
- `atmospheric-model-residuals.md` — existing work on atmospheric residuals.
