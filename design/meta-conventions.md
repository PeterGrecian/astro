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

## Resolving paths from `(camera, night, kind)` — `astro.locator`

Two natural storage zones, each with its own access pattern:

| Tier | Where | Who reads | Access |
|---|---|---|---|
| **Public deliverables + experiments** | S3 (`astro-berrylands-eu-west-1`) | Web visitors; Splay when remote | URL / presigned |
| **Working stills + FITS frames** | local disk / NFS (`~/astro-frames/...`) | Operator at workstation, on-host CLIs | Filesystem path |

This split is natural — videos are produced for sharing and live
where shareable things go; frames are bulky and intermediate and
live where bulky working data goes. **No new URI scheme is needed**;
`s3://` is already canonical for one tier and filesystem paths for
the other.

The cheap unification is one small module that codifies the lookup
(sketch — to land when a second consumer beyond the website Lambda
appears):

```python
from astro import locator

# Working data — returns local Path objects (via NFS or local disk).
paths = locator.frames("eclipticam-v3w", "2026-06-16")
# → [Path("/home/peter/astro-frames/2026/06/16/eclipticam-v3w/night/22/22-00-05.fits.fz"), ...]

brightness_csv = locator.brightness("eclipticam-v3w", "2026-06-16")
state_json     = locator.state("eclipticam-v3w", "2026-06-16")

# Public artefacts — returns S3 URLs (callers presign as needed).
sweep_url = locator.deliverable("eclipticam-v3w", "2026-06-16",
                                "sweep-colour.mp4")
# → "s3://astro-berrylands-eu-west-1/eclipticam-v3w/nights/2026/06/16/sweep-colour.mp4"

# Experiments — list of (meta_dict, mp4_url) pairs.
exps = locator.experiments("eclipticam-v3w", "2026-06-16")
```

Today the lookup logic exists in two places: `astro.frames.list_night_frames`
(working data only) and the per-night camera page in
`mywebsite/lambda/mywebsite.py` (S3 listing inline). When Splay or a
second tool needs both halves, factor into `astro.locator` and have
both callers go through it. Not now — wait for the second consumer.

Why this is small: pip has 8 GB RAM, working stills/FITS at binned
resolution fit comfortably in cache (one night = ~6 GB at float32,
fits with mmap). No invented caching layer needed — the kernel
page cache holds it.

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
