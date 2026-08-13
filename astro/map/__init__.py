"""the map — long-timebase sidereal accumulation.

The map is the estate's long-horizon accumulator: every frame, from every
camera and every calibration epoch, mapped onto a sidereal coordinate system
and summed there. Named 2026-08-13 for the MATHEMATICAL sense of the word — a
mapping from image space to the celestial sphere — not "a picture of a place".
It retires the placeholder "the thrust".

Design: `design/accumulation-bucket-refinement.md` (method, buckets, recursion,
storage constraints), `design/what-accumulation-buys.md` (why depth pays),
`design/accumulator-outlier-rejection.md` (per-cell robustness),
`design/hierarchical-vector-field.md` (the remap this depends on).

THERE IS NOT ONE MAP — THERE IS A MAP PER PROJECTION. The projection is a
property of the instrument's geometry, not a global choice, and is therefore
epoch-bounded:
  polecam      polar/azimuthal about the celestial pole (the pole is a
               coordinate singularity in RA/Dec, but the sky ROTATES about it)
  eclipticam   ecliptic-aligned curved bands (a 102 deg field cannot use one
               tangent plane; gnomonic diverges long before that)
  astrocam     polar about the pole
  canon        TBD — pole_prior_xy and plate_scale are both null (unsolved)
Per-instrument maps accumulate in their native projection; cross-instrument
combination re-projects onto a shared frame LATE, the same discipline as
epochs — accumulate natively, combine only where frames are commensurable.

Order of work: scratch (low-resolution passes to settle plumbing and bucket
thresholds) -> metrics sidecar -> bucketed accumulation -> recursive refinement.
"""
