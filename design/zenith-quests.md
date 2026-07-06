# Zenith quests — M51, Algol, Polaris A/B

**Three targets to attempt at/near the zenith, chosen 2026-07-06.** The zenith
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

## Status / dependencies (what these quests need built)
- **Plate solve as a standing tool** — have the recipe (astrometry.net on the
  derot window) but not a per-night automated solve. Needed for all three.
- **Frequency/magnitude (sensitivity) per-night deliverable** — `bin/sensitivity-*`
  exists (astrocam), needs finishing/generalising. Needed for Algol especially.
- **Narrow Module 3 camera** — M51 (and Polaris-B split) want the finer scale;
  the purchase is effectively part of the M51 quest.
- **Deep de-streaked stacking** — exists (detrans-deep); M51 pushes it hardest.
