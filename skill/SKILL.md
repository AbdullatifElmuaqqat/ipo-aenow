---
name: ipo-aenow
description: Researches any US IPO (upcoming, pricing, or in its first 30 trading days) from its own SEC filings and from history, and gives a walk-forward-tested read for a first-week flip and a six-month hold. Reads the S-1 summary table and writes a plain-English company brief, forecasts where it prices vs its range (from deals whose range moved the same way), values it at the IPO price and at the opening price, compares it with look-alike and same-setup twin IPOs, simulates outcomes from day 1 to month 6 from real past paths, and ends with a five-question summary and a fixed-rule overall read (flip candidate / hold candidate / skip / no clear lean). Can replay any past IPO point-in-time. Use this whenever the user asks about an IPO, a company going public, IPO flipping, whether an IPO is a good buy or overvalued, an IPO's price range, pricing odds or first-day pop, lockups, or "stocks like X when they went public", even if they don't say "skill".
---

# ipo-aenow (IPO analyst)

Answers: *what kind of IPO is this, how did the closest past IPOs of that kind do, where is it likely
to price, and is it priced rich or cheap?* It is history, not a prediction. Retail buyers usually get
the first open, not the IPO price, so returns are shown from both.

Script: `python .claude/skills/ipo-aenow/scripts/ipo.py` (run from the Trading folder; standard
library only). It does all fetching and maths. You interpret and write; never compute a number by
hand. Every number in the report must come from the script, a filing, or a page you opened.

## Commands

| command | what it does |
|---|---|
| `analyze TICKER\|"Company"` | full analysis (all sections below) |
| `comps TICKER` | comparables and verdicts only (faster) |
| `day1 TICKER` | first-day intraday signals 29-34 (Yahoo intraday, up to ~60 days old) |
| `backtest [--limit N\|--all]` | re-runs the method on IPOs from 6-24 months ago, point-in-time; writes `trader/state/ipo-backtest.json` |
| `analyze TICKER --as-of YYYY-MM-DD --mode pre-pricing\|at-open` | replays a past IPO point-in-time (pre-pricing hides the final prospectus; at-open allows the 424B4 filed up to 3 days later, whose terms were set the evening before); never logged |
| `regress` | fixed regression set in `tests/regression.json`: S-1 parser vs 8 hand-read facts, verdict math on 30 frozen IPOs, 2020-25 scoreboard. Run before and after every change |
| `forward` | scores the forward paper log (`trader/state/ipo-forward-log.jsonl`): every live `analyze` of an untraded IPO is logged, then checked once it trades |
| `clean` | empties the cache (`%LOCALAPPDATA%\ipo-analyst\cache`, outside OneDrive) |
| `--selftest` | offline checks |

Flags: `--json`, `--save` (writes `trader/reports/ipo-<TICKER>-<date>.md`), `--facts FILE`,
`--drop CIK:reason`, `--add CIK:reason`, `--coverage "8x; Bloomberg 2026-09-09; Reuters 2026-09-09"`
(order-book coverage, logged so it can be tested once a year of history exists), `--no-log`.
A full `analyze` takes 1-4 minutes when the cache is warm (the decision table reads 10 years of deals).

Archetype matching reads the cover page of every US IPO in the last 10 years the first time (often
20-40 minutes); run it in the background and say so. Later runs use the 30-day cache. SEC needs
`sec_user_agent` in `trader/config.json`.

## Steps

1. **Run** `ipo.py analyze TICKER --json` in the background. Without `--facts` the script now reads the latest
   S-1/A summary table itself (`fund.source` says so); check revenue, prior-year revenue and operating income
   against the filing. If it could not read them, or they look wrong, open the S-1's summary financial table and
   cash-flow statement, write a JSON with
   `rev0`, `rev1` (same-length period a year earlier), `gross`, `opinc`, `cfo`, `capex`, `cash`, `debt`
   (US dollars as filed) and `period_months` (12 for a fiscal year, 9 for nine months; the script
   annualizes), then rerun with `--facts that.json`. Prefer the most recent period. Say which one.
2. **Fill the news signals** the script leaves open: #9 book coverage / oversubscription, #10 retail
   platforms, #29 indicated opening price, the pricing and first-trade dates. Use
   `/day-trader-skill:trader-news` and web search. Count a claim only when **two independent
   sources** agree; otherwise mark it `[unverified]` with the one source. Open a story before using it.
   When coverage is verified, rerun with `--coverage "...; source 1; source 2"` so the forward log keeps it.
3. **Check the archetype.** If the rule picked the wrong one because a number is missing, fix the
   `--facts` input; do not override the rule by hand.
4. **Review the comparables.** Remove one only with a stated reason, or add one only by naming the
   feature the score missed (`--drop` / `--add`, logged in the output). Don't reshuffle to get a nicer answer.
5. **If it already trades**, run `day1` and add signals 29-34.
6. **Closest peer and top 5 stories:** situation at IPO -> first days -> today, with links. For an
   acquisition or delisting, open a source for buyer and price or mark it `[unverified]`.
7. **Write the report** with the template below and save it to `trader/reports/ipo-<TICKER>-<date>.md`.
8. **Chat summary = the summary report.** `analyze TICKER --summary` prints it and `--save` also writes it to
   `trader/reports/ipo-<TICKER>-<date>-summary.md` next to the full report. Reply in chat with it, in this order:
   verdict tags (Flip · Hold · Valuation · Overall), the 30-second answer, the five questions, key numbers
   (8 rows), what could happen (1 day / 1 week / 1 month / 6 months: chance up, median, bad case, good case),
   demand and hype, what to watch next, how much to trust it, and the link to the full report. Under "Demand and
   hype" add the step-2 news (book coverage, retail platforms, indicated open, notable coverage) with two
   sources each, or [unverified]. Use only numbers that are in the report. Keep it under ~500 words. The five
   questions, always in this order:
   1. **What is this company?** what it sells, its type, revenue and growth, who controls it, lockup, its top risk.
   2. **Is the price fair?** valuation vs look-alikes, and the open price above which it is among the priciest IPOs.
   3. **Where will it price, and how might it trade?** pricing odds, chance of a gain by day 5 and month 6 vs all
      recent IPOs, simulated medians and the bad case, plus verified demand / hype news.
   4. **So what?** the overall read (flip candidate / hold candidate / skip / no clear lean): history, not advice.
   5. **Can I trust it?** match quality, missing data, sources, and how close the rules are to the base rate.

## Report template

Under ~1,100 words plus tables, in this order. **Every section ends with one "What it means" line**
(the script prints it: good sign / bad sign / mixed / neutral, in plain words). Keep it; a reader
should never have to guess why a section is there or which way it points.

1. **Verdict line**: Flip ... (confidence) · Hold ... (confidence) · Valuation: OVERVALUED / FAIRLY
   VALUED / UNDERVALUED / MIXED vs comparables. Then the backtest hit rate at that confidence level
   and the base rate it has to beat (from `track_record`; if none, say so).
1b. **Decision table**: chance of a gain from the open at day 1 / 3 / 5 / 30 / 90 / 180 for all recent
   IPOs, for this setup before the open, and for each opening-jump group. Say it is descriptive: tested
   2020-25, these adjustments did not beat the base rate.
1c. **Twin IPOs**: past deals with the same setup, % up and median at each horizon next to all recent
   IPOs, and the 10 most recent twins.
2. **Archetype**: which of the four, the rule values that put it there, matching mode, pool size, and
   whether the pool had to be widened.
3. **Closest peer head-to-head**: metrics table (revenue, growth, FCF margin, float, P/S at IPO) and
   the peer's day 1 / 5 / 30 / 180 returns from the open.
4. **Pricing probability matrix**: below / inside / top / above the first filed range, with 90%
   intervals, neighbors used, and the line "order-book coverage is not modelled" plus the coverage
   news from step 2 shown beside it.
5. **Valuation check**: P/S, P/S per point of growth, Rule of 40, each vs the comparables' median with
   rank and read, the overall label, and the prices at which P/S would equal the comparables' median
   and 75th percentile ("what the comparables imply, not a fair value").
6. **Signal scorecard** (selected rows): # | signal | value | direction | source.
7. **Comparables table** (top 12): company | IPO | similarity | open vs IPO | d1 | d5 | d30 | lockup | today,
   then the closest 5 as 3-line stories.
8. **Pattern**: weighted medians with 90% intervals, % green, leave-one-out flags, and the baselines.
9. **Opening-price caution level**: the open premium above which past comparables' day-5 median was
   clearly negative, and the same level in this IPO's prices; or the weak-evidence level; or "not
   enough evidence".
10. **What decided each verdict**: 3 facts each, and what would flip each one.
11. **Reference checklist** (history, not advice): the caution-level prices, the re-run triggers
    (new S-1/A, a raised or cut range, the 424B4, the first trade), and the market-vs-limit-order note.
12. **Failed sources, [unverified] items, comparables without price data.**
12b. **The company in plain English**: overview, who controls the vote, lockup, use of proceeds, the first risks from
    its own risk summary, and the calendar (quiet period, estimated first earnings, lockup expiry, seasoning).
12c. **Valuation at the opening price**: P/S if it opens at +0 / +25 / +50 / +100 / +150%, ranked against past IPOs at
    their open, and the most-expensive-quarter open price (tested: worse at 6 months in 5 of 6 years).
12d. **Outcome simulation**: 10,000 draws of real past paths for all recent IPOs, twins and look-alikes, at 1 day,
    3 days, 1 week, 2 weeks, 1 month, 3 months, 6 months: percentiles, chance up, >= +20%, <= -20%.
12e. **Sources**: the prospectus used, the financials source, filing index, prices, comparables' prospectuses.
13. **Bottom line** (the script prints it): the evidence table (verdict, base rate, look-alikes, twins,
    valuation, pricing, each with its day-5 and day-180 read and whether it is tested), the good and bad
    signs, then one fixed-rule lean per horizon: **LEANS SKIP** (verdict UNFAVORABLE, or overvalued and
    not FAVORABLE), **WORTH A CLOSER LOOK** (FAVORABLE and not overvalued), or **NO CLEAR LEAN**, with
    how many other parts agree, then one **Overall read**: FLIP CANDIDATE, HOLD CANDIDATE, SKIP, NO CLEAR FLIP /
    HOLD LEANS SKIP, or NO CLEAR LEAN, plus the open-price line for a long hold. The lean follows the tested verdict only. It is a summary of history,
    never a buy/sell call: say so, and say how close to the base rate the rule's record is.

End with: history, not a prediction; retail usually buys at the open; not financial advice.

## How it works (so you can explain it)

- **Archetypes**, first rule that fits (thresholds in `ipo-config.json` -> `archetypes`):
  1. Hyper-growth / capital-intensive: revenue >= $1B and growth > 50% (capex intensity is reported;
     cloud compute bought as an operating cost does not show up as capex).
  2. High-margin SaaS / software: gross margin > 70% and NRR > 110% (NRR is read from the S-1; when not
     disclosed, a software industry code counts instead).
  3. Profitable / moderate growth: free cash flow > 0 and growth 15-40%.
  4. Consumer / marketplace / hardware: by industry code.
  Otherwise *unclassified*, which falls back to same-industry matching.
- **Nearest neighbors**: within the archetype, across all industries, distance on z-scored log
  revenue, growth, FCF margin and float (`knn_weights`), blended 80/20 with prospectus-text
  similarity (`weights_archetype`). If fewer than 30 IPOs share the archetype, same-industry IPOs are
  added and the report says so.
- **Base rate**: every run computes the trailing 36-month base rate for all US IPOs >= $200M (share up at
  day 5 and day 180 from the open, and where deals priced vs their first range), cut at the reference date.
- **Pricing** (`pricing.method = revision`): the trailing 36-month base rate of deals whose range moved the
  same way before pricing (raised / cut / unchanged, first vs last S-1/A range), with a three-way headline
  (below / inside / above). Walk-forward 2020-25: log score -1.105 vs -1.353 for the plain base rate, better
  in 6 of 6 years. The neighbor Monte Carlo is still shown as `neighbor_probabilities`, not used.
  "Above" means above the *first* filed range. A fixed expected price (no range, e.g. SpaceX) is read as a
  one-point range. Order-book coverage is not a model input.
- **Valuation at the open**: P/S at the opening price vs past IPOs' P/S at their own open (10 years). The open
  price that would put it in the most expensive quarter is the line to report; tested 2020-25, IPOs above
  it were less often up by day 180 in 5 of 6 years.
- **Outcome simulation**: 10,000 seeded draws of whole past paths (all recent IPOs, twins, look-alikes).
  Descriptive: it shows the spread of outcomes, it is not a model fit.
- **Delisted look-alikes**: the takeover price from the merger proxy or tender offer (or -100% for a
  bankruptcy 8-K) fills their "today" value only; day-5 and day-180 still need prices.
- **S-1 parser**: reads the summary table (units, interim vs annual columns, the most recent period and the
  same period a year earlier). Regression set: 8 of 8 filings match hand-read revenue and operating income.
- **Valuation**: the IPO's P/S (at the final price, or the range midpoint) ranked among comparables
  valued at their own IPO price. Rich >= 75th percentile, cheap <= 25th. OVERVALUED needs rich on both
  P/S and P/S-per-growth-point; MIXED when they disagree.
- **Verdicts** (`verdict.method` = `shrunk`): the chance of a gain from the open (flip: day 5, hold: day
  180) is the comparables' similarity-weighted share of gains, shrunk toward the base rate:
  p = (n_eff x comps + k x base) / (n_eff + k) for the flip (k = 40). The **hold uses the base rate alone**
  (`by_horizon.d180.method = base`): in the 404-IPO walk-forward the comparables made day 180 worse
  (Brier 0.2427 vs 0.2349). FAVORABLE when p > 0.5 + delta (flip 0.05, hold 0.10), UNFAVORABLE below 0.5 - delta, else MIXED.
  Walk-forward 2020-25 (404 IPOs, `scorecard-v3.md`): flip right 58.5% on calls vs 48.8% always-unfavorable,
  better than the base rate in 6 of 8 years, favorable calls +5.8% at day 5 vs +2.0% for all IPOs.
  Because the base rate is low (about a third of IPOs are up by day 5), the rule rarely says FAVORABLE.
  Report p, the comparables' share and the base rate (printed under the verdict line).
  Confidence is always "low": on the training window, distance from 50% did not rank right from wrong.
  `method: zero` restores the v1 rule (median vs zero), which did worse than "always unfavorable".
  Track record (2026-11 evaluation, `trader/reports/ipo-eval/scorecard-v2.md`): flip 72% on 47 calls vs
  69% always-unfavorable; hold 67% vs 66%. That is close to the base rate, not a proven edge: say so.
  The verdict ignores the signals and the pricing simulation on purpose, so the backtest measures one
  fixed rule.
- **Decision-time signals** (`signals`, shown, not used by the verdict: `anchor: false`): where it
  priced vs the first range, IPO ETF 20-day move, VIX < 20, and the opening jump (< 0 / 0-25% / > 25%).
  Each adds one log-odds step to the base rate: (logit(group share up) - logit(all)) x n/(n+50), from
  10 years of deals known before the date. Walk-forward 2020-25 (401 IPOs, each scored by a model that
  never saw it, `trader/reports/ipo-eval/scorecard-v3.md`): Brier 0.2501 / 0.2510 with signals vs
  0.2479 for the base rate alone at day 5, better in only 2 of 6 years; same at day 180. So they stay
  descriptive. Re-test before ever setting `anchor: true`.
- **Twin IPOs**: past deals whose known signals all match this one exactly. Context, same evidence
  as the signals.
- **Forward test**: `trader/state/ipo-forward-log.jsonl` is the untouched test. Do not retune the
  rules on the 2020-25 data again; judge changes on the forward log after 6-12 months.
- **Caution level**: on a grid of open premiums (0% to +100%), the first level where comparables that
  opened at or above it had a negative day-5 median with n >= 15 and an interval below zero.

## Limits to state when they matter

- Point-in-time runs (`backtest`, `as_of`) use only filings and prices dated before the cutoff; a target's
  XBRL financials must end >= 45 days before it, and comparables' financials must be filed before it.

- Comparables' financials come from SEC XBRL filed after their IPO (pre-IPO periods); for an IPO under
  a year old, the longest year-to-date period, annualized.
- Companies that left the market usually have no Yahoo prices, so their outcomes are missing.
- Current peer multiples need a Yahoo login, so valuation compares with comparables at their own IPO.
- When nothing in history resembles the IPO (say, a $1T company), the archetype pool is thin and the
  similarity scores show it: say so plainly.

## Security and scope

- Tools it needs: Bash to run `python .claude/skills/ipo-aenow/scripts/ipo.py`, Read / Write for reports, and web
  search / fetch for the news step. No other tools, no installs, no dependencies beyond the Python standard library.
- Network: HTTPS GET only, to `www.sec.gov`, `data.sec.gov`, `efts.sec.gov`, `query1/2.finance.yahoo.com`
  (enforced in `http_get`; anything else is refused). Nothing about the user is sent except the SEC contact
  (`sec_user_agent`), which SEC requires in the User-Agent header and which goes to sec.gov hosts only.
- Files written: the cache under `%LOCALAPPDATA%\ipo-analyst\cache`, and `trader/reports/`, `trader/state/`
  (backtest results, forward log). No code is downloaded or executed; filings are parsed as text.

## Never

Give a recommended order price, a "cancel above" instruction, or a buy/sell call: the caution level
and comparables' prices are historical reference levels, labeled as such. Place, size or approve an
order, or call trader-broker. Invent a comparable, a signal value or an outcome. Scrape around a login
or CAPTCHA. Add dependencies or paid APIs without asking.
