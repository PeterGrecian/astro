# The catalogue as a growing deliverable — cadence tiers, confidence, nightly discovery

**The local star catalogue is not just an internal table — it is THE public
deliverable of the science layer. It grows nightly (star #0 is Polaris), each
entry carries a confidence value, and it is fed by accumulators at nested
cadences (nightly / weekly / monthly / all-time). "N new stars tonight" is the
headline the whole rig earns.**

Drafted 2026-08-03 (astro-science), from Peter's deliverables framing. Builds on
the local-catalogue spec (`zenith-quests.md` §"our own catalogue"), the three-
cadence pipeline (`drift-scan-cadences.md`), and the deliverables surface
(`meta-conventions.md`, `/astro` pages). Design only.

## Cadence-tiered accumulation — daily / weekly / monthly / all-time

The pipeline already accumulates at nested internal rates (capture s → derot-
stack ~100× → global-solve nightly, `drift-scan-cadences.md`). The **deliverable**
tiers sit above that: published deep stacks + catalogue snapshots at human
cadences, each deeper than the last.

| Tier | Integration | What it delivers | Cadence |
|---|---|---|---|
| **Nightly** | one night | tonight's stack, tonight's detections, **new stars found tonight**, light-curve points | every morning |
| **Weekly** | ~7 nights co-added | deeper stack (fainter floor), confidence promotions, denser field | weekly timer |
| **Monthly** | ~30 nights | the deep field; the moon-net's monthly baseline; seasonal light curves | monthly |
| **All-time** | every clear night ever | the definitive accumulator + the full catalogue (the forever-growing spine) | continuous |

The tiers are **the same accumulator read at different depths**, not separate
pipelines — each deeper tier lowers the detection floor, so a source marginal
nightly becomes solid weekly, solid-weekly becomes catalogue-grade monthly. This
is the natural home for the "position saturates, structure doesn't" ladder
(`what-accumulation-buys.md`): deeper tiers are where faint detection, photometric
depth, and PSF-residual structure actually accrue. Storage stays bounded — deep
stacks are ~one frame each; the catalogue is KB/source; raw pixels freed on a
rolling window (`drift-scan-cadences.md` retention).

## The catalogue — #0 is Polaris, and it grows every night

The local catalogue (`zenith-quests.md`) is the permanent spine: mint an ID when
a detection persists (persistence = identity). As a **deliverable** it gets:

- **A canonical numbering with an anchor: star #0 = Polaris.** Not `SC-000001` as
  an opaque serial but a numbered catalogue with a meaningful zero — Polaris, the
  pole star, the brightest anchor, static on its pixels forever (STATE), the seed
  of the whole vector field. Everything else is numbered as it's discovered.
  (Whether #0 is literally Polaris or Polaris is `SC-0000` is cosmetic; the point
  is the catalogue has a *named anchor* the public recognises, and the field's
  geometric origin doubles as the catalogue's origin.)
- **A discovery order = a timeline.** Because IDs are minted in the order sources
  cross the persistence threshold, the catalogue *is* a discovery log: #0 Polaris
  (night 0), then the bright stars (first nights), working down the magnitude
  ladder as depth accrues. The ID number encodes roughly when — and how deep — a
  star entered the record.
- **Nightly new-star count as the headline.** "Tonight: 47 new stars, 3 promoted
  to confirmed, catalogue now 12,431." That single line is the rig's daily
  earned result — the see/identify quest made into a *running scoreboard* rather
  than a one-off plot (`zenith-quests.md` already frames the running tally as the
  live completeness curve; this publishes it).

## Confidence — a first-class field, not a binary gate

Today the catalogue is binary: persists ⇒ mint. That's too crude for a
deliverable and for honest science. Every entry (and every nightly detection)
carries a **confidence value** that *grows with evidence* — the deliverable twin
of the outlier-rejection principle (`accumulator-outlier-rejection.md`) and the
completeness ceiling (`zenith-quests.md`).

What drives confidence up:
- **Persistence** — number of frames / nights the source re-appears where the
  moving field predicts (the core identity evidence; a one-night blip is low
  confidence, a source seen 40 nights is high).
- **Field agreement** — how tightly its field-predicted (x,y) tracks sidereal
  drift across *different* anchoring configurations (a real star agrees under many
  configs; noise doesn't — `zenith-quests.md`).
- **Depth of detection** — SNR in the tier where it's seen (nightly-marginal =
  low; monthly-solid = high).
- **Catalogue cross-match** — a Gaia/Tycho match is a confidence *boost* (an
  independent survey agrees) but NOT a gate — an unmatched-but-persistent source
  can still reach high confidence on our own evidence (the "see vs identify" gap
  stays real).
- **Brightness-ceiling consistency** — its measured flux respecting the local
  completeness ceiling M(region) (`zenith-quests.md`): a flux above M where the
  catalogue is complete *lowers* confidence (should have matched → suspect).

Confidence tiers make the deliverable honest and drive promotion across cadence
tiers: `candidate` (1–few nights, low) → `probable` (persists, field-consistent)
→ `confirmed` (deep, many nights, tracks perfectly) → optionally `catalogued`
(Gaia cross-walk). A nightly new detection enters as `candidate`; weekly/monthly
depth *promotes* it. Confidence is per-source AND time-stamped (it was 0.4 last
week, 0.8 now) so the public catalogue shows sources *earning* their place.

Classification confidence is the same machinery (`zenith-quests.md`): fixed
position ⇒ **star**; smooth motion ⇒ **wanderer** (planet/asteroid/satellite) with
a confidence on the motion fit; one-off ⇒ **false detection**, rejected. So the
catalogue emits three tables (stars / wanderers / rejects) each with per-row
confidence.

## The deliverable surface (how it reaches /astro)

Mirrors the existing schema-as-API convention (`meta-conventions.md`):

- **`catalogue.json`** (all-time, the spine): `[{id, ra_dec, mean_mag, class,
  confidence, first_seen, n_nights, gaia_id|null, light_curve_ref}, ...]`. #0 =
  Polaris. Grows monotonically; confidence + n_nights update in place. Schema-
  versioned; consumers tolerate unknown keys.
- **Per-night `discoveries.json`**: `{night, n_new, n_promoted, catalogue_total,
  new_ids:[...], promotions:[{id, from_conf, to_conf}]}` — feeds the nightly
  headline + the calendar.
- **The `/astro` catalogue page** (new deliverable): the growing catalogue with
  confidence-coloured entries, the nightly scoreboard, the running see-vs-identify
  curve, and click-through to a source's light curve + its patch in the deep
  stack. The calendar (`build-calendar-index` / `<camera>/index.json`) gains a
  "new stars" number per night.
- **Cadence-tiered deep stacks** published under the per-camera night/week/month
  paths, each the visual backing for the catalogue at that depth.

## Status / open questions
- **Design only.** The catalogue table + persistence-minting is specified
  (`zenith-quests.md`) but not built; confidence as a graded field, the cadence-
  tier accumulators-as-deliverables, and the `/astro` catalogue page are all new.
- **Persistence threshold vs confidence** — is minting still gated at a hard
  persistence count, with confidence layered on, or does a source enter at
  confidence 0 and there's no gate at all (everything detected is a low-confidence
  row)? Leaning: enter as low-confidence `candidate` immediately, no hard gate,
  so the record is complete and confidence does the filtering — but that inflates
  the table with noise; may need a floor. Decide with real detection rates.
- **#0 = Polaris mechanics** — Polaris is the field origin; making it catalogue
  #0 is natural but check it doesn't special-case awkwardly (it's saturated, an
  anchor not an integration target — `what-accumulation-buys.md`). Likely fine: it
  IS a real star with a real position, just also the scaffolding.
- **Confidence calibration** — the number should mean something (a 0.9 source is
  right 90% of the time). Needs validation against Gaia on the matched subset to
  calibrate the persistence/field-agreement → confidence mapping.
- **Cadence-tier storage** — publishing nightly+weekly+monthly+all-time stacks
  multiplies deliverable bytes; decide which tiers persist vs regenerate
  (`drift-scan-cadences.md` decimation options apply).

## See also
- `design/zenith-quests.md` — the local catalogue spec (`SC-` mint-on-persistence, classification from behaviour, running tally), the completeness ceiling.
- `design/drift-scan-cadences.md` — the three internal cadences these deliverable tiers sit above; retention.
- `design/what-accumulation-buys.md` — why deeper tiers matter (faint detection, photometric depth, PSF structure).
- `design/accumulator-outlier-rejection.md` — persistence/rejection, the evidence confidence is built from.
- `design/hierarchical-vector-field.md` — the field that predicts positions; Polaris as origin/anchor/#0.
- `design/meta-conventions.md` — JSON-as-API deliverable schema convention.
- STATE.md (astro-science) — "deliverables" (the public face); the see-vs-identify quest.
