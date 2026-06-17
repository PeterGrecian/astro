# worklog/

Dated session logs. One file per working session, named by the
session's primary date: `worklog/YYYY-MM-DD.md` (or
`YYYY-MM-DD-evening.md` etc. if a day had multiple distinct
sessions).

## What goes here

- **What you set out to do** that day.
- **What actually happened** — discoveries, dead-ends, surprises.
- **What's still open** — handoff for the next session.
- **Decisions made in passing** that didn't yet rise to
  `DECISIONS.md` level.
- **Tactical notes** ("the v3w daemon ran at 21:18", "puppy is on
  /home/peter/astro-unify still") that would be useful to a future
  you trying to reconstruct context.

## What doesn't

- **Permanent design rationale** → `design/`.
- **Open work items** → `TODO.md` / `TODO-other.md`.
- **Crystallised architectural choices** → `DECISIONS.md`.
- **Per-night observations of the sky data** → those belong with the
  night's deliverables on S3, or `design/` if they're general findings.

Worklog entries are *transient* in the sense that none of the
ongoing system depends on them, but they're *durable* enough that
they're worth keeping in git — six months from now you'll thank
your past self for noting that flap-cycle pattern at 21:37 BST on
the night the saturation guard finally landed.

Don't curate. Don't delete. Don't rewrite. The point is a reliable
record of what happened.
