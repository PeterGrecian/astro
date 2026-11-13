---
id: 2026-11-13-winter-milky-way
title: The winter Milky Way, beside Orion, from a London suburb
instrument: eclipticam
date: 2026-11-13
night: 2026-11-12
camera: eclipticam-v3w
taken: 2026-11-13
tags: [eclipticam, v3w, milky-way, derotation, sky-brightness]
source:
  frames: eclipticam-v3w, night 2026-11-12, 60 s subs 03:40-04:20 UTC (GMT); 32 of 40 passed the clear-sky gate (glow-fit ratio <= 1.5)
  stack: "`derot-sky stack` (astro bin/derot-sky) with the night's refined camera model (skyglow-cammodel.json, from cammodel-2026-10-29) and per-frame alignment (derot-sky-align.npy); sky glow subtracted per frame; output fixed to the sky at 04:00 UTC"
  figures: astro scratch/milky-way-1112/figs.py (crop, stretch, galactic plane and star labels via bin/derot-annotate)
  band: "median of a 9 px median-filtered stack (stars removed), within 5 deg of the galactic plane against 15-30 deg from it; sky level 46 ADU per 2x2 cell (derot-sky-frames.json)"
figures:
  - src: astro/notes/figs/2026-11-13-winter-milky-way/deep.jpg
    field: "about 66° × 43° (fisheye; the 10° bar holds at the centre)"
    caption: >
      40 minutes of sky around 04:00 GMT on 13 November, 32 one-minute
      frames turned back to hold the stars still and averaged. Orion is
      right of centre and Sirius at the bottom, left of centre. The faint band rising
      through the left of the frame, between Orion and Procyon, is the
      Milky Way.
  - src: astro/notes/figs/2026-11-13-winter-milky-way/labelled.jpg
    field: "about 66° × 43°"
    caption: >
      The same picture with labels. Orange: the plane of the Galaxy (thin
      lines 10° either side). Blue: bright stars and the Rosette Nebula.
  - src: astro/notes/figs/2026-11-13-winter-milky-way/compare.jpg
    field: "each panel about 35° × 23°, on the plane in Monoceros"
    caption: >
      Two minutes (left) against forty (right), the same stretch. The band
      is there in two minutes but buried in noise; stacking twenty times
      the light is what lifts it out.
---

The camera that films the ecliptic caught the Milky Way at about 4 a.m.
GMT: a faint band running up past Orion's eastern side, through Monoceros
towards Gemini. This is the winter Milky Way. It is the part we see when
we look out of the Galaxy, not into its centre.

## What it is

In summer the Milky Way through Cygnus and Sagittarius is the view
towards the middle of the Galaxy, thick with stars and dust. In November
the night side of the Earth faces the other way. The band beside Orion lies
between galactic longitude 190° and 240°, close to the *anticentre*
(longitude 180°, in Auriga). We are looking outwards, through the thin
outer disc and the Perseus arm, at far fewer stars. It is the faintest
stretch of the band, and the hardest to see from a city.

## How bright it is

Measured on the stacked frame with the stars filtered out, the band within
5° of the plane is about **1 ADU** above sky 15° to 30° away. The sky
itself is 46 ADU. **So the winter Milky Way is about 2 to 3% of
Berrylands' sky glow.** It is brightest at longitude 210° to 220°, in
Monoceros, where it is about 3%, and fades southwards into Canis Major.

That is far below what an eye can pick out against a suburban sky. The
camera sees it because each 60 s frame has its smooth sky glow fitted and
subtracted, and because 32 frames are averaged.

## Caveats

- The per-frame glow model is smooth, but a band 20° wide is not small
  next to it, so the model may take some of the Milky Way's light with
  the sky. The 2 to 3% figure is more likely low than high.
- Stars soften towards the right edge and corners. The camera model is
  weakest there (2.5 px residuals beyond 35° off axis), and the lens may
  add coma of its own. The frame is cropped to the region every frame in
  the 40 minutes covered.
- One night, one window. A second clear night would confirm the number.
