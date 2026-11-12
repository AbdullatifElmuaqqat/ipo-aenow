# ipo-analyst v4 — scorecard (2026-11-11)

All tests are walk-forward on IPOs first-traded 2020-2025: for each test year, rules and statistics use only deals
whose outcome was known before that year began. Rules were written down before they ran (`plan-v4.md`).

## What v4 changed and whether it passed

| # | change | test | result | status |
|---|---|---|---|---|
| 1 | Hold verdict = base rate only | 404 IPOs, Brier | 0.2349 vs 0.2427 with comparables | **adopted** |
| 3 | Caution level from all IPOs | day-5 median above vs below the level, per year | worse above it in 3 of 6 years | rejected |
| 5 | Valuation at the opening price | day-180 share up, most expensive quarter at the open vs the rest | lower in **5 of 6** years (2020: 36% vs 73%; 2021: 11% vs 27%) | **adopted** |
| 6 | Hot-deal rule (priced above range -> no UNFAVORABLE flip) | Brier per year | better in 3 of 6 years, pooled no better | rejected |
| 7 | Pricing by range revision | log score | -1.105 vs -1.353, better in **6 of 6** years | **adopted** |
| 8 | S-1 summary parser | 8 hand-read filings | 8 of 8 match revenue, prior revenue, operating income | **adopted** |
| 2, 4, 9 | mode flag, range wordings, takeover prices | checks | pass | done |

## Scoreboard (pre-registered bars from v1)

| bar | v1 | v2 | v3 | **v4** |
|---|---|---|---|---|
| Flip beats "always unfavorable" by >= 5 pts | -18.8 | +3.1 | +9.7 | **+9.7** (58.5% vs 48.8%, 404 IPOs) |
| Hold beats it by >= 5 pts | +0.3 | +0.5 | -1.2 | -3.1 (base rate: 63.5% vs 66.6%; best Brier of all tested) |
| Confidence labels hold up | no | yes | yes | yes (single tier) |
| Pricing beats "always inside" | 27% vs 68% | 45% vs 70% | - | exact bucket 50.3% vs 51.3% (tie); **below / inside / above call 72.6% vs 51.3%** |
| No future-data leaks | driver only | native | native | native, two explicit modes |

## Returns from following the flip calls (day 5 from the open, 2020-25)
Called favorable: **+5.8%** average · called unfavorable: **-4.6%** · every IPO: +2.0%.

## Figma and SpaceX (point-in-time replays, before pricing)

| | v3 | v4 | what happened |
|---|---|---|---|
| Figma pricing | inside | **above (82%)** | priced above its first range |
| Figma hold | no call | **unfavorable** | -66% from the open by month 6 |
| Figma open-price line | - | $71.12 | opened at $85 |
| Figma flip | unfavorable | unfavorable | +6% by day 5 (miss) |
| SpaceX value at open | overvalued | already in the most expensive quarter at $135 | -5% from the open after ~5 months |
| SpaceX flip | unfavorable | unfavorable | +23% by day 5 (miss) |

## Known weaknesses
- The flip edge is modest; the hold has none beyond knowing the base rate.
- Hot, heavily demanded deals get called unfavorable on the flip (Figma, SpaceX).
- No measured hype (news volume / tone, search interest, retail demand); order-book coverage is only logged.
- About a third of look-alikes have no price history; archetype coverage not re-measured after the S-1 parser.
- The 2024-26 window has been looked at several times; the forward paper log is the clean test from here.
