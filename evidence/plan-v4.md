# ipo-analyst v4 — plan (written before any v4 result was computed)

Test data: the 2020-2025 walk-forward (`wf_data.jsonl`, `bt3.jsonl`, 404 IPOs). Training for test year Y uses only
deals whose horizon ended before Y-01-01. Score: Brier / log score, years better (of 6), paired difference with a 90%
interval, hit vs always-unfavorable, returns from following the calls. Settings are fixed below; nothing is tuned.

| # | change | type | adoption rule |
|---|---|---|---|
| 1 | Hold verdict = trailing base rate only (comparables ignored at day 180) | already measured | adopt: base-rate Brier 0.2349 beat the verdict's 0.2427 on 404 IPOs |
| 2 | `--mode pre-pricing` (no filing dated on/after the cutoff) vs `at-open` (424B4 within 3 days allowed); backtest = at-open | correctness | self-test |
| 3 | Caution level from every IPO in the 10-year lookback (not 40 comparables) | prediction | adopt if, walk-forward, day-5 median of IPOs opening at/above the level is below that of IPOs opening under it in >= 4 of 6 years |
| 4 | More price-range wordings | parsing | check on the SpaceX S-1/A and the 7 case filings |
| 5 | Valuation at the opening price: P/S at the open vs prior IPOs' P/S at their open | prediction | adopt (as a report section and hold caution) if the richest quarter at the open has a lower day-180 share up than the rest in >= 4 of 6 years |
| 6 | Demand rule: if the deal priced above its first range, the flip cannot be UNFAVORABLE (becomes MIXED) | prediction | adopt if, on bt3 rows, flip Brier/hit with the rule beat without it overall and in >= 4 of 6 years |
| 7 | Pricing: P(outside the first range, and which side) from the trailing base rate split by range revision (raised / cut / unchanged before pricing) | prediction | adopt if log score beats the plain base rate pooled and in >= 4 of 6 years |
| 8 | S-1 summary-table parser for targets without `--facts` | parsing | must match the 8 hand-made facts files (rev0, rev1, opinc within 1%) |
| 9 | Takeover price for delisted comparables (merger filings) | data | coverage reported before/after; the verdict is not retuned |
| 10-12 | monthly forward check, coverage logging, regression set | process | regression set passes on the frozen data |

Extras (no effect on calls): plain-English S-1 brief, IPO calendar, sources per number, GitHub packaging.
