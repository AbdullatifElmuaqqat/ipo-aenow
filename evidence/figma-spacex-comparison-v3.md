# ipo-analyst v3 replay: Figma and SpaceX vs what happened (2026-11-11)

The skill was not edited for this test. Each IPO was run twice, point-in-time, with S-1/A facts only:
**A pre-pricing** (business day before the first trade; the driver hid every filing dated on or after it) and
**B at the open** (first-trade date; the final prospectus is fair to know, its terms were set the evening before).
All four reports were frozen by hash before any outcome was fetched (`freeze.txt`, audit PASS).

Note found while running: one line in `build_target` that I did not write lets a point-in-time run use a 424B4 filed up
to 3 days after the cutoff. That is fair "at the open" but leaks the final price into a "pre-pricing" run; the driver
blocked it for snapshot A. Left as is (no skill edits in this test).

## Scorecard

| question | Figma (FIG), first trade 2025-07-31 | right? | SpaceX (SPCX), first trade 2026-06-12 | right? |
|---|---|---|---|---|
| **Flip** (day 5 from the open) | UNFAVORABLE, p 44-45% | ❌ actual **+6.3%** | UNFAVORABLE, p 44% | ❌ actual **+23.3%** |
| **Hold** (day 180 from the open) | MIXED, p 43% | no call; actual **-66.5%** (would have been right to say unfavorable) | UNFAVORABLE, p 26% | open: -4.6% at day ~150 (leaning right) |
| **Pricing vs first range** | "inside" 60% (base rate) | ❌ priced **above** ($33 vs $25-28; range raised to $30-32) | "inside" 62% | can't score: range not parsed |
| Neighbor pricing model (shown, not used) | 76-78% above | ✅ | 73-84% above | can't score |
| **Valuation** (at the IPO price) | FAIRLY VALUED (16.6-17.6x sales vs 15.0x) | ❌ misses the real risk: it **opened at $85 (+158%)**, ~45x sales | OVERVALUED at B (94x vs 10.3x) | so far +6% from IPO, -5% from open: open |
| **Twin IPOs** (same setup) | B: 72 twins, 56% up by day 1/5, **27% by day 180** | ✅ matched the path: up early, down later | 360 twins, 50% / 33% | flip ❌, hold open |
| **At-open table** (opened > 25% above) | day 1 50%, day 180 **28%** | ✅ the lowest long-run odds of all groups | opened +11% (0-25% group): day 5 40% | ❌ |
| **Caution level** | not set | ❌ a +158% open is exactly when one is needed | not set | - |
| **Bottom line** | flip LEANS SKIP; hold NO CLEAR LEAN | ❌ / missed | flip LEANS SKIP; hold LEANS SKIP | ❌ / open |

**Hits on scorable calls: 0 of 3** (two flips wrong, one hold no-call that should have been a skip; SpaceX hold is
not resolved). "Always unfavorable" would also have missed both flips. Two IPOs say little about a rule, but both
failures point the same way.

## What the reports got right
- **Long-run caution on Figma**: base rate 35%, twins 27%, the at-open table 28% for big pops. The descriptive layers said "this falls apart later", which is what happened (-66% from the open).
- **SpaceX valuation**: 94x sales vs 10x for comparables at the open snapshot, flagged clearly.
- **Hygiene**: no leaks, every number traceable, honest "what it means" lines, and the report says the verdict is near the base rate.

## What the reports got wrong, and why (gaps)
1. **Hot deals.** Both were heavily demanded (FIG raised its range and priced above; SPCX opened +11% and ran +41% by day 3). The flip verdict is anchored on a base rate where ~60% of IPOs fall by day 5, so it calls UNFAVORABLE on exactly the deals that pop. The neighbor pricing model saw the demand (76-84% "above") but v2 switched it off because on average it did worse.
2. **Valuation stops at the IPO price.** Retail buys at the open. Figma at $33 looked fairly valued; at $85 it was not. The skill never re-prices at the actual open.
3. **The comparables pulled the hold the wrong way on Figma** (look-alikes 73% up vs base 35% -> MIXED instead of UNFAVORABLE).
4. **SpaceX's price range was not parsed** from its S-1/A, so pricing and range signals were blank.
5. **Caution level never fires**, even on a +158% open.

History, not a prediction; not financial advice.
