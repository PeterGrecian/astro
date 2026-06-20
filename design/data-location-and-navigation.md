# Data location & navigation — strategy

**Decided 2026-06-20.** How we find a `(camera, night)`'s data when it can
live in multiple layouts, on multiple roots, and in multiple storage tiers —
and how a human gets to "today's images" without typing paths.

## The problem

Three independent old/new boundaries piled up during the unify-cameras split:

1. **Puppy frames** — capture still writes the *legacy* tree
   `night/<date>/<subcam>/HH/*.fits.fz` (deliverables land there too). The
   *canonical* tree `YYYY/MM/DD/<camera>/` exists but holds only
   `state.json` + `brightness.csv` so far.
2. **S3 deliverables** — old `eclipticam/nights/` (`v3w_`-prefixed files,
   frozen 06-16) vs new `eclipticam-v3w/nights/` (un-prefixed, 06-16→).
3. **Storage tiers** — nights also move to cold media: muppet USB stick,
   S3 deep-archive tarballs, squashed-and-source-deleted. Recorded in
   `whereisallthedata.csv`.

## The decision: dual-read via a resolver, don't move data for the code

Layout is for **human** convenience; software resolves whatever scheme via a
helper. So:

- **Don't migrate the 45 GB legacy puppy tree just to satisfy the code.** A
  one-time tidy is acceptable *only* when capture also moves to write
  canonical (so the split stops growing) — until then it's maintaining the
  split from both sides. Deferred.
- **`astro/locate.py`** is the resolver. `resolve(cfg, night)` probes
  `cfg.search_roots` × layouts (canonical / percam / flat) and returns where
  the night *actually* is. `list_nights(cfg)` resolves every candidate the
  same way so `today` and `latest` agree.
- **Relocation flexibility**: `cfg.search_roots` (from optional camera.json
  `frames_roots`, default `[frames_root]`). Data moves to a cold disk →
  register the root, resolution keeps working. Nothing computes a fixed path.

## `whereisallthedata.csv` is the registry for *moved* data

The CSV (written by `bin/cold-archive-night`) is the source of truth for data
a live filesystem probe can't see: USB-stick / deep-archive / squashed
nights, with `storage_class` and per-tier sizes. `astro.locate.resolve()`
falls back to it when no live root holds the night, returning the recorded
location + `online` flag instead of "not found". So:

- recent/live nights → live probe (fast, no registry entry needed)
- archived nights → registry tells you it's on the USB stick / in S3 cold

**Schema gap (TODO):** the CSV has no `camera` column (starcam-only history).
`registry_locations()` treats a missing camera as "matches any". When
eclipticam nights get archived, add a `camera` column and have stage-4
`astro-storage` write registry rows on every squash/move so it never drifts.

## Human navigation surfaces

- **`bin/astro-where <camera> [today|yesterday|latest|YYYY-MM-DD]`** — prints
  the resolved dir. `splay "$(astro-where eclipticam-v3w today)"`. `-v` shows
  root/layout/storage; offline nights warn on stderr.
- **`bin/astro-latest-links --camera ...`** — maintains
  `<root>/latest-<camera>` symlinks → today's resolved dir. Run nightly
  (cron or alongside astro-state). `cd ~/eclipticam-frames/latest-eclipticam-v3w`.
- **GC**: `bin/gc.py` now skips symlinks outright so the `latest-*` pointers
  aren't misreported as orphans (and never deleted — they're nav aids).
- **Website** (`mywebsite`): reads the new S3 layout directly per camera
  prefix (committed separately). Longer term it could read a published
  per-camera `index.json` manifest so it does zero location logic.

## Branch note

This work landed on `unify-cameras`, then `main` was subsumed via
`git merge -s ours` (2026-06-20, `ce7be38`) after verifying main's 4
capture fixes were already present on unify-cameras. pip / puppy /
eclipticam-Pi all track `main` now.
