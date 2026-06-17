# Metadata conventions — the schema layer

Both the website player and the (eventual) standalone Splay consume
the same data. To keep them in sync without sharing code, they agree
on **the S3 layout and the JSON schemas**, not on a runtime library.

Drafted 2026-06-17. Adjust as the experiments machinery matures.

## S3 layout per camera, per night

```
s3://astro-berrylands-eu-west-1/
└── <camera>/
    └── nights/
        └── YYYY/MM/DD/
            ├── summary.json
            ├── brightness.png
            ├── max.jpg
            ├── derot.jpg
            ├── thumb.jpg
            ├── sweep-mono.mp4
            ├── sweep-colour.mp4
            ├── sweep-diff.mp4
            └── experiments/
                └── <experiment-slug>/
                    ├── meta.json
                    └── <artefacts: .mp4, .jpg, .png, ...>
```

`<camera>` is the post-split camera name: `astrocam`,
`eclipticam-v1`, `eclipticam-v3w`. Legacy `eclipticam/nights/...`
remains as it was for backfill; new deliverables land under the
split names.

`<experiment-slug>` is the `--name` passed to `bin/astro-experiment`.
Operator-curated; bump to `-v2` etc. when an old variant needs to
survive alongside a new one.

## summary.json (deliverables only)

Schema-2, set by `astro.present.summary`. Covers the *deliverable*
artefacts (the every-night menu, see TODO.md "Deliverables (website)").
Experiments are NOT listed here.

Minimum surface for downstream consumers:

```jsonc
{
  "schema": 2,
  "camera": "eclipticam-v3w",
  "night": "2026-06-16",
  "verdict": "clear" | "cloudy" | "no-data",
  "n_frames": 165,
  "n_stacked": 142,
  "derot": {
    "pole_xy": [1520.0, -176.0],
    "window_utc": ["2026-06-16T22:00:00Z", "2026-06-16T23:00:00Z"]
  },
  "badpix": { "bad_pct": 0.034 }
}
```

Fields may grow; consumers MUST treat unknown keys as informational
and not error on them.

## meta.json (per experiment)

Schema set by `astro.experiments.ExperimentMeta`. Each
`experiments/<slug>/meta.json` is independent — no parent index, no
cross-experiment references. The website *lists* experiments by S3
listing, not by reading any summary.

```jsonc
{
  "schema": 1,
  "name": "mci-colour-60",
  "kind": "mci",
  "camera": "eclipticam-v3w",
  "night": "2026-06-16",
  "description": "minterpolate fps=60 mi_mode=mci mc_mode=aobmc on sweep-colour.mp4",
  "args": { "input": "sweep-colour.mp4", "fps": "60" },
  "repo": "astro",
  "commit": "f7c49a3",
  "dirty": false,
  "run_at_utc": "2026-06-17T11:42:18Z",
  "artefacts": ["mci-colour-60.mp4", "meta.json"]
}
```

`schema` is the integer set by `astro.experiments.META_SCHEMA`.

`repo` + `commit` are the load-bearing fields — they let the website
(and Splay) trace any frame back to the exact code that made it.
Operator runs that bump output without bumping the slug MUST bump the
commit before publishing, or accept that the new content is silently
indistinguishable from the old in the meta.

## What the website needs

- The per-night player page lists every `.mp4` under
  `<camera>/nights/YYYY/MM/DD/`: root deliverables (sorted first),
  then `experiments/*/*.mp4` (alphabetical by slug). Presigns each,
  hands to `render_skycam_player(srcs=...)`.
- Future: per-experiment page reads
  `<camera>/nights/<night>/experiments/<slug>/meta.json` and renders
  `name`, `description`, commit short-hash, run time, and the
  artefacts.

## What Splay (eventually) needs

Same listing. Same JSON. Same presigning (or direct S3 access if the
operator has IAM creds). The shader-driven controls operate on the
artefacts client-side; the menu and the per-frame metadata come from
the JSON layer.

The principle: **JSON is the API.** Either runtime can be rewritten
without touching the other if the contract holds.

## Versioning

If a schema needs an incompatible change:
1. Bump the `schema` integer in summary.json (or add one to meta.json
   if it lacks one).
2. The producer (publish-night-cam / astro-experiment) writes the
   new schema only.
3. Consumers (website Lambda, Splay) MUST tolerate both schemas for
   at least one season before the old one is retired.

Trivial additions (new optional keys) don't need a bump — consumers
should already tolerate unknown keys.
