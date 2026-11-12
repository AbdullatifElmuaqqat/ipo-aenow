# Anthropic, PBC (ANT) - IPO analysis, reference date 2026-11-11
VERDICT  Flip FAVORABLE (low; backtest 33/46 right at low)  |  Hold UNFAVORABLE (low; backtest 29/44 right at low)
  flip: chance of a gain by day 5 (from the open) 55% = comparables 78% (n_eff 22) shrunk toward the trailing base rate 42% (n=215); method shrunk
  hold: chance of a gain by day 180 (from the open) 33% = comparables 46% (n_eff 4) shrunk toward the trailing base rate 33% (n=181); method base
> **What it means (mixed):** flip: look-alike IPOs were up by day 5 78% of the time, vs 42% for recent IPOs in general; combined chance 55% (favorable); hold: look-alike IPOs were up by day 180 46% of the time, vs 33% for recent IPOs in general; combined chance 33% (unfavorable). Most IPOs fall after the open, so a call has to beat that.

## Decision-time signals (base rate + one shrunk step per signal; steps from 764 past deals)
This deal: priced = not known yet; ipo_etf = down; vix = <20; open = not known yet
| chance of a gain from the open | all recent IPOs | this setup, before the open | open below IPO price | open 0-25% above | open > 25% above |
|---|---|---|---|---|---|
| by day 1 | 41% (n=215) | 36% | 39% | 33% | 39% |
| by day 3 | 46% (n=215) | 43% | 45% | 40% | 46% |
| by day 5 | 42% (n=215) | 39% | 42% | 37% | 40% |
| by day 30 | 38% (n=211) | 38% | 37% | 38% | 38% |
| by day 90 | 34% (n=199) | 32% | 35% | 32% | 31% |
| by day 180 | 33% (n=181) | 31% | 36% | 30% | 30% |
The open columns are what history says once the first price prints; they are not targets or advice. Tested 2020-25 (day 5 and day 180): these adjustments did not beat the plain base rate, so the verdict does not use them.
> **What it means (bad sign):** before the open, the known signals move the day-5 chance from 42% to 39% (ipo_etf = down (down 0.13 log-odds), vix = <20 (down 0.00 log-odds)). The open columns show how much the first print matters: check the column it opens in.

## Twin IPOs: past deals with the same setup (ipo_etf = down; vix = <20); 185 found
| from the open | day 1 | day 3 | day 5 | day 30 | day 90 | day 180 |
|---|---|---|---|---|---|---|
| twins: % up | 39% (n=185) | 48% (n=185) | 46% (n=185) | 48% (n=182) | 37% (n=172) | 34% (n=172) |
| all recent IPOs: % up | 41% (n=215) | 46% (n=215) | 42% (n=215) | 38% (n=211) | 34% (n=199) | 33% (n=181) |
| twins: median | -1.2% | -0.6% | -0.8% | -1.1% | -9.9% | -20.3% |

Most recent twins:
| company | first trade | day 1 | day 3 | day 5 | day 30 | day 90 | day 180 |
|---|---|---|---|---|---|---|---|
| Aspen Neuroscience, Inc. (ASPE) | 2026-10-30 | +1% | -16% | -20% |   n/a  |   n/a  |   n/a  |
| CITY THERAPEUTICS, INC. (CTY) | 2026-10-16 | -3% | -9% | -10% |   n/a  |   n/a  |   n/a  |
| Iambic Therapeutics, Inc. (IAM) | 2026-10-15 | +17% | +1% | -2% |   n/a  |   n/a  |   n/a  |
| Electra Therapeutics, Inc. (ETRA) | 2026-09-18 | -12% | -9% | -21% | -42% |   n/a  |   n/a  |
| Orion180 Insurance Group Inc. (OIG) | 2026-09-18 | +1% | -9% | -14% | -14% |   n/a  |   n/a  |
| BlossomHill Therapeutics, Inc. (BLSM) | 2026-08-07 | +2% | +5% | +4% | +63% |   n/a  |   n/a  |
| Latigo Biotherapeutics, Inc. (LTGO) | 2026-08-07 | -13% | -12% | -4% | +7% |   n/a  |   n/a  |
| Braveheart Bio, Inc. (BRVE) | 2026-08-06 | -1% | -9% | -13% | -8% |   n/a  |   n/a  |
| Attovia Therapeutics, Inc. (ATTO) | 2026-08-05 | +4% | -4% | -11% | +6% |   n/a  |   n/a  |
| Apnimed, Inc. (APMD) | 2026-07-31 | +14% | +17% | +27% | +19% |   n/a  |   n/a  |
> **What it means (neutral):** 185 past IPOs had the same setup; 46% were up by day 5 vs 42% of all recent IPOs. This is context: the walk-forward found setups like this did not predict better than the base rate.
Status upcoming; price None; range [70.0, 78.0]; mcap at price n/a; filing https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm

## The company in plain English (from its prospectus)
For the first time in history, intelligence is something humans can build. The cognitive capability to reason, analyze, synthesize, decide, and create is producible at scale and accessible on demand. We believe this abundance of super intelligence 1 will rapidly transform every sector of the global economy in ways greater than the impact of industrialization, electricity, semiconductors, and the internet. If this technology truly delivers on its potential—with the risks well managed—it could significantly accelerate global growth and dramatically improve quality of life for people around the w...
- **Who controls it:** dual-class shares; a controlled company (insiders hold the majority vote); selling shareholders sell 3% of the offering
- **Lockup:** 180 days; can end early (earnings-release clause)
- **Banks:** Goldman Sachs, Morgan Stanley, J.P. Morgan, Citigroup, Barclays, Wells Fargo
- **Risk 1:** Our models have in the past behaved, and may in the future behave, in unintended, misaligned, or autonomous ways, including by taking harmful actions that no user or third party directed, which could adversely affect our reputation and brand, business, financi...
- **Risk 2:** Our success depends in large part on our ability to continue to develop the most advanced and capable AI models, and any failure to do so could adversely affect our business.
- **Risk 3:** If we are unable to secure adequate compute or if we fail to direct our compute effectively across our workloads, we may be unable to train models that remain competitive with those of our competitors or adequately serve our customers.
- **Risk 4:** Constraints on the critical inputs supporting compute could limit our ability to secure adequate compute.
- **Risk 5:** We are highly dependent on the continued service of our co-founders, senior management team, and key technical employees, and the loss of any of these individuals may adversely affect our business, financial condition, and results of operations.
> **What it means (neutral):** the facts a reader needs before any number: what it sells, who has the votes, when insiders can sell, and what the company itself says could go wrong.

## Signal scorecard
| # | signal | value | dir | source |
|---|---|---|---|---|
| 1 | Price range and revisions | 2026-11-10: $70.0-$78.0 | neutral | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=2130357&type=S-1 |
| 2 | Shares offered: launch vs final | 825000000.0 -> 825000000.0 | neutral | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=2130357&type=S-1 |
| 3 | Final price vs range | not priced yet | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 4 | Pricing pace vs comparables (days, public filing to pricing) | [not priced / not found] | neutral | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=2130357&type=S-1 |
| 5 | S-1/A amendments | 2 | neutral | https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=2130357&type=S-1 |
| 6 | Float (shares offered / outstanding) | 6.3% | + | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 7 | Greenshoe (over-allotment) shares | 123750000.0 | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm  (exercise: check later 8-K/424B) |
| 8 | Directed share program / cornerstone indications | DSP no; cornerstone yes | + | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 9 | Reported oversubscription / books covered | [needs news check: count only with 2+ independent sources] | neutral | trader-news / web |
| 10 | Retail allocation platforms (Robinhood IPO Access, SoFi...) | [needs news check] | neutral | trader-news / web |
| 11 | Lead-left bank, bank count, lead's 3-year IPO record | Goldman Sachs; 15 banks; lead median day-30 -8.2% (n=27) | - | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 12 | VC/PE-backed (text heuristic) | yes | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 13 | Selling-shareholder share of the offering | 3% | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 14 | Dual-class / controlled company | dual-class yes; controlled yes | - | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 15 | Use of proceeds | [not found] | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 16 | Lockup | 180 days; early-release clause yes | - | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 17 | Revenue growth (last FY vs prior FY) | +500% vs comparables' median +38% | + | S-1 summary table (parsed from the S-1/A of 2026-11-10) |
| 18 | Gross / operating margin | gross [n/a]; operating -4% (comps -18%) | neutral | S-1 summary table (parsed from the S-1/A of 2026-11-10) |
| 19 | Free cash flow, months of runway after the IPO | [not found] | neutral | S-1 summary table (parsed from the S-1/A of 2026-11-10) |
| 20 | Net cash after the IPO (pre-IPO cash + primary proceeds - long-term debt) | $192,895M | + | S-1 summary table (parsed from the S-1/A of 2026-11-10) |
| 21 | Customer concentration; top risk factors | no single customer > 10% of revenue; largest disclosed customer or customer-group share 25.0% (check the S-1 sentence); risks: read the S-1 Risk Factors | neutral | https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm |
| 22 | Price/sales and EV/revenue at low / mid / top / final | low P/S 20.7x EV/rev 16.3x; mid P/S 21.8x EV/rev 17.5x; top P/S 23.0x EV/rev 18.7x | neutral | S-1 summary table (parsed from the S-1/A of 2026-11-10) |
| 23 | P/S vs comparables at their own IPO price (current peer multiples need Yahoo login; not used) | 21.8x vs median 11.4x (+92%) | - | comparables (SEC + IPO price) |
| 24 | Growth-adjusted P/S (P/S / growth %) vs comparables | 0.04 vs median 0.38 | + | computed |
| 25 | Nasdaq / S&P 500 20-day return; VIX | Nasdaq -7.9%, S&P -3.6%, VIX 19.46 (15-20) | - | https://finance.yahoo.com/quote/%5EIXIC |
| 26 | IPO ETF 20-day return; last 5 US IPOs day-1 / day-5 (from IPO price) | IPO ETF -9.7%; last 5: OIG -3%/-18%, ACCV -9%/-13%, IAM +18%/-1%, CTY +24%/+15%, ASPE -1%/-22% | - | https://finance.yahoo.com/quote/IPO |
| 27 | Sector ETF (XLK) 20-day return | -13.9% | - | https://finance.yahoo.com/quote/XLK |
| 28 | Other US IPOs pricing the same week | 0 | neutral | SEC full-text search (424B4) |
| 29 | Indicated opening price vs IPO price | run `ipo.py day1` once it trades (29: needs news check) | neutral | Yahoo intraday |
| 30 | Minutes from 9:30 to first trade | run `ipo.py day1` once it trades | neutral | Yahoo intraday |
| 31 | Open premium | run `ipo.py day1` once it trades | neutral | Yahoo intraday |
| 32 | First-30-minute volume / float | run `ipo.py day1` once it trades | neutral | Yahoo intraday |
| 33 | Price vs VWAP at 30 and 60 min | run `ipo.py day1` once it trades | neutral | Yahoo intraday |
| 34 | Day high/low vs IPO price | run `ipo.py day1` once it trades | neutral | Yahoo intraday |
| 35 | Post-IPO calendar | first trade date not set yet | neutral | computed from first trade date |
> **What it means (mixed):** 5 signals read positive and 7 negative; the rest are neutral or not known. The verdict does not use them; they explain the setup.

## Comparables (n=40; 6 without price data)
| company | IPO date | sim | biz | sit | open prem | d1 | d5 | d30 | lockup | today | top features | phrases |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CoreWeave, Inc. (CRWV) | 2025-03-28 | 37.3 | 100.0 | 21.6 | -3% | +3% | +38% | +32% | +242% | +25% | growth, float_pct, log_rev | significantly accelerate; models capabilities |
| Sumo Logic, Inc. (None) | 2020-09-17 | 17.4 | 79.7 | 1.9 |   n/a  | - | - | - | - | acquired 2023-04 -45% vs IPO | float_pct, log_rev, growth | intelligence; consistently |
| eToro Group Ltd. (ETOR) | 2025-05-13 | 16.2 | 15.5 | 16.4 | +0% | +0% | +22% | +25% | -27% | -59% | float_pct, log_rev, growth | was founded; investment |
| Ceridian HCM Holding Inc. (DAY) | 2018-04-26 | 16.0 | 70.6 | 2.4 |   n/a  | - | - | - | - | acquired 2025-09 +218% vs IPO | float_pct, log_rev, growth | attract retain; talent |
| Mobileye Global Inc. (MBLY) | 2022-10-26 | 15.9 | 64.8 | 3.7 | +27% | +8% | -3% | +20% | +72% | -79% | float_pct, log_rev, growth | safety; research |
| DROPBOX, INC. (DBX) | 2018-03-23 | 14.8 | 60.9 | 3.3 | +38% | -2% | +8% | +0% | -12% | +12% | float_pct, log_rev, growth | was founded; around world |
| UiPath, Inc. (PATH) | 2021-04-21 | 14.6 | 58.9 | 3.5 | +17% | +5% | +15% | +24% | -24% | -80% | float_pct, log_rev, growth | intelligence; work |
| Dynatrace, Inc. (DT) | 2019-08-01 | 14.3 | 62.5 | 2.2 | +82% | -6% | +3% | -17% | +12% | +71% | float_pct, log_rev, growth | intelligence; applications |
| McAfee Corp. (None) | 2020-10-23 | 14.3 | 59.0 | 3.1 |   n/a  | - | - | - | - | acquired 2022-01 +30% vs IPO | float_pct, log_rev, growth | life people; intelligence |
| DOCUSIGN INC (DOCU) | 2018-04-27 | 14.1 | 59.7 | 2.7 | +31% | +5% | +10% | +52% | +3% | +104% | float_pct, log_rev, growth | around world; research |
| Uber Technologies, Inc (UBER) | 2019-05-10 | 13.7 | 49.7 | 4.7 | -7% | -1% | +2% | +5% | -8% | +67% | float_pct, log_rev, growth | around world; safety |
| Unity Software Inc. (U) | 2020-09-18 | 13.5 | 55.9 | 2.8 | +44% | -9% | +11% | +45% | +45% | -33% | float_pct, log_rev, growth | advantages; shape |
| ZoomInfo Technologies Inc. (ZI) | 2020-06-05 | 13.2 | 53.9 | 3.1 |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  | float_pct, log_rev, growth | intelligence; mission |
| Avantor, Inc. (AVTR) | 2019-05-17 | 13.0 | 39.1 | 6.5 | +5% | -1% | +18% | +30% | +6% | +6% | growth, log_rev, float_pct | around world; research |
| PROCORE TECHNOLOGIES, INC. (PCOR) | 2021-05-20 | 13.0 | 54.6 | 2.6 | +25% | +5% | -3% | +11% | +4% | -9% | float_pct, log_rev, growth | adoption technology; global economy |
| SailPoint, Inc. (SAIL) | 2025-02-13 | 13.0 | 53.2 | 2.9 | +0% | -4% | +7% | -11% | -18% | -13% | float_pct, log_rev, growth | research; intelligence |
| Anaplan, Inc. (None) | 2018-10-12 | 13.0 | 57.6 | 1.9 |   n/a  | - | - | - | - | acquired 2022-05 +288% vs IPO | float_pct, log_rev, growth | intelligence; culture |
| Neutron Holdings, Inc. (LIME) | 2026-07-01 | 13.0 | 57.2 | 2.0 | +8% | -4% | -6% | +39% | +5% | -35% | float_pct, log_rev, growth | around world; advantages |
| Gitlab Inc. (GTLB) | 2021-10-14 | 12.9 | 55.1 | 2.3 | +22% | +10% | +12% | +3% | -50% | -50% | float_pct, growth, log_rev | innovation velocity; deployment |
| MULESOFT, INC (None) | 2017-03-17 | 12.8 | 54.7 | 2.3 |   n/a  | - | - | - | - | acquired 2018-04 +112% vs IPO | float_pct, growth, log_rev | risks; history |
| Coursera, Inc. (COUR) | 2021-03-31 | 12.6 | 52.7 | 2.5 | +18% | +15% | +49% | -10% | -14% | -90% | float_pct, log_rev, growth | global economy; world-class |
| POWERSCHOOL HOLDINGS, INC. (PWSC) | 2021-07-29 | 12.6 | 54.6 | 2.1 |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  | float_pct, log_rev, growth | singular focus; adoption technology |
| Couchbase, Inc. (BASE) | 2021-07-22 | 12.4 | 56.5 | 1.4 |   n/a  | - | - | - | - | acquired 2025-08 +2% vs IPO | float_pct, growth, log_rev | applications; environments |
| INSTRUCTURE HOLDINGS, INC. (INST) | 2021-07-23 | 12.2 | 50.4 | 2.7 |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  | float_pct, log_rev, growth | world-class; mission |
| BENTLEY SYSTEMS INC (BSY) | 2020-09-23 | 12.2 | 50.6 | 2.6 | +27% | +20% | +7% | +28% | +57% | +62% | float_pct, log_rev, growth | quality life; global economy |
| PAYCOR HCM, INC. (PYCR) | 2021-07-22 | 12.2 | 52.3 | 2.1 |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  | float_pct, log_rev, growth | talent; capabilities |
| Pivotal Software, Inc. (None) | 2018-04-20 | 12.1 | 50.9 | 2.5 |   n/a  | - | - | - | - | acquired 2019-11 +0% vs IPO | float_pct, log_rev, growth | development; improvement |
| Jamf Holding Corp. (JAMF) | 2020-07-23 | 12.0 | 52.0 | 2.0 |   n/a  | - | - | - | - | acquired 2025-12 -50% vs IPO | float_pct, log_rev, growth | singular focus; was founded |
| Rubrik, Inc. (RBRK) | 2024-04-25 | 12.0 | 50.5 | 2.4 | +21% | -4% | -15% | -14% | +0% | +183% | float_pct, log_rev, growth | intelligence; risks |
| Expensify, Inc. (EXFY) | 2021-11-10 | 12.0 | 54.6 | 1.4 | +47% | +3% | +11% | -6% | -64% | -96% | float_pct, log_rev, growth | global economy; around world |
| Freshworks Inc. (FRSH) | 2021-09-22 | 11.7 | 49.3 | 2.3 | +20% | +10% | -1% | +16% | -54% | -73% | float_pct, log_rev, growth | around world; intelligence |
| WalkMe Ltd. (WKME) | 2021-06-16 | 11.7 | 51.3 | 1.9 |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  | float_pct, log_rev, growth | research; applications |
| Sprinklr, Inc. (CXM) | 2021-06-23 | 11.7 | 49.1 | 2.3 | -9% | +21% | +59% | +29% | -3% | -55% | float_pct, log_rev, growth | helping; decide |
| Ping Identity Holding Corp. (None) | 2019-09-20 | 11.6 | 51.1 | 1.8 |   n/a  | - | - | - | - | acquired 2022-09 +90% vs IPO | float_pct, log_rev, growth | intelligence; deployment |
| CrowdStrike Holdings, Inc. (CRWD) | 2019-06-12 | 11.5 | 45.2 | 3.0 | +87% | -9% | +20% | +38% | -23% | +1322% | float_pct, growth, log_rev | intelligence; model |
| monday.com Ltd. (MNDY) | 2021-06-10 | 11.5 | 47.5 | 2.6 | +12% | +3% | +24% | +19% | +83% | -56% | float_pct, growth, log_rev | building; work |
| Cloudflare, Inc. (NET) | 2019-09-13 | 11.5 | 49.3 | 2.0 | +20% | +0% | +4% | -12% | +14% | +1599% | float_pct, log_rev, growth | people around; around world |
| Navan, Inc. (NAVN) | 2025-10-30 | 11.1 | 44.9 | 2.7 | -12% | -9% | -20% | -37% | -27% | +12% | float_pct, log_rev, growth | safety; demand |
| Global-E Online Ltd. (GLBE) | 2021-05-12 | 11.0 | 45.6 | 2.4 | -3% | +5% | +11% | +128% | +135% | +73% | float_pct, growth, log_rev | focus efforts; quarter |
| ZUORA INC (ZUO) | 2018-04-12 | 11.0 | 54.8 | None |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |   n/a  |  | models; research |
> **What it means (neutral):** the closest match scores 37/100 (a reasonable match); 6 of 40 have no price data, so results lean on companies that survived.

## Pattern (similarity-weighted, returns from the first open unless noted)
| horizon | n | median | 90% interval | 25-75% | % green | leave-one-out flips |
|---|---|---|---|---|---|---|
| d1_open | 25 | +2.6% | -1.0% .. +4.6% | -3.7% .. +5.3% | 52% | CoreWeave, Inc. |
| d1_ipo | 25 | +20.0% | +4.0% .. +34.9% | +0.0% .. +36.4% | 80% | - |
| d2_open | 25 | +5.0% | +2.2% .. +9.3% | -2.7% .. +11.8% | 76% | - |
| d2_ipo | 25 | +28.8% | +18.8% .. +34.8% | +6.7% .. +40.3% | 84% | - |
| d3_open | 25 | +11.7% | +3.1% .. +18.4% | +1.1% .. +24.3% | 80% | - |
| d3_ipo | 25 | +31.4% | +28.6% .. +36.0% | +25.0% .. +42.4% | 88% | - |
| d5_open | 25 | +10.5% | +4.2% .. +18.2% | +2.4% .. +21.7% | 76% | - |
| d5_ipo | 25 | +34.5% | +23.3% .. +38.1% | +21.6% .. +44.7% | 92% | - |
| d30_open | 25 | +20.3% | +4.8% .. +29.3% | +0.4% .. +31.7% | 72% | - |
| d30_ipo | 25 | +36.4% | +28.4% .. +44.6% | +25.0% .. +51.8% | 88% | - |
| d90_open | 25 | +2.7% | -7.7% .. +52.3% | -15.1% .. +70.7% | 52% | CoreWeave, Inc. |
| d90_ipo | 25 | +21.4% | +9.0% .. +93.9% | -15.1% .. +123.6% | 72% | - |
| lockup_open | 25 | +3.1% | -11.5% .. +14.4% | -22.8% .. +56.8% | 52% | CoreWeave, Inc. |
| lockup_ipo | 25 | +22.2% | +1.7% .. +99.6% | -14.4% .. +104.9% | 64% | - |
| d180_open | 24 | +0.0% | -17.6% .. +14.4% | -23.7% .. +56.8% | 50% | CoreWeave, Inc. |
| d180_ipo | 24 | +22.2% | -10.7% .. +99.6% | -17.6% .. +104.9% | 62% | - |
| y1_open | 24 | -20.6% | -24.7% .. +51.7% | -40.9% .. +70.1% | 46% | eToro Group Ltd., DROPBOX, INC., UiPath, Inc., Uber Technologies, Inc, PROCORE TECHNOLOGIES, INC., SailPoint, Inc., Gitlab Inc., Coursera, Inc., Expensify, Inc., Freshworks Inc., Sprinklr, Inc., monday.com Ltd., Global-E Online Ltd. |
| y1_ipo | 24 | +4.0% | -30.2% .. +72.9% | -30.8% .. +98.8% | 50% | CoreWeave, Inc. |
| y2_open | 20 | -7.8% | -50.2% .. +23.9% | -52.6% .. +109.9% | 50% | Mobileye Global Inc., DROPBOX, INC., UiPath, Inc., Unity Software Inc., PROCORE TECHNOLOGIES, INC., Gitlab Inc., Coursera, Inc., Expensify, Inc., Freshworks Inc., Sprinklr, Inc. |
| y2_ipo | 20 | -12.7% | -29.1% .. +41.3% | -39.7% .. +120.7% | 50% | Mobileye Global Inc., DROPBOX, INC., UiPath, Inc., Unity Software Inc., PROCORE TECHNOLOGIES, INC., Gitlab Inc., Coursera, Inc., Expensify, Inc., Freshworks Inc., Sprinklr, Inc. |
| y3_open | 19 | -16.2% | -45.1% .. +30.1% | -55.4% .. +76.0% | 42% | - |
| y3_ipo | 19 | +5.0% | -36.3% .. +45.3% | -48.8% .. +124.0% | 53% | DROPBOX, INC., Dynatrace, Inc., DOCUSIGN INC, Avantor, Inc., PROCORE TECHNOLOGIES, INC., BENTLEY SYSTEMS INC, CrowdStrike Holdings, Inc., monday.com Ltd., Cloudflare, Inc., Global-E Online Ltd. |
| today_open | 25 | +5.8% | -50.5% .. +24.9% | -55.9% .. +66.8% | 48% | CoreWeave, Inc., DROPBOX, INC., Dynatrace, Inc., DOCUSIGN INC, Uber Technologies, Inc, Avantor, Inc., BENTLEY SYSTEMS INC, Rubrik, Inc., CrowdStrike Holdings, Inc., Cloudflare, Inc., Navan, Inc., Global-E Online Ltd. |
| today_ipo | 34 | +11.2% | -13.2% .. +54.3% | -49.8% .. +90.0% | 53% | - |
Open premium over IPO price: median +18.2% (90% +5.1%..+25.4%, n=25)
Baseline, all US IPOs >= $200M in the prior 12 months (from open): d1 -0.7% n=79, d5 -4.6% n=79, d30 -1.6% n=75
Baseline, same VIX bucket (15-20) and range direction (0): d5 +21.7% n=33, d30 +25.0% n=29
> **What it means (good sign):** look-alikes were up by day 5 76% of the time (median +10.5%) vs 42% for all recent IPOs (median -2.2%): better than a typical IPO.

## Signal effects in the comparables (day-5 from open, + vs -)
- range raised vs cut: + +10.4% (n=12) vs - +18.2% (n=1)
- priced at/above top vs at/below bottom: + +10.4% (n=17) vs - +37.9% (n=3)
- float < 15% vs > 30%: + +10.4% (n=24) vs - +18.2% (n=1)
- profitable vs losing money: + +18.2% (n=5) vs - +6.7% (n=19)
- VIX < 20 vs >= 20: + +15.1% (n=18) vs - +7.2% (n=7)
- IPO ETF 20d up vs down: + +7.8% (n=17) vs - +15.1% (n=8)
- no selling shareholders vs > 30%: + +10.5% (n=13) vs - +15.1% (n=4)
> **What it means (neutral):** which features went with better or worse day-5 moves among these comparables. Gaps under ~5 points, or groups under ~8 deals, are noise; the verdict does not use this table.

## Reference levels by open premium (historical reference level, not a target)
| open premium | d5 median (n) | d30 median (n) |
|---|---|---|
| -100% .. +0% | +37.9% (5) | +31.7% (5) |
| +0% .. +10% | +18.2% (4) | +25.0% (4) |
| +10% .. +25% | +12.0% (7) | +2.8% (7) |
| +25% .. +50% | +7.8% (7) | +20.3% (7) |
| +50% .. +100% | +2.5% (2) | -16.7% (2) |
| +100% .. up |   n/a  (0) |   n/a  (0) |
Historical reference level: not enough evidence
> **What it means (neutral):** history shows no clear 'opened too high' level for deals like this.

## Archetype: Hyper-growth / capital-intensive
Why: revenue $44.3B (>= $1B); growth +500% (> 50%); capex not reported. Matching: archetype (pool of this archetype: 18; widened with same-industry IPOs because it was small)
> **What it means (bad sign):** it is a Hyper-growth / capital-intensive IPO; so few IPOs of this kind exist that the pool was widened with same-industry deals, so comparables are loose.

## Closest peer: CoreWeave, Inc. (CRWV), first trade 2025-03-28, similarity 37.3
| metric | this IPO | peer at its IPO |
|---|---|---|
| Revenue (latest period, annualized) | $44.3B | $1.9B |
| Growth | +500% | +500% |
| FCF margin | n/a | -311% |
| Float | +6% | +8% |
| Price / sales at IPO | 21.8x | 9.7x |
Peer's path from the first open (opened -3% vs its IPO price): day 1 +2.6%, day 5 +37.9%, day 30 +31.7%, day 180 +242.1%
> **What it means (neutral):** CoreWeave, Inc. is the nearest match at similarity 37.3/100. It was +37.9% five days after its open.

## Pricing simulation (where the final price lands vs the first filed range)
2,000 Monte Carlo draws over the 30 most similar past deals (range width, S&P / Nasdaq / sector 20-day momentum, float, lead bank's pricing and day-30 record).
| outcome | probability | 90% interval |
|---|---|---|
| Below the range | 13% | 0% .. 15% |
| Inside the range, below the top | 46% | 5% .. 26% |
| At the top | 26% | 0% .. 13% |
| Above the range (raised range / Rule 430A) | 15% | 59% .. 87% |
Most likely: **inside** the range (below 13% / inside 72% / above 15%); from 168 recent deals whose range was **unchanged** before pricing (tested: beat the plain base rate in 6 of 6 years). The probability column above is this model; the Monte Carlo line describes the neighbor model (shown, not used).
Not modelled: order-book coverage: no record of it exists for past deals, so it cannot be weighted.
> **What it means (good sign):** most likely it prices inside its range (72%), which is what most IPOs do. The most similar past deals lean much higher (74% above), a hint of strong demand that the tested model does not trust.

## Valuation check
**MIXED: rich on sales, cheap for its growth** (at the range midpoint, $74.00; n=40 comparables at their own IPO price)
| measure | this IPO | comparables' median | rank | read |
|---|---|---|---|---|
| Price / sales | 21.8x | 11.4x | 78% | rich |
| P/S per point of growth | 0.04 | 0.38 | 8% | cheap |
Price at which P/S would equal the comparables' median: $38.64; at their 75th percentile: $69.93. These are what the comparables' multiples imply, not a fair value.
> **What it means (mixed):** at $74.00 it costs 21.8x sales vs 11.4x for comparables at their IPO (rich); per point of growth it is cheap. Overvalued IPOs have done worst in the backtest.

## Valuation at the opening price (retail buys at the open)
Price / sales at the open, ranked against 527 past IPOs at their own open (median 10.8x; most expensive quarter from 37.5x).
| if it opens | at | price / sales | rank among past opens |
|---|---|---|---|
| +0% vs IPO price | $74.00 | 21.8x | 65% |
| +25% vs IPO price | $92.50 | 27.3x | 69% |
| +50% vs IPO price | $111.00 | 32.8x | 73% |
| +100% vs IPO price | $148.00 | 43.7x | 77% (most expensive quarter) |
| +150% vs IPO price | $185.00 | 54.6x | 80% (most expensive quarter) |
**Most-expensive-quarter line: an open above $126.95** (+72% vs $74.00). Tested 2020-25: IPOs that opened above their line were less often up by day 180 in 5 of 6 years.
> **What it means (neutral):** the price you pay matters: above $126.95 (+72% vs the IPO price) it would be among the most expensive quarter of IPOs at the open, and those were less often up 6 months later.

## Outcome simulation (10,000 draws of real past IPO paths, from the first open)
Each draw is one past IPO's whole path, so its day 1, week 1 and month 6 belong together. History, not a forecast.

**all recent IPOs** (215 deals)
| from the open | worst 10% | 25% | median | 75% | best 10% | chance up | >= +20% | <= -20% |
|---|---|---|---|---|---|---|---|---|
| 1 day | -16% | -6% | -0% | +3% | +12% | 41% | 5% | 6% |
| 3 days | -22% | -11% | -1% | +6% | +16% | 46% | 6% | 13% |
| 1 week | -26% | -13% | -2% | +7% | +17% | 42% | 8% | 16% |
| 2 weeks | -31% | -13% | -1% | +8% | +21% | 44% | 10% | 19% |
| 1 month | -35% | -19% | -4% | +9% | +22% | 41% | 13% | 23% |
| 3 months | -52% | -35% | -11% | +15% | +38% | 36% | 22% | 40% |
| 6 months | -73% | -51% | -18% | +10% | +48% | 34% | 19% | 47% |

**twin IPOs (same setup)** (185 deals)
| from the open | worst 10% | 25% | median | 75% | best 10% | chance up | >= +20% | <= -20% |
|---|---|---|---|---|---|---|---|---|
| 1 day | -14% | -8% | -1% | +3% | +11% | 40% | 2% | 5% |
| 3 days | -21% | -10% | -1% | +6% | +17% | 48% | 9% | 11% |
| 1 week | -22% | -11% | -1% | +8% | +22% | 46% | 12% | 13% |
| 2 weeks | -28% | -10% | -0% | +11% | +30% | 47% | 16% | 14% |
| 1 month | -27% | -13% | -0% | +16% | +37% | 50% | 21% | 17% |
| 3 months | -45% | -28% | -9% | +18% | +46% | 39% | 23% | 34% |
| 6 months | -66% | -41% | -21% | +8% | +50% | 33% | 18% | 51% |

**look-alike companies** (34 deals)
| from the open | worst 10% | 25% | median | 75% | best 10% | chance up | >= +20% | <= -20% |
|---|---|---|---|---|---|---|---|---|
| 1 day | -9% | -4% | +3% | +5% | +15% | 54% | 3% | 0% |
| 3 days | -7% | +1% | +12% | +24% | +35% | 81% | 27% | 3% |
| 1 week | -6% | +2% | +11% | +22% | +38% | 79% | 29% | 0% |
| 2 weeks | -13% | -2% | +8% | +16% | +25% | 67% | 18% | 0% |
| 1 month | -15% | +0% | +8% | +22% | +31% | 78% | 33% | 3% |
| 3 months | -27% | -5% | +5% | +46% | +310% | 63% | 38% | 17% |
| 6 months | -50% | -24% | +3% | +57% | +242% | 54% | 30% | 31% |
> **What it means (neutral):** in the simulated paths a 1-week flip was up 46% of the time (median -1%), a 6-month hold 33% (median -21%); the worst 10% of 6-month paths lost -66% or more. Shorter holds were less extreme in both directions.

## Reference checklist (from history, not advice or an order instruction)
1. Opening-price caution level: not enough evidence in the comparables to set one.
2. Re-run triggers: a new S-1/A (range raised, cut or shares changed) -> rerun `analyze`; the 424B4 (final price) -> rerun `analyze`, the pricing table becomes the actual; the first trade -> run `day1`.
3. On the first day the open can be far above the IPO price. A market order fills at whatever the open is; a limit order caps the price paid but may not fill. Any order in this pack goes through trader-risk and your typed yes.

## Bottom line
| evidence | chance up by day 5 | chance up by day 180 | tested? |
|---|---|---|---|
| Verdict: look-alikes shrunk to the base rate | 55% | 33% | yes: about the base rate (flip 72%, hold 66% right) |
| All recent US IPOs (base rate) | 42% | 33% | yes: the best single input 2020-25 |
| Look-alike companies (pattern, % up) | 76% | 50% | inside the verdict |
| Twin IPOs, same setup (n=185) | 46% | 34% | yes: no gain over the base rate |
| Valuation vs comparables | - | MIXED: rich on sales, cheap for its growth | weak: few overvalued deals |
| Pricing vs range | inside | - | yes: base rate by range revision, 6 of 6 years |
| Valuation at the open | - | most-expensive-quarter line $126.95 | yes: worse at 6 months in 5 of 6 years |
| Simulated paths (twins) | 46% | 33% | history of real paths |
- Flip (day 5 from the open): **FAVORABLE**; hold (day 180): **UNFAVORABLE**; valuation: **MIXED: rich on sales, cheap for its growth**.
- Good signs: pattern, pricing. Bad signs: decision, archetype.
- Quick flip: **WORTH A CLOSER LOOK**: IPOs like this more often rose by day 5 after the open. 1 of 3 other parts point the same way.
- Long hold: **LEANS SKIP**: IPOs like this more often fell than rose by day 180 after the open. 3 of 3 other parts point the same way.
- The lean follows the tested verdict only; the other rows are shown so you can see where the evidence agrees or splits.
- **Overall read: FLIP CANDIDATE: history favors a short trade (sell within about a week), not a long hold; for a long hold, an open above $126.95 would put it in the most expensive quarter of IPOs.**
- How much to trust it: this rule was right 72% of the time on flips in the backtest, close to simply assuming every IPO falls; treat the lean as a reminder of the odds, not a forecast.
- History, not a prediction; retail usually buys at the open, not the IPO price; not financial advice or a buy/sell recommendation.

## Sources (every number above comes from these)
- Prospectus used: https://www.sec.gov/Archives/edgar/data/2130357/000162828026072484/anthropicpbc-sx1ax2.htm
- Financials: S-1 summary table (parsed from the S-1/A of 2026-11-10) (https://data.sec.gov/api/xbrl/companyfacts/CIK0002130357.json)
- Filing index: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=2130357&type=S-1
- Prices: Yahoo Finance chart API (daily bars, unofficial)
- List of past IPOs: SEC full-text search, 424B4 filings
- Comparables' prospectuses: [CoreWeave, Inc.](https://www.sec.gov/Archives/edgar/data/1769628/000119312525067651/d899798d424b4.htm); [Sumo Logic, Inc.](https://www.sec.gov/Archives/edgar/data/1643269/000119312520248044/d821436d424b4.htm); [eToro Group Ltd.](https://www.sec.gov/Archives/edgar/data/1493318/000121390025043558/ea0223534-12.htm); [Ceridian HCM Holding Inc.](https://www.sec.gov/Archives/edgar/data/1725057/000119312518135134/d559012d424b4.htm); [Mobileye Global Inc.](https://www.sec.gov/Archives/edgar/data/1910139/000110465922112004/tm227410-23_424b4.htm); [DROPBOX, INC.](https://www.sec.gov/Archives/edgar/data/1467623/000119312518092764/d553522d424b4.htm); [UiPath, Inc.](https://www.sec.gov/Archives/edgar/data/1734722/000119312521125014/d98556d424b4.htm); [Dynatrace, Inc.](https://www.sec.gov/Archives/edgar/data/1773383/000119312519210943/d668054d424b4.htm); [McAfee Corp.](https://www.sec.gov/Archives/edgar/data/1783317/000119312520275538/d89887d424b4.htm); [DOCUSIGN INC](https://www.sec.gov/Archives/edgar/data/1261333/000119312518139042/d506878d424b4.htm); [Uber Technologies, Inc](https://www.sec.gov/Archives/edgar/data/1543151/000119312519144716/d647752d424b4.htm); [Unity Software Inc.](https://www.sec.gov/Archives/edgar/data/1810806/000119312520249257/d908875d424b4.htm)

Failed sources: none
Note: History, not a prediction. Retail buyers usually get the first open, not the IPO price.
Note: Financials come from SEC XBRL filed after each IPO (pre-IPO periods); for an untraded IPO pass --facts from the S-1.
Note: 6 of 40 comparables have no price data (left the market or renamed); results lean toward survivors.