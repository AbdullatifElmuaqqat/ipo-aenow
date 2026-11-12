# ipo-analyst v3 — scorecard (2026-11-11)

## 1. Verdict: **PUSH AS EXPERIMENTAL** — the flip side now shows an edge; the hold side should be switched to the base rate

| pre-registered bar (`plan.md`) | v1 | v2 (64 IPOs) | **v3 (404 IPOs, 2020-25 walk-forward)** |
|---|---|---|---|
| (a) flip AND hold beat the best always-rule by >= 5 pts | ❌ -18.8 / +0.3 | ❌ +3.1 / +0.5 | ❌ flip **+9.7** ✅ (58.5% vs 48.8%) · hold **-1.2** ❌ (65.4% vs 66.6%) |
| (b) confidence levels with >= 5 calls >= 55% | ❌ | ✅ (one tier) | ✅ flip 58.5%, hold 65.4% (one tier) |
| (c) pricing bucket beats "always inside" | ❌ 27% vs 68% | ❌ 45% vs 70% | ❌ (unchanged; the 2 replays: neighbors were right, base rate wrong) |
| (d) leakage audit | driver only | ✅ native | ✅ native (see the 424B4 note in section 6) |

## 2. What v3 added (this session)

| change | effect |
|---|---|
| Coverage: wider cover-price patterns, multi-class share counts from the prospectus, XBRL share-count de-duplication, one-time cache re-read | testable 2025 IPOs **42 → 68** of 231; CoreWeave, Figma, Chime, Circle, Netskope, StubHub, Gemini now in; Chime / Netskope no longer double-counted |
| Decision-time signals (priced vs range, IPO ETF 20d, VIX, opening jump), one shrunk log-odds step each, no tuning | walk-forward: **no gain over the base rate**, kept descriptive (`anchor: false`) |
| Decision table at day 1 / 3 / 5 / 30 / 90 / 180 and **twin IPOs** (same setup) | context; on Figma the twins and the "> 25% open" column matched the real path (up early, down later) |
| "What it means" line after every section; **Bottom line** with an evidence table and a fixed-rule lean per horizon | readability; the lean follows the tested verdict |
| Forward paper log + `--coverage` field + `forward` command | the untouched test for the next 6-12 months; order-book coverage now recorded |
| Self-test: multi-class shares, cover price, signal steps | 17 check groups pass |

## 3. Walk-forward 2020-2025 (each IPO scored by a model that never saw it)

**The skill's verdict** (look-alikes shrunk to the base rate), 404 IPOs:

| | Brier verdict | Brier base rate | paired diff (90%) | years better | hit on calls | always-unfavorable | McNemar p |
|---|---|---|---|---|---|---|---|
| Flip (day 5) | **0.2452** | 0.2491 | -0.004 (-0.0085 .. +0.0006) | **6 of 8** | **58.5%** (195 calls) | 48.8% | 0.10 |
| Hold (day 180) | 0.2427 | **0.2349** | +0.0078 (+0.0012 .. +0.0145) | 3 of 8 | 65.4% (185 calls) | 66.6% | 0.003 (worse) |

Returns from following the calls (from the open): flip FAVORABLE **+5.8%** at day 5, UNFAVORABLE **-4.6%**, every IPO +2.0%. Hold FAVORABLE (7 calls) **-29.7%**, every IPO -10.2%.
Caveat: the verdict's settings were picked on 2023-11 .. 2024-11; the clean years 2020, 2021, 2022 and 2025 all improved on flip.

**The signals** (401 IPOs): base rate 0.2479 / 0.2396 (day 5 / 180); + pricing, ETF, VIX 0.2501 / 0.2415; + opening jump 0.2510 / 0.2412. Better in 2 of 6 years: not adopted.

## 4. Replays: Figma and SpaceX (`replay-v3/comparison.md`)

| | Figma | SpaceX |
|---|---|---|
| Flip | UNFAVORABLE ❌ (+6.3%) | UNFAVORABLE ❌ (+23.3%) |
| Hold | MIXED, actual -66.5% (should have been a skip) | UNFAVORABLE, -4.6% so far (open) |
| Pricing | "inside" ❌, priced above (neighbors said 77% above ✅) | range not parsed |
| Valuation | fairly valued at $33; opened at $85 (not re-checked at the open) | overvalued 94x sales |
| Twins / at-open table | ✅ up early, down later | flip ❌ |

## 5. Gaps, ranked

1. **Hold uses the comparables and it hurts** (Brier worse, FAVORABLE holds -29.7%). Fix: hold = base rate only (`d180.shrink_k` very large). Not applied (test-only session).
2. **Hot deals get called UNFAVORABLE on the flip** (Figma, SpaceX). The demand signal the neighbors see is switched off; a re-test of "neighbors say > 70% above" as a flip input is the next experiment.
3. **No valuation at the opening price.** Retail buys at the open; Figma at $85 was a different stock from Figma at $33.
4. **Pricing can only tie "always inside"** (bar c).
5. **Coverage left**: 86% of IPOs unclassified (S-1 tables not parsed), 37% of comparables without prices (no takeover prices), SpaceX's range not parsed, ~8 IPOs a year still lack a share count or price.
6. **Caution level** almost never fires (not even on a +158% open).

## 6. Notes
- A line in `build_target` that this session did not write lets a point-in-time run use a 424B4 filed up to 3 days after the cutoff. Fair at the open (terms set the evening before), a leak for a pre-pricing view; the replays blocked it in the driver.
- The 2024-26 window has now been looked at three times; the forward log is the clean test from here.
- History, not a prediction; not financial advice.
