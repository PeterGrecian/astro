# Two-speaker 2-axis tilt dither rig

> Shared electronics, different application: the **PWM-as-DAC + RC-filter +
> current-driver** technique in "Electronics" below is also used to make
> *audible sound* on a Pi in `~/Berrylands/pwmaudio/` (there the coil drives a
> speaker for tones; here it drives voice coils as silent µm actuators). This
> doc stays in astro — it's an astronomy deliverable.

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

---

## Bench PoC results — 2026-07-31 (deskpi + IMX219 V2)

First end-to-end validation of the mechanism. **The chain works: commanded
current → cone travel → measurable camera image shift.** Details in
`~/Berrylands/pwmaudio/experiments/dither-deflection.md`; roadmap in the
`astro-speaker-dither` strand STATE.

**What's proven (critical early steps, now cleared):**
- Driver: common-emitter → **darlington (2N3904 → B882/D882)** delivers full
  coil current. Measured **5.6 V RMS ≈ 0.70 A / ~3.9 W** into the 8 Ω coil.
- Actuator: a **Faital Pro 4FE35** (4" full-range) moves the cone **~3 mm**,
  throwing the image **~230 px** across a 640-wide frame at high duty — the
  original feeble speaker gave nothing. Force & range are now a *non-issue*
  (~1000× more travel than the 0.1 px ≈ 0.77 µm dither target needs).
- Capture + detector: V4L2 raw-Bayer on ARMv6 (rpicam barred), FFT phase-corr
  cross-correlation resolves shifts to **~0.008 px** (control), drift ~0.02 px.

**Two empirical gotchas found:**
- **PWM carrier landed at 8 kHz, not the requested 20 kHz** — pigpio
  `set_PWM_frequency` snaps to a discrete ladder. 8 kHz is dead in the audible
  band → loud. Fix: use `pi.hardware_PWM(18, 40000, duty*1e6)` (true HW PWM,
  arbitrary freq) → carrier inaudible + coil L and a shunt cap attenuate it far
  harder. A **10 µF shunt cap across the coil** (coil = the L+R) made it
  non-painful; +100 µF better (fc ≈ 2.3 kHz / 680 Hz).
- **Response is stick-slip, not proportional.** Camera *resting in contact*
  with the cone → hard **deadband then snap-to-detent** (e.g. 0 up to ~duty 30,
  then jumps to a plateau). Slow **ramps do NOT cure it** — a pure friction
  contact has no elastic element to creep through, so it stick-then-slips
  regardless of drive shape. And at high duty the camera **flew off the cone.**

## THE critical remaining step — the flexure stage (hard; ribbon is the crux)

The blocker is now purely mechanical: **sub-micron *smooth* motion**. Ordinary
bearings/slides can't do it — they have ~micron breakaway stiction (exactly the
stick-slip measured above). The right answer is a **flexure**, not a bearing: a
thin elastic blade / parallelogram that *bends* — no sliding surfaces → no
friction → continuous sub-µm travel, plus an elastic restoring force that makes
the response smooth, monotonic, and self-returning (also fixes "flew off").

**The camera ribbon (CSI flex) is the particularly difficult part.** It fights
the flexure on the very axis that matters:
- Its bending stiffness is comparable to a soft sub-µm flexure → an
  uncontrolled parallel spring that shifts rest position and effective stiffness.
- Flex PCB has its own creep/hysteresis/self-friction → **reintroduces
  stick-slip** through the cable — designing out the bearing friction only to
  let it back in via the ribbon.
- It pulls cross-axis as the camera translates → adds unwanted sensor tilt.

**Mitigations (easiest → most involved):**
1. Generous **service loop** oriented to bend in its floppy (out-of-plane)
   plane, routed symmetrically so it's net-neutral at the rest point.
2. Anchor the ribbon to the *moving stage* at the camera (no relative motion at
   the connector); put the flex loop further back where stiffness matters less.
3. **Match flexure stiffness UP to swamp the ribbon** — we have ~1000× excess
   travel, so afford a *stiffer* flexure that dominates the ribbon's variation,
   then **gear down** to sub-µm at the sensor. Converts the excess range into
   "make the ribbon irrelevant." Likely the cleanest path.
4. **Calibrate it out** if the ribbon disturbance is *repeatable* (needs the
   flexure to have killed stick-slip first).
5. Eliminate relative motion entirely: whole camera + short pigtail on the
   moving stage; only static upstream wiring bends.

**Early characterization:** the drift/return metric (relaxed start-vs-end shift,
already computed each run) *is* a ribbon-hysteresis meter — drive a slow ramp,
check return-to-zero repeatability with a service loop in place.

## Difficulty-ranked remaining roadmap (Peter, 2026-07-31)
1. **Flexure stage + ribbon strain-management — CRITICAL, hardest, do FIRST.**
2. Bond camera→cone rigidly (easy; unblocks proportional re-test in the interim).
3. **Real DAC** (MCP4725 12-bit → linear current driver) — easy quality upgrade;
   removes the PWM carrier entirely and gives far finer low-end resolution than
   8-bit PWM (the usable dither range is the bottom few % of drive). NB driven
   *linearly* the D882 dissipates more (active region) → heatsink / proper
   current-source stage. Park as Phase 2; does NOT fix stick-slip (mechanical).
