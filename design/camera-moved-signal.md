# The "camera moved today" signal — sub-epoch geometry boundaries

**A lightweight per-day marker, one level below `position_index`, that records a
nudge or small re-aim: same hardware generation, but the pole / plate-scale
shifted enough that frames across the boundary must NOT be co-added blindly.**

Drafted 2026-08-03 (astro-science). Design only — nothing built yet. Promoted
from an idea because a re-aim invalidates the pole + plate scale that the
sidereal-space static accumulator and every plate-solve rest on; if de-rotation
co-adds across an unrecorded move, the aliasing/misregistration bakes into the
accumulator permanently.

## The two-level geometry model

The estate already has ONE level of geometry epoch:

- **`position_index`** (`POSINDEX`, stamped per-FITS; registry in `camera.json`
  `position_registry`) = a **generation epoch**: a sensor / lens / mount *swap*.
  astrocam is index 2 (imx708 v3s); index 1 was the imx219 v2. Each index is a
  distinct calibration epoch — plate scale, pole, FOV, orientation, pedestal all
  change and must not be mixed. Increments **rarely**, on a deliberate hardware
  change, and carries a full geometry record in the registry.

What's missing is the level **below** it:

- **the sub-epoch move** = a *nudge*: the same physical camera, lens and mount,
  but the **pointing moved** — a bump, a re-aim, a mount settle. Plate scale is
  essentially unchanged (same optics), but the **pole moves in pixel coords** and
  the **occlusion map** (which sky the trees/gutter block) changes. It does not
  warrant a generation bump — it's the same generation of everything — yet
  de-rotation keyed off a stale pole will smear every star.

This has **already happened, and was handled by hand**: `astrocam/occlusion.json`
records *"camera moved ~2026-06-09, settled since… Supersedes the stale
2026-06-09 tree/eves cells (pre-move pointing)."* A re-aim silently invalidated
the occlusion tiles and the pole; someone noticed, re-marked by hand, and wrote a
prose note. This design turns that ad-hoc recovery into a **first-class recorded
event** the accumulator can key off automatically.

```
position_index   (generation)   swap sensor/lens/mount   → new registry entry
      └── move_epoch (sub-epoch) nudge/re-aim, same HW    → new pole + occlusion,
                                                            same plate scale
              └── night          one night's frames       → one pole fit
                     └── frame    one FITS                 → POSINDEX + (below) MOVEID
```

## What the signal must do (the science requirement)

The **only** hard requirement from the science side: **de-rotation and the
accumulator must key off the move boundary** — a shifted accumulator that
integrates across a move mixes two different pole positions into one cell and
destroys the sub-pixel registration the whole thrust depends on. Concretely:

1. Every frame must **self-identify its move epoch** (like `POSINDEX` does for
   generation) so an accumulator built across an archive knows where the
   geometry breaks, independent of config drift.
2. The accumulator **resets / re-solves geometry** at each boundary: a move epoch
   is the unit over which a single (pole, plate-scale, distortion) solution is
   valid. Frames within one move epoch co-add; frames across one do not (or
   co-add only after each side is independently solved onto the shared sphere).
3. The boundary is **cheap to raise** — the failure mode this fixes is *forgetting
   to record a nudge*, so recording one must be a one-liner, not a ceremony.

Everything else (how it's detected, how the number is chosen) is mechanism.

## Where the marker lives — three surfaces, distinct jobs

Mirror the `position_index` design exactly, one level down. Three surfaces, each
already present for `position_index`:

### 1. `camera.json` — the registry (authoritative, human-curated)

Add a `move_registry` beside `position_registry`, scoped **within** a
generation. A move epoch is `(position_index, move_index)`:

```jsonc
"move_index": 0,
"move_index_notes": "Sub-epoch within the current position_index. INCREMENT on any nudge / re-aim / mount settle that shifts the pole in pixel coords, even though sensor+lens+mount are unchanged (so position_index does NOT change). Each (position_index, move_index) pair is a distinct pole+occlusion solution that must NOT be co-added across. Stamped per-FITS as MOVEID. Registry below.",
"move_registry": {
  "2.0": {"from": "2026-07-29", "pole_prior_xy": null, "plate_scale_deg_px": null, "occlusion_file": "occlusion.json",     "notes": "First imx708 pointing. Geometry STALE / unsolved — the accumulator's prereq night. Established at the v3s swap."},
  "2.1": {"from": "2026-08-11", "pole_prior_xy": [1901, 1788], "plate_scale_deg_px": 0.0207, "occlusion_file": "occlusion-2.1.json", "notes": "Example: bumped during a cover clean; pole re-solved, right tree clump shifted one tile."}
}
```

Key `"<position_index>.<move_index>"` so the pair is unambiguous and sorts. Each
entry carries **the geometry that changed** — `pole_prior_xy`, `plate_scale`
(usually inherited unchanged), and the `occlusion_file` in force for that
pointing (occlusion is exactly what a re-aim breaks). `from` is the first night
(UTC night label) of the epoch; the next entry's `from` closes it.

This **supersedes** loose top-level `pole_prior_xy` / `occlusion_file`: those
become the *default / current* view (= the highest move epoch), with the registry
holding the history. Backfill across an old boundary reads the registry entry for
the night's epoch, never the current top-level values.

### 2. per-FITS header — `MOVEID` (self-identifying, like POSINDEX)

Stamp `MOVEID = move_index` into every FITS next to `POSINDEX`, via a new
`StreamingConfig.move_index` field (identical plumbing to `position_index` —
see `astro/capture/streaming.py:194`). Then any tool reading an archived frame
knows both its generation AND its sub-epoch **from the frame alone**, which is
the property that makes a whole-archive accumulator safe against config drift.
`None` = don't write the header (cameras that don't track sub-epochs, e.g.
eclipticam, stay unchanged — same rule as `position_index`).

The pair `(POSINDEX, MOVEID)` on a frame is the complete geometry key.

### 3. astro-storage inventory — the event log (the boundary as data)

The **event** ("moved on night N") is recorded in astro-storage's per-camera
inventory, so the boundary is queryable as *data* without parsing `camera.json`
history. That is astro-storage's mechanics to own (this is the science/storage
seam): astro-science needs the boundary to *exist and be keyable*; astro-storage
decides how the inventory row is written. The camera.json registry is the
authoritative source; the inventory is the indexed, per-night view of it.

## Raising a move — the one-liner

The failure mode is forgetting, so make it trivial. A house-style helper (astro
`bin/`, to build):

```
astro-moved astrocam            # today's night, current pointing
astro-moved astrocam 2026-08-11 # a specific night, backfilling a known move
```

It:
1. increments `move_index` in `camera.json` (and appends a `move_registry` entry
   stubbed from the current geometry, `from` = the given night, geometry fields
   `null` = "re-solve me");
2. writes the event into the astro-storage inventory for that night;
3. reminds the operator that the **pole + occlusion for the new epoch are now
   STALE** and must be re-solved before the accumulator trusts frames ≥ that
   night — the same trail-arc fit that the v3s swap already needs.

The daemon reads `move_index` from config (like `position_index`) and stamps it;
no restart choreography needed beyond the config edit the helper makes.

## Detection — assist, don't gate

The marker is **operator-asserted** (a human knows they bumped the camera); the
one-liner is the interface. But detection can *prompt*: nightly processing already
fits a pole per night. If a night's fitted pole jumps by ≫ its fit uncertainty
from the previous night's within the same move epoch, **flag it** — "pole moved
N px vs last night; run `astro-moved` if this was a re-aim." This catches the
silent nudge (the 2026-06-09 case) without ever *auto*-incrementing (a cloud
artefact or bad fit must not silently fork the geometry history). Assist, never
gate.

## What this is NOT

- **Not focus breathing.** VCM breathing is a *within-epoch* continuous dither
  (radial ε·R), modelled per-frame via `LENSPREP`; it does not move the pole and
  needs no boundary. See STATE's dither section.
- **Not a new generation.** If the sensor / lens / mount *hardware* changes, that
  is a `position_index` bump (new `position_registry` entry) and `move_index`
  resets to 0 under it. Move epochs are strictly nested inside generations.
- **Not automatic.** Detection prompts; only the operator (or a deliberate
  backfill) increments. The history of geometry must be trustworthy.

## Open questions

- **Reset convention:** does `move_index` reset to 0 on a `position_index` bump
  (nested, chosen above) or run monotonically forever (flat)? Nested keeps the
  key `"pos.move"` self-describing and matches "sub-epoch"; flat is simpler to
  stamp. Leaning nested.
- **eclipticam:** it doesn't track `position_index` today. If its pointing is
  effectively fixed, it may never need a move epoch; if it gets re-aimed, it
  should adopt the same two-level scheme rather than a bespoke one.
- **Retroactive boundaries:** the 2026-06-09 astrocam move predates this and sits
  under the *imx219* generation (now archived as index 1). Worth a registry
  backfill only if that era's frames ever feed an accumulator; otherwise leave
  the prose note in occlusion.json as the record.

## Relationship to the accumulator

The static accumulator (**the map** — see accumulation-bucket-refinement.md)
integrates every frame into a fixed
sphere frame via de-rotation. Its unit of geometric validity is exactly **one
move epoch**: one (pole, plate-scale, distortion) solution spans all frames with
the same `(POSINDEX, MOVEID)`. The accumulator's outer loop is therefore *per
move epoch* — solve geometry once, remap-then-shift all that epoch's frames, and
co-add onto the shared sphere; a boundary starts a fresh geometry solve whose
output lands on the *same* sphere (so a re-aim doesn't fork the science product,
only the intermediate solution). This design gives that loop its boundary
signal.
