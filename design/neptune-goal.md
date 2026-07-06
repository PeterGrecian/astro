# North-star goal: track Neptune in autumn 2026

Peter's framing (2026-06-25). The whole eclipticam astro effort is a RACE
between several aspects toward one concrete goal: **positively track
Neptune in the autumn.** Neptune is mag ~7.8 — well below the naked-eye
limit (~6) — so this is fundamentally a question of DEPTH, not pointing.

## Where we are (honest baseline)

**2 objects positively identified: Polaris (mag 2.0) and the Moon
(mag -11).** Both bright. We do NOT yet know what limiting magnitude we
can resolve — that is THE open question.

## Why Neptune is the right target

| | |
|---|---|
| Magnitude | **+7.8** (≈100× fainter than Polaris, ~6 mag below) |
| Autumn visibility | well-placed ALL autumn in v3w's field (az ~150, alt ~35) at a convenient evening hour: Sept ~midnight → Dec ~18h as the season moves earlier |
| So pointing is NOT the obstacle | Altair-based star-ID + plate solve gives where-in-frame; Neptune will be there (moon-net anchoring ABANDONED 2026-07-06, superseded by star-ID) |
| The obstacle IS depth | can an f/2.2 ultra-wide Pi camera, through DOUBLE GLAZING, reach mag 8? Unknown. |

## The gating question: limiting magnitude

The single number that decides feasibility: **what is our faintest
reliably-detected magnitude in a deep full-res in-focus stack?** Measure
it by detecting stars + cross-matching to a catalog (Tycho-2/Gaia, which
carry magnitudes) and finding where detection drops out. If limiting mag
> ~8, Neptune is reachable. The repo already has the pipeline
(`detect-stars`, `cross-match-gaia`, `photo-compare`, solve-field +
Tycho-2 indexes, photutils). This is the next milestone to chase —
reframes "identify objects" as "measure our depth."

Depth-improving levers we have: full-res capture (more pixels per star),
in-focus (sharper -> higher peak SNR; the 661-vs-250 star-count jump
06-21 vs out-of-focus), detrans-deep stacking (register + bg-subtract ->
faint stars on clean sky, √N gain), green-Bayer-plane detection (lower
noise: 1960 vs 5684 grey-bin), and longer baselines.

## The race (parallel aspects, all feeding the goal)

- **Pointing / astrometry** — **Altair-based star-ID + plate solve** (2026-07-05
  onward): identify bright stars directly in v3w night frames, fit the local
  plate → precise pixel↔sky across the field. Supersedes the moon-net anchoring
  (ABANDONED 2026-07-06 — hand-marking was tedious; stars are direct). See
  `project-v3w-star-id-moon-anchor`.
- **Depth / magnitude** — limiting-magnitude measurement (above). THE
  gating unknown.
- **Capture** — full-res 4608x2592 + lens 3.15 in-focus (both landed),
  raw Bayer archive ("most options"), the v1 moon-complement.
- **Processing+storage topology** — moving to the eclipticam Pi SSD
  (storage locality). Real-time at a 1-day interval, so CPU is fine; the
  shrink/ship-and-free (stage 4) is being developed. NOT a near-term
  blocker: puppy+muppet ~400GB root each, plus a 360GB and a 1TB disk
  being commissioned -> plenty of temporary headroom while stage 4 matures.

## Next concrete step toward the goal

Measure the limiting magnitude on a deep in-focus full-res stack. That
number tells us whether Neptune-in-autumn is feasible and what depth
levers we still need. Everything else (the net for pointing, storage for
sustainability) is in service of getting a mag-7.8 detection.
