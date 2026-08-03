# Atmospheric distortion — the static field breathes with weather

**Peter (2026-08-03): there will be atmospheric distortion, and inaccuracies in
how it's modelled with temperature and air pressure. The existing model treats
refraction as a STATIC function of (x,y) — right to first order for a fixed
camera, but the pressure/temperature COEFFICIENT is time-varying, so the field's
amplitude breathes night to night (and within a night). That residual is a real
error floor; it is also exactly the kind of model that improves over time and
triggers reprocessing.**

Drafted 2026-08-03 (astro-science). Refines the refraction model already on
record (`worklog/2026-07-05.md` + memory `project-v3w-star-id-moon-anchor.md`)
with the time-varying-coefficient correction and its consequences for confidence
and retrospective reprocessing.

## What the existing model says (and where it's exactly right)

The estate's drift model (Peter's synthesis) separates three symmetries:

```
drift(x,y) = sidereal rotation  (rigid, about the pole)
           + lens distortion    (radial, about the optical centre)
           + refraction          (vertical, about the horizon)
```

Three distinct symmetries → triple-separable from star tracks. The key insight
for refraction: **for a FIXED camera, each pixel always sees the same altitude, so
refraction is a static function of (x,y) — captured in the vector field with NO
time term; altitude is baked into the y-coordinate.** This is correct and
powerful: the *geometric pattern* of refraction (which pixels are lifted, and in
which direction — always vertically toward the zenith) genuinely does not move,
because the camera doesn't.

## Where it's an approximation (Peter's point)

The **pattern** is static per pixel; the **amplitude** is not. Atmospheric
refraction bends light by an angle that depends on the air's refractivity, which
scales with:

- **air pressure** (∝ density; higher pressure → more bending),
- **temperature** (colder air → denser → more bending),
- **humidity / water vapour** (a smaller term),
- **wavelength** (blue refracts more than red → *chromatic* differential
  refraction, a colour-dependent shift).

So the refraction at pixel (x,y) is `R(x,y) = k(weather) · shape(x,y)` — a static
spatial `shape` (the vertical, altitude-dependent pattern) times a **time-varying
scalar coefficient** `k` that breathes with pressure and temperature. The static-
field model bakes in *one* value of `k` (the average over the fit's nights); on a
night that's colder or higher-pressure than average, every low-altitude pixel is
off by `Δk · shape(x,y)`. The model isn't wrong in form — it's missing the weather
term on its coefficient.

Two more time-varying effects the static field cannot hold at all:

- **Seeing** (turbulence) — a *random*, fast (sub-second to seconds) blurring +
  position jitter. Not a static offset; it broadens the PSF and adds centroid
  noise. Sets a per-frame precision floor that varies with conditions.
- **Scintillation** — brightness flicker, a *photometric* noise term (matters for
  the light curves / variability science, `catalogue-deliverable.md`).

## The consequences

### 1. It's a real error floor — name it, don't ignore it
The uncorrected weather term is a **systematic** in astrometry (a night-dependent
vertical shift, worst at low altitude — so worst for v3w, near-zero for astrocam's
near-pole field where refraction is negligible, per the memory). Left unmodelled
it (a) limits how tightly the vector field registers frames from different nights
onto the sphere, and (b) masquerades as a spurious tiny "wobble" — which directly
threatens the PSF-structure / astrometric-wobble science
(`what-accumulation-buys.md`): a pressure swing could fake a companion signal. So
for that science it MUST be modelled out, not averaged over.

### 2. The fix — make k a logged covariate, not a constant
Fit `shape(x,y)` once (static, from the star tracks over many nights, as already
planned) but let the **coefficient `k` be a per-frame value driven by logged
weather** — barometric pressure + temperature at capture time. The memory already
anticipates half of this ("triple-separate over 20 days with **logged barometric
pressure**"); the refinement is that k is not a single fitted constant but a
*function of the logged conditions*, evaluated per frame:
- log pressure + temperature per night (cheap — a sensor on the Pi, or a local
  weather API keyed to the site);
- `k(P, T)` from the standard refraction formula (Bennett / Sæmundsson — the
  physics is known), or fit a small correction to it from the data;
- apply `k(frame) · shape(x,y)` when de-rotating each frame → the weather breathing
  is removed before co-adding, not smeared into the stack.
This turns pressure/temperature from an *unmodelled error* into a *known
covariate*, the same move as breathing→LENSPREP (`STATE`: a modellable field, not
lost signal).

### 3. Chromatic refraction ties to the CFA accumulator
Blue shifts more than red, so differential refraction is **colour-dependent** — and
the accumulator already keeps CFA planes separate (`STATE` "raw mosaics + drift:
the Earth demosaics"). So the R/G/B planes want *slightly different* refraction
coefficients; folding chromatic refraction into the per-plane accumulation is
natural (each plane gets its own `k_colour(P,T)`), and getting it wrong shows as a
colour-dependent radial smear at low altitude.

### 4. It's a prime reprocessing driver
The refraction model is never final — the `k(P,T)` fit improves as more nights
across more weather accumulate, and the physics form can be refined. Per
`retrospective-reprocessing.md`, **a better atmospheric model reprocesses every
past night**: re-de-rotate the held raws with the improved `k(P,T)` → tighter
cross-night registration → deeper stacks + any weather-faked wobbles removed. This
is a textbook case of the archive appreciating: the weather was logged, so the
correction can always be re-applied better later. It also sets the **retention
tension** sharply — a refraction-model jump wants to reach the raws before they
age out.

### 5. It feeds confidence
The per-frame/per-night atmospheric residual (how well `k(P,T)·shape` fit that
night's bright-anchor positions) is a **quality signal**: a night with large
unexplained atmospheric residual (unstable air, bad seeing) gets lower weight in
the accumulator and lowers the confidence contribution of its detections
(`catalogue-deliverable.md`). Good-seeing nights are worth more — which also
motivates the `drift-scan-cadences.md` "temporal decimation: keep best-seeing
stacks."

## Status / open questions
- **Design / refinement only.** The static-shape refraction model is specified
  (worklog + memory); the time-varying `k(P,T)` covariate, chromatic per-plane
  refraction, seeing/scintillation as quality terms, and the confidence hook are
  new here.
- **Do we need a weather sensor, or is a local API enough?** Site pressure +
  temperature at ~night cadence may suffice for the slowly-varying k; within-night
  variation (a front passing) may want on-Pi logging. Cheapest sufficient source
  TBD.
- **How big is the effect at zenith?** For the near-zenith fields the whole rig
  targets (`zenith-quests.md`: airmass ~1, near-zero refraction), the weather term
  may be *below* our precision — in which case it's a v3w-low-altitude concern
  only, and astrocam/zenith work can defer it. Estimate the magnitude before
  building: at altitude h, differential refraction across the field and its
  swing over realistic P/T ranges vs our ~0.1 px centroid precision.
- **Seeing floor** — quantify the per-frame centroid jitter from seeing at this
  site; it caps the sub-pixel precision (STATE says 0.14 px is systematics-
  limited — is seeing part of that systematic, or averaged out by many frames?).

## See also
- `worklog/2026-07-05.md` + memory `project-v3w-star-id-moon-anchor.md` — the static three-symmetry model + refraction-as-pressure-dependent-departure (the base this refines).
- `design/retrospective-reprocessing.md` — a better atmo model reprocesses old data (logged weather makes it always re-correctable).
- `design/what-accumulation-buys.md` — weather-faked wobble threatens the companion/wobble science → must model, not average.
- `design/hierarchical-vector-field.md` — refraction is the atmospheric term OF this field; static shape, breathing amplitude.
- `design/catalogue-deliverable.md` — atmospheric residual as a per-night quality → confidence weight.
- `design/zenith-quests.md` — near-zenith = near-zero refraction (why the effect may be small for the primary fields).
