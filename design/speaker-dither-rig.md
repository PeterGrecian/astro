# Two-speaker 2-axis tilt dither rig

**Status: DESIGN 2026-07-07.** Cheap speaker drivers ordered. Two voice coils
give orthogonal camera-tilt axes → full 2D sub-pixel dither, commanded and
independent of sky-drift. **Especially for astrocam** (see why).

## Why two speakers / two axes — and why astrocam NEEDS it

A single tilt (about the pole-pointing axis) gives only the transverse
(radial-from-pole) wobble; it relies on **sky-drift** for the orthogonal
(along) axis. That's fine for v3w. But **astrocam is the case that needs two**:

1. **astrocam points at the celestial pole → stars barely drift** (short arcs).
   The sky-drift dither axis is weak/absent near the pole → a single-speaker rig
   leaves ~1 usable dither direction. Two orthogonal speakers give **full 2D from
   the speakers alone**, independent of the tiny drift.
2. **astrocam is fixed-focus** (glued IMX219, no VCM) → no focus-breathing radial
   axis → **the speakers are its ONLY dither source**; they must supply both axes.
3. Near-pole field has stars at **all orientations** (radial arcs) → needs
   isotropic 2D dither = two orthogonal tilts.

v3w (has drift + VCM breathing) could manage on 1 speaker; **astrocam genuinely
needs 2.** So the rig is designed 2-axis, deployed on astrocam first.

## Mechanics

- Camera plate on a compliant 2-axis flexure (or gimbal): two orthogonal nod
  axes through the camera's centre of mass, low friction, spring-return.
- **Speaker A** pushes the plate → nod about axis 1 → image shifts in direction 1.
- **Speaker B** (orthogonal) → nod about axis 2 → image shifts in direction 2.
- Small-angle tilt ≈ pure image translation (uniform shift for all stars).
- Throw is tiny: **0.1 px = 8 arcsec tilt; 0.5 px = 40 arcsec** (f≈2588 px on
  astrocam full-res). Voice coil **~1 µm/mA**; full dither ~**16 µm on a 100 mm
  arm = ~16 mA**. Well within a scrap speaker's linear range.

## Drive — circular (Lissajous) dither

Drive the two coils with **independent PWM sines 90° out of phase**:
```
A(t) = a·sin(2π f t)        B(t) = a·cos(2π f t)
```
→ the boresight traces a **circle** during the exposure → every star gets a
small circular dither → **uniform 2D sub-pixel sampling in one frame**, for every
source, in every orientation. (Better than a 1-axis S-streak, which samples one
transverse direction; the circle covers all phases isotropically.)
- **f ≈ 0.018 Hz** (one full circle per ~55 s exposure), or a few cycles/frame.
- Far below the cone resonance → **linear spring** → amplitude ∝ drive current,
  self-calibrating (measure the circle radius vs mA from the frames).
- Independent axes also allow **commanded (dx,dy)** offsets (e.g. a deterministic
  drizzle raster) instead of a circle, if wanted.

## Electronics

- Pi: 2× PWM outputs (hardware PWM pins) → 2× transistor/MOSFET drivers →
  2× voice coils. Low current (~16 mA peak) → a small NPN or logic-level MOSFET
  each, flyback diode across each coil. Shared ground.
- Optionally a series resistor to set the mA/µm scale; current = amplitude.
- Sync: the dither phase must be **known vs the exposure** so frames can be
  detranslated. Either (a) start the sine at exposure-open (open-loop, phase from
  a timestamp), or (b) log the commanded (A,B) per frame in the FITS header
  (like LENSPOS for breathing) → DITHERX/DITHERY/DITHPHAS.

## Calibration & use
- **Self-calibrate**: drive a known mA, measure the resulting streak/circle in
  px from a star → µm/mA and px/mA. Linear near DC.
- **Detranslate**: the commanded (dx,dy)(t) is known → shift each sub-exposure
  (or model the within-exposure smear) → rain onto the drizzle super-grid.
- Header per frame: DITHERAX/AY amplitude (mA), DITHFREQ, DITHPHAS — so the
  reconstruction knows the exact within-frame path (mirrors LENSPOS/LENSPREP).

## Sequence
1. **Tonight**: v3w breathing runs (radial axis) → measures residual transverse
   dither needed → sizes the speaker amplitude.
2. Build the 2-axis flexure + 2 coil drivers; bench-calibrate µm/mA.
3. **Deploy astrocam first** (it needs it most — pole-pointing, fixed-focus).
4. Add header logging + a detranslate/drizzle path that reads the commanded dither.
5. v3w as a 3rd axis (breathing radial + speaker 2D transverse).

## Relation to breathing (v3w)
v3w: breathing = radial (∝R) axis; speakers = 2D transverse. astrocam: speakers =
the whole 2D dither. Both feed the same drizzle super-grid reconstruction.
See `project-v3w-star-id-moon-anchor` (S-streak / breathing / drizzle threads).
