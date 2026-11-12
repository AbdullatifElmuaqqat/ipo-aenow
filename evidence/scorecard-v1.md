# ipo-analyst — performance scorecard (2026-11-10)

## 1. Verdict: **DO NOT PUSH as a decision tool** (fine to commit as research code, labeled experimental)

| pre-registered bar | result | pass? |
|---|---|---|
| (a) flip AND hold each beat the best "always" rule by ≥ 5 pts, n ≥ 60 | flip **50.0%** vs 68.8% (always unfavorable): **−18.8 pts**. Hold **67.5%** vs 67.2%: **+0.3 pts**. n = 64 | ❌ |
| (b) every confidence level with ≥ 5 calls right ≥ 55%, and high ≥ medium ≥ low | flip low 47% (19 calls) < 55%. Hold high 57% < medium 89% | ❌ |
| (c) pricing bucket beats "always inside the range" | **26.8%** vs **68.3%** (n = 41) | ❌ |
| (d) leakage audit passes | PASS **only through the eval driver**: ipo.py as written leaked in 2 of 5 cases (see gaps 1–2) | ✅ (with fixes) |

## 2. Metrics (full backtest, 64 IPOs first-traded 2024-11 to 2026-05, point-in-time, seed 19)

| metric | value |
|---|---|
| Flip (day 5 from open): calls / call rate | 32 / 50%; 23 of 32 calls FAVORABLE |
| Flip hit rate (90% bootstrap) | 50.0% (34%–66%) |
| Flip baselines | always unfavorable 68.8%, always favorable 31.3% |
| Flip by confidence | high 2/4 (50%), medium 5/9 (56%), low 9/19 (47%) |
| Hold (day 180 from open): calls / call rate | 40 / 62.5%; **38 of 40 calls UNFAVORABLE** |
| Hold hit rate (90%) | 67.5% (55%–80%) |
| Hold baselines | always unfavorable 67.2%, always favorable 32.8% |
| Hold by confidence | high 8/14 (57%), medium 8/9 (89%), low 11/17 (65%) |
| Pricing bucket hit / always-inside | 26.8% / 68.3% |
| Avg probability given to the bucket that happened | 0.285 vs 0.305 for plain base-rate frequencies (worse than no model) |
| Model's top pick vs reality | picked "above" 13×, actual "above" 8×; picked "mid" 22×, actual mid 18× |
| Valuation label vs median day-180 | OVERVALUED −33% (n=2), FAIRLY VALUED −20% (n=19), UNDERVALUED −13% (n=3), MIXED +2% (n=6): not monotonic |
| Caution level set | 3 of 64 (5%); weak level 22 of 64, day-5 median −13% above it vs −11% below: no separation |
| Archetype coverage | **84% unclassified**, consumer 6, profitable 3, hyper-growth 1 |
| Comparables without price data | 37% on average (survivor bias) |
| Speed | warm cache 7.4 s median per full analysis, 11.1 min for 66 IPOs; cold first run 191 s |

Previous 25-IPO backtest (ipo.py's own): flip 54% vs 64%, hold 62.5% vs 60%. Same picture at 2.6× the sample.

## 3. The 5 case replays (S-1/A facts, strict cutoffs, frozen before outcomes — `freeze.txt`)

| ticker | group | archetype | snap | flip (conf) | d5 open | hold (conf) | d180 open | valuation | pricing pick → actual | result |
|---|---|---|---|---|---|---|---|---|---|---|
| KLAR | known | profitable* | A / B | MIXED (low) | −0.3% | UNFAV (low) | −66.4% | fairly valued | above → **above** ✅ | hold ✅ |
| SFD | known | consumer | A / B | FAV (**high**) | +3.7% | UNFAV (**high**) | +12.7% | undervalued | mid/top → **below** ❌ | flip ✅ hold ❌ |
| NIQ | known | unclassified | A / B | UNFAV (low/med) | −7.1% | MIXED | −12.8% | mixed | above → **mid** ❌ | flip ✅ |
| CSQR | blind | unclassified | A / B | MIXED | +3.2% | MIXED / FAV (low) | n/a yet | mixed / undervalued | above → **below** ❌ (gave it 0–2%) | — |
| LYNX | blind | profitable | A / B | MIXED | −9.6% | MIXED | n/a yet | fairly valued | above/mid → **below** ❌ | — |

*Klarna counts as "profitable" only because consumer deposits inflate its operating cash flow (gap 5).
Cases: flip 2/2 right on calls (SFD, NIQ), hold 1/2, pricing 1/5 (always-inside would get 1/5). Known vs blind: the blind pair got **no** flip or hold calls, so there is nothing to compare; n is too small to detect hindsight either way.
Analyst layer (news): book coverage was verifiable before pricing (2 sources) only for Klarna ("8× oversubscribed"), which then priced above range. NIQ "7×" had one source ([unverified]). No pre-cutoff source for SFD, CSQR, LYNX, or any retail-platform or indicated-open signal.

## 4. Gaps, ranked by impact

| # | gap | evidence | root cause | type |
|---|---|---|---|---|
| 1 | **No edge over "IPOs usually fall"** | Hold calls are 95% UNFAVORABLE, so hold ≈ the always-unfavorable rule (+0.3 pts). Flip calls lean FAVORABLE (23/32) in a sample where 69% fell by day 5 → −18.8 pts | `verdict()` ipo.py:987 compares the comparables' median with **zero**, not with the recent base rate; comparables span 10 years (`lookback_years`), incl. the 2020–21 boom | rule |
| 2 | **Point-in-time leaks in ipo.py** | Audit failed: NIQ range history included a cutoff-day filing; CSQR comparable SPCX used 9-month financials ending 2026-09-30; LYNX flip changed FAVORABLE → MIXED once fixed | `_upcoming_deep` ipo.py:1386 ignores as_of; `stage_a` ipo.py:700 grace=120 is relative to the comparable's IPO, not the analysis date; `_fundamentals` ipo.py:424 keeps periods ending before the date even if disclosed after (SFD target got FY2024, published after its IPO) | leakage |
| 3 | **Pricing model worse than base rates** | 26.8% vs 68.3% inside; avg p on the truth 0.285 < 0.305 for base rates; CSQR "below" given 0–2% | `pricing_sim` ipo.py:1131: neighbors are similar on range width / momentum / float but carry no recency or regime weight; `argmax` of 4 buckets favors the tails | calibration |
| 4 | **Confidence labels uncalibrated** | Hold "high" 57% < medium 89%; SFD hold wrong at "high"; flip "high" 2/4 | `verdict()` ipo.py:995–1000: confidence from n, CI and leave-one-out only, never checked against hit rates | calibration |
| 5 | **Archetype layer mostly inactive** | 84% unclassified in the backtest; Klarna "profitable" via deposit cash flow; NIQ growth 0.4% (one quarter annualized) vs 19% full year | `archetype()` ipo.py:1047 needs XBRL financials that pre-IPO targets lack; `fcf_margin` ipo.py:1034 treats lender deposits as operating cash; SKILL.md step 1 "prefer the most recent period" | data / rule |
| 6 | **Universe drops the biggest IPOs** | 66 of 231 2025 filings (29%) lack a share count (37) or a cover price (29): CRWV, FIG, CRCL, CHYM, STUB, GEMI, NTSK, MDLN | `_derive` ipo.py:771 (no multi-class share sum), `parse_cover` price; backtest filter ipo.py:1762 | data |
| 7 | **Survivor bias** | 37% of comparables have no price data; untestable IPOs (delisted) never enter the backtest | Yahoo-only prices (ipo.py:514); filter ipo.py:1762 | data |
| 8 | Caution level almost never set | 3/64; weak level shows no separation | n ≥ 15 per threshold rarely met with 40 comparables (`reference.min_n`) | rule |
| 9 | Future facts shown in reports | comparables' later delisting dates appear in replays | `stage_b` ipo.py:753 reads all later filings | leakage (display only) |

Speed is not a gap: 7 s warm per analysis.

## 5. Top 5 improvements (described, not implemented)

1. **Fix the three leaks in ipo.py** (filter `_upcoming_deep` by `ref_date`; cap comparables' financial periods at the analysis date; store XBRL `filed` and require filed < date). Moves: bar (d) without the driver. Test: rerun `freeze.py` on cases built by plain ipo.py.
2. **Judge against the base rate, not zero.** Call FAVORABLE/UNFAVORABLE only when the comparables differ from the trailing 12–24-month all-IPO median (`baseline()` already computes it), and weight comparables by recency. Moves: flip/hold hit rate minus best baseline (bar a). Test: same 64-IPO backtest.
3. **Calibrate or drop confidence.** Map confidence to backtested hit rates per level and hide "high" until it has ≥ 10 calls at ≥ 65%. Moves: bar (b). Test: by-confidence table.
4. **Replace the pricing argmax with base-rate-anchored probabilities** (start from the last 24 months' bucket frequencies, shift by neighbors, report the most likely bucket only if it beats "inside"). Moves: bar (c), avg p on truth > 0.305. Test: pricing block of `score.py`.
5. **Fix coverage: dual-class share counts, cover-price fallback, lender rule, and S-1 table parsing for pre-IPO targets.** Moves: unclassified share (84% → < 30%) and testable share of 2025 filings (18% → > 50%). Test: `select_cases.py` drop counts and the backtest archetype table.

## 6. Limits

- 64 IPOs: the flip interval (34%–66%) is wide, but even its top barely reaches the 68.8% baseline.
- Hold is scored at day 180; blind 2026 cases have no day-180 result yet.
- Survivorship: delisted IPOs are missing from both the test set and the comparables.
- Residual leak not removable in the backtest: targets' and comparables' pre-IPO financials come from XBRL filed after their IPO (gap 2, third cause). The 5 cases avoid it with S-1 facts.
- Hindsight: Claude knows 2025 outcomes, and the news searches surfaced CSQR's and LYNX's results; script outputs (all scored numbers) were computed before those searches and frozen by hash.
- Not financial advice; history, not a prediction.

Files: `plan.md`, `cases.json`, `facts/`, `cases/`, `freeze.txt` (and `freeze-v1-FAILED.txt`), `actuals.json`, `bt_rows.jsonl`, `metrics.json`, `backtest-previous.json`.
