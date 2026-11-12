# ipo-analyst v3 — walk-forward plan (written before any v3 result was computed)

## Data
Every US IPO with first trade 2013-01 .. 2026-05 that passes the backtest filters (first trade on Yahoo, price on the
424B4 cover, not ADR or units, market cap at IPO price >= $200M), after the coverage fixes (wider cover-price
patterns, multi-class share counts read from the prospectus). Outcomes: day 5 and day 180 from the first open.

## Walk-forward
Test years 2020, 2021, 2022, 2023, 2024, 2025. For test year Y the signal steps are estimated only from deals that
first traded 2016-01-01 or later **and whose horizon ended before Y-01-01**. Every test deal is scored by a model that
never saw it. Base rate: trailing 36 months before the deal's own first trade, only deals whose horizon had ended.

## Models (fixed; nothing tuned)
| model | probability of a gain from the open |
|---|---|
| B0 | always unfavorable (classifier only) |
| M0 | base rate only (what v2 is, without the comparables) |
| M1 | M0 + 3 pre-open signals: priced vs first range (below / inside / above), IPO ETF 20-day (up / down), VIX (< 20 / >= 20) |
| M2 | M1 + opening jump vs IPO price (< 0 / 0-25% / > 25%), known at the open, where the flip and hold are measured from |

Each signal: one log-odds step = (logit(group share up) - logit(all)) x n / (n + 50). k = 50, groups and cut points are
fixed above. Call FAVORABLE when p > 0.55, UNFAVORABLE when p < 0.45, else MIXED (one delta for both horizons).

## Scored (pooled and per year; the average over years is the headline, not the best year)
- Brier score and log score (lower Brier / higher log is better), paired difference vs M0 with a 90% bootstrap interval.
- Hit rate on calls vs B0; McNemar test, forced call (p > 0.5) vs B0, per deal.
- Returns from following the calls: mean return of deals called FAVORABLE (buy at the open, sell at the horizon) vs
  buying every deal; B0 means no trades.

## Adoption rule
Adopt M1 into the pre-open verdict (as the anchor the comparables shrink toward) and M2 as the at-open table only if,
for that model vs M0: pooled log score improves, the mean per-year Brier improves, and at least 4 of 6 years improve.
Otherwise v2 stays. Either way, start the forward paper log (next 6-12 months, untouched) and the order-book field.
The 5 cases are used only to check the output reads right.

## Addendum (written before it ran): the v2 verdict itself, 2020-2025
The full point-in-time analysis (comparables shrunk to the base rate, current config) is run on every testable IPO
first-traded 2020-01 .. 2026-01 and scored per year exactly like M0-M2. Caveat stated in advance: the verdict's
k / delta / tau were chosen on IPOs first-traded 2023-11 .. 2024-11, so 2023-2024 are partly in-sample; 2020-2022 and
2025 are clean out-of-sample years.
