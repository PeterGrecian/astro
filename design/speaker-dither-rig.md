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

**3-point corner scheme (Peter's design — the camera IS the moving plate):**
The camera is a **2 cm square**. Mount it on three of its four corners:
```
  P0 constrained (pivot) ──────── P1 → speaker A
        │
  P2 → speaker B                  P3 free (follows)
```
- **P0** — constrained pivot (the fixed reference).
- **P1, P2** — the two ADJACENT corners, each on a **speaker voice coil**.
- **P3** — diagonal, free.
- Speaker A (P1) nods the plate about the **P0–P2 edge**; speaker B (P2) about
  the **P0–P1 edge** → **two orthogonal tilt axes = clean 2D**, no separate
  gimbal (the constraint geometry gives the axes for free).
- **Throw is tiny** — arm = the 20 mm edge: **0.1 px shift = 8 arcsec = 0.77 µm
  coil throw; 0.5 px = 40 arcsec = 3.9 µm**. At ~1 µm/mA → **sub-mA to ~1 mA**
  drive, deep in the linear regime. (Bare-coil µm/mA changes once the camera
  loads it — self-calibrate.)

**Weighted diaphragm (anti-microphony, Peter):** mass-load each cone so it
ignores ambient acoustic/vibration (footsteps, wind, sound) that would inject
*uncommanded* dither — critical, since the reconstruction assumes the dither is
ONLY what we drive. Bonus: lower f0 = more stable/predictable settling.
- **Bench-check**: weighting lowers resonance f0 = ½π√(k/m); we drive ~0.018 Hz
  and must stay **stiffness-controlled** (below f0 → position ∝ current, linear,
  no phase lag). The **camera mass already dominates** the light cone, so f0 is
  already low; confirm f0 stays comfortably above 0.018 Hz on the bench.

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

**PWM-as-DAC, NOT PWM-at-0.03Hz (Peter).** Running hardware PWM literally at
0.03 Hz is daft (33 s period, terrible resolution). Instead: keep a **fast PWM
carrier (~10 kHz)** and slowly vary the **duty cycle** in software to trace the
sine; an **RC low-pass** smooths the carrier into an analog control voltage. The
0.03 Hz lives in the duty-cycle *program* (a `sin(2π f t) → duty` loop, rewrite
every ~10–50 ms), not the PWM frequency.

- **2 channels**: the Pi's two hardware PWM channels (GPIO12/13 or 18/19) — one
  per speaker = the two orthogonal tilt axes; drive 90° out of phase → circle.
- **RC filter (Peter)**: cutoff between the sine and the carrier, e.g.
  **fc ≈ 10 Hz (R≈16 k, C≈1 µF)**: the 0.03 Hz sine passes unattenuated with
  **~zero phase lag** (0.03 ≪ 10 → negligible RC phase error — important, the
  reconstruction needs the dither phase vs exposure precisely); the 10 kHz
  carrier is knocked down ~1000×. Duty resolution (12–16 bit at 10 kHz) gives
  >1000 smooth voltage levels over the sine — ample for µm throws.
- **Driver = voltage→CURRENT, not just voltage.** The RC gives a voltage but the
  coil throw ∝ **current** (~1 µm/mA), and coil R drifts with temperature. So
  follow the filter with a **current source** (transistor + emitter/sense
  resistor, or an op-amp current driver) so µm/mA stays linear and temp-stable.
  Low current (~1 mA peak here, from the 20 mm-arm geometry) → a small NPN or
  logic-level MOSFET each, flyback diode across each coil, shared ground.
- Series sense resistor sets the mA/µm scale; current = commanded amplitude.
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
