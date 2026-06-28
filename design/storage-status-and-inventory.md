# Storage status, inventory store, and consolidation

Drafted 2026-06-28. Ties together the storage thinking that was
previously spread across `COLD_STORAGE.md`, `storage-layout.md`
(§"eclipticam processing+storage" / STAGE 4), `whereisallthedata.csv`,
and conversation. Three decisions captured here:

1. **Inventory store moves CSV → DynamoDB** (so the web Lambda can read it).
2. **A public storage-status page** at `/astro/storage`, linked from the
   astro hub, rendered by the mywebsite Lambda.
3. **Data consolidates onto muppet/bigdisk** (off puppy, off the
   eclipticam Pi) as the warm tier, with Deep Archive as cold.

This doc is the *observability + inventory* layer. It does NOT redefine
the tiers (Hot/Warm/Cold → Deep Archive) — those live in COLD_STORAGE.md
and storage-layout.md and are unchanged.

## Why this now

Snapshot 2026-06-28:

| Host | Disk | Used | Free | |
|---|---|---|---|---|
| puppy | 468G NVMe | 432G | **12G (98%)** | 🔴 the crisis |
| muppet root | 233G NVMe | 169G | 52G | 🟠 |
| muppet bigdisk | 839G xfs | 619G | 220G | 🟢 warm-tier home |
| eclipticam root | 15G SD | 6.5G | 7.1G | 🟢 |
| eclipticam SSD | 109G | 17G | 87G | 🟢 |

Problems: (a) puppy at 98% — astrocam captures there nightly and it's
nearly full; (b) drifted duplicates — puppy astrocam 181G vs bigdisk's
frozen copy 159G, nobody can say which night is where without ssh; (c)
raw FITS have no automatic Glacier path (only *deliverables* go to S3),
so local disks fill forever. STAGE 4 (`astro-storage`, ship+free with a
keep-policy) is the unbuilt piece that fixes (c); this doc is its status
half.

## Decision 1 — inventory store: DynamoDB, not CSV

Today `whereisallthedata.csv` is the per-(night × location) registry,
read by `astro/locate.py` (`_registry_rows`) as the fallback when a live
filesystem probe can't see a night (moved/archived). Written by
`cold-archive-night`.

**The CSV cannot be read by the mywebsite Lambda** (it sits in
`~/astro` on a workstation). The status page needs the inventory; that
single fact tips the store to DynamoDB. Data volume (~20 nights) does
NOT justify Dynamo on its own — the Lambda-readability does.

Table `astro-storage-inventory`:

| Attr | Role | Example |
|---|---|---|
| `night` (PK) | partition | `2026-05-20` |
| `loc` (SK) | `camera#host#path` | `starcam#muppet#~/starcam-backup/2026-05-20` |
| `camera` | | `starcam` |
| `host` | | `muppet` |
| `storage_class` | GSI PK | `local` \| `usb-stick` \| `deep-archive` |
| `bytes` | map of sizes | `{raw_bayer, binned, raw_sum8, binned_sum2, tarball}` |
| `online` | bool | derived (`storage_class == "local"`) |
| `notes`, `updated_at` | | |

- **Writers**: `cold-archive-night` + per-host reporters → `PutItem`
  (each host owns its own rows; no CSV-merge race).
- **Readers**: `locate.py` (query by `night`, optional `camera` filter —
  drop-in for `registry_locations`) AND the `/astro/storage` Lambda.
- **GSI on `storage_class`**: "what's still local" / "what's in Glacier"
  in one query, no scan.
- CSV becomes a *generated export* (`locate.py --dump-csv`) for
  git-diff/grep, not the master. One source of truth, killing the drift
  that motivated all of this (matches the unified-infrastructure habit).

Capacity (df per host) is separate from inventory — a small
`astro-host-capacity` table (or items) keyed by `host`, written by the
same reporter: `{host, fs, size, used, avail, pct, updated_at}`.

## Decision 2 — status page at /astro/storage

A new Lambda route in `mywebsite/lambda/routes/astro.py`, rendered like
the existing astro pages (server-rendered, dark iOS theme), linked from
the astro hub (`render_astro_hub`). Public — disk numbers aren't
sensitive. Reads the two DynamoDB tables; no host access needed.

Sections (the four asks):

1. **Capacity** — per-host disk bars, colour-coded (pi-fleet style).
2. **Inventory & location** — which camera-nights live where; flag
   duplicates / drift (same night, >1 `local` row with differing bytes).
3. **Migration progress** — consolidation to muppet: moved / pending /
   verified counts.
4. **Archive tier** — what's in Deep Archive, what's local-only,
   retention. Driven by the `storage_class` GSI.

## Decision 3 — consolidate warm tier on muppet/bigdisk

Per the host-split evolution (laptops are the INTERIM tier until the Pi
appliances are self-sufficient), muppet/bigdisk (220G free) becomes the
warm store; puppy and the eclipticam Pi shed raw FITS to it, then old
nights age muppet→Deep Archive.

**Caveat to resolve before relying on it**: bigdisk is a ~15yo Seagate
(see [[project_muppet_hardware]] / COLD_STORAGE.md "sticks are cheap-
and-rubbish, one copy each"). Consolidating live data onto a single
aging disk needs the Deep Archive second copy to be current FIRST — the
inventory's `deep-archive` rows are the proof that it's safe to free
local. The status page makes that visible: never delete a `local` row
whose night lacks a `deep-archive` sibling.

## Build order (later sessions)

1. Create the two DynamoDB tables (terraform in mywebsite or astro infra).
2. `locate.py`: read DynamoDB (keep CSV export). Backfill table from the
   current CSV.
3. Per-host reporter (df + per-night du + storage_class) → PutItem, cron.
   This is the "hosts push their truth" decision, writing to Dynamo
   rather than storage.json-to-S3.
4. `/astro/storage` Lambda route + hub link.
5. Fold into STAGE 4 `astro-storage` ship+free: it writes inventory rows
   as it moves/archives, so the page is always current.

## Related
- COLD_STORAGE.md — tiers, squash format, sticks-vs-Glacier.
- storage-layout.md §"eclipticam processing+storage" — STAGE 4, budget math.
- `astro/locate.py` — current CSV reader to migrate.
- memory: [[project-astro-host-split]], [[project_muppet_hardware]].
