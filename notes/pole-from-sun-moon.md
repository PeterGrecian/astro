# Pole determination from sun + moon

Written 2026-06-05.

Eclipticam is a fixed window-mounted camera that does **not** see the
celestial pole (cf. astrocam, which does). For derotation-stacking
to work on eclipticam, the pole position must be known to the pixel
grid. This note records why solar/lunar arc-fitting is a strong
approach, and why that conclusion makes on-Pi derotation-stacking
attractive for the whole astro project.

## Why sun + moon work as anchors

The pole is the axis of apparent diurnal rotation. Any two
well-anchored sky positions across time over-determine it. The sun
and moon are the best anchors a camera can have because:

- **Ephemerides (JPL DE440) are milliarcsecond-precise.** Negligible
  contribution to the error budget.
- **Both are bright enough to centroid sub-pixel** even through
  clouds. Sun limb-fits to ~0.1 px (~8" on V3 Wide @ 80"/px). Moon
  to ~1 px (worse near terminator, better near full moon).
- **NTP-disciplined Pi clocks are sub-millisecond.** Sun moves
  15"/s; timing contributes sub-arcsec error.
- **Both move enough over a day to fully constrain the fit.** Sun
  sweeps 120° of arc in 8 daylight hours. On eclipticam that's most
  of the FoV. Pole error scales as `centroid_error / arc_length_px`,
  so a day of solar observation gives ~1" pole accuracy. A month of
  combined sun+moon, with declinations spanning ±28° (moon) and
  ±23° (sun, annual), pushes that to milliarcseconds.

## Error budget summary

| Source | Magnitude |
|---|---|
| JPL DE440 sun/moon ephemeris | <1 mas |
| Pi NTP clock | <1" (sun at 15"/s) |
| Sun limb-fit centroid | ~8" per obs |
| Moon centroid (near full) | ~80" per obs |
| **Per-obs total** | ~10–80" |
| **After 1 day of arc** | ~1" |
| **After 1 month of arcs** | mas-class |

## Caveats specific to eclipticam (window mount)

- **Window-glass distortion** introduces a position-dependent static
  offset on top of true optics. The pole derived from sun/moon tracks
  is *the true pole, viewed through the distortion gradient at the
  pixel positions sun/moon actually occupy*. It is therefore only
  directly valid for derotating stars in the same image region.
  Full-field derotation needs a static distortion map calibrated
  separately (e.g. from a dark-sky plate-solve).
- **Atmospheric refraction** lifts the sun/moon ~30' near the horizon.
  Predictable from altitude → correct analytically before fitting,
  not after.

## Why this matters for the architecture

Pole calibration via sun/moon is **cheap, automatic, self-improving,
and survives a stable mount indefinitely.** That makes "fit pole
once at install + verify daily off sun + verify nightly off moon"
a robust loop. Mount drift becomes a measurable residual rather than
a silent failure mode.

The implication for the wider astro project: **on-Pi derotation
stacking is a strong idea**, not a fallback. If pole accuracy is
not the bottleneck (and it isn't, by the analysis above), and the
Pi 4/5 has spare CPU for the warp + sum, then there's no reason to
ship raw frames to puppy for derotation. Local accumulation reduces
NFS bandwidth ~10× and keeps each host's astronomy self-contained.

## Comparison with astrocam

| | Astrocam | Eclipticam |
|---|---|---|
| Sees celestial pole? | Yes (in frame) | No (off-field) |
| Derotation centre | Pole, single rotation angle | Off-field rotation → per-pixel WCS warp |
| Pole calibration | Plate-solve any clear-night frame; cross-check via long arcs | Sun/moon arc-fitting, daily/nightly |
| Distortion sensitivity | Low (rotation about visible centre tolerates ~1' pole error) | High (off-axis rotation amplifies errors linearly with distance from pole) |
| Mount stability requirement | Loose (pole re-derives nightly) | Tight (per-frame plate-solve still needed; mount drift is what sun/moon detect) |

## Open questions

- What's the simplest sun-fit code? `astropy.coordinates.get_sun`
  for ephemeris + a circle-fit to a binary mask of the solar disc.
  Probably one afternoon's work on eclipticam.
- Sub-pixel moon centroid: limb-fit (fit a circle to the bright limb,
  use phase to weight the fit away from the terminator), or
  cross-correlate against a phase-rendered template? Latter is
  more accurate but heavier.
- How often does the sun-fit need to refit the pole from scratch
  vs. just contributing a residual to a Kalman-style running
  estimate? Probably re-fit weekly, residual-track daily.
