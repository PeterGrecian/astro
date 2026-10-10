---
id: 2026-10-10-astrocam-rings
title: Newton's rings on astrocam, the glass cover shows itself
instrument: astrocam
date: 2026-10-10
night: 2026-10-09
tags: [astrocam, interference, newtons-rings, flat-field, glow-model, derotation]
source:
  frames: astrocam, night 2026-10-09; 61 clean dark frames spread through the night
  map: astrocam-frames/2026-10-09/derot-sky-residual.npy (median of glow-subtracted frames, each divided by its sky level), built by `derot-sky residual` (astro c2f56bb)
  model: astrocam-frames/2026-10-09/skyglow-cammodel.json (f 1683.9 binned px, lens axis (1155.9, 639.3))
  method: sensor column offsets removed, 3 px smoothing, ring centre found by maximising the contrast of the profile averaged around it; scratch/fringes/rings.py, fig.py
figures:
  - src: astro/notes/figs/2026-10-10-astrocam-rings/rings.png
    caption: >
      Left: the part of astrocam's 10-09 sky that stays fixed to the camera
      while the stars turn, as a percentage of the sky's brightness. Houses
      and the frame edge are masked dark grey. Right: the same, averaged in
      circles around the ring centre.
---

Peter: *"the glass cover for the camera is very thin and flat. probably the
cause of the newton's rings."*

## How the rings turned up

The deep de-rotated sweep for 10-09 turns every frame so the stars stay put
and averages the night. Once the sky-glow model was fixed, the background was
flat enough to stretch hard, and it showed five or six concentric rings
around the pole, steady all night, plus faint vertical stripes.

Rings around the pole are what de-rotation does to anything fixed to the
camera: a blemish at some distance from the pole is swept round a circle of
that radius. So the rings said only that something was camera-fixed, not
what. Taking the median of 61 clear frames in the camera's own frame (the
stars move between them and drop out) showed the real pattern directly:
rings in the camera, centred somewhere else entirely.

## What the pattern is

- **Centre** at pixel (973, 850) on the binned frame, 9.4 degrees from the
  lens axis. It is not the pole (697, 475) and not the lens axis
  (1156, 639), so it is neither the sky nor the lens.
- **About seven bright rings** out to 33 degrees from the centre, closing
  up as they go out: the first bright ring is 10.5 degrees out, the next
  ones about 5, then 4 degrees apart.
- **Faint**: about plus or minus 0.3% of the sky's brightness near the
  centre, up to about 0.8% at the edge. Invisible in any one frame; it took a
  whole night and a hard stretch to see.
- The vertical stripes are a separate thing: small offsets between sensor
  columns.

## Why a thin flat cover makes rings

The camera is focused on the stars, so the cover glass in front of it is
completely out of focus. Each pixel looks through the cover in one
direction. Some light bounces twice inside a thin layer of the cover before
going on, and when it rejoins the light that went straight through, the two
interfere. Whether they add or cancel depends on the angle the light crosses
the layer at, so equal angles give equal brightness: rings, centred on the
direction square to the layer. Physicists call these fringes of equal
inclination; Newton's rings are their cousin, from the same thin layer of
air between two pieces of glass.

That reading makes three checkable claims:

1. **The cover is tilted about 9.4 degrees to the lens.** The ring centre is
   where the cover's surface is square on, and it sits 9.4 degrees from the
   lens axis, towards the bottom left of the frame.
2. **The layer is about 10 micrometres thick, which is air, not glass.**
   About six and a half rings from the centre to 33 degrees needs a layer
   about 11 micrometres thick if it is air. Even very thin cover glass is
   ten or more times thicker, and would crowd dozens of rings into the same
   space, finer than sky light can show. The
   layer doing this is the air gap under the cover: Newton's rings in the
   literal sense.
3. **It is faint for a reason.** Each glass surface reflects about 4% of the
   light, so the two-bounce light is weak to begin with, and sky light
   mixes many colours whose rings fall in different places and mostly blur
   each other out. About 1% left over is the right size.

One thing does not fit a perfectly even gap: the rings close up more slowly
than an even layer predicts, and they are squeezed towards the top right.
The gap is probably a slight wedge or bow, as you would expect for a thin
cover held at its edges.

## Why it matters, and the fix

At 1% it is far below anything you would see in a picture, but it is the
same size as the faint structure the deep sweeps are after, and it is a
pattern a flat field would need to carry for any careful brightness
measurement. It may not hold still: the gap can change with temperature, and
10-09 had a lens moving during the night, which left a trace of the rings at
the right edge after correction.

The pipeline now builds this map every night and subtracts it before
de-rotation (astro c2f56bb). On 10-09 the rings and stripes are gone.

## Still to check

- **Colour.** Interference rings scale with wavelength: the red rings should
  sit about 13% further out than the blue ones. A lens or vignetting effect
  would not do that. This is the decisive test.
- **Night to night.** Do the rings stay put, drift with temperature, or move
  when the cover is touched?
- **The tilt.** Is the cover in fact about 9 degrees off square to the lens?
