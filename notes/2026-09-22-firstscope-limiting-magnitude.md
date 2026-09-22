---
id: 2026-09-22-firstscope-limiting-magnitude
title: How faint does the FirstScope actually see
instrument: firstscope
date: 2026-09-22
night: 2026-09-20
tags: [limiting-magnitude, star-counts, photometry, de-rotation, psf]
source:
  frames: 600 of 11,911 frames at 3 s, night 2026-09-20, xoverpi
  stack: mean-2026-09-20-00-0-600.fits (de-rotated coadd, 30 minutes)
  method: source counts against standard cumulative star counts
  scratch: muppet:/home/peter/tmp/derot
  scratch_note: >
    The stack is SCRATCH. Redoing this needs the night's frames and a rebuilt
    de-rotated coadd. Stack and per-night measurements by astro-capture;
    the counting, the correction and the estimate by astro-deliverables,
    2026-09-22.
figures:
  - src: ~/tmp/derot/mean-2026-09-20-00-0-600.fits
    caption: >
      The de-rotated field, with the 19 sources counted for this estimate
      circled. Every circle is one star; the detector originally found 35
      blobs here, because each star is drawn as a broken ring rather than a
      dot, and the rings fragment.
    crop: [126, 703, 1975, 2355]
    stretch: {fn: asinh, gain: 6.0, lo_pct: 50, hi_pct: 99.9}
    overlay:
      radius: 22
      points: [[250,1242],[237,1114],[302,934],[243,996],[620,1296],[990,1199],[836,1230],[1082,927],[1377,877],[1270,1089],[926,557],[1237,595],[1114,448],[1162,505],[1442,628],[717,914],[667,471],[657,623],[533,744]]
---

A 76 mm scope with no tracking, stacking half an hour of three-second
frames, reaches about **12th magnitude**. The interesting part is not the
number but how you get it without a star catalogue: count how many stars
you can see in a known patch of sky, and look up how many stars there are
supposed to be. The sky itself is the calibration.

## Counting what is there

The de-rotated 30-minute stack was matched-filtered at the PSF scale and
everything above 5 sigma was counted, over two regions of the canvas that
differ five-fold in area:

| region | area | sources | density |
|---|---|---|---|
| full depth, 600 frames | 0.063 deg² | 3 | 47 /deg² |
| half depth and up, ~442 frames | 0.321 deg² | 19 | 59 /deg² |

Standard cumulative star counts — about 8 stars per square degree brighter
than 10th magnitude, 55 brighter than 12th, 135 brighter than 13th — put a
density of 59 per square degree at **V ≈ 12.1**.

## The correction that mattered

The first pass counted **35** sources in the larger region, not 19, and gave
V ≈ 12.8. That was wrong, and the way it was wrong is worth recording.

The detector was finding 35 separate blobs, but their median
nearest-neighbour separation was 15.5 pixels. For 19 stars scattered at
random across that region the nearest neighbour should sit around 120
pixels. Stars do not clump at 30 arcsec.

Looking at the pixels settles it: **each source is a ring, not a dot** — the
annulus of a defocused Newtonian with a central obstruction, about 20 pixels
across, and the detector was breaking each ring into two to four arcs and
counting them separately. Merging detections within 25 pixels gives 19
sources, and the estimate drops by 0.7 magnitudes.

The clue was in the cross-check all along. An independent estimate from
astro-capture's polar strip — 269 sources over 9.7 square degrees at a
median depth of 114 frames — gives V ≈ 11.3, which scaled to 600 frames
predicts 12.2. Against the over-counted 12.8 that looked like a 0.6
magnitude disagreement to be explained away. Against the corrected 12.1 the
two methods agree to a tenth of a magnitude.

## What it implies elsewhere

Stacking gains go as the square root of the number of frames, which the
88-percent-of-ideal result on this night supports, so one number gives the
others:

| | |
|---|---|
| single 3 s frame | V ≈ 8.6 |
| stars used for the PSF fit (130–270 sigma) | V ≈ 7.8 to 8.5 |
| whole night at today's pointing, 27x | V ≈ 12.2 |
| pole-centred ceiling, 106x | V ≈ 13.7 |

That last line is the case for walking the mount onto the pole. The
difference between today's 4.32 degrees and a field centred on the pole is
about 1.5 magnitudes, for no extra hardware and no longer night.

## How much to trust it

The dominant uncertainty is not the counting. Poisson error on 19 sources is
about 0.25 magnitudes; the star-count model and the unfiltered response are
worth more than that.

- **The band is not V.** The sensor is panchromatic, so red stars are
  favoured and V is a stand-in. A few tenths.
- **Galactic latitude, with a direction.** The field is near Polaris, about
  27 degrees above the galactic plane, where counts run below the all-sky
  average used here. Fewer stars available per magnitude means you must go
  deeper to find 59 of them, so the true limit is if anything slightly
  fainter.
- **5 sigma is not completeness.** Turnover begins half a magnitude to a
  magnitude brighter; this is nearer a 50 percent completeness point than a
  hard floor.
- **The area depends on an unmeasured plate scale.** Density is sources per
  square degree, and the square degrees come from the FirstScope's
  *theoretical* 1.925 arcsec per binned pixel. A 10 percent error there
  moves the area 21 percent and the answer about 0.2 magnitudes.

That last one has a fix, and it is the same fix that turned astrocam's sky
brightness from a map reading into a measurement: plate-solve a stack and
cross-match it to Gaia. See [the astrocam plate
solve](/astro/notes/2026-09-22-astrocam-plate-solve) for what that produced
on the other camera — a measured scale, a real field of view, and a
photometric zeropoint. On the FirstScope it would replace this entire
estimate with a measured limit.
