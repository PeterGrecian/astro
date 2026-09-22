---
id: 2026-09-21-astrocam-sky-brightness
title: What our sky actually measures, in mag per square arcsecond
instrument: astrocam
date: 2026-09-22
night: 2026-09-21
tags: [sky-brightness, plate-solve, photometry, light-pollution, calibration]
source:
  frames: 598 frames at 59.9 s, night 2026-09-21, astrocam (imx708, POSINDEX 3)
  reference_frame: 1790043983195.fits.fz (2026-09-22T02:26:23.195Z)
  tools: [solve-field, cross-match-gaia, scan-brightness]
  catalogue: Tycho-2 indexes (astrometry.net, muppet) for the solve; Gaia DR3 for the zeropoint
  scratch: muppet:/home/peter/tmp/platesolve
  scratch_note: >
    Crops, WCS files and detection CSVs are SCRATCH. The night's frames and
    brightness.csv under astrocam-frames/2026-09-21 are archive and are all
    that is needed to redo this. Measurements by astro-capture, 2026-09-22.
figures:
  - src: /mnt/bigstore/astro-data/astrocam-frames/2026-09-21/brightness.png
    caption: >
      Per-frame brightness across the night, stops above the chart pedestal.
      The trough at 02h is the darkest hour; the sharp rise after 04h is dawn.
---

The house has always quoted its sky from a light pollution map: Bortle 6,
SQM around 19.4. On the night of 2026-09-21 we measured it instead, from our
own frames, and it is about 1.3 magnitudes brighter than that.

## The night

Astrocam ran 598 frames of 59.9 s at gain 1. Capture opened when the sun
reached 10 degrees below the horizon at 19:01 UTC and closed at 04:48.

| hour (UTC) | frames | frame mean (ADU) | stops above pedestal |
|---|---|---|---|
| 19 | 56 | 102.813 | 5.723 |
| 20 | 61 | 95.100 | 5.495 |
| 21 | 60 | 90.187 | 5.329 |
| 22 | 60 | 87.570 | 5.232 |
| 23 | 60 | 85.152 | 5.136 |
| 00 | 60 | 82.725 | 5.032 |
| 01 | 60 | 82.153 | 5.007 |
| **02** | **60** | **81.845** | **4.993** |
| 03 | 60 | 82.336 | 5.015 |
| 04 | 60 | 110.972 | 5.930 |

The darkest single frame of the night landed at **02:26:23 UTC, 03:26 BST**,
at a frame mean of 81.711 ADU, which is 4.987 stops above the pedestal. The
six darkest frames all fall between 02:23 and 02:28.

## The moon

The moon was a **waxing gibbous, 79.2 percent illuminated**, 10.96 days old.
It does not spoil the result because it had already **set at 00:19 UTC**, two
hours and seven minutes before the darkest frame. At 02:26 it sat 17.2 degrees
below the horizon; the sun was 29.1 degrees down.

That matters for the ranking below. This night reached its trough under a
gibbous moon that had merely got out of the way. The two September nights that
beat it were genuine new moon nights, 1.2 and 4.8 percent illuminated. On moon
terms this was the least favourable of the three by a wide margin.

| night | darkest frame (ADU) | stops | moon illum at trough |
|---|---|---|---|
| 2026-09-10 | 78.812 | 4.849 | 1.2 % |
| 2026-09-13 | 79.671 | 4.891 | 4.8 % |
| **2026-09-21** | **81.711** | **4.987** | **79.2 %, set 00:19** |
| 2026-08-19 | 83.830 | 5.080 | 49.7 % |

(The 69.888 ADU frame from 2026-06-09 is excluded: that is the imx219 era,
POSINDEX 1, a different sensor with a different black level and pedestal. It
is not comparable.)

## The plate solve

Sky brightness in physical units needs a plate scale and a photometric
zeropoint, and astrocam had neither: `plate_scale_deg_px` in camera.json has
been flagged STALE and INVALID since the imx708 swap in July, being an
imx219-era value, and no zeropoint existed for this camera at all.

Both came from one frame. The green channel was extracted from the Bayer
mosaic (the two greens sit on the anti-diagonal, so the in-capture 180 degree
rotation leaves them where they are), and five 600 px crops were solved
against the Tycho-2 indexes on muppet. All five solved.

| crop | native arcsec/px | zeropoint (Gaia G) | sky above black (ADU) | mu_G |
|---|---|---|---|---|
| centre | 60.88 | 11.526 | 33.5 | 18.14 |
| left | 56.84 | 11.392 | 30.0 | 17.98 |
| top | 58.92 | 11.539 | 27.5 | 18.30 |
| bottom | 60.74 | 11.431 | 35.0 | 17.99 |
| right | 58.54 | 11.609 | 21.5 | (excluded) |

The right crop is excluded: 23 matched stars against 36 to 70 elsewhere, and a
median astrometric residual of 129 arcsec against 37 to 43 arcsec for the rest.

Exposure time cancels, because the star and the sky are measured in the same
frame:

    mu_G = ZP + 2.5 * log10(4 * p^2 / S_sky)

## Results

**Plate scale: 58.9 arcsec/px native, 0.016366 deg/px.** The stale value of
0.0190 deg/px was 16 percent too coarse. The 56.8 to 60.9 spread across the
field is real radial distortion of about 7 percent, so a single scalar will
always be an approximation here. Implied horizontal field of view is **75.4
degrees**, not the 66 degrees asserted in camera.json's focus notes.

**Black level 64, now measured rather than inferred.** The first percentile of
all four Bayer channels is exactly 64.00, because part of the frame is
permanently occluded by trees and roofline and sits at the electronic floor
all night. The occluded region is a built-in dark reference. Strictly this is
an upper bound, since a light leak would raise it, but four independent
channels agreeing exactly is hard to explain otherwise.

**Sky surface brightness: mu_G = 18.1 mag/arcsec^2**, with a spread of 18.0 to
18.3 across the four good crops. The result is barely sensitive to the black
level: moving it by 2 ADU either way shifts mu by 0.07.

## What that means, honestly

Three effects push the true zenith figure darker than 18.1, and none of them
is large enough to recover 19.4:

- Astrocam points at the celestial pole, so it is looking at 51.4 degrees
  altitude through airmass 1.28, not at the zenith. Worth perhaps 0.2 to 0.4.
- Gaia G is a very broad band and the sky's LED and sodium spectrum is not a
  star's spectrum, so there is an unmodelled colour term of a few tenths.
- The 6 px photometric aperture loses some of the PSF wing, which biases the
  zeropoint low and mu low, perhaps 0.1.

Taken generously that is about **18.5 zenith-equivalent, which is Bortle 7**,
the suburban to urban transition, rather than the Bortle 6 we have been
claiming. And this was measured on one of the darkest nights of the year so
far, after moonset, in the darkest hour of that night.
