# Zenith quests — M51, Algol, Polaris A/B, Mizar & Alcor, Polaris B by binocular

**Targets to attempt at/near the zenith (and the pole), begun 2026-07-06.** The zenith
is where a Pi camera performs best: airmass ~1, near-zero refraction, tightest
PSF, darkest sky. These three exercise the same skills as the harder
ecliptic-planet goals (Neptune/Uranus/Titan) but under the best conditions and —
crucially — on targets that are up every clear night for months, so a campaign
can accumulate unlimited nights.

## Shared method (camera-agnostic)

The v3w streak/tracking machinery transfers to all three and to astrocam:
- **Star ID + plate solve** — identify stars (as with Altair/Aquila on v3w,
  Deneb+Polaris on astrocam), fit the local plate/WCS. STILL PENDING as a
  standing tool; these quests motivate finishing it.
- **Frequency-vs-magnitude / sensitivity plots** — the completeness curve
  (`bin/sensitivity-*`). PENDING as a per-night deliverable; needed for the
  variable-star photometry.
- **Sub-pixel streak astrometry / gain-corrected mosaic / deep de-streaked
  stacking** — all apply. For extended M51, bin2/interp is fine (no undersampling
  concern for extended broadband light, unlike point sources).

## Quest 1 — M51 (the Whirlpool galaxy)

- **RA 13h30, Dec +47.2. Integrated mag 8.4, ~11×7 arcmin.** Culminates at
  **alt 86°** (near-zenith for lat 51.4) — the ideal deep target. High July
  evenings (alt 75° @ 20:00 UTC, dropping through the night).
- **The challenge:** EXTENDED, low surface brightness (~13 mag/sq-arcmin — the
  mag-8.4 light spread over ~77 sq-arcmin, so each patch is far fainter than a
  mag-8 star). And SMALL:
  | Feature | wide v3w (80″/px) | narrow Mod3 (40″/px) |
  |---|---|---|
  | whole (11′) | 8 px | **17 px** |
  | core→companion M51b (4.5′) | 3.4 px | **6.9 px** |
  | core (1.5′) | 1.1 px | 2.3 px |
- **→ M51 WANTS THE NARROW CAMERA.** On the wide it's a fuzzy 8px blob; on the
  narrow it's a ~17px resolvable galaxy pair. This quest ties directly to the
  narrow-Module-3 purchase (point it at zenith).
- **The gift:** fixed target, up for months → stack UNLIMITED nights (no motion
  window like a planet). Deep-stacking has no time limit here.
- **Graduated wins:** T1 detect the CORE + companion M51b (NGC 5195) double-
  nucleus (deep-stack + resolution); T2 hint of SPIRAL ARMS (hard deep-destreaked
  stacking, many nights, bg-subtract); T3 resolved arm detail (dream; narrow cam
  + long campaign).
- **First step:** check if M51 is even in v3w's field (v3w looks SOUTH; M51 is
  near-zenith/NW — probably NOT in frame). If not → this is a "point the narrow
  camera up" quest from the start.

## Quest 2 — Algol (β Persei, the Demon Star)

- **RA 03h08, Dec +40.9. Eclipsing binary: mag 2.1 → 3.4 every 2.87 days,
  eclipse ~10 h.** Near the zenith band.
- **Why:** a DRAMATIC, PREDICTABLE light curve — catch a whole eclipse in one
  night, star visibly dims and rebrightens on schedule. Exercises the
  PHOTOMETRY / magnitude-vs-time skill (the sensitivity work), repeatable every
  ~3 days. Easy targets (bright), profound result (you measure a stellar eclipse).
- **Method:** track Algol + comparison stars each frame, gain-corrected mosaic
  photometry, plot mag vs time → the eclipse curve. NEEDS the frequency/magnitude
  / photometry tooling finished.
- **Seasonal:** Perseus is a late-autumn/winter target (low in summer evenings).

## Quest 3 — Polaris A/B (the Titan rehearsal)

- **Polaris (α UMi): companion Polaris B at 18 arcsec, mag 2.0 vs 9.0.**
- **Why:** a bright star with a FAINT close companion = EXACTLY the Saturn/Titan
  glare + resolution problem, but Polaris NEVER SETS and its geometry is FIXED
  (no orbital-phase waiting). **The perfect practice target for splitting Titan.**
  Tests PSF-subtraction + resolution + the faint-near-bright regime.
- **Separation in pixels:** 18″ = 0.23px (wide v3w) / 0.46px (narrow) — WAY below
  resolvable! So Polaris B needs the SUPER-RESOLUTION (drizzle / string-of-dots)
  to split — which is exactly why it's the Titan rehearsal (Titan is also
  sub-few-px). Polaris is astrocam's pole star (always in frame) → the natural
  astrocam super-resolution test.
- **Method:** the whole dither/drizzle + PSF-subtraction stack, on a fixed,
  always-available bright+faint pair. Prove it on Polaris B → apply to Titan.
- **CORRECTION (2026-07-09): optics-blocked on Pi lenses.** 18″ is below the
  ~39″ Dawes limit of a ~3 mm Pi lens — the same wall Quest 4 records for
  Mizar A–B (14.4″). The Airy disks merge in the optics; dithering/drizzle
  beats pixel-aliasing, not diffraction, so no amount of super-resolution
  recovers the split from a bare Pi camera. **Unblocked by Quest 5** (binocular
  aperture). The *contrast* half of the Titan rehearsal (faint companion in a
  bright star's PSF wings) moves there; the *sub-pixel* machinery rehearsal
  continues on v3w streaks regardless.

## Quest 4 — Mizar & Alcor (the calibration double)

- **Mizar (ζ UMa, mag 2.2) + Alcor (80 UMa, mag 4.0): separation 11.8 arcmin,
  PA ~71°.** Dec +54.9 = **near-zenith** for lat 51.4 (culm alt 86°); Ursa Major
  is **circumpolar** → up all year, any clear night.
- **Scope (chosen 2026-07-07): split Mizar–Alcor + photometry. NOT Mizar A–B.**
  Mizar is *itself* a telescopic double (A–B, 14.4″) — but 14.4″ is **below the
  ~39″ Dawes limit of a ~3 mm Pi lens** (the Airy disks merge in the OPTICS before
  the sensor → the info is never captured → **dithering cannot recover it**;
  dithering beats pixel-aliasing, NOT diffraction). So the A–B split needs a real
  aperture we don't have — deliberately out of scope.
- **What it exercises (3 skills, all achievable):**
  1. **Resolve** the 11.8′ pair — 10–18 px apart, trivial on any camera; confirms
     the field + scale. v3w (science cam) the natural choice.
  2. **Photometry** — Mizar/Alcor = 1.8 mag = **5.2× brightness ratio**; measure
     it → validates the magnitude calibration (the sensitivity/limiting-mag work).
  3. **Astrometry** — a **known 11.8′ separation at known PA 71°** = a precise
     **ruler + compass** in the field → measures plate scale + roll directly →
     **feeds the standing plate solve** (`design/standing-plate-solve.md`). A
     calibration gift: a fixed, always-up, bright, known-geometry reference.
- **Why it's arguably the most immediately useful zenith quest:** it doubles as a
  calibration standard for everything else — the ruler for plate scale, the ratio
  for photometry — always available, near-zenith, in the best air.

## Quest 5 — Polaris B by binocular (the £0 aperture)

**Chosen 2026-07-09.** Peter's "cheat" for the Polaris split: put a Pi camera
behind **one half of a pair of cheap binoculars** (e.g. 10×50), pointed at the
pole. Still DIY, long-focal-length, high-light-pollution astronomy — the pair
of 50 mm tubes is technically an interferometer baseline, but the prisms don't
preserve phase, so one tube it is.

- **Why it works:** a 50 mm objective has a Dawes limit of ~2.3″ (even 30 mm
  gives 3.9″) → the 18″ A–B split becomes **seeing-limited (~2–4″), not
  optics-limited**. The wall that blocks Quests 3 and Mizar A–B simply isn't
  there.
- **Two coupling stages** (IMX219 numbers, 1.12 µm px):
  | Stage | Optics | efl | scale | A–B sep |
  |---|---|---|---|---|
  | **T1 afocal** (no surgery) | camera + own lens through the eyepiece | ~47 mm (4.7 mm × 10×) | ~4.9″/px | **3.7 px** |
  | **T2 prime** (open one half) | objective only, sensor at focus | ~180 mm | ~1.3″/px | **14 px** |
  Afocal first — zero-commitment proof the optics chain works; prime is the
  better end state (B well clear of A's core).
- **The real challenge is CONTRAST, not resolution:** B is mag ~8.7 next to A
  at 2.0 — a ~470× ratio. PSF-wing modelling + subtraction (the Titan method)
  at 4–14 px separation = the Titan rehearsal, preserved from Quest 3 but at a
  far kinder separation.
- **No tracking needed — the pole is the cheat within the cheat.** Polaris
  moves ~0.17″/s: 1 px per ~7 s at prime, ~28 s afocal. Short unguided
  exposures, stack forever, Polaris never leaves even a 1° field. Mount = a
  fixed bracket. Light pollution is irrelevant for a mag-8.7 *point source*;
  A's halo is the enemy, and that's ours regardless of sky.
- **The toolkit transfers:** at 4.9″/px vs ~3″ seeing the afocal image is
  undersampled again → the streak/dither/drizzle + sub-pixel machinery applies
  to the new instrument unchanged.
- **Stretch goal — the Cepheid:** Polaris A is the nearest Cepheid (~0.05 mag,
  3.97 d period). With B (constant) and field stars as in-frame comparisons, a
  photometric campaign on this rig could **detect the pulsation of a Cepheid
  from a light-polluted garden**. Exercises exactly the photometry chain Algol
  (Quest 2) needs, available in summer while Perseus isn't.
- **Graduated wins:** T1 see B at all (afocal, stack + wing-subtract); T2 clean
  split at prime focus; T3 the Cepheid light curve.

## Status / dependencies (what these quests need built)
- **Plate solve as a standing tool** — have the recipe (astrometry.net on the
  derot window) but not a per-night automated solve. Needed for all three.
- **Frequency/magnitude (sensitivity) per-night deliverable** — `bin/sensitivity-*`
  exists (astrocam), needs finishing/generalising. Needed for Algol especially.
- **Narrow Module 3 camera** — M51 (and Polaris-B split) want the finer scale;
  the purchase is effectively part of the M51 quest.
- **Deep de-streaked stacking** — exists (detrans-deep); M51 pushes it hardest.
- **Binocular half + Pi camera bracket** — Quest 5's only hardware; already
  owned (afocal T1 needs no surgery at all).
