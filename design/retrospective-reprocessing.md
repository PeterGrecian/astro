# Retrospective reprocessing — the archive appreciates, it doesn't depreciate

**Peter's question (2026-08-03): when we have more stars and better vector fields,
do we revisit old data and reprocess? YES — and it's the defining property of the
whole design, not an optional extra. Every model that improves (vector field,
catalogue, ePSF, sensor map, confidence) retroactively deepens every past night.
The archive becomes MORE valuable over time. Raw retention exists precisely to
enable this.**

Drafted 2026-08-03 (astro-science). Promotes and generalises the principle
already stated for the distortion model in `drift-scan-cadences.md` §"Why
retrospective re-derot matters" — extending it to the catalogue, the field's
anchor density, the ePSF, the sensor gain map, and confidence values. Ties
together this session's design chain.

## The principle: yesterday's frames, tonight's model

Each night's frames were processed by *that night's best models*. As the models
improve over weeks and months, old frames were processed with WORSE models than
we now have. **Reprocessing them with the current models gives strictly better
results.** So the value of a night's raw data does not decay — it *rises*, because
the machinery that extracts signal from it keeps getting better.

Already stated for distortion (`drift-scan-cadences.md`): re-warp old frames with
the improved distortion model → strictly better stacks; "the archive becomes more
valuable over time, not less… the historical data is the calibration source *and*
the re-derotation target." This doc says: **that is true of EVERY model in the
chain, not just distortion.**

## What improves — and what reprocessing recovers from the past

| Model that improves | Why it improves over time | What reprocessing old data recovers |
|---|---|---|
| **Vector field / distortion (SIP)** | more bright anchors sweep more of the sensor (`hierarchical-vector-field.md` time-densification) → field anchored almost everywhere | old frames re-warped onto the sphere more accurately → tighter stacks, points not smears |
| **The catalogue itself** | grows nightly (`catalogue-deliverable.md`); new stars minted, IDs assigned | re-run old detections against the fuller catalogue → sources that were "unknown blobs" last month are now NAMED in last month's data |
| **Field anchor density** | a faint gap that had no nearby bright anchor last month gets one when a bright star drifts through | old frames' faint detections in that gap now get a good field prediction → identifiable retroactively |
| **ePSF** | built from more, better-confirmed single stars | re-subtract old frames with the better ePSF → fainter/closer companions + cleaner residuals (`what-accumulation-buys.md`) |
| **Sensor gain / colour map** | *accumulates* per-pixel as anchors sweep every pixel (`hierarchical-vector-field.md` "sensor map accumulates") | old frames re-flat-fielded with the mature map → better photometry retroactively |
| **Confidence values** | more nights = more persistence evidence | old detections re-scored: a candidate from months ago is now `confirmed` because the intervening nights confirmed it |
| **Cloud/plane rejection** | clip references + transparency model improve | old stacks recombined with better outlier rejection → cleaner deep stacks |

The pattern is uniform: **the models are functions of the ENTIRE archive; growing
the archive improves the models; better models reprocess the archive.** It closes
a convergent loop.

## The virtuous loop (and why it converges, not diverges)

```
more nights ──► more anchors, deeper stacks, more persistence evidence
    ▲                             │
    │                             ▼
reprocess old          better field / catalogue / ePSF / sensor map / confidence
data with new models ◄────────────┘
```

- **It converges.** Each pass' gains shrink as the models mature — the field is
  eventually anchored everywhere, the sensor map fully sampled, bright stars'
  confidence saturated. Reprocessing is worth most early (models crude, fast
  improvement) and tapers (`drift-scan-cadences.md`: "revisit after the global
  solve has converged enough that further retrospective gains are small"). So it's
  not infinite work — it's front-loaded and self-limiting.
- **The frontier is the faint tail.** Bright stars converge in nights and stop
  benefiting from reprocessing (position saturates — `what-accumulation-buys.md`).
  The faint sources near the floor are where reprocessing keeps paying: a marginal
  blob promoted to a confirmed catalogue star *by reprocessing months of old data
  under a better field* is the archetypal win.

## What this demands — raw retention is the enabler (the cost)

Reprocessing needs the **raw frames**, not just the derived stacks — you can't
re-warp a stack under a better field. So the retention policy IS the reprocessing
policy (`drift-scan-cadences.md`):

- **Keep raws for a rolling window** long enough to capture the reprocessing
  value (heuristic: ~3 months; revisit as the global solve converges). Within the
  window, any model improvement can reach back.
- **Beyond the window, raws are freed** (ship-and-free discipline, GLOBAL.md) —
  but by then the models have converged on that data and the *derived* products
  (deep stack + per-frame source tables + catalogue) hold the distilled value
  forever. The source tables (KB/frame, kept forever — `zenith-quests.md`) are the
  permanent record of what each old frame contained, so identity/photometry
  reprocessing survives even after the pixels are gone; only *pixel-level* re-warp
  needs the raws.
- **Tension to manage:** a big field/ePSF improvement AFTER the raw window has
  closed can't reach the pixels — only the source tables. So time reprocessing
  passes to land *before* raws age out (or extend the window when a major model
  jump is imminent). This is a scheduling concern for the global-solve cadence.

## Where it runs
The slow batch reprocessing is a **puppy / NFS job** (CPU + full archive both
there — `drift-scan-cadences.md`), not the Pi hot loop. Cadence: after the global
solve improves a model materially, or on a timer, or triggered when the catalogue/
field crosses an improvement threshold. Not every night — reprocessing when the
models haven't moved is wasted compute.

## Deliverable consequence — the catalogue is versioned, and old nights update
Because reprocessing changes past results, the deliverables are not write-once:
- A past night's `discoveries.json` / stack can be **re-emitted** when reprocessing
  finds new stars or promotes confidences in it — "3 new stars found in last
  month's data" is itself a deliverable (retrospective discovery).
- The catalogue carries `first_seen` AND a `last_reprocessed` / model-version
  stamp, so an entry's confidence history reflects both new nights and
  reprocessing passes. Consumers see sources' confidence rise from *both* the
  passage of time and the improvement of the instrument.
- Mirrors `meta-conventions.md`'s `repo`+`commit` provenance: a reprocessed
  product records which model version produced it, so old and new are
  distinguishable and a regression is traceable.

## Status / open questions
- **Design / principle only.** The distortion re-derot case is specified
  (`drift-scan-cadences.md`); generalising to catalogue/ePSF/sensor-map/confidence
  reprocessing, and the versioned-deliverable consequence, are new here.
- **Trigger policy** — timer vs model-improvement-threshold vs manual. Leaning:
  reprocess a night when the field/catalogue serving it has improved beyond a
  measurable margin since it was last processed (skip when nothing moved).
- **Retention window vs model-jump timing** — the load-bearing tension above; a
  major field improvement should trigger a reprocessing sweep of the still-held
  raws before they age out. Needs the global-solve convergence data to set.
- **Cost** — full-archive re-warp is expensive; scope each pass (only nights
  whose serving model changed; only the faint-tail cells where gains land, not
  saturated bright stars).

## See also
- `design/drift-scan-cadences.md` — the original statement (distortion re-derot; archive appreciates; retention window; puppy batch job).
- `design/hierarchical-vector-field.md` — the field + sensor map that densify over time (what reprocessing exploits).
- `design/catalogue-deliverable.md` — the growing catalogue + confidence that reprocessing retroactively deepens; versioned deliverables.
- `design/what-accumulation-buys.md` — bright stars saturate (stop benefiting); the faint tail is the reprocessing frontier.
- `design/accumulator-outlier-rejection.md` — better rejection also reprocesses cleaner.
- GLOBAL.md — ship-and-free retention discipline (the constraint reprocessing works within).
