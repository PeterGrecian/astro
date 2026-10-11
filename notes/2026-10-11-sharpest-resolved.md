---
id: 2026-10-11-sharpest-resolved
title: Sharpest thing resolved by each camera
instrument: eclipticam
date: 2026-10-11
night: 2026-10-09
tags: [resolution, deconvolution, double star, orion, record]
source:
  frames: "eclipticam v3w, 9 nights 2026-09-17 to 10-09, 672 frames of 60 s, stacked on the 03:13 UTC 2026-10-10 frame (see note 2026-10-10-orion-m42)"
  probes: "~/.splay-probes.log 2026-10-10: (1009,1095) and (1014,1101), the two stars of this pair"
  catalogue: "iota Ori (SIMBAD) 05 35 25.99 -05 54 35.6, V 2.77, O9 III. Struve 747 (WDS 05350-0600): A = HD 36960 05 35 02.68 -06 00 07.3, V 4.72, B0.5 V; B = HD 36959 05 35 01.01 -06 00 33.4, V 5.53, B1 V; A-B 36 arcsec, unresolved here"
  method: "Richardson-Lucy, 30 iterations, top-hat line kernel 6.0 superpixels at 9.3 deg. Predicted offset from a quadratic tangent-plane fit to 10 Orion stars (residual 0.1-0.2 superpixel near the sword). Peaks by 3x3 local maximum, positions by 3x3 centroid. Scripts ~/astro/scratch/orion/knot/knot.py, fig.py"
figures:
  - src: astro/notes/figs/2026-10-11-sharpest-resolved/iota-stf747.png
    caption: >
      iota Ori close up. Stacked, it is one smeared dash with a bump on it.
      Deconvolved, a second star separates out exactly where the catalogue
      puts Struve 747 (dashed circles: iota Ori where measured, Struve 747 at
      the catalogue's offset from it), and it does so in the September nights
      and the October nights separately. Square-root brightness scale.
---

Peter: *"we should have a field note for sharpest thing resolved."* This is
it, and it will be updated whenever the record falls.

## Eclipticam v3w

Wide angle means low resolving.

### The record: iota Ori and Struve 747, 8.2 arcminutes

**iota Ori**, the bright star at the tip of Orion's sword, and **Struve 747**,
a fainter pair of hot young stars just south-west of it, **8.2 arcminutes
apart**: about a quarter of the Moon's width.

That sounds wide, and for an eye it is. For this camera it is not. Each pixel
covers about 1.3 arcminutes of sky, and in a one-minute frame every star is
smeared into a dash about 12 pixels long. The two stars are 6 pixels apart,
so their dashes overlap and in the stack they are one blob with a bump on
it. They only come apart when the smear is undone (the deconvolution in the
Orion note): Struve 747 then stands clear of iota Ori.

Struve 747 is itself a double, 36 arcseconds apart. That is well inside one
pixel, so here it counts as one star.

### Why it is real and not an artefact

Undoing a smear can invent things. The usual fake is a single bright star
split into two peaks along its trail. So the second peak had to pass three
checks before it counts:

1. **It is where the catalogue says.** Measured from iota Ori, the second
   peak is 3.09 superpixels away at 48 degrees with 0.26 of iota Ori's
   brightness. The catalogue, taken through the camera's measured geometry,
   says 3.15 superpixels at 45 degrees with 0.24.
2. **Other bright stars do not do it.** Eleven other bright stars in the same
   deconvolved image have no side peak above 5% of their own brightness.
   iota Ori's is 26%.
3. **It is there in independent data.** September's four nights alone, and
   October's four nights alone (leaving out 9 October), each show it:

| data | separation | angle | brightness vs iota Ori |
|---|---|---|---|
| September only | 3.10 | 48 deg | 0.28 |
| October only | 2.95 | 47 deg | 0.23 |
| 9 October alone | 3.38 | 42 deg | 0.23 |
| all nine nights | 3.09 | 48 deg | 0.26 |
| **catalogue** | **3.15** | **45 deg** | **0.24** |

(Separations in superpixels: one superpixel is a 2x2 block of the sensor,
about 2.6 arcminutes here.)

Peter had already clicked on both stars when he probed the sword on 10
October, at the two positions this note confirms.

### What would beat it

The trails are the limit. Undoing a smear of fixed length cannot recover
fine detail along the trail, so pairs lined up east-west are harder than
this one, which lies diagonally. Frames of different lengths, or a camera
that tracks, would move the record. The next candidate in the sword is
theta1 and theta2 Ori at the heart of M42, 1.6 arcminutes apart: five times
closer, and here still one knot.
