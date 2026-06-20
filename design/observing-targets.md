# Observing targets — what the pipeline is ultimately aimed at

**Status**: planning / motivation, not a work list. These are the
science targets that justify the per-night derot + distortion work;
the concrete tasks they imply live in `TODO.md` (barrel-distortion,
per-tile pole, multi-night stacking). Moved out of TODO.md 2026-06-20
because they're durable direction, not items to tick off.

## Neptune (mag +7.8), Nov 2026

Late Sep / early Oct opposition; observable through November. Estimated
~28 h of derotated stacking (~4 dark nights × ~7 h) for 5–6× current
single-hour SNR. Needs:
- sharp per-night `final/derot.fits.fz`
- a planet-aware motion model (Neptune drifts ~1 arcmin/day vs.
  sidereal — can't just co-add across nights at the sidereal pole)
- the camera to survive winter (warm + dry; cover working).

## Uranus (mag +5.6), Nov 2026 opposition

Brighter, easier. Should appear in the per-night derot already; a
blink-comparator diff vs. the previous night should be unmistakable.

## Wandering-star (planet) blink discriminator

Subtract two per-night `derot.fits.fz` at identical pole + distortion.
Stars cancel; planets / asteroids / comets leave a ±star signature at
tonight's and yesterday's pixel positions. Sketch:

    derot-diff <A> <B>  →  <B>/diff-vs-<A>.fits.fz

This is the general mechanism behind both the Uranus and Neptune
detections — anything that moves against the fixed stars pops out.
