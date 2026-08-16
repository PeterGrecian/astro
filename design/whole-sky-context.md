# Whole-sky astronomy — the field around this project

Written 2026-08-16, prompted by Peter: *"I should know more about the whole-sky
astronomy world."*

This estate keeps independently arriving at ideas that whole-sky astronomy has
already named, formalised and tooled. That is not a criticism of the derivations
— several were reached from first principles and one of them (the integer-shift
ring quantisation) went somewhere the standard tools deliberately do not. But
**not knowing the vocabulary costs real time**: you re-derive the motivation,
you cannot search the literature for the failure modes, and you write code that
a mature library already contains.

This document is the map of that field: what it is called, who works in it, what
we have converged on, where we genuinely diverge, and which standards are worth
adopting. It is orientation, not a bibliography.

---

## 1. Pixelisation — how to tile a sphere

**The problem:** a sphere cannot be tiled by a regular grid. Any scheme trades
off between equal-area cells, iso-latitude rows, hierarchical subdivision, and
cheap neighbour queries.

| Scheme | Property | Where used |
|---|---|---|
| **HEALPix** | equal-area, iso-latitude, hierarchical, 12·N_side² cells | Planck, WMAP, LSST, Gaia sky maps — the dominant one |
| **GLESP** | equal-area, exact quadrature for spherical harmonics | CMB analysis |
| **Igloo** | equal-area rings | historical |
| **Quad-cube** (QSC) | 6 projected cube faces | COBE — now historical |

HEALPix (Górski et al. 2005) is the one to know. The name is an acronym:
**H**ierarchical **E**qual **A**rea iso**L**atitude **Pix**elisation.

**What we converged on independently:** `accumulation-bucket-refinement.md`
derives equal-area rings with θ-count ∝ sin r, quantised to 24 × 2ⁿ, and the doc
itself calls this *"the HEALPix idea in its simplest useful form."* The
motivation — that unequal cell areas make depth a function of radius and corrupt
the comparison the map exists to make — is exactly HEALPix's motivation.

**Where we deliberately diverge — and why HEALPix is NOT a drop-in:** this
accumulator has a fifth requirement no whole-sky scheme optimises for — that a
**sidereal rotation be an exact integer index shift**. HEALPix is equal-area and
iso-latitude but its rings are not built so that a rotation lands on cell
boundaries. The 24 × 2ⁿ quantisation was invented here precisely to buy that
property (24 divides 360).

**But that requirement was itself withdrawn (2026-08-16)** — see
`accumulation-bucket-refinement.md`. Two reasons: 24 divides 360 for the *solar*
day and the sky turns at the *sidereal* rate (15.041069°/h, no nice fraction of
it); and we are targeting sub-pixel, so even correct-rate rounding (~0.24 px at
the rim) exceeds the measured 0.14 px single-frame precision. Drizzle handles
fractional placement natively.

**So the divergence has closed, and the question is now open again.** With the
integer shift gone, the reason not to use HEALPix has gone with it. Worth
revisiting: pure equal-area rings at the 1.81e7 floor is what the design now
prefers, and that is very close to what HEALPix would give — with the advantage
of a mature implementation, neighbour queries and interoperability.

### Projections (and the one that started this)

Peter, 2026-08-16: *"an orthogonal projection onto the sphere at the pole results
in unequal area samples."* Correct, and it is a projection problem, not a
rotation problem — quaternions cannot help with it (see §5).

The projections have standard three-letter **FITS WCS codes**, so they are
things you *declare in a header*, not custom schemes you document:

| Code | Name | Radial law | Property |
|---|---|---|---|
| `TAN` | gnomonic / tangent plane | tan θ | great circles → straight lines; diverges at 90° |
| `SIN` | orthographic | sin θ | **unequal area** — Jacobian → 0 at θ=90° |
| `ZEA` | zenithal equal-area (Lambert) | 2 sin(θ/2) | **exactly area-preserving everywhere** |
| `AIT` | Hammer-Aitoff | — | all-sky, equal-area, elliptical |
| `CAR` | plate carrée | — | trivial, badly distorted at poles |

`ZEA` is the standard answer to the question that prompted this document. The
substitution `sin θ → 2 sin(θ/2)` is one line and costs nothing structurally.

Note `TAN` is why `accumulation-bucket-refinement.md` rejects a single tangent
plane for eclipticam's 102° field: *"gnomonic projection diverges long before
that."* That is the standard, named reason.

---

## 2. Drift-scan and transit astronomy — our actual tribe

A fixed camera letting the sky drift past is **drift-scan** or **transit**
astronomy. It is a real subfield, currently unfashionable for professional
imaging but with serious precedent.

- **SDSS** — the original imaging camera ran in **TDI drift-scan**, producing an
  entire sky survey that way (Gunn et al. 1998). This is *remap-then-shift
  implemented in silicon*: charge is clocked across the CCD at the drift rate.
  The estate's TDI framing is the same idea in software.
- **Pan-STARRS** — large-scale survey coaddition practice.
- **Evryscope** — a fixed multi-camera all-sky array doing long-baseline
  accumulation. The closest professional analogue to this estate's design.
- **ASAS / ASAS-SN, SuperWASP, HATNet, Fly's Eye** — wide-field fixed or
  semi-fixed survey cameras, variability-focused.
- **GMN (Global Meteor Network)** — all-sky meteor cameras with published
  triangulation methodology. **Directly relevant to `transients.md`**, including
  the multi-camera altitude-and-speed-by-triangulation goal already recorded in
  STATE.

**Worth knowing:** transit astronomy's characteristic problem is that a source's
PSF is a *streak*, and the literature on trailed-source photometry and
astrometry is the right place to look for the along-track/cross-track asymmetry
this estate derived independently (STATE: *"along-track resolution is
compromised; cross-track keeps full PSF resolution"*).

---

## 3. Resampling and coaddition

- **Drizzle** (Fruchter & Hook 2002) — variable-pixel linear reconstruction.
  Already adopted by name across `accumulation-bucket-refinement.md`,
  `what-accumulation-buys.md` and STATE. Built for undersampled dithered data,
  which is exactly this archive.
- **ePSF fitting** (Anderson & King 2000) — effective PSF from dithered
  undersampled data. Already named in STATE and `retrospective-reprocessing.md`.
- **Optimal coaddition / IMCOM** — the formal treatment of combining
  undersampled dithered images without aliasing. **The most relevant unread
  work**: it is the same problem the accumulator solves, treated rigorously,
  with known results about when band-limiting assumptions hold. Directly bears
  on the open question at `accumulation-bucket-refinement.md:412` — whether the
  data is band-limited enough for a Fourier-phase approach.
- **Kaiser–Squires** and the weak-lensing stacking literature — adjacent, for
  optimal-weight coaddition.

---

## 4. Astrometry, catalogues, time

**Astrometry.** The **FITS WCS** standard (Greisen & Calabretta) is the
interchange format for "what direction is this pixel." **SIP** (Simple Imaging
Polynomial) carries the distortion — both already load-bearing here
(`hierarchical-vector-field.md`, `standing-plate-solve.md`).
**astrometry.net** does blind quad-matching solves; already in use via
`solve-field`, and the reason the roll solve sidesteps needing a readable
catalogue.

**Catalogues.**
- **Gaia** (DR3) — the reference frame everything now ties to; µas astrometry.
- **Tycho-2** — bright stars; the index files are on puppy, kd-tree packed for
  `solve-field` and not directly readable.
- **UCAC, 2MASS** — older/infrared complements.
- **AAVSO** — the amateur variable-star network. **This is the community that
  would care about the Algol and Polaris-Cepheid quests in
  `zenith-quests.md`**, and it accepts observation submissions. The most
  plausible route from this archive to an outside audience.

**Time — worth acting on early.** The standard for anything periodic is
**BJD_TDB** (Barycentric Julian Date, Barycentric Dynamical Time). Light travel
time across Earth's orbit is **±8 minutes**; for a year-scale variability study
that is a large systematic, and Polaris's 3.97 d Cepheid pulsation is exactly
the kind of target it corrupts. Retrofitting timestamps across an archive is
painful, so adding BJD_TDB to frame headers is cheap now and expensive later.

---

## 5. Quaternions — what they are and are not for

Peter raised these 2026-08-16. They belong in a specific layer:

```
image plane --projection--> sphere --rotation--> sphere
            (lens, SIP,              (rigid, isometric:
             area distortion)         quaternion's job)
```

**What they solve here:**
- **No singularity at the pole.** A pole-pointing camera is the worst case for
  angle parameterisation (RA degenerates as r → 0, and Polaris sits in the dead
  disc). Quaternions have no gimbal lock anywhere.
- **Rotations compose and average correctly.** Angles are not a vector space.
  Two logged bugs share this root cause: the circular-mean error (*"the
  arithmetic mean errs by 11.58° from mod-180 wrap alone"*) and the transients
  angle-clustering bug (*"0.4° and 179.7° are the same horizontal direction"*).
  `scipy.spatial.transform.Rotation.mean()` is the correct rotation average.
- **Epoch composition.** `camera-moved-signal.md` requires every `(POSINDEX,
  MOVEID)` epoch to land on *the same sphere*. That is a fixed rotation per
  epoch; composing and refining them is quaternion arithmetic. This is what
  makes an all-time sweep across the imx219→imx708 boundary well-posed.
- **The sidereal rotation is a one-parameter quaternion family**:
  `q(t) = [cos(ωt/2), sin(ωt/2)·n̂]`, with `n̂` the pole *direction* — a unit
  3-vector, not a pixel coordinate, so it is shared across cameras and epochs.

**What they do NOT solve:** anything non-rigid — the projection, radial
distortion, the SIP field, refraction, and **cell-area equalisation**. A
quaternion preserves area by construction, so it cannot fix an area-distorting
projection; composing one with `SIN` gives a rotated `SIN`.

**The clean split** is quaternion for the rotation, vector field for the optics.
That sharpens the estate's own deepest lever (STATE): *"A field error is fixed in
image space; a timing/pole error is fixed in sky phase. Opposite signatures, so
they separate."* Quaternions put the sky-phase half in its natural algebra.

`scipy.spatial.transform.Rotation` implements all of it; no new dependency.

---

## 6. What is installed, and what is worth adding

Checked on pip, 2026-08-16:

| Package | Status | Verdict |
|---|---|---|
| `astropy` 7.0.1 | present | WCS, FITS, time scales (incl. BJD_TDB) |
| `numpy` 2.2.4, `scipy` 1.15.3 | present | `scipy.spatial.transform.Rotation` covers quaternions |
| `healpy` | **missing** | only if we adopt HEALPix proper |
| `astropy_healpix` | **missing** | **worth adding as a CROSS-CHECK** — validate our ring areas against a reference implementation, without adopting the scheme |
| `drizzle` (STScI) | **missing** | **worth adding** for the drizzle prototype rather than writing it |
| `reproject` | **missing** | useful for WCS-to-WCS resampling comparisons |

---

## 7. Recommendations

**Adopt:**
1. **Emit standard-WCS FITS products** — even if the internal accumulator stays
   custom, declaring `ZEA` (or whatever the ring scheme maps to) makes the
   output readable by every tool in the field. The difference between a private
   format and one anyone can use.
2. **BJD_TDB in frame headers**, before the archive grows further.
3. **`drizzle` and `astropy_healpix`** as dependencies — one to use, one to
   check against.

**Revisit:**
4. **Whether HEALPix should now replace the custom ring scheme**, since the
   integer-shift requirement that justified diverging has been withdrawn.

**Read:**
5. **IMCOM / optimal coaddition** — bears directly on the open band-limiting
   question, and on whether the Fourier-phase alternative to drizzle is sound.

**Engage:**
6. **AAVSO** — the existing variable-star quests have a natural audience, and
   an outside audience is a forcing function for calibration rigour.

---

## Related

- `accumulation-bucket-refinement.md` — the ring scheme, projections per camera,
  and the withdrawn integer shift.
- `hierarchical-vector-field.md` — the SIP field; the camera→sphere map.
- `camera-moved-signal.md` — epochs, and why they must share one sphere.
- `transients.md` — meteors; GMN is the professional counterpart.
- `zenith-quests.md` — the variable-star targets AAVSO would care about.
- `retrospective-reprocessing.md` — why standards adoption pays off over time.
