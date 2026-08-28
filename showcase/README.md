# Astro Showcase — Curated Astrophotography in Git

One file per photo in the [Astro Photos Showcase](https://www.petergrecian.co.uk/astro/photos).
**These markdown cards in Git are the source of truth; S3 is the render target.**

## Architecture

- **Text & Metadata in Git**: Full observational narratives, equipment setup, exposure details, and technical processing recipes are version-controlled, diffable, and reviewable in Git.
- **Binary Imagery in S3**: High-resolution 4K deliverables and web-optimized thumbnails are stored in S3 (`showcase/items/` and `showcase/thumbs/`) and served with CDN edge caching.

## What a Card Contains

Each `.md` card carries:
1. **YAML Frontmatter**:
   - `id`: unique slug (e.g. `2026-08-20-canon-cygnus-milky-way`)
   - `title`: display headline
   - `category`: `deep-sky`, `milky-way`, `star-trails`, `derotated`, `widefield`, `solar-system`, `lunar`
   - `target`: celestial target / object name (e.g. `NGC 7000 / Deneb`)
   - `constellation`: e.g. `Cygnus`
   - `featured`: boolean (sets hero banner in gallery)
   - `date`, `time`, `camera`, `night`
   - `equipment`: `optics`, `focal_length`, `f_ratio`, `sensor`, `mount`, `filter`
   - `exposure`: `subs`, `sub_time`, `total_integration`, `iso_gain`, `bortle`
   - `source`: recipe for generating or cropping the image

2. **Prose Sections**:
   - `# Caption`: what the viewer is seeing.
   - `# Observation & Processing`: how the image was captured, calibrated, stacked, and stretched.
   - `# Technical Highlights`: bullet list of discriminator points, registration accuracy, optical specs, or algorithms used.

## Publishing Workflow

    ./publish.py <card.md> [--publish]

Without `--publish`, it performs a local dry-run. With `--publish`, it uploads full resolution + thumbnail to S3 and registers the item in `s3://astro-berrylands-eu-west-1/showcase/index.json`.

## Front Matter CMS in VS Code

`frontmatter.json` configures the Showcase folder for the Front Matter CMS extension in VS Code with interactive buttons for:
- **Render preview**: writes to `showcase/_render/` for local previewing.
- **Publish to showcase**: renders and syncs directly to S3 via `publish.py`.
