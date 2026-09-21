---
id: 2026-09-20-firstscope-derotation
title: De-rotation recovers 88 percent of a perfect stack
instrument: firstscope
date: 2026-09-20
night: 2026-09-20
tags: [de-rotation, stacking, pole, focus]
source:
  frames: 11911 frames at 3 s, night 2026-09-20, xoverpi
  tools: [derot-stack, derot-strip, derot-pole-refine, star-fwhm]
  scratch: muppet:/home/peter/tmp/derot
  scratch_note: >
    The arrays these figures are rendered from are SCRATCH, not archive.
    Re-rendering this entry after that directory is cleared needs the stack
    rebuilt from the night's frames first. Measurements by astro-capture.
figures:
  - src: ~/tmp/derot/mean-2026-09-20-00-0-600.fits
    caption: >
      600 frames — half an hour — de-rotated about the celestial
      pole and coadded. The slanted edges are the footprint of the field
      itself, swinging through the canvas as the sky turned; everything
      inside them is stacked sky.
    crop: [126, 703, 1975, 2355]
    crop_note: >
      Corners chosen by Peter in splay, 2026-09-21, probing the de-rotated
      mean at (126,731), (1975,703) and (1960,2355) — the bounding box
      of those three points is this crop.
    stretch: {fn: asinh, gain: 6.0, lo_pct: 50, hi_pct: 99.9}
  - src: ~/tmp/derot/mean-2026-09-20-00-0-600.fits
    caption: >
      The full-depth centre of the same stack, close up. The brightest star
      carries the annulus of a defocused Newtonian; the faint diagonal weave
      is correlated noise, not sky.
    crop: [632, 1428, 1443, 1756]
    stretch: {fn: asinh, gain: 6.0, lo_pct: 50, hi_pct: 99.9}
  - src: ~/tmp/derot/preview-max.fits
    caption: >
      The whole night as one pole-centred polar strip, 4x reduced. In polar
      coordinates de-rotation is a pure shift along the position-angle axis,
      which is why ten hours fits in a single array.
    stretch: {fn: asinh, gain: 5.0, lo_pct: 40, hi_pct: 99.9}
    scale: 0.5
---

A 76 mm scope with no tracking and no finder, stacking 600 three-second
frames, lands within 12 percent of the theoretical best a stack of that
depth can do. De-rotating about the celestial pole recovers a 19.2x drop in
noise where a perfect square-root-of-N stack would give 21.7x. The rest of
the night's interest is in what the number costs to get: how close the field
sits to the pole, and how long a star therefore dwells inside it.

# Notes

The pole is 4.32 degrees from the field centre, bearing 54 degrees left of
straight up, and it held all night — the fits from hour 00 and hour 04 agree.
That matters more than it sounds. Dwell time inside a 0.69 x 0.52 degree
field goes as the reciprocal of the distance to the pole, so every degree
closer is worth real integration.

Over four nights the scope has been walked onto the pole: 13.38 degrees, then
7.66, then 4.32. At 13.38 degrees a star crossed the field in about 12
minutes; at 4.32 it dwells for 37 minutes. Push the field centre inside 0.28
degrees and a star stays put for the whole night. The stack depth that buys
follows the same curve — 15x, then 27x, against a ceiling of 106x if the
field were centred on the pole itself.

The whole night also renders as a single pole-centred polar strip, 1619 by
22561 pixels, spanning 149.2 degrees of position angle from 2978 frames at a
median depth of 114. It holds 269 sources above 5 sigma. The strip works
because in polar coordinates de-rotation is a pure shift along the
position-angle axis, so a night's worth of rotation becomes one long
translation rather than 2978 separate resamplings.

Focus is the one thing this rig cannot measure on a single frame, and that is
worth stating plainly rather than quoting a number for. A real star here
spreads about 13 sigma of detection over 5 or 6 pixels, so its brightest
single pixel stands only 3 or 4 sigma above the noise. Anything that IS
bright enough to fit per-pixel in one 3-second frame turns out to be a
residual hot pixel or a cosmic ray — a fit restricted to single-frame
sources above 20 sigma duly returned a sub-pixel 0.9 pixel "PSF" with
elliptical shapes, which is a picture of the detector, not the optics. Depth
is not a luxury on this instrument; it is the only way it can see its own
focus. Fitting 2D Gaussians to stars standing at 130 to 270 sigma in the
600-frame stack gives 6.0 pixels FWHM, which at 1.925 arcsec per binned pixel
is about 11.5 arcsec — and that is an upper bound, because any error in the
pole enters the stack as smear.

# Numbers

- Noise reduction from 600 de-rotated frames: 19.2x, against 21.7x for a
  perfect square-root-of-N stack — 88 percent of ideal.
- Pole offset 4.32 degrees, bearing 54 degrees left of straight up; field
  centre declination 85.7. Hour 00 and hour 04 fits agree.
- Four-night walk onto the pole: 13.38 -> 7.66 -> 4.32 degrees.
- Dwell inside the field, T = 9504 / distance in degrees seconds: about 12
  minutes at 13.38 degrees, 37 minutes at 4.32, all night below 0.28.
- Stack depth available: 15x, then 27x, with a ceiling of 106x at the pole.
- Polar strip: 1619 x 22561 px, 149.2 degrees of position angle, 2978 frames,
  median depth 114, 269 sources above 5 sigma.
- PSF 11.5 arcsec FWHM (6.0 px at 1.925 arcsec/px), IQR 5.7-8.3 px, from 2D
  Gaussian fits to 130-270 sigma stars in the 600-frame stack. UPPER BOUND.
- Night total: 11,911 frames at 3 s.
