# ipo-analyst v2 — frozen algorithm choice (written before any v2 test-window result was read)

Pass bars and the 5 cases are unchanged from `plan.md`. The test window is the same 24-to-6-months window (2024-11 to 2026-05).

## Code changes in ipo.py (v1 snapshot in `skill-v1/`)
1. Leaks: `_upcoming_deep` now gets only filings before the cutoff; comparables that listed within 550 days of the
   cutoff re-read their financials from XBRL facts **filed** before the cutoff (`_pit_fund`, `known_by`); a point-in-time
   target keeps only periods ending >= 45 days before the cutoff (`lag_days`); later delisting dates are hidden.
2. Base rate: every analysis computes the trailing 36-month all-US-IPO base rate (day-5, day-180 from the open, and
   where deals priced vs their first range), cut at the cutoff.
3. Verdict against the base rate (`verdict_vs_base`), pricing anchored on the base rate (`blend_pricing`).

## Selection, on the training window only (IPOs first-traded 2023-11 to 2024-11, n = 39 with outcomes)
| part | candidates | chosen | train result |
|---|---|---|---|
| Flip | V0 (vs zero), V1 (excess vs base), V2 (shrink to base), V3 (V2 + recency), base only | **V2: k = 40, delta = 0.05** | 9/15 right (60%) vs 51% best always-rule; V0 43% |
| Hold | same grid | **V3: k = 10, delta = 0.10, tau = 1 year** (in practice the base rate) | 26/36 (72%) vs 72% always-unfavorable; V0 50% |
| Pricing | neighbors, base only, blends 0.1-0.75 | **base only (alpha = 0)** | log score -1.307 vs -1.478 for neighbors; neighbors never helped |
| Confidence | tertiles of distance from 50% | **single tier ("low")** | tiers did not rank: flip 3/5, 3/5, 3/5; hold 11/12, 9/12, 6/12 (inverted) |

Selection rule used: the largest hit-rate edge over the best always-rule with a call rate >= 30% (pricing: best mean log score).
Only the frozen choice and v1 are scored on the test window; no parameter is changed after that.
