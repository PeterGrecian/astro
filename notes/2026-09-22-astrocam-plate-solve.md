---
id: 2026-09-22-astrocam-plate-solve
title: The camera works out which stars it is looking at
instrument: astrocam
date: 2026-09-22
night: 2026-09-21
tags: [plate-solve, astrometry, photometry, calibration, gaia]
source:
  frames: one 59.9 s frame, night 2026-09-21, astrocam (imx708, POSINDEX 3)
  reference_frame: 1790043983195.fits.fz (2026-09-22T02:26:23.195Z)
  tools: [solve-field, cross-match-gaia]
  catalogue: Tycho-2 indexes (astrometry.net, muppet) for the solve; Gaia DR3 for the magnitudes
  scratch: muppet:/home/peter/tmp/platesolve
  scratch_note: >
    Crops, WCS files, correspondence tables and detection CSVs are SCRATCH.
    The archive needed to redo the whole thing is astrocam-frames/2026-09-21.
    Measurements and solve by astro-capture, 2026-09-22.
figures:
  - src: ~/tmp/platesolve/crop_centre.fits
    caption: >
      One 600-pixel crop of the green channel, as the solver saw it. The
      circles are the 18 stars it matched to the catalogue — that match is
      what turns a picture into a measurement. The bright wash to the lower
      left is the sky itself, which is the subject of the companion note.
    stretch: {fn: asinh, gain: 4.0, lo_pct: 60, hi_pct: 99.5}
    overlay: {corr: ~/tmp/platesolve/crop_centre.corr, radius: 14}
---

A camera that knows nothing about the sky can still be told where it is
pointing and how sensitive it is, by the stars in its own picture. It works
in two steps: first work out *which* stars these are, then look up how
bright they are already known to be. Do both on one frame and the camera has
calibrated itself against the sky it was photographing.

## Step one: which stars are these

The green channel was pulled out of the Bayer mosaic and five 600-pixel crops
were handed to solve-field, the astrometry.net solver, running against the
Tycho-2 indexes on muppet. The solver knows nothing about where the camera
was pointed. It looks at the pattern of bright points, searches for a
matching pattern in its star catalogue, and reports where on the sky that
pattern sits and at what scale.

All five crops solved. The picture above is the centre crop with the matched
stars circled.

That immediately fixed something we had been carrying for months.

| | was | is |
|---|---|---|
| plate scale | 0.0190 deg/px | **0.016366 deg/px** |
| | (imx219 era, flagged INVALID since July) | 58.9 arcsec/px native |
| field of view | 66 degrees (asserted) | **75.4 degrees** |

The old number was 16 percent too coarse. It had been marked stale in
`camera.json` since the imx708 swap in July, which is honest as far as it
goes, but a stale number still gets used by anything that does not read the
note beside it.

The spread across the five crops is 56.8 to 60.9 arcsec/px, and that spread
is not error — it is about 7 percent of real radial distortion across a
75-degree field. A single scalar plate scale will always be an approximation
on this lens.

## Step two: how bright are they known to be

Knowing which star is which means the catalogue magnitude of each one can be
read off. Every detected star was matched to Gaia DR3: 36 to 70 stars per
crop, with a median astrometric residual of 37 to 43 arcsec — comfortably
inside one pixel.

Their known brightness against our measured flux gives the zeropoint, the
number that converts our arbitrary counts into real magnitudes.

| crop | zeropoint (Gaia G) |
|---|---|
| centre | 11.526 |
| left | 11.392 |
| top | 11.539 |
| bottom | 11.431 |

Four independent crops agreeing to about a tenth of a magnitude is the
result: the calibration is a property of the camera, not an artefact of
where in the frame you look.

One crop was thrown out. The right-hand crop matched only 23 stars against
36 to 70 elsewhere, with a median residual of 129 arcsec against 37 to 43 —
so its solve is the odd one out and its zeropoint was not used.

## Why the two steps together give the sky

The useful trick is that the sky brightness then falls out of the same frame,
and the exposure time cancels:

    mu_G = ZP + 2.5 * log10(4 * p^2 / S_sky)

The stars and the sky between them were recorded in the same exposure,
through the same optics, on the same sensor. Anything that would scale both
equally — how long the shutter was open, how sensitive the sensor is — divides
out. What remains is a physical measurement of how bright our sky is, which
is [the companion note](/astro/notes/2026-09-21-astrocam-sky-brightness).

## The unplanned result: black level 64, measured

Part of every astrocam frame is permanently blocked by trees and roofline.
That corner sees no sky, all night, which makes it a dark reference built
into every exposure.

The first percentile of all four Bayer channels is exactly **64.00**. That is
the sensor's electronic zero, measured. It is the value `camera.json` has
always carried, but carried as INFERRED — the documented figure for this
sensor family rather than one taken from our own hardware.

Strictly it is an upper bound, since a light leak could only raise it. Four
independent channels landing on exactly the same number is hard to explain
any other way.

## Caveats

- Gaia G is a very broad band, and the sky's LED and sodium spectrum is
  nothing like a star's. There is an unmodelled colour term of a few tenths
  in anything derived from this zeropoint.
- The camera points at the celestial pole: 51.4 degrees altitude, airmass
  1.28. None of this is a zenith measurement.
- The photometric aperture is 6 px and loses some of the PSF wing, which
  biases the zeropoint slightly low.
