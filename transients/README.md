# transients — the curated collection, in git

One file per published item in the [Transients gallery](https://www.petergrecian.co.uk/astro/transients).
**These files are the source of truth. S3 is a render target.**

That is the inversion, and it is deliberate. `bin/add-transient` publishes
straight to S3 and keeps no local state — its docstring says so — which meant
the prose lived in exactly one bucket. The pictures are argument as much as
decoration, and the reasoning behind each one is hand-written and not
reproducible from the data. So it belongs in version control, where it can be
diffed, reviewed, and assembled by a layout tool.

## What a card is

Front matter (the fields `add-transient` publishes), a `source:` block, and
three prose sections:

- **Caption** — what you are looking at.
- **Reasoning** — why we say it is that. Written for a general reader: the
  naive reading named first and then defeated, terms glossed in place, plain
  words, intuition before measurement.
- **Evidence** — the short discriminator points, in the language of
  `bin/find-transients` (ends interior / touches border, single-sub vs
  persistent, non-sidereal angle, solar altitude) so a reader can walk from the
  card into the code.

**The two registers are deliberate.** Accessible prose over a technical bullet
list; do not let the jargon leak up into the Reasoning, and do not "improve"
the bullets into prose.

## Why the image is not in git

Each card carries the recipe that made its picture — the frames, the crop, the
stretch — and `render.py` rebuilds it:

    ./render.py 2026-08-23-plane-two-lights-and-a-distance.md --root ~

Keep the JPEG and lose the recipe and you can never re-crop or re-stretch for a
different layout, which is the first thing a layout tool wants. Keep the recipe
and lose the JPEG and you type one command. **The raw FITS is the archive; the
picture is a build artefact** — the same call the accumulator design already
makes about raw frames. It also keeps the repo text-only: fifty cards of
1-2 MB JPEGs is ~60 MB of binaries git will never delta-compress and can never
forget.

Verified: `render.py` reproduces the published plane image with a maximum pixel
difference of 0.

`--root` is the directory the `source: frames:` paths hang off, so the same
card renders on a capture host (`--root ~`) or on a workstation with the export
mounted.

## Publishing

Today, still by hand — `bin/add-transient IMAGE --title ... --rationale ...`,
which is what created these. **The obvious next step is `add-transient --from
<card.md>`**: parse the front matter, call `render.py` for the image, and
publish. That closes the loop and makes the git copy the thing you edit rather
than a transcript of what was published. Until then, edits here must be
mirrored by hand, and the id in the front matter is what makes a re-publish
replace the entry instead of adding a new one.
