# ipo-analyst v2 vs v1 — scorecard (2026-11-10)

## 1. Verdict: **PUSH AS EXPERIMENTAL** (v1 was DO NOT PUSH)

Same pre-registered bars, same 5 cases, same test window (IPOs first-traded 2024-11 to 2026-05). v2's algorithms were
chosen on an earlier, separate window (2023-11 to 2024-11) and frozen in `plan-v2.md` before the test was scored.

| bar | v1 | v2 | pass? (v2) |
|---|---|---|---|
| (a) flip AND hold beat the best "always" rule by >= 5 pts | flip **-18.8**, hold +0.3 | flip **+3.1** (72.3% vs 69.2%), hold +0.5 (66.7% vs 66.2%) | ❌ (closer, not there) |
| (b) every confidence level with >= 5 calls >= 55%, high >= medium >= low | fail (hold high 57% < medium 89%) | one tier only ("low"): flip 72%, hold 67% | ✅ (by dropping the tiers that did not rank) |
| (c) pricing bucket beats "always inside the range" | 26.8% vs 68.3% | 4-bucket 45.0% vs 70.0%; 3-way headline 70.0% = always inside | ❌ (ties at best) |
| (d) leakage audit passes | only through the eval driver | **PASS with plain ipo.py**, 0 driver fixes, 0 future delisting dates shown | ✅ |

Pre-registered rule: (d) passes and one of (a)-(c) passes -> PUSH AS EXPERIMENTAL.

## 2. What changed in ipo.py (v1 kept in `skill-v1/`)

| change | where | why |
|---|---|---|
| Range history reads only filings before the cutoff | `build_target` -> `_upcoming_deep(t, dict(sub, filings=fs))` | v1 read every filing |
| Comparables' financials only from XBRL facts **filed** before the cutoff | `_pit_fund`, `_fundamentals(known_by=)` | v1 let a comparable use a period ending up to 120 days after its own IPO (CSQR's comp SPCX used a period ending after the cutoff) |
| Point-in-time target keeps periods ending >= 45 days before the cutoff | `fundamentals(lag_days=45)` | v1 gave SFD full-year 2024, published after its IPO |
| Later delisting dates hidden in point-in-time runs | `analyze` | display leak |
| Trailing 36-month base rate, always computed | `base_rate_recs`, `base_rate`, `first_range` | the verdict and pricing are anchored on it |
| Verdict vs base rate, not zero | `verdict_vs_base`, config `verdict.method = shrunk` | v1's main failure |
| Pricing anchored on the base rate (`base_alpha = 0`) + three-way headline | `blend_pricing` | the neighbor model never beat the base rate |
| Report prints p(gain), comparables' share and base rate under the verdict | `render` | so a reader sees how little the comparables move it |
| Self-test: 3 new checks (shrinkage, excess rule, pricing blend) | `selftest` | new logic |

## 3. Algorithms tried (training window, n = 39 with outcomes)

| part | candidates | train result | chosen |
|---|---|---|---|
| Flip | V0 median vs 0; V1 share-up vs base (+/- 5-20 pts); V2 shrink to base (k 5-80, delta 0-0.10); V3 V2 + recency (tau 1-4 y); base only | V0 43% vs 51% always; **V2 k40 d0.05: 60% on 15 calls (+8.7)** | V2 |
| Hold | same grid | V0 50% vs 72%; V3 k10 d0.10 tau 1: 72% on 36 (+0.4) | V3 |
| Pricing | neighbors; base only; blends 0.1-0.75 | log score neighbors -1.478, **base -1.307**, every blend worse than base | base only |
| Confidence | tertiles of distance from 50% | flip 3/5 per tier; hold 11/12, 9/12, 6/12 (inverted) | single tier |

Test window, same choices: flip V2 72.3% (47 calls) vs V0 48.4%; hold V3 66.7% vs V0 65.8%; pricing base 45% (4-bucket) vs neighbors 25%, log score -1.296 vs -1.342.

## 4. Metrics, v1 vs v2 (test window, 64-65 IPOs scored)

| metric | v1 | v2 |
|---|---|---|
| Flip calls / hit (90%) | 32 / 50.0% (34-66%) | 47 / **72.3% (62-83%)** |
| Flip FAVORABLE calls | 23 | 0 |
| Hold calls / hit (90%) | 40 / 67.5% (55-80%) | 42 / 66.7% (55-79%) |
| Best always-rule (flip / hold) | 68.8% / 67.2% | 69.2% / 66.2% |
| Pricing exact bucket | 26.8% | 45.0% |
| Avg probability on the bucket that happened | 0.285 (base rates 0.305) | 0.295 (base rates 0.311) |
| Valuation OVERVALUED, median day-180 | -33% (n=2) | -33% (n=3); FAIRLY VALUED -17% (n=15) |
| Caution level set | 3/64 | 3/65 |
| Unclassified archetype | 84% | 86% |
| Comparables without price data | 37% | 37% |
| Median seconds per analysis (warm) | 7.4 | 6.2 |

## 5. The 5 cases, v2 (frozen in `freeze-v2.txt`, audit PASS)

| ticker | flip v2 (v1) | actual d5 | hold v2 (v1) | actual d180 | pricing v2 (v1) | actual |
|---|---|---|---|---|---|---|
| KLAR | MIXED (MIXED) | -0.3% | MIXED (UNFAV ✅) | -66.4% | inside (above ✅) | above |
| SFD | MIXED (FAV ✅) | +3.7% | UNFAV ❌ (UNFAV ❌) | +12.7% | inside (mid) | below |
| NIQ | UNFAV ✅ (UNFAV ✅) | -7.1% | MIXED (MIXED) | -12.8% | inside ✅ (above) | mid |
| CSQR | UNFAV ❌ (MIXED) | +3.2% | UNFAV (MIXED) | n/a yet | inside (above) | below |
| LYNX | MIXED (MIXED) | -9.6% | UNFAV (MIXED) | n/a yet | inside (above) | below |

Cases are worse for v2 (flip 1/2 vs 2/2, hold 0/1 vs 1/2, pricing 1/5 both). Five cases are too few to weigh against 65, but they show the trade: v2 gave up v1's two right calls that went against the base rate.

## 6. What v2 is, plainly

v2 is mostly the base rate, applied consistently and leak-free: most IPOs fall after the open, and most price inside their range. It removes v1's 19-point flip deficit and stops claiming confidence it cannot back, but its edge over "always unfavorable" (+3 pts flip, +0.5 hold) is inside the noise: the flip interval (62-83%) contains the 69% baseline. The comparables add little: they only tip a call when the base rate is near 50%.

## 7. Gaps still open, ranked

1. **No edge yet beyond the base rate** (bar a). Next candidates, to be tested on a fresh window: condition the base rate on market regime (IPO ETF momentum, VIX), on deal features known before pricing (range raised/cut, upsizing, float), and on the analyst-layer book-coverage signal (Klarna's "8x" was the one pre-pricing tell in the cases).
2. **Pricing can only tie "always inside"** (bar c). The bar compares a 4-way pick with a 2-bucket baseline; a model needs to spot out-of-range deals before pricing. Range revisions in S-1/A amendments (already parsed) are the obvious next input.
3. **Archetype layer still 86% unclassified** and **29% of IPOs are dropped** (missing share counts for dual-class, missing cover prices). Not touched in v2.
4. **Survivor bias**: 37% of comparables have no price data.
5. **Caution level** set in 3 of 65.
6. Residual: XBRL pre-IPO periods are approximated by the 45-day rule, not by the S-1 itself.

## 8. Limits

Training window has 39 IPOs with outcomes; selection on it is noisy. The test window is the same one v1 was scored on (needed to compare), so it is out-of-sample for the parameters but not new data for this study. Hindsight on 2025 cases as before. Not financial advice; history, not a prediction.

Files: `plan-v2.md`, `algo_choice.json`, `bt2_train.jsonl`, `bt2_test.jsonl`, `bt_rows_v2.jsonl`, `metrics-v2.json`, `cases-v2/`, `freeze-v2.txt`, `skill-v1/`, `driver/`.
