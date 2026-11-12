# ipo-aenow — an IPO research skill that proves its claims

**Version 4.0.1** (2026-11). One place to understand the tool and review it; questions for reviewers are at the end.

## In one paragraph
ipo-aenow is a Claude Code skill (a Python script plus instructions) that researches a US IPO from the company's
own SEC filings and from history. It reads the prospectus, finds past IPOs that looked like it, and reports how
deals like it did from the first open (day 1, 3, 5, a week, a month, 3 and 6 months). It gives a **flip** read
(day 5), a **hold** read (day 180), where it will likely **price** against its range, whether the **price is
fair** (at the IPO price and at the opening price), a simulation of outcomes, and a fixed-rule overall read
(flip candidate / hold candidate / skip / no clear lean). It is research, not financial advice, and it says how
close its rules are to the plain base rate.

## Install
You need Claude Code and Python 3.10+ (standard library only, nothing to `pip install`).

**1. Copy the skill into your project.** Only the `skill/` folder, renamed to `ipo-aenow`:
```bash
git clone https://github.com/AbdullatifElmuaqqat/ipo-aenow.git
mkdir -p my-project/.claude/skills
cp -r ipo-aenow/skill my-project/.claude/skills/ipo-aenow
```
The result must be `my-project/.claude/skills/ipo-aenow/SKILL.md` (not `.../ipo-aenow/skill/SKILL.md`).

**2. Add your SEC contact.** SEC EDGAR refuses requests without a name and email in the User-Agent header.
Create `my-project/trader/config.json`:
```json
{"sec_user_agent": "First Last first.last@gmail.com"}
```
- Name, a space, then the email, all in one string. Examples: `"Sam Lee samlee92@gmail.com"`,
  `"Maria Garcia maria.garcia+sec@outlook.com"` (a `+sec` alias keeps it apart from your main inbox).
- Use a real address you own. Placeholders with `example.com`, or a string without `@`, are refused.
- It is sent only to sec.gov, never to Yahoo or anywhere else.
- Installed for all projects instead (`~/.claude/skills/ipo-aenow/`)? Then the file goes in `~/trader/config.json`.
- Or skip the file and set an environment variable: `SEC_USER_AGENT="First Last first.last@gmail.com"`.

If you see `ipo.py: SEC needs a contact. Create <path> ...`, the file is missing or refused; the message prints
the exact path it looked in.

**3. Check it** (from `my-project/`; on macOS / Linux use `python3`):
```bash
python .claude/skills/ipo-aenow/scripts/ipo.py --selftest
```

**4. Use it.** In Claude Code, opened in `my-project/`: `/ipo-aenow FIG`, or ask "should I flip the Figma IPO?".
Or run it directly: `python .claude/skills/ipo-aenow/scripts/ipo.py analyze FIG --summary --save`.
The first run downloads and caches about 10 years of SEC filings (20-40 minutes); later runs take 1-4 minutes.

## Security
- HTTPS GET only, to SEC EDGAR (`www.sec.gov`, `data.sec.gov`, `efts.sec.gov`) and Yahoo Finance
  (`query1/2.finance.yahoo.com`); any other host is refused in code. No code is downloaded or run.
- The only personal data sent is the SEC contact in the User-Agent header, to sec.gov only (SEC's own rule).
- Writes only its cache (`%LOCALAPPDATA%/ipo-analyst/cache`) and `trader/` in the project. `trader/` is in `.gitignore`.
- Yahoo Finance endpoints are unofficial; use them under Yahoo's terms. SEC asks for no more than 10 requests a
  second; the script stays under 5.

## What one run produces
1. A **summary report** (~700 words, also the chat reply): verdict tags, a 30-second answer, five questions
   (what is it, is the price fair, how might it price and trade, so what, can I trust it), key numbers, simulated
   outcomes, demand and hype, what to watch, trust. Example: `examples/figma-summary-pre-pricing.md`.
2. A **full report** (~6,000 words): every table, each section ending in a plain-English "what it means".
   Examples: `examples/anthropic-full-report.md`, `examples/spacex-full-report-at-open.md`.
3. A line in a **forward paper log**, scored later on what actually happened.

## How it works (data -> method)
- **Data**: SEC EDGAR (full-text search for 424B4 filings to list ~2,700 US IPOs since 2013; prospectuses; XBRL
  company facts), Yahoo Finance daily bars (prices, IPO ETF, VIX, sector ETFs). Standard-library Python only.
- **Company facts**: the S-1/A summary table is parsed automatically (units, interim vs annual columns, latest
  period vs a year earlier); a plain-English brief (business, control, lockup, use of proceeds, risks, calendar).
- **Look-alikes**: four archetypes (hyper-growth, SaaS, profitable, consumer); nearest neighbors on revenue,
  growth, cash-flow margin, float, plus prospectus-text similarity.
- **Flip verdict**: look-alikes' similarity-weighted share of gains by day 5, shrunk toward the trailing
  36-month base rate of all IPOs: p = (n_eff x comps + 40 x base) / (n_eff + 40); FAVORABLE above 55%,
  UNFAVORABLE below 45%.
- **Hold verdict**: the base rate alone (comparables made it worse in testing).
- **Pricing**: the trailing base rate of deals whose range moved the same way (raised / cut / unchanged)
  before pricing.
- **Valuation at the open**: price/sales at the opening price ranked against past IPOs at their own open; the
  open price above which it would be in the most expensive quarter.
- **Simulation**: 10,000 seeded draws of whole real past paths (all recent IPOs, same-setup twins, look-alikes).
- **Point-in-time**: any run can be replayed as of a past date (`--as-of`, `--mode pre-pricing|at-open`);
  nothing filed or priced after the cutoff reaches the result (leak audits, SHA-256 freezes before scoring).

## How well it works (walk-forward 2020-2025, each IPO scored by rules that never saw it)
| | result |
|---|---|
| Flip | right **58.5%** on its calls vs 48.8% for "always unfavorable" (404 IPOs); better than the base rate in 6 of 8 years; favorable calls averaged **+5.8%** by day 5 vs +2.0% for all IPOs |
| Hold | no edge: 63.5% vs 66.6% for "always unfavorable" (but the best probability score of everything tested) |
| Pricing | below / inside / above call right **72.6%** vs 51.3% for "always inside"; better than the plain base rate in 6 of 6 years |
| Valuation at the open | most expensive quarter at the open less often up at 6 months in **5 of 6** years |
| Rejected after testing | pricing / market / opening-jump signals inside the verdict, an all-IPO caution level, a hot-deal rule, confidence tiers |
Details: `evidence/scorecard-v1.md` .. `scorecard-v4.md`, the pre-registered plans `evidence/plan*.md`, raw results `evidence/*.json`.

## Real examples
- **Figma** (2025), as of the day before trading: pricing **above** its range (82%) - right; hold unfavorable -
  right (-66% from the open by month 6); open-price line $71.12, it opened at $85; flip unfavorable - wrong (+6%).
- **SpaceX** (2026): flagged as already among the most expensive IPOs at its $135 price; flip unfavorable - wrong (+23%).
See `evidence/figma-spacex-comparison-v3.md` and `evidence/scorecard-v4.md`.

## Known weaknesses
1. The flip edge is modest and the hold has none.
2. It calls hot, heavily demanded deals unfavorable on the flip.
3. Hype is not measured (news volume / tone, search interest, social media, retail demand); order-book coverage is logged only.
4. About a third of look-alikes have no price history (takeover prices fill only their final value).
5. One 3,000-line script; the full report is long.

## Files
- `skill/` the skill as shipped (install as `.claude/skills/ipo-aenow/`): `SKILL.md` (instructions), `README.md`, `ipo-config.json`, `scripts/ipo.py`, `tests/regression.json`.
- `evidence/` scorecards, plans written before each test, raw walk-forward results.
- `examples/` real reports.

## Questions for a reviewer
1. Is the evaluation sound? Anything that could still leak future information, or overstate the flip result?
2. What would most improve the flip on hot deals without fitting noise (we have ~400 test IPOs)?
3. How would you measure IPO hype in a way that can be tested historically?
4. Is the base-rate-shrinkage verdict a reasonable design, or is there a better simple model for this sample size?
5. What would make the report more useful to a non-expert?

## License
MIT, see `LICENSE`. Research and education only; not financial advice.
