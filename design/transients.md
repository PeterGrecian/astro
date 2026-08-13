# Transients — meteors and satellites as a deliverable, not as noise

**The archive currently THROWS AWAY every meteor it records. The accumulator's
outlier rejection classes them with planes and cosmic rays — "non-sidereal ⇒
reject" — which is right for the stack and wrong for the science. The same test
that rejects a streak from the sum can emit it to a transients table. Reject
from the co-add, keep for the catalogue.**

Drafted 2026-08-11/12 (astro-science), prompted by Peter spotting meteors by eye
while scrubbing the 2026-08-10 sweeps: *"lets start some science about it."*
Tool exists (`bin/find-transients`, `astro 6b168db`); the classifier is proven on
a known event but **not yet usable on a full night** — see "Status" for exactly
what fails.

## Why this is a gap and not an oversight

Two designs already on record between them guarantee a meteor is discarded:

- `accumulator-outlier-rejection.md` rejects non-sidereal streaks from the sum,
  naming meteors explicitly alongside planes and cosmic rays. Correct — a meteor
  must not co-add. But rejection is the *end* of its life; nothing catches it.
- `catalogue-deliverable.md` mints catalogue entries on **persistence**
  ("persistence = identity", `zenith-quests.md`), with confidence growing as a
  source is re-detected night after night.

A meteor is **sub-second and never repeats**. It fails the catalogue's entry
condition by definition and is deleted by the accumulator's robustness layer. It
falls through every crack in the science layer. Yet an all-night, all-sky,
multi-camera archive is *exactly* the instrument that records them well — and
"what does a year-scale urban dataset yield?" is this strand's whole question.

## The classification problem

### What does NOT work

**Brightness profile alone.** A meteor ablates: dim → bright → dim, tapering to
points at both ends. A satellite reflects sunlight steadily: flat, with abrupt
ends. Sound physics, but two things defeat it in practice:

1. **Saturation.** In the delivered JPEGs the streak core clips at 255 along its
   entire length (measured: 41 of 91 pixels pinned, every one of 12 slices
   reading 255). There is no profile left to measure. It is recoverable only by
   integrating the *unsaturated wings* — perpendicular flux in slices, excluding
   the core. That works (see below) but is fiddly and needs the wings to exist.
2. **Stacking destroys it.** See the next section — this is the load-bearing
   trap.

**A bare length cut.** On a fixed camera stars TRAIL, and near the field edge a
trail is long. A throwaway scan of eclipticam with only a length+elongation cut
flagged **42 frames of pure star trails**. Length is necessary, never sufficient.

### THE RULE: sweep frames cannot classify — always work on SUBS

**A sweep frame is a 10-minute stack, and stacking destroys both pieces of
evidence that matter.** This was learned the hard way, twice in one session:

- It **smears the brightness profile flat**, so a meteor reads as a steady
  satellite trail. On 2026-08-10 the 00:05:14 streak was called "not a meteor —
  continuous and untapered, a satellite" from the stacked view. The individual
  sub showed a clean tapered meteor. The stack had averaged 13 subs together.
- It **merges 10 minutes into one image**, so two streaks appearing "together"
  may be simultaneous or 10 minutes apart. A pair in one sweep frame carries no
  timing information at all — and timing is the whole question when asking
  whether meteors cluster.

So: **`find-transients` reads subs and never sweep output.** Sweeps are for
human spotting; subs are for measurement.

### The primary test is GEOMETRIC (Peter, 2026-08-11)

> *"I think we might find satellites too — they should start and/or end off
> screen."*

| | Satellite | Meteor |
|---|---|---|
| **Ends** | crosses the field ⇒ ≥1 end touches the border | **ignites and burns out inside** ⇒ both ends interior |
| **Persistence** | steps across consecutive subs | present in **exactly one** sub |
| **Profile** | flat | dim → bright → dim |

The end test is the good one precisely because it is **geometric, not
photometric**: it survives the saturated cores that defeat profile analysis, and
it needs no calibration. It is the primary discriminator; everything else scores
confidence.

### A third class: CONTRAILS (Peter, 2026-08-12 — *"the meteor looks like a contrail"*)

The satellite/meteor dichotomy above is **incomplete**. A candidate in the EOS
2026-08-11 sweep (frame 312/339) looked meteor-like in a single frame and was a
**contrail**. Evidence from the neighbouring sweep frames:

| frame | streak |
|---|---|
| 305, 311 | **absent** — clean sky |
| 312, 320 | **present**, sharp-edged |
| 330 | present but visibly **broadened and diffused** |

It crosses the whole frame (both ends off-screen), has soft diffuse edges rather
than a thin hard filament, and shares the lit-cloud quality of the skyglow-lit
cloud around it. These are the night's last frames (sky mean 84 → 123 across
them), so it is lit from below by **dawn twilight**.

A meteor lasts under a second and appears in exactly one sub. This **persists
over many minutes and spreads**.

**Why it matters even though the current classifier "gets away with it":** a
contrail scores `ends_touching=2` and `persists >> 1`, so it lands in the
**satellite** bucket — correctly *rejected* as non-meteor, but wrongly labelled.
Aircraft and their trails are already named in `accumulator-outlier-rejection.md`
as things that must not co-add, so the estate cares about them independently.

**Proposed discriminator — WIDTH GROWTH OVER TIME**, which cleanly separates the
two persistent classes:

| | Satellite | Contrail |
|---|---|---|
| width | thin, **constant** | starts thin, **broadens and softens** |
| motion | moves position frame to frame | drifts slowly with wind, near-static |
| within a sub | streaks (traverses during the exposure) | static feature |

Measure perpendicular FWHM per sub and fit `d(width)/dt`; a positive trend is a
contrail.

**Secondary consequence — it is a cloud-verdict concern, not only a classifier
one.** A contrail is a *lit linear cloud*: it lifts the frame mean and could pull
an otherwise-clear night toward "cloudy". Related to the pedestal / `scs`
double-duty trap.

**Note on method:** this one was disproved by the **neighbouring sweep frames**,
without needing the subs — because persistence over *minutes* is exactly what a
stack shows well. The earlier rule ("sweep frames cannot classify") is about
sub-second structure: a stack destroys the ablation profile and sub-second
timing, but it is the right tool for *is this thing still here ten minutes
later?*

### Illumination as a hard constraint (Peter, 2026-08-11)

> *"its in the middle of the night — the satellite won't be illuminated."*

A satellite is visible only while *it* is sunlit and the ground is dark. Below a
solar altitude of about −18° the Earth's shadow reaches past most of LEO:

| Solar altitude | Shadow height |
|---|---|
| −12° | ~142 km |
| −15° | ~225 km |
| −18° | ~328 km |
| **−23°** | **~560 km** |

The 2026-08-10 events sat at **−23.2°**, putting the shadow at ~560 km — above
Starlink (~550 km) and well above the ISS (~420 km). A bright fast streak at
local midnight is therefore very unlikely to be a sunlit satellite. Implemented
as `solar_altitude()` / `shadow_height_km()` in the tool, recorded per detection.
Caveat: high-altitude and geostationary objects can stay lit, and Starlink trains
catch light unusually late, so this argues strongly but does not prove.

## Do they come in bunches?

Asked directly (Peter, 2026-08-11) after screengrabbing a pair from eclipticam.
Three different answers by timescale — the distinction matters:

- **Across a season: yes.** That is what a shower *is* — Earth ploughing through
  a debris stream. The Perseids (109P/Swift-Tuttle) peak Aug 12–13, so 2026-08-10
  is the rising flank.
- **Across a night: yes, strongly.** Rates climb toward dawn as the observer
  rotates onto Earth's leading edge; the radiant rises and the geometric sweep
  increases. Pre-dawn rates are typically several times the evening rate.
- **Within minutes: no.** Arrivals are a **Poisson process** — independent and
  memoryless. Random arrivals look far clumpier than intuition allows, which is
  why apparent "bunches" are usually chance. Real short-timescale clustering from
  a fresh dust filament is claimed occasionally and remains contested.

**The testable form.** For N events in a night of length T, the chance that at
least one pair falls within Δt is ≈ `1 − exp(−[N(N−1)/2]·Δt/T)`:

| N/night | pair within 1 min | within 5 min | within 15 min |
|---|---|---|---|
| 2 | 0.00 | 0.01 | 0.04 |
| 4 | 0.02 | 0.07 | 0.20 |
| 6 | 0.04 | 0.17 | 0.43 |
| 10 | 0.11 | 0.43 | 0.82 |

So a pair **in the same 30 s sub** is genuinely notable (P≈0.02); a pair merely
**in the same 10-minute sweep window** is unremarkable (P≈0.2, one night in
five). Since a sweep frame cannot distinguish these, *the eyeball impression of
"a pair" is not evidence of clustering* — only sub timestamps are.

**Parallelism cuts both ways.** Near-parallel streaks are the common-radiant
shower signature (shower meteors travel parallel paths). They are also exactly
what a **Starlink train** looks like. The illumination test above is what
separates them.

## The tool

`bin/find-transients` — runs per camera per night over subs.

```
find-transients --camera canon --night 2026-08-10
find-transients --camera astrocam --nights 2026-08-04..2026-08-12 --save-cutouts
```

Writes `<night_dir>/transients.json` (one record per candidate: t_utc, verdict,
confidence, geometry, ends_touching, persists, sun_alt_deg, reasons, profile) and
optionally a PNG cutout per candidate. Reads FITS (full dynamic range, unclipped
core) or JPEG. Parallel via `--jobs`.

**Runs on muppet**, where the frames are — [[compute-follows-the-data]]. The same
night scanned from pip over wifi read at 4.9 MB/s against ~34 MB/s local.

## Status — works on one event, NOT yet on a night

**Acceptance test PASSES** on the hand-confirmed meteor. Canon 2026-08-11
00:05:14 yields `len=237px elong=138 ang=85.8 ends=0`, the only long streak in a
3010×2007 field — matching the by-hand measurement, with the end test firing
correctly.

**But a full-night run is dominated by false positives.** On 2026-08-08 it
reported 10 "meteors" from **8 subs** — more than one per frame, which is not a
meteor rate. The cutouts settled it instantly: **foliage**. Leaves and branches
silhouetted against the sky, whose sharp high-contrast edges trip the threshold
and whose stems are elongated enough to pass the shape test.

Every *number* looked right — `conf=1.00`, `ends=0`, single sub, tapered
profile. Only the picture was wrong. **`--save-cutouts` earned its place on
first use**; a purely numeric pipeline would have published nonsense.

Tells that should have been caught before looking:

- **four "meteors" in a single sub** (22:29:40) — physically implausible;
- the real meteor was **237 px**, the false positives **48–74 px**, clustered
  just above the 40 px floor;
- angles clumped at **153–160°** — a field direction, whereas real meteors
  arrive at random angles.

**Root cause: the 40 px floor was tuned on the single meteor then known.**
Textbook overfitting to one example.

### Required fixes, in order

1. **Median-subtract across the night before detecting.** Foliage is static and
   star trails are near-static, so a per-pixel median over the night's subs kills
   both false-positive classes at once. This is the real fix; everything else is
   a refinement.
2. **Raise the length floor** to ~150 px (real 237, false 48–74) — but only as a
   stopgap, since it also loses the unrecovered 23:51:42 candidate.
3. **Occlusion mask.** Already listed in STATE as a pending canon refinement
   ("foreground foliage in frame"); this makes it *blocking* rather than
   cosmetic.
4. **Tune the confidence thresholds** (currently 0.6 meteor / 0.35 satellite —
   guesses) against eyeballed cutouts.

### Known unresolved

- The **23:51:42** canon candidate (spotted and hand-measured as ~54 px) is not
  recovered by the tool — below the length floor or too faint. Unresolved, not
  disproven.
- The **eclipticam pair** Peter screengrabbed is not yet located in the subs; the
  scan that was run searched the wrong tree and returned star trails.

## What the data can and cannot answer yet

**Canon cannot answer "meteors all week"** — it has frames on only **08-08 and
08-10**; 08-10 was its first dense night. **astrocam** has run continuously all
month and is the right instrument for a rate-vs-night curve across the Perseid
build-up.

**Multi-camera is the prize.** On 2026-08-10 canon, astrocam and eclipticam all
recorded meteors. Two cameras seeing the *same* event from different positions
gives **altitude and speed by triangulation** — real meteor science rather than
counting. Requires the transients tables to carry precise t_utc (they do) and
per-camera pointing (canon's pole is still UNSOLVED, so this waits on the plate
solve).

## Proposed deliverable shape

Following `catalogue-deliverable.md`'s pattern, once detection is trustworthy:

- `transients.json` per night (exists) → aggregate `transients-index.json`;
- a **nightly count** on the night page, and a **rate-vs-night chart** across the
  season — the Perseid curve as measured from an urban back garden;
- confidence tiers as for the catalogue (candidate → probable → confirmed), with
  the key difference that confidence can never come from persistence; it comes
  from geometry, illumination and multi-camera coincidence;
- meteors kept OUT of the accumulator regardless — this table is a *parallel*
  output of the same rejection pass, never an input to the sum.

### Cross-camera, not per-camera (Peter, 2026-08-13)

The shape above still hangs each count off a *camera's* night page, because
that is how every deliverable is currently built: S3 is
`<camera>/nights/<night>/`, the site routes `/astro/<camera>/night/<night>`,
and the calendar is per camera. **Transients cut across that grain.** Peter:
*"we could do them not per camera — I'm thinking we need more joined up
unified deliverables. maybe a transients section which has crops of meteors
with camera and time info."*

Why the cross-camera cut is the right one *for this deliverable specifically*:

- **A meteor is an event in the sky, not an event in a camera.** The camera is
  metadata about how it was observed. Filing it under one camera is the same
  category error as filing a star under the lens that saw it.
- **The prize needs it.** Two cameras on one event give altitude and speed by
  triangulation; three all recorded meteors on 2026-08-10. Coincidence is only
  visible if the events sit in ONE list ordered by time — per-camera pages
  structurally hide the thing we most want to find.
- **Confidence comes from coincidence.** This doc already says confidence can
  never come from persistence; multi-camera agreement is the substitute, and
  it is only computable across cameras.
- **The rate curve is an estate result, not a camera result.** "What does a
  year-scale urban dataset yield" is answered by the whole instrument.

Proposed form — a **crop-led** section, evidence first:

- **`/astro/transients`** (Peter, 2026-08-13 — the confirmed path). It sits as a
  SIBLING of the camera pages, not under one: the route dispatch matches
  cameras by explicit alternation
  (`/astro/(astrocam|eclipticam|canon)/night/...`), so `transients` cannot
  collide, and `/astro/storage` + `/astro/disks` are the existing precedent for
  a cross-cutting astro page that belongs to no single camera.
  A time-ordered gallery for a night (and across nights),
  each entry a **cutout PNG** of the streak with `camera`, `UTC time`,
  `night`, length/elongation, and class. The crop IS the deliverable: it is
  what a human uses to judge, and this session proved three times that only
  the picture settles it.
- key layout: `transients/<night>/<epoch_ms>-<camera>.png` + a single
  `transients/<night>/index.json`, aggregated to `transients/index.json`.
  Note `<epoch_ms>` is already the estate-wide frame naming convention, so a
  crop's identity is derivable from the frame it came from.
- **Coincidence badge** when two cameras have events within a few seconds —
  the cross-camera payoff made visible.
- per-camera night pages keep a *link* ("3 transients this night →"), so the
  camera view still works; it just stops being the only axis.

Build order: the per-night `transients.json` (already written locally by
`find-transients`) is the raw material; upload it, then the crops, then the
aggregate index, then the page. **All of it gated on detection being
trustworthy** — see Status; as of 2026-08-13 recall against Peter's 38 probes
is 1/38, so a published count would be a wrong number on the public face.

## Provenance

Peter spotted the meteors by eye; both of his physical arguments (mid-night
illumination, visible taper) were correct and both overturned an earlier wrong
call made from the stacked view. The end-of-streak discriminator is his. The
lesson recorded here — **stacked views cannot classify transients, and a
confident number is not a verified detection** — cost two wrong conclusions in
one session and is the reason this doc leads with it.
