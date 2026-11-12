# ipo-analyst evaluation — pre-registered plan (2026-11-10)

Written before any analysis ran. Bars and picks below are not changed after results come in.

## Pass bars for "worth pushing"
- (a) Flip AND hold hit rates each beat the better of always-favorable / always-unfavorable by >= 5 points, over >= 60 evaluated IPOs.
- (b) Every confidence level with >= 5 calls is right >= 55% of the time, and hit rate high >= medium >= low.
- (c) Pricing bucket (below / mid / top / above the first filed range) is right more often than "always inside the range" (mid + top).
- (d) Leakage audit passes.

Verdict rule: all four pass -> PUSH. (d) passes and at least one of (a)-(c) passes -> PUSH AS EXPERIMENTAL. Otherwise DO NOT PUSH (as a decision tool; it can still be committed as research code).

## Case selection rule (mechanical, ipo.py's own universe + filters)
Filters, same as `ipo.py backtest`: a first trade found on Yahoo, a ticker, a price on the 424B4 cover, not an ADR, not units, market cap at IPO price >= $200M.
- 3 known: the largest by market cap that first traded 2025-01-01..2025-12-31, at most one per archetype where possible.
- 2 blind: the 2 largest that first traded 2026-07-01..2026-09-30 (after Claude's training data).

Result (scratchpad `select_cases.py`, output `cases.json`):

| group | ticker | company | first trade | mcap at IPO | archetype (stage-A data) | why picked |
|---|---|---|---|---|---|---|
| known | KLAR | Klarna Group plc | 2025-09-11 | $15.1B | unclassified | largest eligible 2025 IPO |
| known | SFD | Smithfield Foods | 2025-01-28 | $7.9B | consumer | largest consumer (FRMI, #2, is also unclassified) |
| known | NIQ | NIQ Global Intelligence | 2025-07-23 | $6.2B | profitable | largest profitable |
| blind | CSQR | Csquare, Inc. | 2026-07-16 | $3.5B | unclassified | largest Jul-Sep 2026 |
| blind | LYNX | Lyntris Inc. | 2026-08-19 | $2.0B | unclassified | 2nd largest Jul-Sep 2026 |

Coverage note found during selection (not a pick change): of 231 2025 IPO filings only 42 pass the filters.
37 have no market cap (share count not parsed), 29 have no price on the cover; this drops CRWV, FIG, CRCL, CHYM,
STUB, GEMI, NTSK, MDLN. The rule is kept as written; this is logged as a gap.

## Snapshots per case
- A "pre-pricing": as_of = the business day before the first trade (filings and prices strictly before it).
- B "at first trade": as_of = first-trade date; the 424B4 is treated as public on the evening before (its terms were
  announced at pricing), every Yahoo series is cut before as_of.

## Full backtest
`backtest --all` logic through the leak-safe driver, default window (24 to 6 months ago). Previous 25-IPO result copied to `backtest-previous.json`.
