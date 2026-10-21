---
id: 2026-10-21-astrocam-rings-not-the-glass
title: astrocam's rings outlived the glass, so they are inside the camera
instrument: astrocam
date: 2026-10-21
night: 2026-10-20
camera: astrocam
taken: 2026-10-09..2026-10-20
tags: [astrocam, interference, flat-field, ir-filter, derotation, follow-up]
follows: 2026-10-10-astrocam-rings
source:
  frames: astrocam, nights 2026-10-09 (glass on), 2026-10-17 (glass off, sensor board refitted), 2026-10-20 (glass off, repointed); 61 clean dark frames per night
  maps: "`derot-sky residual --stat clipped` per Bayer colour (`--channel R/G/B/G1/G2/sum`), a 3-sigma clipped mean of glow-subtracted frames each divided by its sky level (astro bin/derot-sky)"
  fit: "`camera-rings centre` (split-half profile agreement, grid then local refine) and `camera-rings colour` (astro bin/camera-rings); all angles through the 10-09 camera model (same lens)"
figures:
  - src: astro/notes/figs/2026-10-21-astrocam-rings-not-the-glass/glass.png
    field: "75° × 42° per panel (the whole frame)"
    caption: >
      The part of the sky that stays fixed to the camera, band-passed so only
      ring-sized structure is left, plus or minus 0.6% of the sky's
      brightness. Left: with the glass on. Middle and right: after it came
      off. The red cross is the fitted ring centre. Houses, trees and the frame
      edge are masked black.
  - src: astro/notes/figs/2026-10-21-astrocam-rings-not-the-glass/colour.png
    field: "0-36° from the ring centre"
    caption: >
      The 10-09 rings in each colour, averaged in circles around the centre.
      Red and blue have about half as many rings as green over the same
      angles, and three to four times the strength. Note the different
      vertical scales.
---

Peter, watching the 10-20 video: *"shows fringes despite glass cover
removed."*

The [10-10 note](2026-10-10-astrocam-rings.md) blamed the rings on a thin
air gap under the glass screen protector, and Peter took the glass off on
10-17. This is the follow-up: the rings did not go, so the glass was not
the cause.

## The rings stayed

The same median-of-the-night map as before, built for the nights after the
glass came off, still shows the rings at the same strength: about 0.3% of
the sky, as on 10-09. The centre barely moved:

| night | what changed | ring centre (binned px) | from the lens axis |
|---|---|---|---|
| 10-09 | glass on | (973, 849) | 9.4° |
| 10-17 | glass off, sensor board refitted | (940, 914) | 11.7° |
| 10-20 | glass off, camera repointed | (987, 867) | 9.5° |

Three things changed between those nights: the glass, the sensor board
(it fell off its circuit board on 10-17 and was put back), and the
pointing. The rings ignored all three. Rings that stay fixed in the camera
while the camera is repointed, and outlast a part being removed, live in
what is left: the camera module itself, its lens and the filter in front of
the sensor.

## Two things it is not

**Not a counting artefact.** The raw frames count light in whole steps, and
on a dark night the sky is only 30 to 80 steps above the camera's zero. A
median of whole numbers sticks to whole numbers, and that alone would draw
contour lines of the sky's smooth fall-off: rings. Swapping the median for
an average that still throws out stars left the rings in place. The median
was only exaggerating them a little in blue.

**Not the pixel grid.** Each 2×2 cell of the sensor has two green
photosites at different positions. Their two maps agree almost perfectly
(correlation 0.97), so the rings are not a beat between some fine pattern
and the grid.

## The colour test, and why it rules out a thin gap

The 10-10 note named this as the decisive test: interference in a thin
flat layer sets each ring where the light's path difference is a whole
number of wavelengths, so red rings should sit a little further out than
green, and blue a little further in, by around 10%.

That is not what the colours do (second figure). Green has six rings
between 11 and 34 degrees. Red has three over the same range and blue
four, so their rings are about twice as far apart, and they are three to
four times stronger: red 2.1%, blue 1.6%, green 0.55% of the sky. A 10%
shift with wavelength cannot double the spacing, and nothing about a thin
gap makes the outer colours stronger. So it is not a thin air gap.

Nor is it the lens's anti-reflection coating. Those coatings are a quarter
of a wavelength thick, about a ten-thousandth of a millimetre. Across 33
degrees, a layer that thin changes the light's path by far less than one
wavelength, so it cannot make even a single ring: at most a gentle change
of colour from the middle to the edge.

## What it probably is

The camera has an infrared-cut filter just in front of the sensor. It is
made the same way as a coating, but with dozens of layers rather than one,
and it lets through a band of colours rather than all of them. Two
properties of such filters fit what we see:

- **Their transmission ripples across the band**, a little more here and a
  little less there, and the ripple is largest near the edges of the band,
  where it cuts off red at one end and violet at the other. Red and blue
  sit near those edges and green sits in the middle, which matches red and
  blue having the strong rings and green the weak ones.
- **The ripple slides with the angle the light arrives at.** Light at a
  steeper angle sees the pattern shifted towards blue. So each direction
  into the camera sees a slightly different slice of the ripple, and equal
  angles see equal brightness: rings, centred where light meets the filter
  square on. In each colour the spacing follows that colour's share of the
  ripple, not its wavelength, which is why red and blue can share a spacing
  that green does not.

This is still a hypothesis. It explains the strength order and why the
spacing does not follow wavelength. It does not yet explain the exact
spacings, which need the filter's actual transmission curve, and that
curve is not published. A narrowband test would settle it: through a
narrow coloured filter, ripple rings should shift or fade as the band
moves, in a way a lens effect would not.

## What changes

- **Removing the glass did not fix it, and no change of window or cover
  will.** Only a different camera module would, and the IMX477 HQ cameras
  bought on 10-09 have a separate filter of their own, so they are worth
  checking the same way.
- **Software stays the fix.** The pipeline already subtracts a per-night
  ring map. It should now be built per colour, because red and blue carry
  rings that green does not, and a single map made from all four
  photosites under-corrects both. Build it with the clipped average, not
  the median, on these dark nights.
- The 10-10 note's centre, strength and three-checkable-claims reading
  still describe the pattern. Its cause does not: claims 1 and 2 (a tilted
  cover and a 10-micrometre air gap) are withdrawn.
