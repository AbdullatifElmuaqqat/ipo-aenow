# ipo-aenow

A research skill for Claude Code that studies a US IPO the way an analyst would, and then checks itself against
history without peeking at the future. It reads the company's own SEC filings, finds past IPOs that looked like it,
and reports how deals like it did from the first open: day 1, 3, 5, a week, a month, three and six months.

It is **research, not a trading signal and not financial advice**. Every number is traceable to a filing or a data
feed, every section ends with a plain-English "what it means", and the report says how close its rules are to the
plain base rate.

## What a report contains
- The company in plain English: what it sells, who controls the vote, lockup, use of proceeds, its own top risks, the post-IPO calendar.
- Verdicts: **flip** (day 5 from the open) and **hold** (day 180), each as a chance of a gain next to the base rate of all recent IPOs.
- Where it is likely to price vs its range (from deals whose range moved the same way before pricing).
- Valuation at the IPO price and **at the opening price**, with the open above which it would be among the most expensive quarter of IPOs.
- Twin IPOs (same setup) and look-alike companies, with their real paths.
- An **outcome simulation**: 10,000 draws of real past IPO paths, so day 1 and month 6 stay consistent.
- A bottom line: an evidence table, good and bad signs, and a fixed-rule read (flip candidate / hold candidate / skip / no clear lean).
- Sources: links to every filing used.

## How it was tested (2026-11)
- Point-in-time replays with a leak audit (no filing or price dated after the cutoff reaches the result), frozen by SHA-256 before outcomes were fetched.
- Walk-forward 2020-2025: each IPO scored by rules that never saw it (404 IPOs).

| | result |
|---|---|
| Flip verdict | right **58.5%** on its calls vs 48.8% for "always unfavorable"; Brier 0.2452 vs 0.2491 for the base rate; better in 6 of 8 years; IPOs it called favorable averaged **+5.8%** by day 5 vs +2.0% for all |
| Hold verdict | the base rate alone (comparables made it worse); 63.5% right on calls vs 66.6% always-unfavorable: no edge, stated as such |
| Pricing vs range | base rate split by range revision beat the plain base rate in **6 of 6** years |
| Valuation at the open | the most expensive quarter at the open was less often up by day 180 in **5 of 6** years |
| Tried and rejected | pricing/market/opening-jump signals in the verdict, an all-IPO caution level, a hot-deal rule: none beat the base rate |

Full scorecards, pre-registered plans and raw results: `evidence/` in the repository (scorecard-v1 .. v4).

## Commands
```
python scripts/ipo.py analyze TICKER [--summary] [--save] [--facts s1.json] [--coverage "8x; src1; src2"]
python scripts/ipo.py analyze TICKER --as-of 2025-07-30 --mode pre-pricing   # replay a past IPO, point-in-time
python scripts/ipo.py backtest --all        # re-run the method on IPOs 6-24 months old
python scripts/ipo.py forward               # score the forward paper log (every live analysis is logged)
python scripts/ipo.py regress               # fixed regression set: parser, verdict math, 2020-25 scoreboard
python scripts/ipo.py --selftest            # offline checks
```
Standard-library Python only. SEC requires a contact in `trader/config.json` (`sec_user_agent`).

## Limits
Most IPOs fell outside the four business archetypes before the S-1 parser was added (86%; not yet re-measured);
37% of look-alikes have no price history (takeover prices fill only their final value); the flip edge is modest and the hold has none; the forward log is the clean
test from here. History, not a prediction.
