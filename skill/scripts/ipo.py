#!/usr/bin/env python
"""ipo-aenow: research one US IPO from free data (SEC EDGAR + Yahoo Finance).

Standard library only. Reads filings and prices, scores comparable IPOs, and prints
an evidence-based lean. It never places, sizes or approves an order.

  python ipo.py analyze TICKER|"Company name" [--json] [--save] [--facts FILE]
  python ipo.py comps   TICKER|"Company name" [--drop CIK:reason] [--add CIK:reason]
  python ipo.py day1    TICKER
  python ipo.py backtest [--limit N | --all]
  python ipo.py clean
  python ipo.py --selftest
"""
import argparse
import gzip
import hashlib
import html
import json
import math
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TRADING = SKILL.parents[2]            # .../Trading/.claude/skills/ipo-aenow -> .../Trading
TRADER = TRADING / "trader"
CONFIG_FILE = SKILL / "ipo-config.json"
BACKTEST_FILE = TRADER / "state" / "ipo-backtest.json"
REPORTS = TRADER / "reports"
CACHE = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "ipo-analyst" / "cache"
REC = CACHE / "rec"
CACHE_DAYS = 30
MIN_GAP = 0.22                         # seconds between requests to one host (< 5 a second)
EFTS = "https://efts.sec.gov/LATEST/search-index?"
TODAY = date.today()

FAILED = {}                            # source -> first error, so a report can list failed sources
_failed_lock = threading.Lock()


def fail(source, err):
    with _failed_lock:
        FAILED.setdefault(source, str(err)[:160])


def cfg():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- HTTP + cache

_next = {}
_rate_lock = threading.Lock()


def _throttle(host):
    with _rate_lock:
        t = max(time.time(), _next.get(host, 0.0))
        _next[host] = t + MIN_GAP
    d = t - time.time()
    if d > 0:
        time.sleep(d)


_ua = None


def sec_ua():
    global _ua
    if _ua:
        return _ua
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        try:
            ua = json.loads((TRADER / "config.json").read_text(encoding="utf-8")).get("sec_user_agent", "").strip()
        except (OSError, ValueError):
            ua = ""
    if not ua or "example.com" in ua or "@" not in ua:
        sys.exit(f"ipo.py: SEC needs a contact. Create {TRADER / 'config.json'} with "
                 "{\"sec_user_agent\": \"First Last first.last@gmail.com\"} using your real name and email (example.com is refused), "
                 "or set SEC_USER_AGENT.")
    _ua = ua
    return ua


ALLOWED_HOSTS = ("www.sec.gov", "data.sec.gov", "efts.sec.gov", "query1.finance.yahoo.com", "query2.finance.yahoo.com")


def http_get(url, *, sec=False, max_bytes=None, ttl=CACHE_DAYS * 86400, cache=True):
    """GET with a polite rate limit, retries and a gzip cache outside OneDrive.
    Big filings are read only up to max_bytes and not cached raw (their parsed record is).
    Only HTTPS to SEC EDGAR and Yahoo Finance; the SEC contact (User-Agent SEC requires) goes to sec.gov only."""
    u = urllib.parse.urlparse(url)
    host = u.netloc.lower()
    if u.scheme != "https" or host not in ALLOWED_HOSTS:
        raise ValueError(f"ipo.py: refusing to fetch {u.scheme}://{host} (only SEC EDGAR and Yahoo Finance over HTTPS)")
    sec = sec and host.endswith(".sec.gov")
    key = hashlib.sha1(f"{url}|{max_bytes}".encode()).hexdigest()
    path = CACHE / (key + ".gz")
    if cache and path.exists() and time.time() - path.stat().st_mtime < ttl:
        return gzip.decompress(path.read_bytes()).decode("utf-8", "replace")
    headers = {"User-Agent": sec_ua() if sec else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ipo-aenow",
               "Accept-Encoding": "identity"}
    data = None
    for attempt in range(4):
        _throttle(host)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                data = r.read(max_bytes) if max_bytes else r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 3:
                raise
        time.sleep(1.5 * 2 ** attempt)
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data))
    return data.decode("utf-8", "replace")


def get_json(url, **kw):
    return json.loads(http_get(url, **kw))


def rec_get(name):
    p = REC / (name + ".json")
    if p.exists() and time.time() - p.stat().st_mtime < CACHE_DAYS * 86400:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def rec_put(name, obj):
    REC.mkdir(parents=True, exist_ok=True)
    (REC / (name + ".json")).write_text(json.dumps(obj), encoding="utf-8")


def prune_cache(all_files=False):
    n = 0
    if not CACHE.exists():
        return 0
    cut = time.time() - CACHE_DAYS * 86400
    for p in CACHE.rglob("*"):
        if p.is_file() and (all_files or p.stat().st_mtime < cut):
            p.unlink(missing_ok=True)
            n += 1
    return n


# ---------------------------------------------------------------- text helpers

def html_text(s):
    s = re.sub(r"(?is)<(script|style|ix:header)\b[^>]*>.*?</\1\s*>", " ", s)
    s = re.sub(r"(?s)<[^>]*>", " ", s)
    s = re.sub("[\u200b-\u200d\u2060\ufeff]", "", html.unescape(s))
    s = s.replace("\xa0", " ").replace("\u2009", " ").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s)


def num(s):
    try:
        return float(s.replace(",", ""))
    except (AttributeError, ValueError):
        return None


def d_(s):
    return date.fromisoformat(s[:10]) if s else None


def iso(d):
    return d.isoformat() if d else None


BANKS = ["Goldman Sachs", "Morgan Stanley", "J.P. Morgan", "BofA Securities", "Citigroup", "Barclays",
         "Credit Suisse", "Deutsche Bank", "Jefferies", "UBS", "Wells Fargo", "RBC Capital", "Evercore",
         "TD Cowen", "Cowen", "Piper Sandler", "William Blair", "Stifel", "KeyBanc", "Needham", "Raymond James",
         "Truist", "BMO Capital", "Mizuho", "Nomura", "Guggenheim", "Baird", "Oppenheimer", "Canaccord",
         "Leerink", "SVB Securities", "Allen & Company", "Moelis", "Lazard", "LionTree", "Macquarie", "HSBC",
         "Cantor", "B. Riley", "Roth Capital", "Benchmark", "Craig-Hallum", "Lake Street", "ThinkEquity",
         "Aegis Capital", "EF Hutton", "Maxim Group", "Boustead", "Univest", "Santander", "Loop Capital",
         "Wedbush", "JMP Securities", "Citizens", "Samuel A. Ramirez", "Siebert"]

SPAC_RE = re.compile(r"\b(acquisition corp|acquisition co\b|blank check|spac)\b", re.I)


# ---------------------------------------------------------------- SEC: IPO universe

def efts(params, ttl):
    url = EFTS + urllib.parse.urlencode(params)
    return get_json(url, sec=True, ttl=ttl)


def _quarters(start, end):
    q = date(start.year, 3 * ((start.month - 1) // 3) + 1, 1)
    while q <= end:
        nxt = date(q.year + (q.month == 10), 1 if q.month == 10 else q.month + 3, 1)
        yield max(q, start), min(nxt - timedelta(1), end)
        q = nxt


def _display(name):
    parts = re.findall(r"\(([^()]*)\)", name)
    tick = None
    for p in parts:
        if not p.startswith("CIK"):
            tick = p.split(",")[0].strip()
            break
    return re.sub(r"\s*\([^()]*\)", "", name).strip(), tick


def universe(start, end):
    """Every 424B4 that says 'initial public offering price', first one per company."""
    out = {}
    for qs, qe in _quarters(start, end):
        ttl = CACHE_DAYS * 86400 if qe < TODAY - timedelta(35) else 86400
        frm = 0
        while True:
            try:
                d = efts({"q": '"initial public offering price"', "forms": "424B4", "dateRange": "custom",
                          "startdt": qs.isoformat(), "enddt": qe.isoformat(), "from": frm}, ttl)
                hits = d["hits"]["hits"]
                total = d["hits"]["total"]["value"]
            except Exception as e:               # noqa: BLE001 - a failed page is reported, not fatal
                fail("SEC full-text search", e)
                break
            for h in hits:
                s = h["_source"]
                adsh, fn = h["_id"].split(":", 1)
                if not s.get("ciks"):
                    continue
                cik = int(s["ciks"][0])
                name, tick = _display((s.get("display_names") or [""])[0])
                filed = s.get("file_date")
                sic = (s.get("sics") or [""])[0] or ""
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fn}"
                row = {"cik": cik, "name": name, "ticker": tick, "sic": sic, "filed": filed, "adsh": adsh, "url": url}
                if cik not in out or filed < out[cik]["filed"]:
                    out[cik] = row
            frm += len(hits)
            if not hits or frm >= total:
                break
    rows = [r for r in out.values() if r["sic"] != "6770" and not SPAC_RE.search(r["name"])]
    return sorted(rows, key=lambda r: r["filed"])


def submissions(cik):
    d = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", sec=True, ttl=7 * 86400)
    def rows(block):
        return list(zip(block["form"], block["filingDate"], block["accessionNumber"], block["primaryDocument"]))
    f = rows(d["filings"]["recent"])
    if not any(x[0] in ("S-1", "F-1") for x in f):
        for extra in d["filings"].get("files", []):
            try:
                f += rows(get_json("https://data.sec.gov/submissions/" + extra["name"], sec=True, ttl=7 * 86400))
            except Exception as e:  # noqa: BLE001
                fail("SEC submissions (older pages)", e)
    f.sort(key=lambda x: x[1])
    return {"name": d.get("name"), "sic": d.get("sic") or "", "tickers": d.get("tickers") or [],
            "exchanges": d.get("exchanges") or [], "filings": f}


def doc_url(cik, accn, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{doc}"


# ---------------------------------------------------------------- SEC: parse filings

def parse_cover(t):
    """Offer terms from the first ~200KB of a 424B4 / S-1/A, as plain text."""
    c = {}
    for pat in [r"initial public offering price (?:of [^$]{0,60}?)?(?:is|of|will be) (?:US)?\$\s?([\d.]+)",
                r"public offering price (?:is|of) \$\s?([\d.]+) per (?:share|ADS)",
                r"Initial public offering price\s*\$\s?([\d.]+)",
                r"Public offering price\s*\$\s?([\d.]+)",
                r"Price to (?:the )?public\D{0,40}?\$\s?([\d.]+)",
                # looser cover wordings, tried only when the ones above find nothing
                r"PRICE (?:US)?\$\s?([\d.]+) (?:A|PER) (?:SHARE|ADS)",
                r"offering price[^.$]{0,90}? is (?:US)?\$\s?([\d.]+)",
                r"Initial public offering price\s*(?:\(\d\))?\s*(?:US)?\$\s?([\d.]+)"]:
        m = re.search(pat, t[:60000], re.I)
        if m and num(m.group(1)) and 1 <= num(m.group(1)) <= 5000:
            c["price"] = num(m.group(1))
            break
    for pat in (r"between (?:US)?\$\s?(\d+(?:\.\d+)?) and (?:US)?\$\s?(\d+(?:\.\d+)?)",
                r"(?:price range|range) of (?:US)?\$\s?(\d+(?:\.\d+)?)\s?(?:to|-|–|and) (?:US)?\$\s?(\d+(?:\.\d+)?)",
                r"(?:US)?\$\s?(\d+(?:\.\d+)?)\s?(?:to|–) (?:US)?\$\s?(\d+(?:\.\d+)?) per (?:share|ADS)"):
        for m in re.finditer(pat, t[:80000], re.I):
            lo, hi = num(m.group(1)), num(m.group(2))
            if lo and hi and 0 < lo <= hi <= lo * 3:
                c["range"] = [lo, hi]
                break
        if c.get("range"):
            break
    if not c.get("range"):                     # a fixed expected price instead of a range (SpaceX, 2026)
        m = re.search(r"expect the (?:initial )?public offering price (?:per share )?(?:to|will) be (?:US)?\$\s?(\d+(?:\.\d+)?) per (?:share|ADS)", t[:40000], re.I)
        if m and num(m.group(1)):
            c["range"] = [num(m.group(1))] * 2
            c["fixed_price"] = True
    head = t[:6000]
    m = (re.search(r"(?:we are|is) offering\s+(?:an aggregate of\s+)?([\d,]{5,})\s+(?:of our\s+)?(?:Class [A-Z]\s+)?(?:ordinary shares|common shares|shares|American Depositary)", head, re.I)
         or re.search(r"([\d,]{6,})\s+(?:Shares|shares|American Depositary Shares)", head))
    if m:
        c["offered"] = num(m.group(1))
    m = re.search(r"selling (?:stock|share)holders[^.]{0,160}?offering(?: an aggregate of)? ([\d,]{5,}) (?:shares|ADS)", t[:20000], re.I)
    if m:
        c["secondary"] = num(m.group(1))
    m = re.search(r"(?:option|right) (?:for a period of \d+ days )?to purchase up to (?:an additional |a maximum of )?([\d,]{4,}) (?:additional )?(?:shares|ADSs|American)", t[:60000], re.I)
    if m:
        c["greenshoe"] = num(m.group(1))
    c["adr"] = bool(re.search(r"American Depositary Share", head, re.I))
    c["units"] = bool(re.search(r"each unit consist", t[:15000], re.I))
    c["dsp"] = bool(re.search(r"directed share program", t, re.I))
    c["cornerstone"] = bool(re.search(r"(indicated an interest in purchasing|cornerstone investor)", t, re.I))
    m = re.search(r"under the (?:trading |ticker )?symbol\s*\"?\s*([A-Z]{1,5})\b", t[:20000])
    if m:
        c["symbol"] = m.group(1)
    seg = t[:20000]
    found = sorted((seg.find(b), b) for b in BANKS if seg.find(b) >= 0)
    banks = []
    for _, b in found:                       # "Cowen" inside "TD Cowen" counts once
        if not any(b in x or x in b for x in banks):
            banks.append(b)
    c["banks"] = banks
    return c


def parse_deep(t):
    """Facts deeper in the prospectus summary (needs ~2.5MB of the filing)."""
    c = {}
    outs = {}
    for m in re.finditer(r"(Class [A-Z] )?(?:common stock|ordinary shares|common shares)\s+(?:to be )?(?:issued and )?outstanding\s+(?:immediately\s+)?after\s+(?:this|the)\s+offering(?: and the concurrent [a-z ]{5,30}?)?[\s.:]*(Class [A-Z] common stock:?\s*)?([\d,]{6,})", t, re.I):
        if re.search(r",\s*(?:and )?Class [A-Z]", t[max(0, m.start() - 80): m.start() + 12]):
            outs = {"total": num(m.group(3))}      # "Class A, Class N, ... and Class F ... outstanding": the all-class total
            break
        if m.group(2):                             # "... after this offering  Class A common stock: N  Class B common stock: N"
            outs.setdefault(m.group(2).strip(" :").lower()[:7], num(m.group(3)))
            for k in re.finditer(r"(Class [B-Z]) common stock:?\s*([\d,]{6,})", t[m.end(): m.end() + 900], re.I):
                outs.setdefault(k.group(1).lower(), num(k.group(2)))
            continue
        outs.setdefault((m.group(1) or "").strip().lower(), num(m.group(3)))
    if not outs:
        for m in re.finditer(r"([\d,]{6,}) shares of (?:our )?(Class [A-Z] )?(?:common stock|ordinary shares)\s+(?:will be|to be) outstanding (?:immediately )?after (?:this|the) offering", t, re.I):
            outs.setdefault((m.group(2) or "").strip().lower(), num(m.group(1)))
    if outs:
        # an unlabeled line next to per-class lines is their total, not another class: never add the two
        by_class = sum(v for k, v in outs.items() if k and v)
        c["outstanding"] = max(outs.get("") or 0, by_class)
    m = re.search(r"lock-?up (?:agreements?|period)[^.]{0,400}?(\d{2,3})(?:-day| days)", t, re.I)
    if m:
        w = t[m.start(): m.start() + 1500]
        # the main lockup, not a short early-release window: 180 when it is stated, else the most common period
        cand = [int(x) for x in re.findall(r"(\d{2,3})(?:-day| days)", w) if 60 <= int(x) <= 400]
        c["lockup_days"] = 180 if 180 in cand else (max(set(cand), key=cand.count) if cand else int(m.group(1)))
        std = re.search(r"(\d{2,3})(?:-day| days) after the date of (?:this|the final) prospectus", t, re.I)   # the standard lockup sentence
        if std and 30 <= int(std.group(1)) <= 400:
            c["lockup_days"] = int(std.group(1))
        longer = re.search(r"up to (\d{3}) days", w)
        if longer and int(longer.group(1)) > c["lockup_days"]:
            c["lockup_days_insiders"] = int(longer.group(1))
        c["lockup_early_release"] = bool(re.search(r"(earnings release|earlier of|early release|eligible for sale prior to the expiration)", w, re.I))
    classes = set(re.findall(r"Class ([A-Z]) (?:common stock|ordinary shares)", t))
    c["dual_class"] = len(classes) >= 2 and bool(re.search(r"(votes? per share|voting power)", t, re.I))
    c["share_classes"] = sorted(classes)
    c["controlled"] = bool(re.search(r"controlled company", t, re.I))
    m = re.search(r"Use of proceeds\s+(.{60,700}?)(?:Dividend policy|Risk factors|Lock-up|Directed share|Listing|Proposed)", t, re.I)
    if m:
        c["use_of_proceeds"] = m.group(1).strip()[:500]
    m = re.search(r"(?:dollar-based )?net (?:revenue |dollar )?(?:retention|expansion) rate[^.%]{0,80}?(\d{2,3})(?:\.\d)?%", t, re.I)
    if m:
        c["nrr"] = int(m.group(1))
    c["vc_backed"] = bool(re.search(r"(venture capital|private equity|funds (?:affiliated with|managed by)|investment funds affiliated)", t, re.I))
    best = 0
    for m in re.finditer(r"(?:one|single|largest|top|two|three|five|\w+) customers? (?:accounted for|represented|comprised) (?:approximately |more than |over )?(\d{1,2}(?:\.\d)?)% of (?:our )?(?:total )?(?:net )?revenue", t, re.I):
        if not re.search(r"\b(no|none of|not)\b", t[max(0, m.start() - 20): m.start() + 20], re.I):
            best = max(best, float(m.group(1)))
    c["top_customer_pct"] = best or None
    c["no_customer_over_10pct"] = bool(re.search(r"no (?:single )?customer (?:accounted for|represented) (?:more than )?10%", t, re.I))
    for pat, key in [(r"(?:Common stock|Class [A-Z] common stock|Ordinary shares|Shares|ADSs) offered by us\s*:?\s*([\d,]{5,})", "offered"),
                     (r"offered by the selling (?:stock|share)holders\s*:?\s*([\d,]{5,})", "secondary"),
                     (r"[Oo]ption to purchase (?:up to )?(?:an )?additional (?:shares|ADSs)[^\d]{0,120}?([\d,]{5,})", "greenshoe")]:
        m = re.search(pat, t)
        if m:
            c["offering_" + key] = num(m.group(1))
    ps = [m for m in re.finditer(r"PROSPECTUS SUMMARY", t, re.I)]
    s = next((m for m in ps if re.search(r"summary highlights|this summary", t[m.end(): m.end() + 400], re.I)), ps[-1] if ps else None)
    start = s.end() if s else 0
    o = re.search(r"\b(Overview|Our Company|Our Business|Who We Are)\b", t[start: start + 40000])
    if o:
        start += o.end()
    ov = t[start: start + 3500]
    ov = re.sub(r"This summary highlights.{0,400}?(?:carefully|entirety)\.?", " ", ov, flags=re.I)
    c["overview"] = ov.strip()
    return c


_S1_ROWS = {
    "rev0": r"(?:Total revenues?|Total net revenues?|Revenues?|Net revenues?|Total net sales|Net sales|Sales)",
    "gross": r"Gross profit",
    "opinc": r"(?:Income \(loss\) from operations|Loss from operations|Income from operations|Operating income \(loss\)|"
             r"Operating \(loss\) income|Operating profit \(loss\)|Operating income|Operating loss)",
    "cfo": r"(?:Net cash (?:provided by \(used in\)|\(used in\) provided by|provided by|used in|flows? from|from)\s+operating activities[a-z ]*|Operating activities)",
    "capex": r"(?:Purchases? of property(?:, plant)? and equipment|Total Capital Expenditures|Capital expenditures)",
}
_NUM = r"\$?\s?\(?\s?-?\$?\s?[\d,]*\d(?:\.\d+)?\s?\)?|[—–-](?=\s)|�"


def _s1_numbers(seg, label, ncol):
    """The first row whose label matches and that carries exactly ncol numbers (dotted leaders and $ are skipped)."""
    for m in re.finditer(r"(?<![A-Za-z])" + label + r"(?:\s*\(\d\))?[\s.:$]*((?:(?:" + _NUM + r")\s*){" + str(ncol) + r"})", seg):
        vals = []
        for tok in re.findall(_NUM, m.group(1)):
            t = tok.replace("$", "").replace(",", "").strip()
            if t in ("—", "–", "-", "�"):
                vals.append(0.0)
                continue
            neg = t.startswith("(") or t.startswith("-")
            try:
                vals.append(-float(t.strip("()-")) if neg else float(t.strip("()")))
            except ValueError:
                break
        if len(vals) == ncol:
            return vals
    return None


def parse_s1_summary(t):
    """Pre-IPO financials from the prospectus summary table, as the facts JSON (rev0, rev1, gross, opinc, cfo, capex,
    cash, period_months), the most recent period vs the same period a year earlier. Returns {} when unsure.
    Checked against hand-read facts in the self-test and the regression set."""
    t = re.sub(r"\s+", " ", t)
    heads = [m.start() for m in re.finditer(r"(?i)summary (?:historical )?(?:consolidated |combined )?(?:financial|operating)", t)]
    out = {}
    hdr_pat = r"(?:(?:For the )?(?:Three|Six|Nine|Twelve) Months? Ended|(?:For the )?(?:Fiscal )?Years? Ended)"
    for start, h in ((s, h) for s in heads for h in re.finditer(hdr_pat, t[s: s + 40000])):
        seg = t[start + h.start(): start + h.start() + 20000]   # the table this header opens
        scale = (1e3 if re.search(r"(?i)in (?:US)?\$? ?thousands", seg[:3000]) else
                 1e6 if re.search(r"(?i)in (?:US)?\$? ?millions", seg[:3000]) else None)
        if not scale:
            continue
        stop = re.search(r"(?i)\b(?:Revenues?|Total revenues?|Net sales|Sales|Consolidated Statements?|Statements? of Operations|Total net revenues?)\b", seg[20:])
        hdr = seg[: 20 + (stop.start() if stop else 400)]
        years = [int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", hdr)]
        labels = re.findall(r"(Three|Six|Nine|Twelve|Fiscal Year|Year)", hdr)
        ncol = len(years)
        if ncol < 2 or not labels or not _s1_numbers(seg[:3000], _S1_ROWS["rev0"], ncol):
            continue                           # no revenue row with one number per column right under this header
        months = {"Three": 3, "Six": 6, "Nine": 9, "Twelve": 12, "Year": 12, "Fiscal Year": 12}
        n_int = sum(months[x] < 12 for x in labels)
        n_ann = ncol - 2 * n_int               # each interim group has 2 columns (this year, last year)
        groups, i = [], 0
        for x in labels:
            k = 2 if months[x] < 12 else max(n_ann, 0)
            if k:
                groups.append((months[x], list(range(i, min(i + k, ncol)))))
            i += k
        interim = sorted([g for g in groups if g[0] < 12 and len(g[1]) == 2], key=lambda g: -g[0])   # longest year-to-date first
        annual = [g for g in groups if g[0] == 12 and len(g[1]) >= 2]
        if not (interim or annual):
            continue
        mo, cols = interim[0] if interim else annual[0]
        pairs = sorted(((years[i], i) for i in cols), key=lambda p: -p[0])     # most recent year first
        i0, i1 = pairs[0][1], (pairs[1][1] if len(pairs) > 1 else pairs[0][1])
        rows = {}
        for k, lab in _S1_ROWS.items():
            v = _s1_numbers(seg, lab, ncol)
            if v is None and k in ("cfo", "capex"):
                v = _s1_numbers(t[:900000], lab, ncol)
            if v is not None:
                rows[k] = v
        if "rev0" not in rows:
            continue
        r = rows["rev0"]
        if not (r[i0] > 0 and r[i1] > 0):
            continue
        out = {"rev0": r[i0] * scale, "rev1": r[i1] * scale, "period_months": mo, "_source": "S-1 summary table (parsed)"}
        for k in ("gross", "opinc", "cfo"):
            if k in rows:
                out[k] = rows[k][i0] * scale
        if "capex" in rows:
            out["capex"] = abs(rows["capex"][i0]) * scale
        m = re.search(r"(?i)Cash(?:, cash equivalents,? and (?:short-term investments|marketable securities)| and cash equivalents)"
                      r"[\s.:$]*\$?\s?\(?([\d,]+(?:\.\d+)?)", seg)
        if m:
            out["cash"] = float(m.group(1).replace(",", "")) * scale
        break
    return out


def filing_text(url, max_bytes):
    return html_text(http_get(url, sec=True, max_bytes=max_bytes, cache=False))


# ---------------------------------------------------------------- SEC: financials (XBRL)

REV = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
       "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue"]


def fundamentals(cik, before, grace=0, known_by=None, lag_days=0):
    """grace: if no period ends before the IPO, accept one ending up to `grace` days after it
    (flagged period_after_ipo). Used for comparables only, never for a backtest target.
    known_by: only facts filed before this date (point-in-time). lag_days: the period must end that many
    days before `before` (a prospectus cannot hold a period that closed weeks before pricing)."""
    f = _fundamentals(cik, before, known_by, lag_days)
    if grace and not f.get("rev0"):
        g = _fundamentals(cik, before + timedelta(grace), known_by)
        if g.get("rev0"):
            g["period_after_ipo"] = True
            g["dei_shares"] = f.get("dei_shares") or g.get("dei_shares")
            return g
    return f


def _fundamentals(cik, before, known_by=None, lag_days=0):
    """Latest period that ENDED before the IPO: a fiscal year, or (for an IPO under a year old) the
    longest year-to-date period with a same-length period a year earlier. Flows are annualized.
    Values come from filings made after the IPO (SEC's XBRL API has no S-1 facts), so the periods
    are pre-IPO but the filing dates are later."""
    try:
        d = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", sec=True)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    facts = d.get("facts", {})
    g = facts.get("us-gaap") or facts.get("ifrs-full") or {}
    last_end = before - timedelta(lag_days)
    seen = lambda f: not known_by or not f.get("filed") or d_(f["filed"]) < known_by  # noqa: E731

    def periods(names):
        """{(months, end): value} for duration facts ending before the IPO."""
        for nm in names:
            units = g.get(nm, {}).get("units", {})
            vals = units.get("USD") or next(iter(units.values()), [])
            by = {}
            for f in vals:
                if not f.get("start") or not seen(f):
                    continue
                s, e = d_(f["start"]), d_(f["end"])
                months = round((e - s).days / 30.44)
                if months in (3, 6, 9, 12) and e < last_end:
                    by[(months, e)] = f["val"]
            if by:
                return by
        return {}

    def pick(by):
        """Prefer a full year; else the longest recent YTD period that has a year-earlier twin."""
        for months in (12, 9, 6, 3):
            ends = sorted(e for m, e in by if m == months)
            for e0 in reversed(ends):
                if (before - e0).days > 400:
                    break
                twin = [e for e in ends if 330 <= (e0 - e).days <= 400]
                if months == 12 or twin:
                    return months, e0, (max(twin) if twin else None)
        return None

    def annual(names, chosen=None):
        by = periods(names)
        if chosen:
            months, e0 = chosen
            v = by.get((months, e0))
            return {} if v is None else {e0: v * 12 / months}
        p = pick(by)
        if not p:
            return {}
        months, e0, e1 = p
        out_ = {e0: by[(months, e0)] * 12 / months}
        if e1:
            out_[e1] = by[(months, e1)] * 12 / months
        annual.months = months
        return out_

    def instant(names):
        for nm in names:
            units = g.get(nm, {}).get("units", {})
            vals = [f for f in (units.get("USD") or []) if not f.get("start") and d_(f["end"]) < last_end and seen(f)]
            if vals:
                return max(vals, key=lambda f: f["end"])["val"]
        return None

    annual.months = None
    rev = annual(REV)
    out = {}
    if rev:
        e0 = max(rev)
        months = annual.months
        out["fy_end"] = iso(e0)
        out["period_months"] = months
        out["rev0"] = rev[e0]
        prior = [e for e in rev if e != e0]
        if prior:
            out["rev1"] = rev[max(prior)]
        for key, names in [("gross", ["GrossProfit"]), ("opinc", ["OperatingIncomeLoss"]),
                           ("cfo", ["NetCashProvidedByUsedInOperatingActivities"]),
                           ("capex", ["PaymentsToAcquirePropertyPlantAndEquipment"])]:
            v = annual(names, (months, e0)).get(e0)
            if v is not None:
                out[key] = v
    out["cash"] = instant(["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"])
    out["debt"] = instant(["LongTermDebtNoncurrent", "LongTermDebt"])
    so = facts.get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    after = [f for f in so if d_(f["filed"]) >= before - timedelta(5) and seen(f)]
    if after:
        first = min(f["filed"] for f in after)
        same = [f for f in after if f["filed"] == first]
        end = max(f["end"] for f in same)      # one filing can repeat the same count: sum distinct values of one date
        out["dei_shares"] = sum({f["val"] for f in same if f["end"] == end})
    return out


def apply_facts(fund, path):
    """For an IPO with no 10-Q yet: numbers Claude read from the S-1 table, keyed like fundamentals()."""
    out = apply_facts_dict(fund, json.loads(Path(path).read_text(encoding="utf-8")))
    out["source"] = f"S-1 table via --facts {Path(path).name}"
    return out


def apply_facts_dict(fund, extra):
    extra = {k: v for k, v in extra.items() if not k.startswith("_")}
    months = extra.get("period_months") or 12
    if months != 12:                       # a year-to-date period: annualize the flows
        for k in ("rev0", "rev1", "gross", "opinc", "cfo", "capex"):
            if extra.get(k) is not None:
                extra[k] = extra[k] * 12 / months
    fund = dict(fund or {})
    fund.update({k: v for k, v in extra.items() if v is not None})
    fund["source"] = "S-1 summary table (parsed automatically)"
    return fund


# ---------------------------------------------------------------- Yahoo

_yc = {}
_yc_lock = threading.Lock()


def yahoo_daily(sym):
    with _yc_lock:
        if sym in _yc:
            return _yc[sym]
    p2 = int(datetime.combine(TODAY + timedelta(2), datetime.min.time(), timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?period1=0&period2={p2}&interval=1d&events=split")
    try:
        r = get_json(url, ttl=12 * 3600)["chart"]["result"][0]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            r = None
        else:
            raise
    out = None
    if r and r.get("timestamp"):
        off = r["meta"].get("gmtoffset", -18000)
        q = r["indicators"]["quote"][0]
        bars = []
        for i, ts in enumerate(r["timestamp"]):
            o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
            if None in (o, h, l, c):
                continue
            bars.append((datetime.fromtimestamp(ts + off, timezone.utc).date(), o, h, l, c, v or 0))
        splits = (r.get("events") or {}).get("splits", {})
        sp = [(datetime.fromtimestamp(int(s["date"]) + off, timezone.utc).date(), s["numerator"] / s["denominator"])
              for s in splits.values() if s.get("denominator")]
        out = {"bars": bars, "splits": sp}
    with _yc_lock:
        _yc[sym] = out
    return out


def split_factor(y, after):
    f = 1.0
    for dt, ratio in (y or {}).get("splits", []):
        if dt > after and ratio:
            f *= ratio
    return f


def last_before(bars, d):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid][0] < d:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


MKT = {"vix": "^VIX", "nasdaq": "^IXIC", "spx": "^GSPC", "ipo_etf": "IPO", "tnx": "^TNX"}


def sector_etf(sic):
    s = int(sic) if str(sic).isdigit() else 0
    if 2833 <= s <= 2836 or s == 8731:
        return "XBI"
    if s // 100 in (35, 36) or 7370 <= s <= 7379 or 3570 <= s <= 3579 or 3670 <= s <= 3679:
        return "XLK"
    if 3840 <= s <= 3851 or s // 100 == 80:
        return "XLV"
    if s // 100 == 48:
        return "XLC"
    if 6000 <= s <= 6411 or 6700 <= s <= 6799 and s != 6798:
        return "XLF"
    if s in (6798,) or s // 100 == 65:
        return "XLRE"
    if s // 100 in (13, 29):
        return "XLE"
    if s // 100 == 49:
        return "XLU"
    if s // 100 in (20, 21):
        return "XLP"
    if 5000 <= s <= 5999 or s // 100 in (70, 78, 79):
        return "XLY"
    if s // 100 in (10, 12, 14, 26, 28, 32, 33):
        return "XLB"
    return "XLI"


def backdrop(d, sic):
    """Market conditions on the day before date d (the first trade)."""
    out = {}
    for key, sym in list(MKT.items()) + [("sector", sector_etf(sic))]:
        try:
            y = yahoo_daily(sym)
        except Exception as e:  # noqa: BLE001
            fail(f"Yahoo {sym}", e)
            continue
        if not y:
            continue
        b = y["bars"]
        i = last_before(b, d)
        if i < 0:
            continue
        if key == "vix":
            out["vix"] = round(b[i][4], 2)
        elif key == "tnx":
            if i >= 63:
                out["tnx"] = round(b[i][4], 3)
                out["tnx_chg_3m"] = round(b[i][4] - b[i - 63][4], 3)
        elif i >= 20:
            out[f"{key}_20d"] = round(b[i][4] / b[i - 20][4] - 1, 4)
    out["sector_etf"] = sector_etf(sic)
    v = out.get("vix")
    out["vix_bucket"] = None if v is None else ("<15" if v < 15 else "15-20" if v < 20 else "20-30" if v < 30 else ">30")
    return out


# ---------------------------------------------------------------- outcomes

HORIZ_BARS = {"d1": 0, "d2": 1, "d3": 2, "d5": 4, "d10": 9, "d21": 20, "d30": 29, "d63": 62, "d90": 89}
HORIZ_CAL = {"d180": 180, "y1": 365, "y2": 730, "y3": 1095}


def outcomes(y, ipo_price, first_trade, lockup_days=None, cutoff=None):
    """Returns from the IPO price and from the first open. cutoff keeps it point-in-time:
    no bar on or after the cutoff date is used, so a horizon not reached by then is None."""
    if not y or not y["bars"] or ipo_price is None:
        return None
    bars = [b for b in y["bars"] if b[0] >= first_trade and (cutoff is None or b[0] < cutoff)]
    if not bars:
        return None
    ipo_adj = ipo_price / split_factor(y, first_trade)
    o0 = bars[0][1]
    out = {"open": o0, "ipo_adj": ipo_adj, "open_prem": o0 / ipo_adj - 1}

    def put(k, c):
        out[k] = {"ipo": c / ipo_adj - 1, "open": c / o0 - 1}

    for k, i in HORIZ_BARS.items():
        if len(bars) > i:
            put(k, bars[i][4])
    cal = dict(HORIZ_CAL)
    cal["lockup"] = lockup_days or 180
    for k, days in cal.items():
        target = first_trade + timedelta(days)
        j = next((n for n, b in enumerate(bars) if b[0] >= target), None)
        if j is not None:
            put(k, bars[j][4])
    if cutoff is None:
        put("today", bars[-1][4])
        out["last_date"] = iso(bars[-1][0])
    if len(bars) >= 30:
        out["dd30"] = min(b[3] for b in bars[:30]) / o0 - 1
    if len(bars) >= 252:
        out["dd1y"] = min(b[3] for b in bars[:252]) / o0 - 1
    return out


# ---------------------------------------------------------------- IPO records

def stage_a(u):
    """Cheap facts: cover terms, first trade, financials, market cap, backdrop."""
    key = f"{u['cik']}-{u['adsh']}-A"
    r = rec_get(key)
    if r is None:
        r = dict(u)
        try:
            r["cover"] = parse_cover(filing_text(u["url"], 200_000))
        except Exception as e:  # noqa: BLE001
            fail("SEC 424B4 cover", e)
            r["cover"] = {}
        filed = d_(u["filed"])
        r["first_trade"] = None
        r["price_status"] = "no ticker"
        if u.get("ticker"):
            try:
                y = yahoo_daily(u["ticker"])
            except Exception as e:  # noqa: BLE001
                fail("Yahoo daily bars", e)
                y = None
            if y and y["bars"]:
                ft = y["bars"][0][0]
                if filed - timedelta(3) <= ft <= filed + timedelta(10):
                    r["first_trade"], r["price_status"] = iso(ft), "ok"
                elif ft < filed - timedelta(3):
                    r["price_status"] = "not an IPO (traded before this 424B4)"
                else:
                    r["price_status"] = "ticker reused later (left market)"
            else:
                r["price_status"] = "no price data (left market or renamed)"
        ref = d_(r["first_trade"]) or filed + timedelta(1)
        try:
            r["fund"] = fundamentals(u["cik"], ref, grace=120)
        except Exception as e:  # noqa: BLE001
            fail("SEC XBRL companyfacts", e)
            r["fund"] = {}
        r["mkt"] = backdrop(ref, u["sic"])
        r["cover_v"] = 2
        rec_put(key, r)
    elif r.get("cover_v") != 2 and not r.get("cover", {}).get("price"):
        try:                                   # cached before the wider price patterns: read the cover once more
            c = parse_cover(filing_text(u["url"], 200_000))
            if c.get("price"):
                r["cover"] = c
        except Exception as e:  # noqa: BLE001
            fail("SEC 424B4 cover", e)
        else:
            r["cover_v"] = 2
            rec_put(key, r)
    _derive(r)
    if r.get("mcap") is None and r.get("first_trade") and r.get("cover", {}).get("price"):
        # SEC's XBRL feed has no share count for many dual-class companies: read it from the prospectus
        r = stage_b(r)
    return r


def stage_b(r):
    """Deeper facts: price-range history, amendments, lockup, structure, business text, status."""
    key = f"{r['cik']}-{r['adsh']}-B"
    b = rec_get(key)
    if b is None:
        b = {}
        try:
            sub = submissions(r["cik"])
        except Exception as e:  # noqa: BLE001
            fail("SEC submissions", e)
            sub = None
        filed = r["filed"]
        if sub:
            fs = sub["filings"]
            regs = [f for f in fs if f[0] in ("S-1", "F-1") and f[1] <= filed]
            amds = [f for f in fs if f[0] in ("S-1/A", "F-1/A") and f[1] <= filed]
            b["amendments"] = len(amds)
            if regs:
                b["first_public_filing"] = regs[0][1]
                b["days_to_pricing"] = (d_(filed) - d_(regs[0][1])).days
            first_rng = last_rng = None
            for f in amds:
                try:
                    c = parse_cover(filing_text(doc_url(r["cik"], f[2], f[3]), 150_000))
                except Exception as e:  # noqa: BLE001
                    fail("SEC S-1/A cover", e)
                    continue
                if c.get("range"):
                    first_rng = first_rng or {"date": f[1], "range": c["range"], "offered": c.get("offered")}
                    break
            for f in reversed(amds):
                if first_rng and f[1] <= first_rng["date"]:
                    last_rng = first_rng
                    break
                try:
                    c = parse_cover(filing_text(doc_url(r["cik"], f[2], f[3]), 150_000))
                except Exception as e:  # noqa: BLE001
                    fail("SEC S-1/A cover", e)
                    continue
                if c.get("range"):
                    last_rng = {"date": f[1], "range": c["range"], "offered": c.get("offered")}
                    break
            b["range_first"], b["range_last"] = first_rng, last_rng or first_rng
            gone = [f for f in fs if f[0] in ("25-NSE", "25", "15-12B", "15-12G", "15-15D") and f[1] > filed]
            b["left_market"] = {"form": gone[0][0], "date": gone[0][1]} if gone else None
        try:
            b.update(parse_deep(filing_text(r["url"], 2_500_000)))
            b["deep_v"] = 3
        except Exception as e:  # noqa: BLE001
            fail("SEC 424B4 prospectus summary", e)
        rec_put(key, b)
    elif b.get("deep_v") != 3:
        try:                                   # cached before the share-count fix (classes were added to their total): re-read once
            b.update(parse_deep(filing_text(r["url"], 2_500_000)))
            b["deep_v"] = 3
            rec_put(key, b)
        except Exception as e:  # noqa: BLE001
            fail("SEC 424B4 prospectus summary", e)
    r["deep"] = b
    _derive(r)
    return r


def _derive(r):
    c, f, b = r.get("cover", {}), r.get("fund", {}), r.get("deep", {})
    for k in ("offered", "secondary", "greenshoe"):      # cover page can be an image: use "The Offering"
        if not c.get(k) and b.get("offering_" + k):
            c[k] = b["offering_" + k]
    price = c.get("price")
    out_sh = b.get("outstanding") or f.get("dei_shares")
    r["mcap"] = price * out_sh if price and out_sh else None
    rng = (b.get("range_last") or {}).get("range") or c.get("range")
    r["range"] = rng
    if not price and rng and out_sh:          # not priced yet: size at the range midpoint
        r["mcap_mid"] = sum(rng) / 2 * out_sh
    fr = (b.get("range_first") or {}).get("range")
    if fr and rng:
        m0, m1 = sum(fr) / 2, sum(rng) / 2
        r["range_rev"] = 1 if m1 > m0 * 1.01 else -1 if m1 < m0 * 0.99 else 0
    if price and rng:
        lo, hi = rng
        r["price_vs_range"] = 2 if price > hi + 1e-9 else 1 if abs(price - hi) < 1e-9 else -1 if abs(price - lo) < 1e-9 \
            else -2 if price < lo - 1e-9 else 0
    off0 = (b.get("range_first") or {}).get("offered")
    if off0 and c.get("offered"):
        q = c["offered"] / off0
        r["upsized"] = 1 if q > 1.02 else -1 if q < 0.98 else 0
    if c.get("offered") and out_sh:
        r["float_pct"] = c["offered"] / out_sh
    if c.get("offered"):
        r["secondary_pct"] = (c.get("secondary") or 0) / (c["offered"] + (c.get("secondary") or 0))


def features(r):
    f, m = r.get("fund", {}), r.get("mkt", {})
    x = {}
    rev0, rev1 = f.get("rev0"), f.get("rev1")
    if rev0 and rev0 > 0:
        x["log_rev"] = math.log10(rev0)
        if f.get("gross") is not None:
            x["gross_margin"] = max(-1.0, min(1.0, f["gross"] / rev0))
        if f.get("opinc") is not None:
            x["op_margin"] = max(-3.0, min(1.0, f["opinc"] / rev0))
        if rev1 and rev1 > 0:
            x["growth"] = min(5.0, rev0 / rev1 - 1)
    if f.get("opinc") is not None:
        x["profitable"] = 1.0 if f["opinc"] > 0 else 0.0
    if r.get("mcap") or r.get("mcap_mid"):
        x["log_mcap"] = math.log10(r.get("mcap") or r["mcap_mid"])
    fm = fcf_margin(r)
    if fm is not None:
        x["fcf_margin"] = max(-3.0, min(1.0, fm))
    for k in ("float_pct", "secondary_pct", "range_rev", "price_vs_range"):
        if r.get(k) is not None:
            x[k] = float(r[k])
    if r.get("deep", {}).get("vc_backed") is not None:
        x["vc_backed"] = 1.0 if r["deep"]["vc_backed"] else 0.0
    for k in ("vix", "ipo_etf_20d", "sector_20d", "nasdaq_20d", "tnx_chg_3m"):
        if m.get(k) is not None:
            x[k] = m[k]
    if r.get("ipos_month") is not None:
        x["ipos_month"] = float(r["ipos_month"])
    return x


# ---------------------------------------------------------------- similarity

STOP = set("""the and for with that this from our are its their which will have has been can such into also may other
more than over these those they them your all any each including include includes through based within
company companies business businesses we us inc corp corporation llc ltd prospectus offering shares stock
common year years million billion approximately about first new one two three market markets provide
provides providing products product services service solutions platform customers customer believe
used using use well able across while where when what who how not only most many per period ended
table contents page summary highlights information elsewhere""".split())


def tokens(s):
    w = [x for x in re.findall(r"[a-z][a-z\-]{2,}", (s or "").lower()) if x not in STOP]
    return w + [a + " " + b for a, b in zip(w, w[1:])]


def tfidf(docs):
    df = {}
    toks = [tokens(d) for d in docs]
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    n = len(docs)
    vecs = []
    for t in toks:
        tf = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        v = {w: (c / len(t)) * math.log((1 + n) / (1 + df[w])) for w, c in tf.items()} if t else {}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})
    return vecs


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def shared_phrases(a, b, k=2):
    common = sorted(((a[w] * b[w], w) for w in a if w in b), reverse=True)
    bi = [w for _, w in common if " " in w][:k]
    return bi if len(bi) == k else bi + [w for _, w in common if " " not in w][: k - len(bi)]


def situation(tx, cx, scale, weights, min_features=1):
    num_, den, parts = 0.0, 0.0, []
    for k, w in weights.items():
        if k in tx and k in cx and w > 0:
            z = abs(tx[k] - cx[k]) / (scale.get(k) or 1.0)
            num_ += w * z * z
            den += w
            parts.append((w * z, k))
    if den == 0 or len(parts) < min_features:      # too few shared metrics: no score rather than a lucky one
        return None, []
    d = math.sqrt(num_ / den)
    return 100 * math.exp(-d), [k for _, k in sorted(parts)[:3]]


def scales(xs):
    out = {}
    keys = {k for x in xs for k in x}
    for k in keys:
        v = [x[k] for x in xs if k in x]
        if len(v) >= 3:
            m = sum(v) / len(v)
            sd = math.sqrt(sum((a - m) ** 2 for a in v) / (len(v) - 1))
            out[k] = sd if sd > 1e-9 else 1.0
    return out


def score_pool(target, pool, conf, with_text, mode="sic"):
    """mode 'sic': business + situation. mode 'archetype': nearest neighbors on revenue scale, growth,
    FCF margin and float (knn_weights), blended with business text (weights_archetype)."""
    sit_w, w = (conf["knn_weights"], conf["weights_archetype"]) if mode == "archetype" else (conf["situation_weights"], conf["weights"])
    tx = features(target)
    xs = [features(c) for c in pool]
    sc = scales(xs + [tx])
    vecs = tfidf([target.get("deep", {}).get("overview", "")] + [c.get("deep", {}).get("overview", "") for c in pool]) if with_text else None
    sims = []
    for i, c in enumerate(pool):
        s, top = situation(tx, xs[i], sc, sit_w, conf.get("knn_min_features", 3) if mode == "archetype" else 1)
        biz_sic = conf["business"]["sic4_bonus"] if c["sic"] == target["sic"] else \
            conf["business"].get("sic3_bonus", 0) if str(c["sic"])[:3] == str(target["sic"])[:3] else 0
        cos, phr = None, []
        if with_text and vecs[0] and vecs[i + 1]:
            cos = cosine(vecs[0], vecs[i + 1])
            phr = shared_phrases(vecs[0], vecs[i + 1])
        sims.append([s, biz_sic, cos, top, phr])
    known = sorted(x[2] for x in sims if x[2] is not None)
    med_cos = known[len(known) // 2] if known else 0.0
    top_cos = known[-1] if known and known[-1] > 0 else 1.0
    for c, (s, biz_sic, cos, top, phr) in zip(pool, sims):
        # text similarity is scaled to the closest prospectus in this pool (raw cosine kept as text_cos)
        text_part = conf["business"]["text"] * min(1.0, (cos if cos is not None else med_cos) / top_cos)
        c["text_cos"] = None if cos is None else round(cos, 3)
        c["biz_score"] = round(biz_sic + text_part, 1)
        c["sit_score"] = round(s, 1) if s is not None else None
        c["similarity"] = round(w["business"] * c["biz_score"] + w.get("situation", w.get("knn", 0)) * (s if s is not None else 0), 1)
        c["match_features"], c["match_phrases"] = top, phr
        c["text_missing"] = cos is None
    return sorted(pool, key=lambda c: -c["similarity"])


# ---------------------------------------------------------------- statistics

def wquantile(vals, ws, q):
    pairs = sorted(zip(vals, ws))
    tot = sum(w for _, w in pairs)
    if tot <= 0:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= q * tot - 1e-12:
            return v
    return pairs[-1][0]


def summarize(items, conf):
    """items: [(value, weight)]. Weighted median, IQR, hit rate, bootstrap 90% interval, leave-one-out."""
    items = [(v, w) for v, w in items if v is not None and w and w > 0]
    n = len(items)
    if n == 0:
        return {"n": 0}
    vals, ws = [v for v, _ in items], [w for _, w in items]
    med = wquantile(vals, ws, 0.5)
    rng = random.Random(conf["bootstrap"]["seed"])
    boots = []
    for _ in range(conf["bootstrap"]["resamples"]):
        idx = [rng.randrange(n) for _ in range(n)]
        boots.append(wquantile([vals[i] for i in idx], [ws[i] for i in idx], 0.5))
    boots.sort()
    lo, hi = boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots)) - 1]
    flips = []
    if n > 2:
        for i in range(n):
            m = wquantile(vals[:i] + vals[i + 1:], ws[:i] + ws[i + 1:], 0.5)
            if (m > 0) != (med > 0):
                flips.append(i)
    return {"n": n, "median": med, "q25": wquantile(vals, ws, 0.25), "q75": wquantile(vals, ws, 0.75),
            "hit": sum(v > 0 for v in vals) / n, "ci90": [lo, hi], "loo_flips": flips}


def _val(c, horizon, base):
    o = c.get("out") or {}
    return o.get("open_prem") if horizon == "open_prem" else (o.get(horizon) or {}).get(base)


def stat_for(comps, horizon, base, conf):
    rows = [(v, c.get("similarity", 1.0), c.get("name")) for c in comps
            if (v := _val(c, horizon, base)) is not None and c.get("similarity", 1.0)]
    s = summarize([(v, w) for v, w, _ in rows], conf)
    flips = s.pop("loo_flips", [])
    if flips:
        s["loo_flip_names"] = [rows[i][2] for i in flips]
    return s


def verdict(s, edge, conf):
    v = conf["verdict"]
    if not s.get("n") or s["n"] < v["min_n"]:
        return "MIXED", "low"
    m, h, (lo, hi) = s["median"], s["hit"], s["ci90"]
    call = "FAVORABLE" if m > edge and h >= v["hit_fav"] else "UNFAVORABLE" if m < -edge and h <= v["hit_unf"] else "MIXED"
    excl = lo > 0 or hi < 0
    flips = bool(s.get("loo_flip_names"))
    if s["n"] >= 20 and excl and not flips:
        conf_ = "high"
    elif s["n"] >= 12 and (excl or abs(h - 0.5) >= 0.15):
        conf_ = "medium"
    else:
        conf_ = "low"
    return call, conf_


def base_share_up(base, horizon):
    i = 1 if horizon == "d5" else 2
    xs = [s[i] for s in base["sample"] if s[i] is not None]
    return ((sum(x > 0 for x in xs) + 1) / (len(xs) + 2) if xs else 0.5), len(xs)


def verdict_vs_base(comps, base, horizon, ref, conf, anchor=None):
    """Verdict against the trailing base rate instead of zero.
    excess: call when the comparables' share of gains differs from the base rate by >= v1_dh.
    shrunk: p = (n_eff * comps' weighted share of gains + k * base share) / (n_eff + k), with similarity weights
            (times exp(-age/tau) when tau_years is set); FAVORABLE when p > 0.5 + delta, UNFAVORABLE below 0.5 - delta.
    Confidence comes from |p - 0.5| against conf_bands, the bands set on an earlier training window.
    verdict.by_horizon.{d5,d180} overrides any of these per horizon."""
    v = dict(conf["verdict"], **(conf["verdict"].get("by_horizon") or {}).get(horizon, {}))
    pb, nb = base_share_up(base, horizon)
    xs = range(nb)
    if anchor is not None:                 # the signal-adjusted base rate (signals.enabled)
        pb = anchor
    tau = v.get("tau_years")
    ws, ups = [], []
    for c in comps:
        val = _val(c, horizon, "open")
        w = c.get("similarity") or 0
        if val is None or not w:
            continue
        if tau and c.get("first_trade"):
            w *= math.exp(-((ref - d_(c["first_trade"])).days / 365.25) / tau)
        ws.append(w)
        ups.append(val > 0)
    den = sum(ws)
    h = sum(w for w, u in zip(ws, ups) if u) / den if den else None
    n_eff = den ** 2 / sum(w * w for w in ws) if den else 0
    if v["method"] == "excess":
        if h is None:
            call, p = "MIXED", pb
        else:
            p = h
            call = "FAVORABLE" if h - pb >= v["v1_dh"] and h > 0.5 else "UNFAVORABLE" if pb - h >= v["v1_dh"] and h < 0.5 else "MIXED"
    else:
        k = 1e9 if v["method"] == "base" else v["shrink_k"]
        p = pb if h is None else (n_eff * h + k * pb) / (n_eff + k)
        d = v["delta"]
        call = "FAVORABLE" if p > 0.5 + d else "UNFAVORABLE" if p < 0.5 - d else "MIXED"
    lo, hi = v.get("conf_bands", [0.1, 0.2])
    gap = abs(p - 0.5)
    conf_ = "high" if gap >= hi else "medium" if gap >= lo else "low"
    return (call, conf_), {"p_gain": p, "base_p_gain": pb, "comps_p_gain": h, "n_eff": n_eff, "base_n": len(xs), "method": v["method"]}


def revision_pricing(t, base_all, ps):
    """Where it prices vs the first range, from the trailing base rate of deals whose range moved the same way before
    pricing (raised / cut / unchanged). Walk-forward 2020-25: log score -1.105 vs -1.353 for the plain base rate, better
    in 6 of 6 years. Laplace-smoothed; falls back to all deals when the revision is not known yet."""
    d = t.get("deep") or {}
    first = (d.get("range_first") or {}).get("range") or t.get("range")
    last = (d.get("range_last") or {}).get("range") or t.get("range")
    if (not first or not last) and t.get("adsh"):         # older cached records: read the range path itself
        rp = range_path(t)
        first, last = first or rp.get("range"), last or rp.get("last") or rp.get("range")
    rev = range_revision(first, last)
    pool = [r for r in base_all if r.get("bucket")]
    same = [r for r in pool if rev and r.get("revision") == rev] or pool
    if not same or not isinstance(ps, dict) or ps.get("status") != "ok":
        return
    probs = {c: (sum(r["bucket"] == c for r in same) + 1) / (len(same) + 4) for c in PRICE_CATS}
    ps["base_probabilities"] = ps.get("base_probabilities") or {c: (sum(r["bucket"] == c for r in pool) + 1) / (len(pool) + 4) for c in PRICE_CATS}
    ps["probabilities"], ps["method"] = probs, "base rate by range revision"
    ps["revision"], ps["revision_n"] = rev or "not known yet", len(same)
    p3 = {"below": probs["below"], "inside": probs["mid"] + probs["top"], "above": probs["above"]}
    ps["headline"], ps["headline_probs"] = max(p3, key=p3.get), p3


def value_at_open(t, train, conf):
    """Price / sales at the opening price, ranked against past IPOs at THEIR opening price (retail buys at the open).
    Walk-forward 2020-25: IPOs that opened in the most expensive quarter were less often up by day 180 in 5 of 6
    years (e.g. 2021: 11% vs 27%). Gives the opening price above which this IPO would be in that quarter."""
    xs = sorted(r["mcap"] * (1 + r["out"]["open_prem"]) / r["fund"]["rev0"] for r in train
                if r.get("mcap") and (r.get("fund") or {}).get("rev0", 0) > 0 and (r.get("out") or {}).get("open_prem") is not None)
    f, d, c = t.get("fund") or {}, t.get("deep") or {}, t.get("cover") or {}
    rev, price = f.get("rev0"), c.get("price") or (sum(t["range"]) / 2 if t.get("range") else None)
    shares = d.get("outstanding") or f.get("dei_shares")
    if len(xs) < 20 or not (rev and rev > 0 and shares and price):
        return {"status": "needs revenue, a share count, a price and 20 past IPOs with data"}
    q50, q75 = xs[len(xs) // 2], xs[int(0.75 * (len(xs) - 1))]
    line = q75 * rev / shares
    out = {"status": "ok", "n": len(xs), "median_ps_at_open": q50, "rich_ps_at_open": q75, "ipo_price": price,
           "rich_open_price": line, "rich_open_premium": line / price - 1,
           "grid": [{"open_premium": g, "open_price": price * (1 + g), "p_s": price * (1 + g) * shares / rev,
                     "rank": sum(1 for v in xs if v < price * (1 + g) * shares / rev) / len(xs)} for g in (0.0, 0.25, 0.5, 1.0, 1.5)]}
    op = (t.get("out") or {}).get("open_prem")
    if op is not None:
        ps_ = price * (1 + op) * shares / rev
        out.update({"actual_open_premium": op, "actual_p_s": ps_, "actual_rank": sum(1 for v in xs if v < ps_) / len(xs), "rich": ps_ >= q75})
    return out


SIM_H = (("d1", "1 day"), ("d3", "3 days"), ("d5", "1 week"), ("d10", "2 weeks"), ("d21", "1 month"), ("d63", "3 months"), ("d180", "6 months"))


def simulate(classes, conf, draws=10000):
    """Monte Carlo over real past paths: each draw picks one past IPO (by weight) from a reference class and takes its
    whole path from the open, so day 1, day 5 and month 6 stay consistent. History, not a forecast."""
    rng = random.Random(conf["bootstrap"]["seed"])
    out = {}
    for name, items in classes.items():
        items = [(w, o) for w, o in items if w and o]
        if len(items) < 10:
            continue
        idx = rng.choices(range(len(items)), weights=[w for w, _ in items], k=draws)
        res = {"n_deals": len(items)}
        for h, _ in SIM_H:
            vs = sorted(v for i in idx if (v := ((items[i][1].get(h) or {}).get("open"))) is not None)
            if len(vs) < draws * 0.3:
                continue
            q = lambda p: vs[min(len(vs) - 1, int(p * len(vs)))]  # noqa: E731
            res[h] = {"p10": q(0.10), "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p90": q(0.90),
                      "up": sum(v > 0 for v in vs) / len(vs), "up20": sum(v >= 0.2 for v in vs) / len(vs),
                      "down20": sum(v <= -0.2 for v in vs) / len(vs), "paths": len(vs)}
        out[name] = res
    return out


OPEN_GROUPS = ("open below IPO price", "open 0-25% above", "open > 25% above")


def signal_x(r, open_prem=None):
    """Decision-time signals of one deal (fixed groups, nothing fitted):
    priced  - final price vs the first filed range (below / inside / above)
    ipo_etf - IPO ETF 20-day move before the first trade (up / down)
    vix     - VIX the day before (< 20 / >= 20)
    open    - first open vs the IPO price; known only once it opens (open_prem, or the deal's own outcome)."""
    b = r.get("bucket") or price_category(r)
    m = r.get("mkt") or {}
    x = {"priced": None if b is None else "inside" if b in ("mid", "top") else b,
         "ipo_etf": None if m.get("ipo_etf_20d") is None else "up" if m["ipo_etf_20d"] > 0 else "down",
         "vix": None if m.get("vix") is None else "<20" if m["vix"] < 20 else ">=20"}
    op = open_prem if open_prem is not None else (r.get("out") or {}).get("open_prem")
    x["open"] = None if op is None else OPEN_GROUPS[0] if op < 0 else OPEN_GROUPS[1] if op <= 0.25 else OPEN_GROUPS[2]
    return x


def _logit(p):
    return math.log(p / (1 - p))


def signal_p(train, x, horizon, base_p, conf, use=None):
    """Base rate plus one shrunk log-odds step per signal: step = (logit(group's share up) - logit(all)) * n/(n+k).
    train: deals with outcomes known before the decision; x: this deal's signal_x. Returns p and the steps."""
    sc = conf.get("signals", {})
    k, use = sc.get("k", 50), use or sc.get("use", ["priced", "ipo_etf", "vix", "open"])
    rows = [(signal_x(r), v > 0) for r in train if (v := ((r.get("out") or {}).get(horizon) or {}).get("open")) is not None]
    if not rows:
        return base_p, {}
    q = (sum(u for _, u in rows) + 1) / (len(rows) + 2)
    lo, steps = _logit(min(max(base_p, 1e-3), 1 - 1e-3)), {}
    for s in use:
        g = x.get(s)
        if g is None:
            continue
        grp = [u for sx, u in rows if sx.get(s) == g]
        if not grp:
            continue
        qg = (sum(grp) + 1) / (len(grp) + 2)
        steps[s] = {"group": g, "n": len(grp), "share_up": sum(grp) / len(grp), "step": (_logit(qg) - _logit(q)) * len(grp) / (len(grp) + k)}
        lo += steps[s]["step"]
    return 1 / (1 + math.exp(-lo)), steps


def decision_signals(t, uni, ref, base, conf, cut=True, train=None):
    """The signal model for this IPO: base rate + pre-open signal steps (the anchor the comparables shrink toward), and
    the at-open table (chance of a gain for each opening-jump group). Steps come from every deal in the lookback whose
    outcome was known by ref."""
    sc = conf.get("signals", {})
    train = train if train is not None else base_rate_recs(uni, ref, conf, cut=cut, months=sc.get("train_months", 120))
    x = signal_x({"bucket": price_category(t), "mkt": t.get("mkt")}, (t.get("out") or {}).get("open_prem"))
    pre = [s for s in sc.get("use", ["priced", "ipo_etf", "vix", "open"]) if s != "open"]
    recent = [r for r in train if d_(r["filed"]) >= ref - timedelta(int(30.44 * conf.get("base_rate", {}).get("months", 36)))]
    out = {"x": x, "train_n": len(train), "by_horizon": {}, "twins": twin_ipos(train, x, recent)}
    for h in sc.get("horizons", ["d1", "d3", "d5", "d30", "d90", "d180"]):
        ups = [v > 0 for r in recent if (v := ((r.get("out") or {}).get(h) or {}).get("open")) is not None]
        pb = (sum(ups) + 1) / (len(ups) + 2) if ups else 0.5
        p1, steps = signal_p(train, dict(x, open=None), h, pb, conf, use=pre)
        table = {g: signal_p(train, dict(x, open=g), h, pb, conf, use=pre + ["open"])[0] for g in OPEN_GROUPS}
        out["by_horizon"][h] = {"base_p": pb, "base_n": len(ups), "p_pre_open": p1, "steps": steps, "at_open": table,
                                "p_at_open": table.get(x["open"]) if x.get("open") else None}
    return out


TWIN_HORIZONS = ("d1", "d3", "d5", "d30", "d90", "d180")


def twin_ipos(train, x, recent):
    """Past IPOs with the same decision-time setup as this one (every signal this deal has, matched exactly), and how
    they did from the open at each horizon, next to all recent IPOs. Descriptive: in the 2020-25 walk-forward these
    signals did not beat the plain base rate."""
    keys = [k for k in ("priced", "ipo_etf", "vix", "open") if x.get(k)]
    tw = [r for r in train if keys and all(signal_x(r).get(k) == x[k] for k in keys)]

    def stats(rs):
        o = {}
        for h in TWIN_HORIZONS:
            vs = sorted(v for r in rs if (v := ((r.get("out") or {}).get(h) or {}).get("open")) is not None)
            o[h] = {"n": len(vs), "share_up": sum(v > 0 for v in vs) / len(vs) if vs else None, "median": vs[len(vs) // 2] if vs else None}
        return o
    ex = sorted(tw, key=lambda r: r["first_trade"], reverse=True)[:10]
    return {"matched_on": {k: x[k] for k in keys}, "n": len(tw), "twins": stats(tw), "all_recent": stats(recent),
            "examples": [{"ticker": r.get("ticker"), "name": r["name"], "first_trade": r["first_trade"],
                          **{h: ((r.get("out") or {}).get(h) or {}).get("open") for h in TWIN_HORIZONS}} for r in ex]}


def reference_levels(comps, conf):
    rc = conf["reference"]
    rows = []
    edges = rc["bins"] + [float("inf")]
    for a, b in zip(edges, edges[1:]):
        sel = [c for c in comps if (c.get("out") or {}).get("open_prem") is not None and a <= c["out"]["open_prem"] < b]
        rows.append({"bin": [a, b if b != float("inf") else None],
                     "d5": stat_for(sel, "d5", "open", conf), "d30": stat_for(sel, "d30", "open", conf)})
    level = weak = None
    for t in rc.get("thresholds") or rc["bins"][1:]:
        sel = [c for c in comps if (c.get("out") or {}).get("open_prem") is not None and c["out"]["open_prem"] >= t]
        s = stat_for(sel, "d5", "open", conf)
        if not s.get("n"):
            break
        if weak is None and s["n"] >= rc["weak_min_n"] and s["median"] < 0:
            weak = {"open_premium_at_or_above": t, "d5": s}
        if s["n"] >= rc["min_n"] and s["median"] < 0 and s["ci90"][1] < 0:
            level = {"open_premium_at_or_above": t, "d5": s}
            break
    return {"bins": rows, "level": level or "not enough evidence", "weak_level": weak or "none"}


# ---------------------------------------------------------------- archetypes, pricing, valuation

ARCH_NAMES = {"hyper_growth": "Hyper-growth / capital-intensive", "saas": "High-margin SaaS / software",
              "profitable": "Profitable / moderate growth", "consumer": "Consumer / marketplace / hardware",
              "unclassified": "Unclassified (falls back to same-industry matching)"}
PRICE_CATS = ("below", "mid", "top", "above")


def fcf_margin(r):
    f = r.get("fund") or {}
    rev = f.get("rev0")
    if rev and rev > 0 and f.get("cfo") is not None:
        return (f["cfo"] - (f.get("capex") or 0)) / rev
    return None


def _in_ranges(sic, ranges):
    s = int(sic) if str(sic).isdigit() else -1
    return any(a <= s <= b for a, b in ranges)


def archetype(r, conf):
    """First rule that fits, in this order. Returns (key, reasons)."""
    a = conf["archetypes"]
    f = r.get("fund") or {}
    x = features(r)
    rev, g, gm, fm = f.get("rev0"), x.get("growth"), x.get("gross_margin"), fcf_margin(r)
    nrr = (r.get("deep") or {}).get("nrr")
    capex_int = (f.get("capex") or 0) / rev if rev and f.get("capex") is not None else None
    if rev and rev >= a["hyper_min_revenue"] and g is not None and g > a["hyper_min_growth"]:
        why = [f"revenue ${rev / 1e9:.1f}B (>= ${a['hyper_min_revenue'] / 1e9:.0f}B)", f"growth {g:+.0%} (> {a['hyper_min_growth']:.0%})"]
        if capex_int is None:
            why.append("capex not reported")
        else:
            why.append(f"capex {capex_int:.0%} of revenue" + (" (capital-intensive)" if capex_int >= a["heavy_capex_pct"]
                       else " (below the heavy-capex mark; infrastructure may be bought as an operating cost)"))
        return "hyper_growth", why
    software = _in_ranges(r.get("sic"), a["software_sic"])
    if gm is not None and gm > a["saas_min_gross_margin"] and ((nrr is not None and nrr > a["saas_min_nrr"]) or (nrr is None and software)):
        return "saas", [f"gross margin {gm:.0%} (> {a['saas_min_gross_margin']:.0%})",
                        f"net revenue retention {nrr}%" if nrr is not None else "NRR not disclosed; software industry code"]
    lo, hi = a["profitable_growth"]
    if fm is not None and fm > 0 and g is not None and lo <= g <= hi:
        return "profitable", [f"FCF margin {fm:+.0%} (> 0)", f"growth {g:+.0%} (in {lo:.0%} to {hi:.0%})"]
    if _in_ranges(r.get("sic"), a["consumer_sic"]):
        return "consumer", [f"industry code {r.get('sic')} is consumer / marketplace / hardware"]
    return "unclassified", ["no rule fits (often missing financials)"]


def price_category(r):
    """Final price vs the FIRST filed range. 'above' covers an upward range revision and Rule 430A pricing above the range."""
    rng = ((r.get("deep") or {}).get("range_first") or {}).get("range") or r.get("range")
    p = (r.get("cover") or {}).get("price")
    if not rng or not p:
        return None
    lo, hi = rng
    if p < lo - 1e-9:
        return "below"
    if p > hi + 1e-9:
        return "above"
    if abs(p - hi) <= 0.005 * hi:
        return "top"
    return "mid"


def bank_pricing(recs, ref):
    """Per lead-left bank: median final price vs first-range midpoint, and median day-30 return from the open."""
    by = {}
    for r in recs:
        if d_(r["filed"]) >= ref:
            continue
        bk = (r.get("cover") or {}).get("banks") or []
        rng = ((r.get("deep") or {}).get("range_first") or {}).get("range")
        p = (r.get("cover") or {}).get("price")
        if not bk or not rng or not p:
            continue
        d30 = ((r.get("out") or {}).get("d30") or {}).get("open")
        by.setdefault(bk[0], []).append((p / (sum(rng) / 2) - 1, d30))
    out = {}
    for b, v in by.items():
        ms = sorted(x for x, _ in v)
        ds = sorted(y for _, y in v if y is not None)
        out[b] = {"n": len(v), "margin": ms[len(ms) // 2], "d30": ds[len(ds) // 2] if ds else None}
    return out


def pricing_features(r, banks):
    rng = ((r.get("deep") or {}).get("range_first") or {}).get("range") or r.get("range")
    m = r.get("mkt") or {}
    x = {}
    if rng:
        x["range_width"] = (rng[1] - rng[0]) / (sum(rng) / 2)
    for k in ("spx_20d", "nasdaq_20d", "sector_20d"):
        if m.get(k) is not None:
            x[k] = m[k]
    if r.get("float_pct") is not None:
        x["float_pct"] = r["float_pct"]
    bk = (r.get("cover") or {}).get("banks") or []
    if bk and bk[0] in banks:
        x["bank_margin"] = banks[bk[0]]["margin"]
        if banks[bk[0]]["d30"] is not None:
            x["bank_d30"] = banks[bk[0]]["d30"]
    return x


def pricing_sim(target, recs, conf, ref):
    """Monte Carlo over the most similar past deals: draw a deal in proportion to similarity, take where it priced.
    Repeated draws give the probabilities; a bootstrap of the neighbor set gives their 90% intervals."""
    pc = conf["pricing"]
    nb = [r for r in recs if price_category(r) and r["cik"] != target["cik"] and d_(r["filed"]) < ref]
    if len(nb) < pc["min_neighbors"]:
        return {"status": f"not enough priced comparables with a filed range ({len(nb)} < {pc['min_neighbors']})"}
    banks = bank_pricing(nb, ref)
    tx = pricing_features(target, banks)
    xs = [pricing_features(r, banks) for r in nb]
    sc = scales(xs + [tx])
    scored = []
    for r, x in zip(nb, xs):
        s, _ = situation(tx, x, sc, pc["weights"])
        if s is not None:
            scored.append((s, r))
    scored.sort(key=lambda z: -z[0])
    top = scored[: pc["k"]]
    cats = [price_category(r) for _, r in top]
    ws = [max(s, 1e-6) for s, _ in top]
    rng = random.Random(conf["bootstrap"]["seed"])
    draws = rng.choices(range(len(top)), weights=ws, k=pc["simulations"])
    probs = {c: sum(1 for i in draws if cats[i] == c) / len(draws) for c in PRICE_CATS}
    boots = {c: [] for c in PRICE_CATS}
    for _ in range(pc["bootstrap"]):
        idx = [rng.randrange(len(top)) for _ in top]
        tw = sum(ws[i] for i in idx)
        for c in PRICE_CATS:
            boots[c].append(sum(ws[i] for i in idx if cats[i] == c) / tw)
    ci = {c: [sorted(v)[int(0.05 * len(v))], sorted(v)[int(0.95 * len(v)) - 1]] for c, v in boots.items()}
    return {"status": "ok", "neighbors_used": len(top), "simulations": pc["simulations"], "probabilities": probs, "ci90": ci,
            "actual": price_category(target), "target_features": tx,
            "lead_bank": ((target.get("cover") or {}).get("banks") or [None])[0],
            "closest_deals": [{"name": r["name"], "ticker": r.get("ticker"), "filed": r["filed"], "similarity": round(s, 1),
                               "priced": price_category(r)} for s, r in top[:8]],
            "not_modelled": "order-book coverage: no record of it exists for past deals, so it cannot be weighted"}


def blend_pricing(ps, base, conf):
    """Anchor the neighbor probabilities on the trailing base rate: p = alpha * neighbors + (1 - alpha) * base.
    Adds a three-way headline (below / inside / above) because 'inside' is two buckets."""
    a = conf["pricing"].get("base_alpha", 1.0)
    bs = base.get("buckets")
    if ps.get("status") != "ok" or not bs or not base.get("n_buckets"):
        return
    ps["neighbor_probabilities"] = dict(ps["probabilities"])
    ps["base_probabilities"] = bs
    ps["probabilities"] = {c: a * ps["probabilities"][c] + (1 - a) * bs[c] for c in PRICE_CATS}
    p = ps["probabilities"]
    p3 = {"below": p["below"], "inside": p["mid"] + p["top"], "above": p["above"]}
    ps["headline"] = max(p3, key=p3.get)
    ps["headline_probs"] = p3
    ps["alpha"] = a


def _pct_rank(v, xs):
    return sum(1 for z in xs if z < v) / len(xs) if xs and v is not None else None


def valuation(target, comps, conf):
    """Is the IPO priced rich or cheap against comparables at their own IPO price?"""
    vc = conf["valuation"]
    f, c, d = target.get("fund") or {}, target.get("cover") or {}, target.get("deep") or {}
    rev, sh = f.get("rev0"), d.get("outstanding") or f.get("dei_shares")
    price = c.get("price") or (sum(target["range"]) / 2 if target.get("range") else None)
    if not (rev and rev > 0 and sh and price):
        return {"status": "needs revenue, a share count and a price or range"}
    g, fm = features(target).get("growth"), fcf_margin(target)
    ps = price * sh / rev
    comp_rows = []
    for x in comps:
        xf = x.get("fund") or {}
        if x.get("mcap") and (xf.get("rev0") or 0) > 0:
            xg, xfm = features(x).get("growth"), fcf_margin(x)
            comp_rows.append({"ps": x["mcap"] / xf["rev0"], "ga": (x["mcap"] / xf["rev0"]) / (xg * 100) if xg and xg > 0 else None,
                              "r40": (xg + xfm) * 100 if xg is not None and xfm is not None else None})
    cps = sorted(r["ps"] for r in comp_rows)
    cga = sorted(r["ga"] for r in comp_rows if r["ga"] is not None)
    cr40 = sorted(r["r40"] for r in comp_rows if r["r40"] is not None)
    if len(cps) < vc["min_n"]:
        return {"status": f"only {len(cps)} comparables with revenue and market cap"}
    ga = ps / (g * 100) if g and g > 0 else None
    r40 = (g + fm) * 100 if g is not None and fm is not None else None

    def lab(rank, higher_is_rich=True):
        if rank is None:
            return "n/a"
        rank = rank if higher_is_rich else 1 - rank
        return "rich" if rank >= vc["rich_pct"] else "cheap" if rank <= vc["cheap_pct"] else "in line"

    ps_l, ga_l = lab(_pct_rank(ps, cps)), lab(_pct_rank(ga, cga)) if ga is not None and cga else "n/a"
    r40_l = lab(_pct_rank(r40, cr40), higher_is_rich=False) if r40 is not None and cr40 else "n/a"
    if ps_l == "rich" and ga_l in ("rich", "n/a"):
        overall = "OVERVALUED vs comparables"
    elif ps_l == "cheap" and ga_l in ("cheap", "n/a"):
        overall = "UNDERVALUED vs comparables"
    elif ps_l == "in line" and ga_l in ("in line", "n/a"):
        overall = "FAIRLY VALUED vs comparables"
    else:
        overall = f"MIXED: {ps_l} on sales, {ga_l} for its growth"
    med = cps[len(cps) // 2]
    q75 = cps[int(0.75 * (len(cps) - 1))]
    return {"status": "ok", "overall": overall, "price_used": price, "price_basis": "final" if c.get("price") else "range midpoint",
            "p_s": ps, "p_s_rank": _pct_rank(ps, cps), "p_s_label": ps_l, "comps_p_s_median": med, "comps_p_s_q75": q75,
            "growth_adj": ga, "growth_adj_rank": _pct_rank(ga, cga), "growth_adj_label": ga_l,
            "comps_growth_adj_median": cga[len(cga) // 2] if cga else None,
            "rule_of_40": r40, "rule_of_40_label": r40_l, "comps_rule_of_40_median": cr40[len(cr40) // 2] if cr40 else None,
            "price_at_comps_median_p_s": med * rev / sh, "price_at_comps_q75_p_s": q75 * rev / sh, "n": len(cps),
            "note": "comparables are valued at their own IPO price; current peer multiples need a Yahoo login"}


def closest_peer(target, comps, val):
    pr = [c for c in comps if (c.get("out") or {}).get("open_prem") is not None]
    if not pr:
        return None
    p = pr[0]

    def m(r, ps=None):
        x, f = features(r), r.get("fund") or {}
        return {"revenue": f.get("rev0"), "growth": x.get("growth"), "fcf_margin": fcf_margin(r), "float_pct": r.get("float_pct"),
                "p_s_at_ipo": ps if ps is not None else (r["mcap"] / f["rev0"] if r.get("mcap") and f.get("rev0") else None)}
    o = p["out"]
    return {"name": p["name"], "ticker": p.get("ticker"), "first_trade": p.get("first_trade"), "similarity": p.get("similarity"),
            "archetype": p.get("archetype"), "target": m(target, (val or {}).get("p_s")), "peer": m(p),
            "open_premium": o.get("open_prem"), "returns_from_open": {h: (o.get(h) or {}).get("open") for h in ("d1", "d5", "d30", "d180")}}


def reference_prices(target, level):
    """Historical reference prices: the IPO price (or range points) times one plus the caution level. Not a recommendation."""
    if not isinstance(level, dict):
        return None
    t = level["open_premium_at_or_above"]
    c = target.get("cover") or {}
    pts = {"final": c["price"]} if c.get("price") else ({"low": target["range"][0], "mid": sum(target["range"]) / 2,
                                                         "top": target["range"][1]} if target.get("range") else {})
    return {k: round(v * (1 + t), 2) for k, v in pts.items()}


# ---------------------------------------------------------------- the analysis

def _sic2(s):
    return str(s)[:2]


def _pit_fund(r, ref):
    """Point-in-time comparable financials: a comparable that listed shortly before `ref` may have its pre-IPO
    figures only in filings made after `ref`. Re-read them from filings dated before `ref` (empty if none)."""
    if d_(r["filed"]) < ref - timedelta(550):
        return
    try:
        f = fundamentals(r["cik"], d_(r["first_trade"]) or d_(r["filed"]) + timedelta(1), grace=120, known_by=ref)
    except Exception as e:  # noqa: BLE001
        fail("SEC XBRL companyfacts", e)
        return
    if f.get("fy_end") and d_(f["fy_end"]) >= ref:
        f = {}
    if not f.get("dei_shares") and (r.get("fund") or {}).get("dei_shares"):
        f["dei_shares"] = r["fund"]["dei_shares"]      # share count is in the prospectus; only used for size
    r["fund"] = f
    _derive(r)


def range_path(r):
    """First and last filed price range before the 424B4 (earliest / latest S-1/A or F-1/A with one), cached per deal.
    Both are public before pricing, so a range revision is a pre-pricing signal."""
    key = f"{r['cik']}-{r['adsh']}-R"
    got = rec_get(key)
    if got is not None and got.get("v") == 2:
        return got
    out = {"v": 2, "range": (got or {}).get("range"), "last": None}
    try:
        fs = [f for f in submissions(r["cik"])["filings"] if f[0] in ("S-1/A", "F-1/A") and f[1] <= r["filed"]]
        if not out["range"]:
            for f in fs[:6]:
                c = parse_cover(filing_text(doc_url(r["cik"], f[2], f[3]), 150_000))
                if c.get("range"):
                    out["range"] = c["range"]
                    break
        for f in reversed(fs[-4:]):
            c = parse_cover(filing_text(doc_url(r["cik"], f[2], f[3]), 150_000))
            if c.get("range"):
                out["last"] = c["range"]
                break
    except Exception as e:  # noqa: BLE001
        fail("SEC S-1/A cover (base rate)", e)
        return out
    rec_put(key, out)
    return out


def exit_value(r, before=None):
    """For a comparable with no price history (it left the market): the takeover price from its merger proxy or tender
    offer, or -100% for a bankruptcy 8-K (item 1.03). Only what was filed before `before`. Cached per deal."""
    key = f"{r['cik']}-{r['adsh']}-X"
    got = rec_get(key)
    if got is None:
        got = {}
        try:
            fs = submissions(r["cik"])["filings"]
            for f in reversed([f for f in fs if f[0] in ("DEFM14A", "SC TO-T", "SC 14D9", "PREM14A") and f[1] > r["filed"]][-3:]):
                txt = re.sub(r"\s+", " ", filing_text(doc_url(r["cik"], f[2], f[3]), 200_000))
                m = re.search(r"(?:right to receive|entitled to receive|offer to purchase[^.]{0,120}?at|for|of)\s+\$\s?(\d+(?:\.\d+)?)\s+(?:per share\s+)?in cash", txt, re.I)
                if m:
                    got = {"kind": "acquired", "price": float(m.group(1)), "date": f[1], "form": f[0]}
                    break
            if not got:
                for f in [f for f in fs if f[0] == "8-K" and f[1] > r["filed"]][-40:]:
                    txt = filing_text(doc_url(r["cik"], f[2], f[3]), 60_000)
                    if re.search(r"Item\s+1\.03", txt) and re.search(r"(?i)chapter 11|bankruptcy", txt):
                        got = {"kind": "bankrupt", "price": 0.0, "date": f[1], "form": "8-K 1.03"}
                        break
        except Exception as e:  # noqa: BLE001
            fail("SEC merger / bankruptcy filings", e)
            return None
        rec_put(key, got)
    if not got or (before and d_(got["date"]) >= before):
        return None
    return got


def s1_brief(t):
    """Plain-English brief from the target's own prospectus: what it does, who controls it, lockup, use of proceeds,
    the first risks listed in its risk summary, and the post-IPO calendar. Facts only, each from the filing."""
    d, c = t.get("deep") or {}, t.get("cover") or {}
    risks, what = [], ""
    try:
        txt = re.sub(r"\s+", " ", filing_text(t["url"], 1_500_000))
        for o in re.finditer(r"\bOverview\b", txt):            # the business overview, not the legal preamble
            what = what_it_does(txt[o.end(): o.end() + 1500])
            if what:
                break
        sd = re.search(r"(\d{2,3})(?:-day| days) after the date of (?:this|the final) prospectus", txt, re.I)
        if sd and 30 <= int(sd.group(1)) <= 400:
            d = dict(d, lockup_days=int(sd.group(1)))
        m = re.search(r"(?i)(?:summary of risk factors|risk factors summary|summary risk factors|summary of the risks)", txt)
        if m:
            seg = txt[m.end(): m.end() + 6000]
            for part in re.split(r"\s*[•●�▪]\s+", seg)[1:7]:
                part = part.strip()
                if 30 < len(part) < 600:
                    risks.append(part[:260].rstrip(" ;,") + ("..." if len(part) > 260 else ""))
    except Exception as e:  # noqa: BLE001
        fail("SEC prospectus (risk summary)", e)
    ft = d_(t.get("first_trade")) if t.get("first_trade") else None
    ld = d.get("lockup_days") or 180
    cal = None
    if ft or t.get("status") != "upcoming":
        base_day = ft or d_(t["ref_date"])
        q_end = date(base_day.year, ((base_day.month - 1) // 3 + 1) * 3, 1)
        q_end = (q_end.replace(day=28) + timedelta(4)).replace(day=1) - timedelta(1)        # last day of that quarter
        cal = {"first_trade": iso(base_day), "quiet_period_ends": iso(base_day + timedelta(25)),
               "first_earnings_estimate": iso(q_end + timedelta(45)), "lockup_expires": iso(base_day + timedelta(ld)),
               "twelve_month_seasoning": iso(base_day + timedelta(365))}
    ctrl = ("dual-class shares" if d.get("dual_class") else "one share class") + ("; a controlled company (insiders hold the majority vote)" if d.get("controlled") else "")
    return {"overview": (d.get("overview") or "")[:700], "what": what, "control": ctrl,
            "selling_holders_share": t.get("secondary_pct"), "lockup": f"{ld} days" + ("; can end early (earnings-release clause)" if d.get("lockup_early_release") else ""),
            "use_of_proceeds": (d.get("use_of_proceeds") or "")[:400], "risks": risks[:5], "calendar": cal,
            "banks": (c.get("banks") or [])[:6]}


def first_range(r):
    return range_path(r).get("range")


def range_revision(first, last):
    """'raised' / 'cut' / 'unchanged' by the range midpoint (1% band), None when either is missing."""
    if not first or not last:
        return None
    m0, m1 = sum(first) / 2, sum(last) / 2
    return "raised" if m1 > m0 * 1.01 else "cut" if m1 < m0 * 0.99 else "unchanged"


def base_rate_recs(uni, ref, conf, cut=True, months=None):
    """Every US IPO (size filter as the backtest) priced in the base window before ref, with outcomes cut at ref."""
    months = months or conf.get("base_rate", {}).get("months", 36)
    rows = [u for u in uni if ref - timedelta(int(30.44 * months)) <= d_(u["filed"]) < ref]
    with ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(stage_a, rows))
    out = []
    for r in recs:
        ft, c = d_(r["first_trade"]), r.get("cover") or {}
        if not (ft and ft < ref and r.get("ticker") and c.get("price") and not c.get("units") and (r.get("mcap") or 0) >= conf["min_mcap_usd"]):
            continue
        r["out"] = outcomes(yahoo_daily(r["ticker"]), c["price"], ft, cutoff=ref if cut else None)
        out.append(r)
    with ThreadPoolExecutor(4) as ex:
        paths = list(ex.map(range_path, out))
    for r, rp in zip(out, paths):
        rng = rp.get("range")
        r["bucket"] = price_category({"cover": r["cover"], "deep": {"range_first": {"range": rng}} if rng else {}})
        r["revision"] = range_revision(rng, rp.get("last"))
    return out


def base_rate(recs, conf):
    """Trailing base rates: day-5 and day-180 from the open (unweighted), and where deals priced vs their first range."""
    st = lambda h: summarize([(v, 1.0) for r in recs if (v := ((r.get("out") or {}).get(h) or {}).get("open")) is not None], conf)  # noqa: E731
    bk = [r["bucket"] for r in recs if r.get("bucket")]
    return {"window_months": conf.get("base_rate", {}).get("months", 36), "n": len(recs), "d5": st("d5"), "d180": st("d180"),
            "buckets": {c: (sum(b == c for b in bk) + 1) / (len(bk) + 4) for c in PRICE_CATS}, "n_buckets": len(bk),
            "sample": [[r["first_trade"], ((r["out"] or {}).get("d5") or {}).get("open"), ((r["out"] or {}).get("d180") or {}).get("open"), r.get("bucket")]
                       for r in recs]}


def build_pool(target, ref, conf, log=print, cutoff=True):
    """Comparables: same 2-digit SIC, priced in the lookback window before ref, filtered and scored."""
    start = ref - timedelta(int(365.25 * conf["lookback_years"]))
    uni = universe(start, ref - timedelta(1))
    month_counts = {}
    for u in uni:
        month_counts[u["filed"][:7]] = month_counts.get(u["filed"][:7], 0) + 1
    target["ipos_month"] = month_counts.get(target["filed"][:7], 0)
    t_arch, t_why = archetype(target, conf)
    target["archetype"], target["archetype_why"] = t_arch, t_why
    mode = "archetype" if conf.get("matching") == "archetype" and t_arch != "unclassified" else "sic"
    if mode == "archetype":
        cands = [u for u in uni if u["cik"] != target["cik"] and d_(u["filed"]) < ref]
        log(f"  {len(uni)} US IPO filings in {start}..{ref}; archetype {ARCH_NAMES[t_arch]} -> reading all cover pages...")
    else:
        cands = [u for u in uni if _sic2(u["sic"]) == _sic2(target["sic"]) and u["cik"] != target["cik"] and d_(u["filed"]) < ref]
        log(f"  {len(uni)} US IPO filings in {start}..{ref}; {len(cands)} share SIC {_sic2(target['sic'])}xx. Reading cover pages...")
    with ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(stage_a, cands))
    for r in recs:
        r["ipos_month"] = month_counts.get(r["filed"][:7], 0)
        if cutoff:
            _pit_fund(r, ref)
    keep = []
    for r in recs:
        c = r.get("cover", {})
        if r["price_status"].startswith("not an IPO") or c.get("units"):
            continue
        if c.get("adr") and not target.get("cover", {}).get("adr"):
            continue
        if r.get("mcap") is not None and r["mcap"] < conf["min_mcap_usd"]:
            continue
        if r.get("mcap") is None and not (c.get("price") and c.get("offered") and c["price"] * c["offered"] >= 40e6):
            continue
        keep.append(r)
    for r in keep:
        r["archetype"] = archetype(r, conf)[0]
    widened = False
    n_arch = None
    if mode == "archetype":
        same = [r for r in keep if r["archetype"] == t_arch]
        n_arch = len(same)
        if len(same) < conf["archetype_min_pool"]:      # too few of this kind: add same-industry IPOs, and say so
            ids = {r["cik"] for r in same}
            same += [r for r in keep if _sic2(r["sic"]) == _sic2(target["sic"]) and r["cik"] not in ids]
            widened = True
        keep = same
    pre = score_pool(target, keep, conf, with_text=False, mode=mode)[: conf["deep_candidates"]]
    log(f"  {len(keep)} candidates ({mode} matching{', widened to same industry' if widened else ''}); reading the prospectus of the closest {len(pre)}...")
    with ThreadPoolExecutor(4) as ex:
        deep = list(ex.map(stage_b, pre))
    deep = [r for r in deep if r.get("mcap") is None or r["mcap"] >= conf["min_mcap_usd"]]
    for r in deep:
        ft = d_(r["first_trade"])
        y = yahoo_daily(r["ticker"]) if r.get("ticker") and ft else None
        r["out"] = outcomes(y, r["cover"].get("price"), ft, r["deep"].get("lockup_days"),
                            cutoff=ref if cutoff else None) if y else None
    scored = score_pool(target, deep, conf, with_text=True, mode=mode)
    for r in scored:
        r["archetype"] = archetype(r, conf)[0]
    n = max(conf["comps_min"], min(conf["comps_max"], len(scored)))
    counts = {"universe": len(uni), "candidates": len(cands), "filtered": len(keep), "deep": len(deep), "mode": mode,
              "archetype": t_arch, "archetype_pool": n_arch, "widened_to_industry": widened}
    return scored[:n], counts, uni, month_counts, scored


def resolve(q):
    """Ticker or company name -> CIK and its filings."""
    qq = q.strip()
    try:
        tick = get_json("https://www.sec.gov/files/company_tickers.json", sec=True, ttl=86400)
        for v in tick.values():
            if v["ticker"].upper() == qq.upper():
                return int(v["cik_str"])
    except Exception as e:  # noqa: BLE001
        fail("SEC company_tickers", e)
    d = efts({"q": f'"{qq}"', "forms": "S-1,S-1/A,F-1,F-1/A,424B4", "dateRange": "custom",
              "startdt": (TODAY - timedelta(800)).isoformat(), "enddt": TODAY.isoformat()}, 86400)
    hits = d["hits"]["hits"]
    for h in hits:
        name = (h["_source"].get("display_names") or [""])[0]
        if qq.lower() in name.lower() or f"({qq.upper()})" in name:
            return int(h["_source"]["ciks"][0])
    if hits:
        return int(hits[0]["_source"]["ciks"][0])
    sys.exit(f"ipo.py: no SEC registration found for {q!r}")


MODES = ("at-open", "pre-pricing")


def cut_filings(fs, as_of, mode="at-open"):
    """Point-in-time filing list. pre-pricing: nothing dated on or after as_of.
    at-open: also the 424B4 filed up to 3 days later, because its terms were set at pricing, the evening before trading."""
    if not as_of:
        return fs
    if mode == "pre-pricing":
        return [f for f in fs if d_(f[1]) < as_of]
    return [f for f in fs if d_(f[1]) < as_of or (f[0] == "424B4" and d_(f[1]) <= as_of + timedelta(3))]


def build_target(cik, facts_file=None, as_of=None, mode="at-open"):
    """The IPO under study, from its own filings. as_of keeps a backtest point-in-time (see cut_filings for mode)."""
    sub = submissions(cik)
    fs = cut_filings(sub["filings"], as_of, mode)
    regs = [f for f in fs if f[0] in ("S-1", "F-1")]
    after = regs[0][1] if regs else "0000"
    p424 = [f for f in fs if f[0] == "424B4" and f[1] >= after]
    amds = [f for f in fs if f[0] in ("S-1/A", "F-1/A", "S-1", "F-1")]
    src = p424[0] if p424 else (amds[-1] if amds else None)
    if not src:
        sys.exit("ipo.py: no S-1/F-1 or 424B4 found for this company")
    t = {"cik": cik, "name": sub["name"], "sic": sub["sic"], "ticker": (sub["tickers"] or [None])[0],
         "filed": src[1], "adsh": src[2], "url": doc_url(cik, src[2], src[3]), "form": src[0],
         "status": "priced" if p424 else "upcoming"}
    t["cover"] = parse_cover(filing_text(t["url"], 200_000))
    if not p424:                       # an S-1/A only has an *assumed* price (the range midpoint)
        t["cover"].pop("price", None)
    t["ticker"] = t["ticker"] or t["cover"].get("symbol")
    y = yahoo_daily(t["ticker"]) if t["ticker"] else None
    ft = None
    if y and y["bars"] and p424:
        f0 = y["bars"][0][0]
        if d_(p424[0][1]) - timedelta(3) <= f0 <= d_(p424[0][1]) + timedelta(10) and (not as_of or f0 <= as_of):
            ft = f0
            t["status"] = "trading" if not as_of else "priced"
    t["first_trade"] = iso(ft)
    ref = as_of or ft or (d_(p424[0][1]) + timedelta(1) if p424 else TODAY)
    t["ref_date"] = iso(ref)
    # point-in-time: XBRL holds pre-IPO periods only from later filings, so keep periods a prospectus could have had
    t["fund"] = fundamentals(cik, ref, grace=0 if as_of else 120, lag_days=45 if as_of else 0)
    if facts_file:
        t["fund"] = apply_facts(t["fund"], facts_file)
    elif amds and (as_of or not (t["fund"] or {}).get("rev0") or not p424):
        # no hand-read facts: read the summary table of the latest S-1/A dated before the cutoff
        try:
            got = parse_s1_summary(filing_text(doc_url(cik, amds[-1][2], amds[-1][3]), 2_500_000))
        except Exception as e:  # noqa: BLE001
            fail("SEC S-1/A summary table", e)
            got = {}
        if got.get("rev0"):
            t["fund"] = apply_facts_dict({k: v for k, v in (t["fund"] or {}).items() if k == "dei_shares"}, got)
            t["fund"]["source"] = f"S-1 summary table (parsed from the {amds[-1][0]} of {amds[-1][1]})"
    t["mkt"] = backdrop(ref, t["sic"])
    t = stage_b(t) if p424 else _upcoming_deep(t, dict(sub, filings=fs))   # fs is already cut at as_of
    t["y"] = y
    return t


def _upcoming_deep(t, sub):
    """No 424B4 yet: the latest S-1/A is the prospectus; range history from all amendments."""
    b = parse_deep(filing_text(t["url"], 2_500_000))
    fs = sub["filings"]
    amds = [f for f in fs if f[0] in ("S-1/A", "F-1/A")]
    rngs = []
    for f in amds + [f for f in fs if f[0] == "FWP"][-3:]:
        try:
            c = parse_cover(filing_text(doc_url(t["cik"], f[2], f[3]), 150_000))
        except Exception as e:  # noqa: BLE001
            fail("SEC S-1/A cover", e)
            continue
        if c.get("range"):
            rngs.append({"date": f[1], "range": c["range"], "offered": c.get("offered")})
    rngs.sort(key=lambda x: x["date"])
    regs = [f for f in fs if f[0] in ("S-1", "F-1")]
    b["amendments"] = len(amds)
    if regs:
        b["first_public_filing"] = regs[0][1]
    if rngs:
        b["range_first"], b["range_last"] = rngs[0], rngs[-1]
    b["range_history"] = rngs
    t["deep"] = b
    _derive(t)
    return t


def bank_records(recs, ref, conf):
    """Median day-30 return (from the open) per lead-left bank over the 3 years before ref."""
    by = {}
    for r in recs:
        if not r.get("out") or not r["cover"].get("banks") or d_(r["filed"]) < ref - timedelta(3 * 365):
            continue
        v = (r["out"].get("d30") or {}).get("open")
        if v is not None:
            by.setdefault(r["cover"]["banks"][0], []).append(v)
    return {k: {"n": len(v), "median_d30_open": sorted(v)[len(v) // 2]} for k, v in by.items()}


def signals(t, comps, base_recs, banks):
    """35 signals: value, direction (+ / - / neutral), source."""
    c, f, b, m = t.get("cover", {}), t.get("fund", {}), t.get("deep", {}), t.get("mkt", {})
    src_424, sub_src = t["url"], f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={t['cik']}&type=S-1"
    xbrl = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{t['cik']:010d}.json"
    fsrc = (f.get("source") or xbrl) + (" [period ends after the IPO]" if f.get("period_after_ipo") else "")
    yq = "https://finance.yahoo.com/quote/"
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None  # noqa: E731
    S = []

    def add(n, grp, name, value, direction, source):
        S.append({"n": n, "group": grp, "signal": name, "value": value, "dir": direction, "source": source})

    def sgn(x, pos=0, neg=0):
        return "neutral" if x is None else "+" if x > pos else "-" if x < neg else "neutral"

    rh = b.get("range_history") or [x for x in (b.get("range_first"), b.get("range_last")) if x]
    add(1, "A", "Price range and revisions", "; ".join(f"{x['date']}: ${x['range'][0]}-${x['range'][1]}" for x in rh) or "[not found]",
        {1: "+", -1: "-"}.get(t.get("range_rev"), "neutral"), sub_src)
    add(2, "A", "Shares offered: launch vs final", f"{(b.get('range_first') or {}).get('offered')} -> {c.get('offered')}",
        {1: "+", -1: "-"}.get(t.get("upsized"), "neutral"), sub_src)
    pvr = {2: "above", 1: "top", 0: "mid", -1: "bottom", -2: "below"}.get(t.get("price_vs_range"))
    pv = t.get("price_vs_range")
    add(3, "A", "Final price vs range", f"${c.get('price')} ({pvr})" if c.get("price") else "not priced yet",
        "neutral" if pv is None else "+" if pv >= 1 else "-" if pv <= -1 else "neutral", src_424)
    pool_days = [x["deep"].get("days_to_pricing") for x in comps if x.get("deep", {}).get("days_to_pricing")]
    dtp = b.get("days_to_pricing")
    add(4, "A", "Pricing pace vs comparables (days, public filing to pricing)",
        f"{dtp} days vs comparables' median {med(pool_days)}" if dtp else "[not priced / not found]",
        "neutral" if not dtp or not pool_days else "+" if dtp < med(pool_days) else "-", sub_src)
    add(5, "A", "S-1/A amendments", b.get("amendments"), "neutral", sub_src)
    fp = t.get("float_pct")
    add(6, "A", "Float (shares offered / outstanding)", f"{fp:.1%}" if fp else "[not found]",
        "neutral" if fp is None else "+" if fp < 0.15 else "-" if fp > 0.30 else "neutral", src_424)
    add(7, "A", "Greenshoe (over-allotment) shares", c.get("greenshoe") or "[not found]", "neutral",
        src_424 + "  (exercise: check later 8-K/424B)")
    add(8, "A", "Directed share program / cornerstone indications",
        f"DSP {'yes' if c.get('dsp') else 'no'}; cornerstone {'yes' if c.get('cornerstone') else 'no'}",
        "+" if c.get("cornerstone") else "neutral", src_424)
    add(9, "A", "Reported oversubscription / books covered", "[needs news check: count only with 2+ independent sources]", "neutral", "trader-news / web")
    add(10, "A", "Retail allocation platforms (Robinhood IPO Access, SoFi...)", "[needs news check]", "neutral", "trader-news / web")
    bk = c.get("banks") or []
    rec = banks.get(bk[0]) if bk else None
    allm = med([v["median_d30_open"] for v in banks.values()])
    add(11, "B", "Lead-left bank, bank count, lead's 3-year IPO record",
        f"{bk[0] if bk else '[not found]'}; {len(bk)} banks; lead median day-30 {rec['median_d30_open']:+.1%} (n={rec['n']})" if rec
        else f"{bk[0] if bk else '[not found]'}; {len(bk)} banks; record: not enough data",
        "neutral" if not rec or allm is None or rec["n"] < 3 else "+" if rec["median_d30_open"] > allm else "-", src_424)
    add(12, "B", "VC/PE-backed (text heuristic)", "yes" if b.get("vc_backed") else "no / not found", "neutral", src_424)
    sp = t.get("secondary_pct")
    add(13, "B", "Selling-shareholder share of the offering", f"{sp:.0%}" if sp is not None else "[not found]",
        "neutral" if sp is None else "+" if sp == 0 else "-" if sp > 0.30 else "neutral", src_424)
    add(14, "B", "Dual-class / controlled company", f"dual-class {'yes' if b.get('dual_class') else 'no'}; controlled {'yes' if b.get('controlled') else 'no'}",
        "-" if b.get("dual_class") or b.get("controlled") else "neutral", src_424)
    add(15, "B", "Use of proceeds", (b.get("use_of_proceeds") or "[not found]")[:240], "neutral", src_424)
    ld = b.get("lockup_days")
    add(16, "B", "Lockup", f"{ld or '[not found]'} days; early-release clause {'yes' if b.get('lockup_early_release') else 'no'}",
        "-" if (ld and ld < 180) or b.get("lockup_early_release") else "neutral", src_424)
    tx = features(t)
    pool_x = [features(x) for x in comps]
    def vs_pool(k):
        v = tx.get(k)
        p = med([x[k] for x in pool_x if k in x])
        return v, p
    g, gp = vs_pool("growth")
    add(17, "C", "Revenue growth (last FY vs prior FY)", f"{g:+.0%} vs comparables' median {gp:+.0%}" if g is not None and gp is not None else "[not found]",
        "neutral" if g is None or gp is None else "+" if g > gp else "-", fsrc)
    gm, gmp = vs_pool("gross_margin")
    om, omp = vs_pool("op_margin")
    add(18, "C", "Gross / operating margin", (f"gross {gm:.0%} (comps {gmp:.0%})" if gm is not None and gmp is not None else "gross [n/a]")
        + "; " + (f"operating {om:.0%} (comps {omp:.0%})" if om is not None and omp is not None else "operating [n/a]"),
        "neutral" if gm is None or gmp is None else "+" if gm > gmp else "-", fsrc)
    fcf = f["cfo"] - (f.get("capex") or 0) if f.get("cfo") is not None else None
    proceeds = (c.get("price") or (sum(t["range"]) / 2 if t.get("range") else 0)) * (c.get("offered") or 0)
    cash_after = (f.get("cash") or 0) + proceeds
    runway = cash_after / (-fcf / 12) if fcf is not None and fcf < 0 else None
    add(19, "C", "Free cash flow, months of runway after the IPO",
        f"FCF ${fcf / 1e6:,.0f}M; " + (f"runway {runway:.0f} months" if runway else "cash-generative") if fcf is not None else "[not found]",
        "neutral" if fcf is None else "+" if fcf > 0 else "-" if runway and runway < 18 else "neutral", fsrc)
    net = cash_after - (f.get("debt") or 0)
    add(20, "C", "Net cash after the IPO (pre-IPO cash + primary proceeds - long-term debt)",
        f"${net / 1e6:,.0f}M" if f.get("cash") is not None else "[not found]", sgn(net if f.get("cash") is not None else None), fsrc)
    tc = b.get("top_customer_pct")
    add(21, "C", "Customer concentration; top risk factors",
        ("no single customer > 10% of revenue; " if b.get("no_customer_over_10pct") else "")
        + (f"largest disclosed customer or customer-group share {tc}% (check the S-1 sentence)" if tc else "no concentration figure found")
        + "; risks: read the S-1 Risk Factors",
        "neutral" if b.get("no_customer_over_10pct") or not tc else "-" if tc > 20 else "neutral", src_424)
    rev0 = f.get("rev0")
    shares = b.get("outstanding") or f.get("dei_shares")
    ps = {}
    if rev0 and rev0 > 0 and shares:
        pts = {}
        if t.get("range"):
            pts = {"low": t["range"][0], "mid": sum(t["range"]) / 2, "top": t["range"][1]}
        if c.get("price"):
            pts["final"] = c["price"]
        for k, p in pts.items():
            ps[k] = {"p_s": p * shares / rev0, "ev_rev": (p * shares - cash_after + (f.get("debt") or 0)) / rev0}
    add(22, "D", "Price/sales and EV/revenue at low / mid / top / final",
        "; ".join(f"{k} P/S {v['p_s']:.1f}x EV/rev {v['ev_rev']:.1f}x" for k, v in ps.items()) or "[needs revenue and share count]",
        "neutral", fsrc)
    comp_ps = [x["mcap"] / x["fund"]["rev0"] for x in comps if x.get("mcap") and (x.get("fund") or {}).get("rev0", 0) > 0]
    mps = med(comp_ps)
    cur = (ps.get("final") or ps.get("mid") or {}).get("p_s")
    prem = cur / mps - 1 if cur and mps else None
    add(23, "D", "P/S vs comparables at their own IPO price (current peer multiples need Yahoo login; not used)",
        f"{cur:.1f}x vs median {mps:.1f}x ({prem:+.0%})" if prem is not None else "[not enough data]",
        "neutral" if prem is None else "-" if prem > 0.5 else "+" if prem < -0.2 else "neutral", "comparables (SEC + IPO price)")
    gadj = cur / (g * 100) if cur and g and g > 0 else None
    comp_g = [x["mcap"] / x["fund"]["rev0"] / (features(x)["growth"] * 100) for x in comps
              if x.get("mcap") and (x.get("fund") or {}).get("rev0", 0) > 0 and features(x).get("growth", 0) > 0]
    mg = med(comp_g)
    add(24, "D", "Growth-adjusted P/S (P/S / growth %) vs comparables",
        f"{gadj:.2f} vs median {mg:.2f}" if gadj and mg else "[not enough data]",
        "neutral" if not gadj or not mg else "+" if gadj < mg else "-", "computed")
    add(25, "E", "Nasdaq / S&P 500 20-day return; VIX",
        f"Nasdaq {m.get('nasdaq_20d', 0):+.1%}, S&P {m.get('spx_20d', 0):+.1%}, VIX {m.get('vix')} ({m.get('vix_bucket')})",
        "-" if (m.get("vix") or 0) >= 25 or (m.get("nasdaq_20d") or 0) < -0.03 else "+" if (m.get("vix") or 99) < 20 and (m.get("nasdaq_20d") or 0) > 0 else "neutral",
        yq + "%5EIXIC")
    ref = d_(t["ref_date"])
    recent = sorted([r for r in base_recs if r.get("out") and d_(r["first_trade"] or "9999-12-31") < ref], key=lambda r: r["first_trade"])[-5:]
    d1s = [(r["out"].get("d1") or {}).get("ipo") for r in recent]
    d5s = [(r["out"].get("d5") or {}).get("ipo") for r in recent]
    md1 = med([x for x in d1s if x is not None])
    add(26, "E", "IPO ETF 20-day return; last 5 US IPOs day-1 / day-5 (from IPO price)",
        f"IPO ETF {m.get('ipo_etf_20d', 0):+.1%}; last 5: " + ", ".join(f"{r['ticker']} {((r['out'].get('d1') or {}).get('ipo') or 0):+.0%}/{((r['out'].get('d5') or {}).get('ipo') or 0):+.0%}" for r in recent),
        "+" if (m.get("ipo_etf_20d") or 0) > 0 and (md1 or 0) > 0 else "-" if (m.get("ipo_etf_20d") or 0) < 0 and (md1 or 0) <= 0 else "neutral",
        yq + "IPO")
    add(27, "E", f"Sector ETF ({m.get('sector_etf')}) 20-day return", f"{m.get('sector_20d', 0):+.1%}", sgn(m.get("sector_20d"), 0.0, -0.03), yq + str(m.get("sector_etf")))
    wk = ref - timedelta(ref.weekday())
    same_week = sum(1 for r in base_recs if wk <= d_(r["filed"]) < wk + timedelta(7) and r["cik"] != t["cik"])
    add(28, "E", "Other US IPOs pricing the same week", same_week, "neutral", "SEC full-text search (424B4)")
    for n, nm in [(29, "Indicated opening price vs IPO price"), (30, "Minutes from 9:30 to first trade"), (31, "Open premium"),
                  (32, "First-30-minute volume / float"), (33, "Price vs VWAP at 30 and 60 min"), (34, "Day high/low vs IPO price")]:
        add(n, "F", nm, "run `ipo.py day1` once it trades" + (" (29: needs news check)" if n == 29 else ""), "neutral", "Yahoo intraday")
    ft = d_(t.get("first_trade")) or (ref if t["status"] != "upcoming" else None)
    if ft:
        cal = f"quiet period ends {ft + timedelta(25)}; lockup expiry {ft + timedelta(ld or 180)}; S&P 12-month seasoning {ft + timedelta(365)}; options listing and first earnings: [needs news check]"
    else:
        cal = "first trade date not set yet"
    add(35, "G", "Post-IPO calendar", cal, "neutral", "computed from first trade date")
    return S


def signal_effects(comps, conf):
    """For the comparables: weighted median day-5 (from the open) when a signal reads + vs -."""
    tests = {
        "range raised vs cut": lambda c: {1: "+", -1: "-"}.get(c.get("range_rev")),
        "priced at/above top vs at/below bottom": lambda c: None if c.get("price_vs_range") is None else "+" if c["price_vs_range"] >= 1 else "-" if c["price_vs_range"] <= -1 else None,
        "float < 15% vs > 30%": lambda c: None if c.get("float_pct") is None else "+" if c["float_pct"] < 0.15 else "-" if c["float_pct"] > 0.30 else None,
        "profitable vs losing money": lambda c: None if (c.get("fund") or {}).get("opinc") is None else "+" if c["fund"]["opinc"] > 0 else "-",
        "VIX < 20 vs >= 20": lambda c: None if c.get("mkt", {}).get("vix") is None else "+" if c["mkt"]["vix"] < 20 else "-",
        "IPO ETF 20d up vs down": lambda c: None if c.get("mkt", {}).get("ipo_etf_20d") is None else "+" if c["mkt"]["ipo_etf_20d"] > 0 else "-",
        "no selling shareholders vs > 30%": lambda c: None if c.get("secondary_pct") is None else "+" if c["secondary_pct"] == 0 else "-" if c["secondary_pct"] > 0.3 else None,
    }
    out = {}
    for name, fn in tests.items():
        g = {"+": [], "-": []}
        for c in comps:
            k = fn(c)
            if k:
                g[k].append(c)
        out[name] = {k: stat_for(v, "d5", "open", conf) for k, v in g.items()}
    return out


def baseline(recs, ref, conf, t=None):
    yr = [r for r in recs if r.get("out") and ref - timedelta(365) <= d_(r["filed"]) < ref]
    out = {"all_us_ipos_12m": {h: stat_for(yr, h, "open", conf) for h in ("d1", "d5", "d30")}}
    if t:
        b, rr = t.get("mkt", {}).get("vix_bucket"), t.get("range_rev")
        same = [r for r in recs if r.get("out") and r.get("mkt", {}).get("vix_bucket") == b and r.get("range_rev") == rr]
        out["same_vix_bucket_and_range_direction"] = {"vix_bucket": b, "range_rev": rr,
                                                      **{h: stat_for(same, h, "open", conf) for h in ("d5", "d30")}}
    return out


def analyze(query, facts_file=None, drops=(), adds=(), as_of_cik=None, as_of=None, log=print, quick=False, mode="at-open"):
    conf = cfg()
    cik = as_of_cik or resolve(query)
    log(f"Resolving {query} -> CIK {cik}")
    t = build_target(cik, facts_file, as_of, mode)
    t["mode"] = mode if as_of else "live"
    ref = d_(t["ref_date"])
    log(f"{t['name']} ({t['ticker']}), SIC {t['sic']}, status {t['status']}, reference date {ref}")
    comps, counts, uni, month_counts, deep_all = build_pool(t, ref, conf, log, cutoff=bool(as_of))
    changes = []
    for d in drops:
        cik_s, _, why = d.partition(":")
        before = len(comps)
        comps = [c for c in comps if str(c["cik"]) != cik_s.strip()]
        changes.append({"action": "drop", "cik": cik_s, "reason": why, "applied": len(comps) < before})
    for a in adds:
        cik_s, _, why = a.partition(":")
        row = next((u for u in uni if str(u["cik"]) == cik_s.strip()), None)
        if row:
            r = stage_b(stage_a(row))
            ft = d_(r["first_trade"])
            y = yahoo_daily(r["ticker"]) if r.get("ticker") and ft else None
            r["out"] = outcomes(y, r["cover"].get("price"), ft, r["deep"].get("lockup_days"), cutoff=ref if as_of else None) if y else None
            comps = score_pool(t, comps + [r], conf, with_text=True, mode=counts["mode"])
        changes.append({"action": "add", "cik": cik_s, "reason": why, "applied": bool(row)})
    for c in comps:
        if c.get("out") is None and (c.get("deep") or {}).get("left_market") and c.get("cover", {}).get("price"):
            ex = exit_value(c, ref if as_of else None)      # survivor bias: how the ones that left the market ended
            if ex:
                c["exit"] = ex
                c["out"] = {"today": {"ipo": ex["price"] / c["cover"]["price"] - 1, "open": None}, "exit": ex}
        c["outcome_missing"] = c.get("out") is None
        lm = (c.get("deep") or {}).get("left_market")
        if as_of and lm and d_(lm["date"]) >= ref:          # a later delisting was not known at the cutoff
            c["deep"] = dict(c["deep"], left_market=None)
    y_cut = ref if as_of else None
    t["out"] = outcomes(t["y"], t["cover"].get("price"), d_(t["first_trade"]), t["deep"].get("lockup_days"), cutoff=y_cut) if t.get("first_trade") else None
    base_all = base_rate_recs(uni, ref, conf, cut=bool(as_of))
    base_recs = [r for r in base_all if d_(r["filed"]) >= ref - timedelta(365)]
    for r in base_recs:
        r["ipos_month"] = month_counts.get(r["filed"][:7], 0)
    base = base_rate(base_all, conf)
    bank_pool = comps + [r for r in base_recs if r.get("out")]
    res = {"target": _public(t), "counts": counts, "changes": changes,
           "comparables": [_public(c) for c in comps],
           "left_market": sum(1 for c in comps if c["outcome_missing"]),
           "pattern": {f"{h}_{b}": stat_for(comps, h, b, conf) for h in ("d1", "d2", "d3", "d5", "d30", "d90", "lockup", "d180", "y1", "y2", "y3", "today") for b in ("open", "ipo")},
           "open_premium": stat_for(comps, "open_prem", None, conf),
           "reference": reference_levels(comps, conf)}
    res["pattern"] = {k: v for k, v in res["pattern"].items() if v.get("n")}
    s5, s180 = stat_for(comps, "d5", "open", conf), stat_for(comps, "d180", "open", conf)
    res["base_rate"] = base
    res["verdict"] = {"flip": verdict(s5, conf["verdict"]["flip_edge"], conf), "hold": verdict(s180, conf["verdict"]["hold_edge"], conf),
                      "flip_basis": s5, "hold_basis": s180, "method": conf["verdict"].get("method", "zero")}
    anchors = {}
    train10 = None
    if conf.get("signals", {}).get("enabled") or not quick:
        train10 = base_rate_recs(uni, ref, conf, cut=bool(as_of), months=conf.get("signals", {}).get("train_months", 120))
    if conf.get("signals", {}).get("enabled"):
        res["decision_signals"] = decision_signals(t, uni, ref, base, conf, cut=bool(as_of), train=train10)
        if conf["signals"].get("anchor"):          # off: the 2020-25 walk-forward found no gain over the base rate
            anchors = {h: v["p_pre_open"] for h, v in res["decision_signals"]["by_horizon"].items()}
    if conf["verdict"].get("method", "zero") != "zero":
        res["verdict"]["flip"], res["verdict"]["flip_vs_base"] = verdict_vs_base(comps, base, "d5", ref, conf, anchors.get("d5"))
        res["verdict"]["hold"], res["verdict"]["hold_vs_base"] = verdict_vs_base(comps, base, "d180", ref, conf, anchors.get("d180"))
    if not quick:
        res["signals"] = signals(t, comps, base_recs, bank_records(bank_pool, ref, conf))
        res["signal_effects"] = signal_effects(comps, conf)
        res["baselines"] = baseline(base_recs + comps, ref, conf, t)
        res["track_record"] = _track_record()
        res["archetype"] = {"key": t.get("archetype"), "name": ARCH_NAMES.get(t.get("archetype")), "why": t.get("archetype_why"),
                            "matching": counts["mode"], "pool_of_same_archetype": counts["archetype_pool"],
                            "widened_to_industry": counts["widened_to_industry"],
                            "comparables_by_archetype": {k: sum(1 for c in comps if c.get("archetype") == k) for k in ARCH_NAMES}}
        res["valuation"] = valuation(t, comps, conf)
        res["closest_peer"] = closest_peer(t, comps, res["valuation"])
        res["pricing_sim"] = pricing_sim(t, deep_all, conf, ref)
        blend_pricing(res["pricing_sim"], base, conf)
        if conf["pricing"].get("method") == "revision":
            revision_pricing(t, base_all, res["pricing_sim"])
        res["value_at_open"] = value_at_open(t, train10 or base_all, conf)
        res["brief"] = s1_brief(t)
        res["sources"] = {"target_filing": t["url"], "financials": (t.get("fund") or {}).get("source") or "SEC XBRL company facts",
                          "xbrl": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{t['cik']:010d}.json",
                          "filing_index": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={t['cik']}&type=S-1",
                          "prices": "Yahoo Finance chart API (daily bars, unofficial)", "deal_list": "SEC full-text search, 424B4 filings",
                          "comparables": [{"name": c["name"], "url": c.get("url")} for c in comps[:12]]}
        tw = [r for r in (train10 or []) if (res.get("decision_signals") or {}).get("twins", {}).get("matched_on")
              and all(signal_x(r).get(k) == v for k, v in res["decision_signals"]["twins"]["matched_on"].items())]
        res["simulation"] = simulate({"all recent IPOs": [(1.0, r.get("out")) for r in base_all],
                                      "twin IPOs (same setup)": [(1.0, r.get("out")) for r in tw],
                                      "look-alike companies": [(c.get("similarity") or 0, c.get("out")) for c in comps]}, conf)
        res["reference_prices"] = reference_prices(t, res["reference"]["level"])
        res["reference_prices_weak"] = reference_prices(t, res["reference"]["weak_level"])
    res["failed_sources"] = dict(FAILED)
    res["notes"] = ["History, not a prediction. Retail buyers usually get the first open, not the IPO price.",
                    "Financials come from SEC XBRL filed after each IPO (pre-IPO periods); for an untraded IPO pass --facts from the S-1.",
                    f"{res['left_market']} of {len(comps)} comparables have no price data (left the market or renamed); results lean toward survivors."]
    return res


def _public(r):
    keep = ("cik", "name", "ticker", "sic", "filed", "first_trade", "status", "ref_date", "url", "form", "price_status",
            "mcap", "range", "range_rev", "price_vs_range", "upsized", "float_pct", "secondary_pct", "ipos_month",
            "similarity", "biz_score", "sit_score", "match_features", "match_phrases", "text_missing", "out", "outcome_missing",
            "archetype", "archetype_why", "mcap_mid")
    o = {k: r[k] for k in keep if k in r}
    o["cover"] = {k: v for k, v in r.get("cover", {}).items()}
    o["fund"] = r.get("fund")
    o["mkt"] = r.get("mkt")
    d = dict(r.get("deep", {}))
    d.pop("overview", None)
    o["deep"] = d
    o["overview_snippet"] = (r.get("deep", {}).get("overview") or "")[:300]
    return o


def _track_record():
    try:
        bt = json.loads(BACKTEST_FILE.read_text(encoding="utf-8"))
        return bt.get("calibration")
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- day1

def day1(query):
    cik = resolve(query)
    t = build_target(cik)
    if not t.get("first_trade"):
        sys.exit("ipo.py day1: no first trade found yet (needs a 424B4 and Yahoo bars).")
    ft = d_(t["first_trade"])
    age = (TODAY - ft).days
    if age <= 6:
        rng, iv = "7d", "1m"
    elif age <= 58:
        rng, iv = "60d", "5m"
    else:
        sys.exit(f"ipo.py day1: first trade {ft} is {age} days ago; Yahoo keeps intraday bars ~60 days.")
    r = get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{t['ticker']}?range={rng}&interval={iv}", ttl=600)["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", -18000)
    q = r["indicators"]["quote"][0]
    bars = []
    for i, ts in enumerate(r["timestamp"]):
        dt = datetime.fromtimestamp(ts + off, timezone.utc).replace(tzinfo=None)
        if dt.date() == ft and q["close"][i] is not None:
            bars.append((dt, q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i] or 0))
    if not bars:
        sys.exit("ipo.py day1: no intraday bars for the first day.")
    ipo = t["cover"].get("price")
    t0 = datetime.combine(ft, datetime.min.time()).replace(hour=9, minute=30)
    first = bars[0][0]

    def upto(mins):
        return [b for b in bars if b[0] < first + timedelta(minutes=mins)]

    def vwap(bs):
        v = sum(b[5] for b in bs)
        return sum((b[2] + b[3] + b[4]) / 3 * b[5] for b in bs) / v if v else None

    out = {"ticker": t["ticker"], "first_trade": iso(ft), "interval": iv, "ipo_price": ipo,
           "indicated_open": "[needs news check: Nasdaq/NYSE indication]",
           "minutes_to_first_trade": round((first - t0).total_seconds() / 60),
           "open": bars[0][1], "open_premium": bars[0][1] / ipo - 1 if ipo else None,
           "vol_30m_pct_float": sum(b[5] for b in upto(30)) / t["cover"]["offered"] if t["cover"].get("offered") else None,
           "high": max(b[2] for b in bars), "low": min(b[3] for b in bars), "close": bars[-1][4]}
    for mins in (30, 60):
        bs = upto(mins)
        if bs:
            vw = vwap(bs)
            out[f"price_{mins}m"] = bs[-1][4]
            out[f"vwap_{mins}m"] = vw
            out[f"above_vwap_{mins}m"] = bs[-1][4] > vw if vw else None
            out[f"held_open_{mins}m"] = bs[-1][4] >= bars[0][1]
    if ipo:
        out["low_vs_ipo"] = out["low"] / ipo - 1
        out["high_vs_ipo"] = out["high"] / ipo - 1
        out["defended_ipo_price"] = out["low"] >= ipo * 0.995
    out["failed_sources"] = dict(FAILED)
    return out


# ---------------------------------------------------------------- backtest

def backtest(limit, log=print):
    conf = cfg()
    bc = conf["backtest"]
    start, end = TODAY - timedelta(int(30.44 * bc["from_months"])), TODAY - timedelta(int(30.44 * bc["to_months"]))
    rows = universe(start, end)
    log(f"Backtest window {start}..{end}: {len(rows)} IPO filings. Checking which traded and passed the size filter...")
    with ThreadPoolExecutor(4) as ex:
        recs = list(ex.map(stage_a, rows))
    tests = [r for r in recs if r.get("first_trade") and r.get("ticker") and r["cover"].get("price")
             and not r["cover"].get("adr") and not r["cover"].get("units") and (r.get("mcap") or 0) >= conf["min_mcap_usd"]]
    tests.sort(key=lambda r: r["first_trade"], reverse=True)
    if limit:
        tests = tests[:limit]
    log(f"Testing {len(tests)} IPOs point-in-time (only data dated before each first trade)...")
    results = []
    for i, r in enumerate(tests, 1):
        ft = d_(r["first_trade"])
        try:
            res = analyze(None, as_of_cik=r["cik"], as_of=ft, log=lambda *_: None, quick=True)
        except SystemExit as e:
            log(f"  [{i}/{len(tests)}] {r['name']}: skipped ({e})")
            continue
        except Exception as e:  # noqa: BLE001
            log(f"  [{i}/{len(tests)}] {r['name']}: failed ({e})")
            continue
        actual = outcomes(yahoo_daily(r["ticker"]), r["cover"]["price"], ft)
        a5 = ((actual or {}).get("d5") or {}).get("open")
        a180 = ((actual or {}).get("d180") or {}).get("open")
        fv, fc = res["verdict"]["flip"]
        hv, hc = res["verdict"]["hold"]
        row = {"name": r["name"], "ticker": r["ticker"], "first_trade": r["first_trade"], "n_comps": len(res["comparables"]),
               "flip": fv, "flip_conf": fc, "actual_d5_open": a5, "hold": hv, "hold_conf": hc, "actual_d180_open": a180}
        results.append(row)
        log(f"  [{i}/{len(tests)}] {r['ticker']:6} {r['first_trade']}  flip {fv:11} ({fc:6}) actual d5 {a5 if a5 is None else f'{a5:+.1%}'}"
            f"  hold {hv:11} ({hc:6}) actual d180 {a180 if a180 is None else f'{a180:+.1%}'}")
    cal = calibration(results)
    out = {"run": datetime.now().isoformat(timespec="seconds"), "window": [iso(start), iso(end)], "tested": len(results),
           "results": results, "calibration": cal, "failed_sources": dict(FAILED),
           "method": "point-in-time: comparables priced before each first trade, their outcomes cut at that date; target financials are pre-IPO periods from later XBRL filings"}
    BACKTEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKTEST_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


REGRESSION = SKILL / "tests" / "regression.json"


def regress():
    """Fixed regression set: run before every change. (1) the S-1 parser against hand-read facts (network, cached),
    (2) the verdict math on 30 frozen walk-forward IPOs (offline), (3) the 404-IPO 2020-25 scoreboard (offline)."""
    reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    conf, ok, lines = cfg(), True, []
    for c in reg["s1"]:
        try:
            got = parse_s1_summary(html_text(http_get(c["url"], sec=True)))
        except Exception as e:  # noqa: BLE001
            lines.append(f"  s1 {c['ticker']}: could not fetch ({e})")
            continue
        bad = [k for k, w in c["expect"].items() if got.get(k) is None or abs(got[k] - w) > 0.01 * abs(w) + 1]
        ok &= not bad
        lines.append(f"  s1 {c['ticker']}: {'PASS' if not bad else 'FAIL ' + ', '.join(bad)}")
    drift = 0
    for r in reg["verdict"]:
        comps = [{"similarity": s, "first_trade": ft, "out": {"d5": {"open": a}, "d180": {"open": b}}} for s, ft, a, b in r["comps"]]
        base = {"sample": r["base_sample"]}
        p5 = verdict_vs_base(comps, base, "d5", d_(r["ref"]), conf)[1]["p_gain"]
        p180 = verdict_vs_base(comps, base, "d180", d_(r["ref"]), conf)[1]["p_gain"]
        drift += abs(p5 - r["p_flip"]) > 1e-9 or abs(p180 - r["p_hold"]) > 1e-9
    ok &= drift == 0
    lines.append(f"  verdict math on {len(reg['verdict'])} frozen IPOs: {'PASS' if not drift else f'FAIL ({drift} changed)'}")
    w = reg["walkforward"]
    br = lambda k: sum((r[k] - r["y5" if "flip" in k else "y180"]) ** 2 for r in w) / len(w)  # noqa: E731
    b_f, b_b, h_b = br("p_flip"), br("base_flip"), br("base_hold")
    good = b_f < b_b
    ok &= good
    lines.append(f"  2020-25 walk-forward ({len(w)} IPOs): flip verdict Brier {b_f:.4f} vs base rate {b_b:.4f} "
                 f"({'PASS' if good else 'FAIL'}); hold uses the base rate, Brier {h_b:.4f}")
    print("regression: " + ("PASS" if ok else "FAIL") + "\n" + "\n".join(lines))
    return ok


FORWARD_LOG = TRADER / "state" / "ipo-forward-log.jsonl"


def forward_log(res, coverage=None):
    """Paper log of every live analysis (never a backtest): the untouched forward test, scored later by `forward`."""
    t, v = res["target"], res["verdict"]
    ds = (res.get("decision_signals") or {}).get("by_horizon") or {}
    row = {"logged": datetime.now().isoformat(timespec="seconds"), "cik": t["cik"], "ticker": t.get("ticker"), "name": t["name"],
           "status": t["status"], "ref_date": t["ref_date"], "range": t.get("range"), "price": (t.get("cover") or {}).get("price"),
           "flip": v["flip"], "hold": v["hold"], "method": v.get("method"),
           "p_flip": (v.get("flip_vs_base") or {}).get("p_gain"), "p_hold": (v.get("hold_vs_base") or {}).get("p_gain"),
           "at_open": {h: d.get("at_open") for h, d in ds.items()} or None,
           "pricing": (res.get("pricing_sim") or {}).get("headline"), "pricing_probs": (res.get("pricing_sim") or {}).get("probabilities"),
           "coverage": coverage}
    FORWARD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FORWARD_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def forward_score():
    """Score the paper log: the latest entry per IPO made before its first trade, against what happened since."""
    if not FORWARD_LOG.exists():
        return {"status": "no forward log yet"}
    rows = [json.loads(x) for x in FORWARD_LOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    last = {}
    for r in rows:
        if r["status"] == "upcoming" or r.get("price"):
            last[r["cik"]] = r
    out = []
    for r in last.values():
        y = yahoo_daily(r["ticker"]) if r.get("ticker") else None
        if not y or not y["bars"] or not r.get("price"):
            out.append({"ticker": r["ticker"], "status": "not traded or not priced yet"})
            continue
        o = outcomes(y, r["price"], y["bars"][0][0])
        row = {"ticker": r["ticker"], "logged": r["logged"], "coverage": r.get("coverage")}
        for kind, h, pk in (("flip", "d5", "p_flip"), ("hold", "d180", "p_hold")):
            a = ((o or {}).get(h) or {}).get("open")
            row[kind] = {"call": r[kind][0], "p": r.get(pk), "actual": a,
                         "right": None if a is None or r[kind][0] == "MIXED" else (r[kind][0] == "FAVORABLE") == (a > 0)}
        out.append(row)
    scored = lambda k: [x[k] for x in out if isinstance(x.get(k), dict) and x[k]["actual"] is not None]  # noqa: E731
    summ = {}
    for k in ("flip", "hold"):
        s = scored(k)
        calls = [x for x in s if x["right"] is not None]
        summ[k] = {"scored": len(s), "calls": len(calls), "right": sum(x["right"] for x in calls),
                   "brier": sum((x["p"] - (x["actual"] > 0)) ** 2 for x in s if x["p"] is not None) / max(1, sum(x["p"] is not None for x in s)),
                   "share_up": sum(x["actual"] > 0 for x in s) / len(s) if s else None}
    return {"entries": len(last), "summary": summ, "rows": out}


def calibration(results):
    cal = {}
    for kind, actual in (("flip", "actual_d5_open"), ("hold", "actual_d180_open")):
        rows = [r for r in results if r.get(actual) is not None]
        calls = [r for r in rows if r[kind] != "MIXED"]
        right = [r for r in calls if (r[kind] == "FAVORABLE") == (r[actual] > 0)]
        base = sum(r[actual] > 0 for r in rows) / len(rows) if rows else None
        by = {}
        for lvl in ("high", "medium", "low"):
            cs = [r for r in calls if r[f"{kind}_conf"] == lvl]
            ok = [r for r in cs if (r[kind] == "FAVORABLE") == (r[actual] > 0)]
            by[lvl] = {"calls": len(cs), "right": len(ok), "hit_rate": len(ok) / len(cs) if cs else None}
        cal[kind] = {"evaluated": len(rows), "calls": len(calls), "mixed": len(rows) - len(calls),
                     "hit_rate": len(right) / len(calls) if calls else None,
                     "base_rate_always_favorable": base, "by_confidence": by}
    return cal


# ---------------------------------------------------------------- printing

def pct(x, d=1):
    return "  n/a " if x is None else f"{x:+.{d}%}"


HNAME = {"d1": "day 1", "d3": "day 3", "d5": "day 5", "d30": "day 30", "d90": "day 90", "d180": "day 180"}


def takeaways(res):
    """One plain-English line per report section: what the numbers mean and whether it is a good or bad sign.
    Built only from the numbers in `res`, so the line always matches its table."""
    T, v = {}, res["verdict"]
    lab = lambda d, up=0.03: "good sign" if d > up else "bad sign" if d < -up else "neutral"  # noqa: E731
    parts = []
    for kind, h in (("flip", "day 5"), ("hold", "day 180")):
        b = v.get(f"{kind}_vs_base")
        if b:
            cp_ = "no comparables with data" if b["comps_p_gain"] is None else f"look-alike IPOs were up by {h} {b['comps_p_gain']:.0%} of the time"
            parts.append(f"{kind}: {cp_}, vs {b['base_p_gain']:.0%} for recent IPOs in general; combined chance {b['p_gain']:.0%} "
                         f"({'a coin flip, so no call' if v[kind][0] == 'MIXED' else v[kind][0].lower()})")
    calls = {v["flip"][0], v["hold"][0]}
    T["verdict"] = ("good sign" if calls <= {"FAVORABLE", "MIXED"} and "FAVORABLE" in calls else
                    "bad sign" if calls <= {"UNFAVORABLE", "MIXED"} and "UNFAVORABLE" in calls else "mixed",
                    "; ".join(parts) + ". Most IPOs fall after the open, so a call has to beat that.")
    ds = res.get("decision_signals")
    if ds:
        b = ds["by_horizon"]["d5"]
        moves = sorted(b["steps"].items(), key=lambda kv: kv[1]["step"])
        txt = ", ".join(f"{s} = {d['group']} ({'up' if d['step'] > 0 else 'down'} {abs(d['step']):.2f} log-odds)" for s, d in moves) or "no signal known yet"
        T["decision"] = (lab(b["p_pre_open"] - b["base_p"]),
                         f"before the open, the known signals move the day-5 chance from {b['base_p']:.0%} to {b['p_pre_open']:.0%} ({txt}). "
                         "The open columns show how much the first print matters: check the column it opens in.")
        tw = ds.get("twins") or {}
        t5, a5 = (tw.get("twins") or {}).get("d5") or {}, (tw.get("all_recent") or {}).get("d5") or {}
        if tw and t5.get("share_up") is not None and a5.get("share_up") is not None:
            d = t5["share_up"] - a5["share_up"]
            T["twins"] = ("neutral" if t5["n"] < 10 else lab(d, 0.10),
                          f"{tw['n']} past IPOs had the same setup; {t5['share_up']:.0%} were up by day 5 vs {a5['share_up']:.0%} of all recent IPOs"
                          + (" (too few to mean much)" if t5["n"] < 10 else "") + ". This is context: the walk-forward found setups like this did not predict better than the base rate.")
    sg = res.get("signals") or []
    plus, minus = sum(s["dir"] == "+" for s in sg), sum(s["dir"] == "-" for s in sg)
    if sg:
        T["signals"] = ("good sign" if plus > minus + 2 else "bad sign" if minus > plus + 2 else "mixed",
                        f"{plus} signals read positive and {minus} negative; the rest are neutral or not known. "
                        "The verdict does not use them; they explain the setup.")
    cs = res["comparables"]
    if cs:
        top = max((c.get("similarity") or 0) for c in cs)
        T["comparables"] = ("bad sign" if top < 30 else "neutral",
                            f"the closest match scores {top:.0f}/100 ({'weak: history has nothing very like this IPO, so lean on the base rate' if top < 30 else 'a reasonable match'}); "
                            f"{res['left_market']} of {len(cs)} have no price data, so results lean on companies that survived.")
    p5, br = res["pattern"].get("d5_open"), res.get("base_rate") or {}
    if p5 and (br.get("d5") or {}).get("n"):
        d = p5["hit"] - br["d5"]["hit"]
        T["pattern"] = (lab(d, 0.10), f"look-alikes were up by day 5 {p5['hit']:.0%} of the time (median {pct(p5['median'])}) vs {br['d5']['hit']:.0%} "
                        f"for all recent IPOs (median {pct(br['d5'].get('median'))}): {'better than' if d > 0.10 else 'worse than' if d < -0.10 else 'about the same as'} a typical IPO.")
    lv = res["reference"]["level"]
    T["reference"] = ("neutral", "history shows no clear 'opened too high' level for deals like this." if isinstance(lv, str)
                      else f"look-alikes that opened {lv['open_premium_at_or_above']:+.0%} or more above their IPO price usually fell by day 5: a caution line, not a target.")
    a = res.get("archetype")
    if a:
        T["archetype"] = ("bad sign" if a["widened_to_industry"] else "neutral",
                          f"it is a {a['name']} IPO; " + ("so few IPOs of this kind exist that the pool was widened with same-industry deals, so comparables are loose."
                                                           if a["widened_to_industry"] else "there were enough IPOs of this kind to compare against."))
    cp = res.get("closest_peer")
    if cp:
        T["peer"] = ("neutral", f"{cp['name']} is the nearest match at similarity {cp['similarity']}/100"
                     + (" (weak, so treat its path as one story, not a guide)." if (cp["similarity"] or 0) < 30 else ".")
                     + f" It was {pct(cp['returns_from_open'].get('d5'))} five days after its open.")
    ps = res.get("pricing_sim") or {}
    if ps.get("status") == "ok" and ps.get("headline"):
        nb, pr = ps.get("neighbor_probabilities") or ps["probabilities"], ps["probabilities"]
        lean = nb["above"] - pr["above"]
        T["pricing"] = ("good sign" if lean > 0.25 else "neutral",
                        f"most likely it prices {ps['headline']} its range ({ps['headline_probs'][ps['headline']]:.0%}), which is what most IPOs do. "
                        + (f"The most similar past deals lean much higher ({nb['above']:.0%} above), a hint of strong demand that the tested model does not trust."
                           if lean > 0.25 else "Similar past deals do not point anywhere special."))
    va = res.get("valuation") or {}
    if va.get("status") == "ok":
        o = va["overall"]
        T["valuation"] = ("bad sign" if o.startswith("OVER") else "good sign" if o.startswith("UNDER") else "neutral" if o.startswith("FAIR") else "mixed",
                          f"at ${va['price_used']:.2f} it costs {va['p_s']:.1f}x sales vs {va['comps_p_s_median']:.1f}x for comparables at their IPO "
                          f"({va['p_s_label']}); per point of growth it is {va['growth_adj_label']}. Overvalued IPOs have done worst in the backtest.")
    vo = res.get("value_at_open") or {}
    if vo.get("status") == "ok":
        if vo.get("actual_open_premium") is not None:
            T["value_at_open"] = ("bad sign" if vo["rich"] else "good sign" if vo["actual_rank"] < 0.5 else "neutral",
                                  f"it opened at {vo['actual_p_s']:.1f}x sales, more expensive than {vo['actual_rank']:.0%} of past IPOs at their open"
                                  + (": the most expensive quarter, which held up worse over 6 months." if vo["rich"] else "."))
        else:
            T["value_at_open"] = ("bad sign" if vo["rich_open_premium"] < 0 else "neutral",
                                  f"the price you pay matters: above ${vo['rich_open_price']:.2f} ({vo['rich_open_premium']:+.0%} vs the IPO price) it would be "
                                  "among the most expensive quarter of IPOs at the open, and those were less often up 6 months later."
                                  + (" It is already there at the IPO price." if vo["rich_open_premium"] < 0 else ""))
    sim = res.get("simulation") or {}
    s = sim.get("twin IPOs (same setup)") or sim.get("all recent IPOs")
    if s and s.get("d5") and s.get("d180"):
        T["simulation"] = (lab(s["d5"]["up"] - 0.5, 0.05) if s["d5"]["up"] >= s["d180"]["up"] else "neutral",
                           f"in the simulated paths a 1-week flip was up {s['d5']['up']:.0%} of the time (median {pct(s['d5']['median'], 0)}), "
                           f"a 6-month hold {s['d180']['up']:.0%} (median {pct(s['d180']['median'], 0)}); the worst 10% of 6-month paths lost "
                           f"{pct(s['d180']['p10'], 0)} or more. Shorter holds were less extreme in both directions.")
    return T


def bottom_line(res, T):
    """Recap of every section's read, then one fixed-rule lean (history, not advice):
    leans SKIP when a verdict is UNFAVORABLE and none is FAVORABLE, or the valuation is OVERVALUED;
    WORTH A CLOSER LOOK when a verdict is FAVORABLE and none is UNFAVORABLE and it is not overvalued; otherwise NO CLEAR LEAN."""
    v = res["verdict"]
    calls = [v["flip"][0], v["hold"][0]]
    over = ((res.get("valuation") or {}).get("overall") or "").startswith("OVER")
    good = [k for k, (lab, _) in T.items() if lab == "good sign"]
    bad = [k for k, (lab, _) in T.items() if lab == "bad sign"]
    def lean(call, horizon):
        if call == "UNFAVORABLE" or (over and call != "FAVORABLE"):
            return "LEANS SKIP", f"IPOs like this more often fell than rose by {horizon} after the open"
        if call == "FAVORABLE" and not over:
            return "WORTH A CLOSER LOOK", f"IPOs like this more often rose by {horizon} after the open"
        return "NO CLEAR LEAN", f"close to a coin flip at {horizon}"
    lf, lh = lean(calls[0], "day 5"), lean(calls[1], "day 180")
    tr = (res.get("track_record") or {}).get("flip") or {}
    # every part of the analysis, side by side: its chance of a gain (or read) at day 5 and day 180, and whether it is tested
    ds = res.get("decision_signals") or {}
    tw = ds.get("twins") or {}
    pat = res.get("pattern") or {}
    f5, f180 = v.get("flip_vs_base") or {}, v.get("hold_vs_base") or {}
    pc_ = lambda p: "n/a" if p is None else f"{p:.0%}"  # noqa: E731
    ev = [("Verdict: look-alikes shrunk to the base rate", f5.get("p_gain"), f180.get("p_gain"), "yes: about the base rate (flip 72%, hold 66% right)"),
          ("All recent US IPOs (base rate)", f5.get("base_p_gain"), f180.get("base_p_gain"), "yes: the best single input 2020-25"),
          ("Look-alike companies (pattern, % up)", (pat.get("d5_open") or {}).get("hit"), (pat.get("d180_open") or {}).get("hit"), "inside the verdict"),
          (f"Twin IPOs, same setup (n={tw.get('n', 0)})", ((tw.get("twins") or {}).get("d5") or {}).get("share_up"),
           ((tw.get("twins") or {}).get("d180") or {}).get("share_up"), "yes: no gain over the base rate")]
    L = ["\n## Bottom line",
         "| evidence | chance up by day 5 | chance up by day 180 | tested? |\n|---|---|---|---|"]
    for nm, a, b, tst in ev:
        L.append(f"| {nm} | {pc_(a)} | {pc_(b)} | {tst} |")
    L.append(f"| Valuation vs comparables | - | {(res.get('valuation') or {}).get('overall', 'n/a')} | weak: few overvalued deals |")
    L.append(f"| Pricing vs range | {(res.get('pricing_sim') or {}).get('headline') or 'priced'} | - | yes: base rate by range revision, 6 of 6 years |")
    vo = res.get("value_at_open") or {}
    if vo.get("status") == "ok":
        L.append(f"| Valuation at the open | - | most-expensive-quarter line ${vo['rich_open_price']:.2f}"
                 + (f"; opened in it: {'yes' if vo['rich'] else 'no'}" if vo.get("actual_open_premium") is not None else "") + " | yes: worse at 6 months in 5 of 6 years |")
    sim = (res.get("simulation") or {})
    sref = sim.get("twin IPOs (same setup)") or sim.get("all recent IPOs") or {}
    if sref.get("d5") and sref.get("d180"):
        L.append(f"| Simulated paths ({'twins' if 'twin IPOs (same setup)' in sim else 'all recent IPOs'}) | {sref['d5']['up']:.0%} | {sref['d180']['up']:.0%} | history of real paths |")
    agree = lambda i, call: sum(1 for e in ev[1:] if e[i] is not None and ((e[i] > 0.5) == (call == "FAVORABLE")))  # noqa: E731
    known = lambda i: sum(1 for e in ev[1:] if e[i] is not None)  # noqa: E731
    L += [f"- Flip (day 5 from the open): **{v['flip'][0]}**; hold (day 180): **{v['hold'][0]}**; valuation: **{(res.get('valuation') or {}).get('overall', 'n/a')}**.",
          f"- Good signs: {', '.join(good) or 'none'}. Bad signs: {', '.join(bad) or 'none'}.",
          f"- Quick flip: **{lf[0]}**: {lf[1]}."
          + (f" {agree(1, calls[0])} of {known(1)} other parts point the same way." if calls[0] != "MIXED" else ""),
          f"- Long hold: **{lh[0]}**: {lh[1]}" + (" (and it is priced rich vs comparables)." if over else ".")
          + (f" {agree(2, calls[1])} of {known(2)} other parts point the same way." if calls[1] != "MIXED" else ""),
          "- The lean follows the tested verdict only; the other rows are shown so you can see where the evidence agrees or splits."]
    # one overall read from the two tested leans and the tested open-price line (history, not advice)
    rich_line = vo.get("rich_open_price") if vo.get("status") == "ok" else None
    opened_rich = vo.get("rich") if vo.get("actual_open_premium") is not None else None
    if lf[0] == "LEANS SKIP" and lh[0] == "LEANS SKIP":
        overall = "SKIP: both the quick flip and the long hold lean against it"
    elif lf[0] == "WORTH A CLOSER LOOK" and lh[0] != "WORTH A CLOSER LOOK":
        overall = "FLIP CANDIDATE: history favors a short trade (sell within about a week), not a long hold"
    elif lh[0] == "WORTH A CLOSER LOOK" and not opened_rich:
        overall = "HOLD CANDIDATE: history favors holding for months" + (f", as long as the open stays under ${rich_line:.2f}" if rich_line else "")
    elif lh[0] == "LEANS SKIP" and lf[0] == "NO CLEAR LEAN":
        overall = "NO CLEAR FLIP, HOLD LEANS SKIP: a coin flip in the first week, and deals like this more often fell over 6 months"
    else:
        overall = "NO CLEAR LEAN: the evidence is close to a coin flip"
    if opened_rich:
        overall += "; it opened in the most expensive quarter of IPOs, which held up worse over 6 months"
    elif rich_line and vo.get("rich_open_premium", 0) < 0:
        overall += f"; at the IPO price it is already among the most expensive quarter of IPOs at the open (that line is ${rich_line:.2f})"
    elif rich_line and "HOLD CANDIDATE" not in overall:
        overall += f"; for a long hold, an open above ${rich_line:.2f} would put it in the most expensive quarter of IPOs"
    L.append(f"- **Overall read: {overall}.**")
    if tr.get("hit_rate") is not None:
        L.append(f"- How much to trust it: this rule was right {tr['hit_rate']:.0%} of the time on flips in the backtest, close to simply "
                 "assuming every IPO falls; treat the lean as a reminder of the odds, not a forecast.")
    L.append("- History, not a prediction; retail usually buys at the open, not the IPO price; not financial advice or a buy/sell recommendation.")
    return L


_BOILER = re.compile(r"(?i)(JOBS Act|emerging growth|this prospectus|forward-looking|securities act|table of contents|Sarbanes|"
                     r"attestation|exemptions?|provisions include|reduced (?:disclosure|obligations)|"
                     r"unless the context|we use the terms|references to|smaller reporting|incorporated in|par value)")


def what_it_does(overview):
    """The first real sentence of the business overview: skips legal boilerplate and fragments."""
    for s in re.split(r"(?<=[.!?])\s+", (overview or "").strip()):
        s = s.strip()
        if len(s.split()) >= 8 and not _BOILER.search(s) and s[:1].isupper():
            return s[:240] + ("..." if len(s) > 240 else "")
    return ""


def five_questions(res, T):
    """The report in five plain answers, each built only from numbers elsewhere in the report (used as the chat summary)."""
    t, v = res["target"], res["verdict"]
    f, br = t.get("fund") or {}, res.get("brief") or {}
    a, va, vo = res.get("archetype") or {}, res.get("valuation") or {}, res.get("value_at_open") or {}
    ps, sim = res.get("pricing_sim") or {}, res.get("simulation") or {}
    L = ["\n## In five questions"]
    # 1. what is it
    first = br.get("what") or what_it_does(br.get("overview"))
    growth = (f["rev0"] / f["rev1"] - 1) if f.get("rev0") and f.get("rev1") else None
    fin = (f"revenue {money(f['rev0'])} a year" + (f", growing {growth:+.0%}" if growth is not None else "")
           + (f", operating margin {f['opinc'] / f['rev0']:+.0%}" if f.get("opinc") is not None and f.get("rev0") else "")) if f.get("rev0") else "financials not read yet"
    L.append(f"1. **What is this company?** {first + ' ' if first else ''}Type: {a.get('name') or 'unclassified'}; {fin}. "
             f"{(br.get('control') or '').capitalize()}{'; lockup ' + br['lockup'] if br.get('lockup') else ''}."
             + (f" Its own first-listed risk: {br['risks'][0] if len(br['risks'][0]) <= 170 else br['risks'][0][:170].rsplit(' ', 1)[0] + '...'}" if br.get("risks") else ""))
    # 2. is the price fair
    p2 = []
    if va.get("status") == "ok":
        p2.append(f"{va['overall'].lower()}: {va['p_s']:.1f}x sales at ${va['price_used']:.2f} vs {va['comps_p_s_median']:.1f}x for look-alikes at their IPO")
    if vo.get("status") == "ok":
        p2.append(("already among the most expensive quarter of IPOs at the open" if vo["rich_open_premium"] < 0 else
                   f"an open above ${vo['rich_open_price']:.2f} ({vo['rich_open_premium']:+.0%}) would put it in the most expensive quarter of IPOs at the open, "
                   "and those were less often up 6 months later") if vo.get("actual_open_premium") is None else
                  f"it opened at {vo['actual_p_s']:.1f}x sales, rank {vo['actual_rank']:.0%} among past opens")
    L.append("2. **Is the price fair?** " + ("; ".join(p2)[:1].upper() + "; ".join(p2)[1:] if p2 else "Not enough data to say") + ".")
    # 3. where will it price, how might it trade
    p3 = []
    if ps.get("headline"):
        p3.append(f"most likely prices **{ps['headline']}** its range ({ps['headline_probs'][ps['headline']]:.0%}"
                  + (f"; its range was {ps['revision']} before pricing" if ps.get("revision") and ps["revision"] != "not known yet" else "") + ")")
    fb, hb = v.get("flip_vs_base") or {}, v.get("hold_vs_base") or {}
    if fb:
        p3.append(f"chance of a gain from the open: {fb['p_gain']:.0%} by day 5, {hb.get('p_gain', 0):.0%} by month 6 "
                  f"(all recent IPOs: {fb['base_p_gain']:.0%} and {hb.get('base_p_gain', 0):.0%})")
    s = sim.get("twin IPOs (same setup)") or sim.get("all recent IPOs") or {}
    if s.get("d1") and s.get("d180"):
        p3.append("simulated medians " + ", ".join(f"{nm} {pct(s[h]['median'], 0)}" for h, nm in SIM_H if s.get(h) and h in ("d1", "d5", "d21", "d63", "d180"))
                  + f"; in the worst 10% of 6-month paths it was {pct(s['d180']['p10'], 0)} or lower")
    L.append("3. **Where will it price, and how might it trade?** " + ("; ".join(p3)[:1].upper() + "; ".join(p3)[1:] if p3 else "Not enough data") + ".")
    # 4. so what
    bl = bottom_line(res, T)
    ov = next((x for x in bl if x.startswith("- **Overall read:")), "- **Overall read: NO CLEAR LEAN.**")
    L.append("4. **So what?** " + ov[2:].replace("**Overall read: ", "**").strip()
             + f" (flip {v['flip'][0].lower()}, hold {v['hold'][0].lower()}; history, not advice).")
    # 5. can I trust it
    cs = res.get("comparables") or []
    top = max((c.get("similarity") or 0) for c in cs) if cs else 0
    tr = (res.get("track_record") or {}).get("flip") or {}
    L.append(f"5. **Can I trust it?** Closest match {top:.0f}/100 ({'weak' if top < 30 else 'reasonable'}); {res.get('left_market', 0)} of {len(cs)} look-alikes "
             f"lack price data; financials from the {f.get('source') or 'SEC XBRL feed'}; failed sources: {', '.join(res.get('failed_sources') or {}) or 'none'}."
             + (f" The flip rule was right {tr['hit_rate']:.0%} of the time in its backtest, a modest edge over assuming every IPO falls; the hold rule has none." if tr.get("hit_rate") else ""))
    return L


def summary_report(res, T=None):
    """The short report (chat and the -summary.md file): verdict tags, a 30-second answer, the five questions,
    key numbers, simulated outcomes, demand and hype, what to watch, and trust. Every number comes from `res`."""
    T = T if T is not None else takeaways(res)
    t, v = res["target"], res["verdict"]
    c, f, br = t.get("cover") or {}, t.get("fund") or {}, res.get("brief") or {}
    va, vo, ps = res.get("valuation") or {}, res.get("value_at_open") or {}, res.get("pricing_sim") or {}
    fb, hb = v.get("flip_vs_base") or {}, v.get("hold_vs_base") or {}
    bl = bottom_line(res, T)
    ov = next((x for x in bl if x.startswith("- **Overall read:")), "- **Overall read: NO CLEAR LEAN.**")
    ov = ov.replace("- **Overall read: ", "").rstrip("*").rstrip(".")
    head = ov.split(":")[0]
    L = [f"# {t['name']} ({t.get('ticker') or 'no ticker yet'}): IPO summary, {t['ref_date']}",
         f"`Flip: {v['flip'][0]}` `Hold: {v['hold'][0]}` `Valuation: {(va.get('overall') or 'n/a').split(':')[0].replace(' vs comparables', '')}` `Overall: {head}`",
         "", "**The 30-second answer.** "
         + (f"History gives it a {fb['p_gain']:.0%} chance of being up a week after the open and {hb.get('p_gain', 0):.0%} after six months, "
            f"against {fb['base_p_gain']:.0%} and {hb.get('base_p_gain', 0):.0%} for IPOs in general. " if fb else "")
         + (f"It most likely prices {ps['headline']} its range. " if ps.get("headline") else "")
         + f"Overall read: **{ov}**."]
    L += five_questions(res, T)
    # key numbers
    rng = t.get("range") or ((t.get("deep") or {}).get("range_last") or {}).get("range")
    growth = (f["rev0"] / f["rev1"] - 1) if f.get("rev0") and f.get("rev1") else None
    rows = [("Price / range", f"${c['price']:.2f}" if c.get("price") else (f"${rng[0]:g}-${rng[1]:g} (not priced yet)" if rng else "not filed")),
            ("Market value", money(t.get("mcap") or t.get("mcap_mid"))),
            ("Revenue (annualized) / growth", f"{money(f.get('rev0'))} / {growth:+.0%}" if growth is not None else money(f.get("rev0"))),
            ("Price / sales vs look-alikes", f"{va['p_s']:.1f}x vs {va['comps_p_s_median']:.1f}x" if va.get("status") == "ok" else "n/a"),
            ("Pricing odds (below / inside / above)", " / ".join(f"{ps['headline_probs'][k]:.0%}" for k in ("below", "inside", "above")) if ps.get("headline_probs") else "n/a"),
            ("Chance up by day 5 (all IPOs)", f"{fb['p_gain']:.0%} ({fb['base_p_gain']:.0%})" if fb else "n/a"),
            ("Chance up by month 6 (all IPOs)", f"{hb['p_gain']:.0%} ({hb['base_p_gain']:.0%})" if hb else "n/a"),
            ("Priciest-quarter open line", f"${vo['rich_open_price']:.2f} ({vo['rich_open_premium']:+.0%} vs IPO price)" if vo.get("status") == "ok" else "n/a")]
    L += ["\n## Key numbers", "| | |\n|---|---|"] + [f"| {a} | {b} |" for a, b in rows]
    # simulated outcomes
    sim = res.get("simulation") or {}
    nm = "twin IPOs (same setup)" if sim.get("twin IPOs (same setup)") else "all recent IPOs"
    s = sim.get(nm) or {}
    if s:
        L += [f"\n## What could happen (10,000 simulated paths from {nm}, from the open)",
              "| holding period | chance up | typical (median) | bad case (worst 10%) | good case (best 10%) |\n|---|---|---|---|---|"]
        for h, lab_ in (("d1", "1 day"), ("d5", "1 week"), ("d21", "1 month"), ("d180", "6 months")):
            x = s.get(h)
            if x:
                L.append(f"| {lab_} | {x['up']:.0%} | {pct(x['median'], 0)} | {pct(x['p10'], 0)} | {pct(x['p90'], 0)} |")
    # demand and hype (what the script measures; news is added by Claude in chat)
    ds = res.get("decision_signals") or {}
    x = ds.get("x") or {}
    m = t.get("mkt") or {}
    L += ["\n## Demand and hype (measured)",
          f"- Range before pricing: **{ps.get('revision') or 'not known'}**; priced vs range: **{x.get('priced') or 'not priced yet'}**.",
          f"- Market mood: IPO ETF {pct(m.get('ipo_etf_20d'), 1)} and Nasdaq {pct(m.get('nasdaq_20d'), 1)} over 20 days; VIX {m.get('vix')}.",
          "- Order-book coverage, retail platforms, news tone: added from the news (two sources each) in the chat summary; not modelled."]
    # what to watch
    cal = br.get("calendar") or {}
    L += ["\n## What to watch next",
          "- Re-run on: a new S-1/A (range or share count change), the final prospectus (424B4, final price), the first trade (`day1`).",
          (f"- Dates: lockup expires {cal['lockup_expires']}; first earnings about {cal['first_earnings_estimate']}; quiet period ends {cal['quiet_period_ends']}."
           if cal else "- Dates: set once the first trade date is known.")]
    tr = (res.get("track_record") or {}).get("flip") or {}
    L += ["\n## How much to trust it",
          f"- Flip rule: right {tr['hit_rate']:.0%} of the time in its backtest; hold rule: about the base rate (no edge). " if tr.get("hit_rate") else "- No backtest record loaded. ",
          f"- {res.get('left_market', 0)} of {len(res.get('comparables') or [])} look-alikes lack price data; failed sources: {', '.join(res.get('failed_sources') or {}) or 'none'}.",
          "\n*History, not a prediction. Retail usually buys at the open, not the IPO price. Not financial advice.*"]
    return "\n".join(L)


def means(T, key):
    t = T.get(key)
    return [f"> **What it means ({t[0]}):** {t[1]}"] if t else []


def render(res):
    t, v = res["target"], res["verdict"]
    L = []
    fl, hl = v["flip"], v["hold"]
    tr = res.get("track_record") or {}
    def trk(kind, lvl):
        b = ((tr.get(kind) or {}).get("by_confidence") or {}).get(lvl) or {}
        return f"backtest {b['right']}/{b['calls']} right at {lvl}" if b.get("calls") else "no backtest yet at this level"
    L.append(f"# {t['name']} ({t.get('ticker')}) - IPO analysis, reference date {t['ref_date']}")
    L.append(f"VERDICT  Flip {fl[0]} ({fl[1]}; {trk('flip', fl[1])})  |  Hold {hl[0]} ({hl[1]}; {trk('hold', hl[1])})")
    for kind, h in (("flip", "day 5"), ("hold", "day 180")):
        b = v.get(f"{kind}_vs_base")
        if b:
            cp_ = "n/a" if b["comps_p_gain"] is None else f"{b['comps_p_gain']:.0%}"
            L.append(f"  {kind}: chance of a gain by {h} (from the open) {b['p_gain']:.0%} = comparables {cp_} (n_eff {b['n_eff']:.0f}) "
                     f"shrunk toward the trailing base rate {b['base_p_gain']:.0%} (n={b['base_n']}); method {b['method']}")
    TK = takeaways(res)
    L += five_questions(res, TK)
    L += means(TK, "verdict")
    ds = res.get("decision_signals")
    if ds:
        L.append(f"\n## Decision-time signals (base rate + one shrunk step per signal; steps from {ds['train_n']} past deals)")
        x = ds["x"]
        L.append("This deal: " + "; ".join(f"{k} = {x.get(k) or 'not known yet'}" for k in ("priced", "ipo_etf", "vix", "open")))
        L.append("| chance of a gain from the open | all recent IPOs | this setup, before the open | " + " | ".join(OPEN_GROUPS) + " |\n|---|---|---|" + "---|" * len(OPEN_GROUPS))
        for h, b in ds["by_horizon"].items():
            L.append(f"| by {HNAME.get(h, h)} | {b['base_p']:.0%} (n={b['base_n']}) | {b['p_pre_open']:.0%} | " + " | ".join(f"{b['at_open'][g]:.0%}" for g in OPEN_GROUPS) + " |")
        L.append("The open columns are what history says once the first price prints; they are not targets or advice. "
                 "Tested 2020-25 (day 5 and day 180): these adjustments did not beat the plain base rate, so the verdict does not use them.")
        L += means(TK, "decision")
        tw = ds.get("twins") or {}
        if tw:
            mo = "; ".join(f"{k} = {v}" for k, v in tw["matched_on"].items()) or "nothing known yet"
            L.append(f"\n## Twin IPOs: past deals with the same setup ({mo}); {tw['n']} found")
            L.append("| from the open | " + " | ".join(HNAME[h] for h in TWIN_HORIZONS) + " |\n|---|" + "---|" * len(TWIN_HORIZONS))
            for nm, s in (("twins: % up", tw["twins"]), ("all recent IPOs: % up", tw["all_recent"])):
                L.append(f"| {nm} | " + " | ".join("n/a" if s[h]["share_up"] is None else f"{s[h]['share_up']:.0%} (n={s[h]['n']})" for h in TWIN_HORIZONS) + " |")
            L.append("| twins: median | " + " | ".join(pct(tw["twins"][h]["median"]) for h in TWIN_HORIZONS) + " |")
            if tw["examples"]:
                L.append("\nMost recent twins:\n| company | first trade | " + " | ".join(HNAME[h] for h in TWIN_HORIZONS) + " |\n|---|---|" + "---|" * len(TWIN_HORIZONS))
                for e in tw["examples"]:
                    L.append(f"| {e['name'][:40]} ({e['ticker']}) | {e['first_trade']} | " + " | ".join(pct(e[h], 0) for h in TWIN_HORIZONS) + " |")
            L += means(TK, "twins")
    c = t["cover"]
    rng_ = t.get("range") or ((t.get("deep") or {}).get("range_last") or {}).get("range")
    L.append(f"Status {t['status']}; price {c.get('price') or 'not priced yet'}; range {('$%g-$%g' % tuple(rng_)) if rng_ else 'not filed'}; "
             f"market cap {('$%.2fB at the price' % (t['mcap'] / 1e9)) if t.get('mcap') else ('$%.2fB at the range midpoint' % (t['mcap_mid'] / 1e9)) if t.get('mcap_mid') else 'not known yet'}; filing {t['url']}")
    br = res.get("brief")
    if br:
        L.append("\n## The company in plain English (from its prospectus)")
        if br["overview"]:
            L.append(br["overview"][:600] + ("..." if len(br["overview"]) > 600 else ""))
        sp = br.get("selling_holders_share")
        L.append(f"- **Who controls it:** {br['control']}" + (f"; selling shareholders sell {sp:.0%} of the offering" if sp is not None else ""))
        L.append(f"- **Lockup:** {br['lockup']}")
        if br["use_of_proceeds"]:
            L.append(f"- **Use of the money raised:** {br['use_of_proceeds'][:300]}")
        if br["banks"]:
            L.append(f"- **Banks:** {', '.join(br['banks'])}")
        for i, r_ in enumerate(br["risks"], 1):
            L.append(f"- **Risk {i}:** {r_}")
        if br["calendar"]:
            cl = br["calendar"]
            L.append(f"- **Calendar:** first trade {cl['first_trade']}; analyst quiet period ends {cl['quiet_period_ends']}; first earnings about "
                     f"{cl['first_earnings_estimate']} (estimate); lockup expires {cl['lockup_expires']}; 12-month seasoning {cl['twelve_month_seasoning']}")
        L.append("> **What it means (neutral):** the facts a reader needs before any number: what it sells, who has the votes, when insiders can sell, and what the company itself says could go wrong.")
    if res.get("signals"):
        L.append("\n## Signal scorecard\n| # | signal | value | dir | source |\n|---|---|---|---|---|")
        for s in res["signals"]:
            L.append(f"| {s['n']} | {s['signal']} | {str(s['value']).replace('|', '/')} | {s['dir']} | {s['source']} |")
        L += means(TK, "signals")
    L.append(f"\n## Comparables (n={len(res['comparables'])}; {res['left_market']} without price data)\n"
             "| company | IPO date | sim | biz | sit | open prem | d1 | d5 | d30 | lockup | today | top features | phrases |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in res["comparables"]:
        o = x.get("out") or {}
        g = lambda k: pct((o.get(k) or {}).get("open"), 0)  # noqa: E731
        if o.get("exit"):
            ex = o["exit"]
            g = lambda k, ex=ex: (f"{ex['kind']} {ex['date'][:7]} {ex['price'] / (x.get('cover') or {}).get('price', 1) - 1:+.0%} vs IPO" if k == "today" else "-")  # noqa: E731
        L.append(f"| {x['name']} ({x.get('ticker')}) | {x.get('first_trade') or x['filed']} | {x.get('similarity')} | {x.get('biz_score')} | {x.get('sit_score')} | "
                 f"{pct(o.get('open_prem'), 0)} | {g('d1')} | {g('d5')} | {g('d30')} | {g('lockup')} | {g('today')} | {', '.join(x.get('match_features') or [])} | {'; '.join(x.get('match_phrases') or [])} |")
    L += means(TK, "comparables")
    L.append("\n## Pattern (similarity-weighted, returns from the first open unless noted)\n| horizon | n | median | 90% interval | 25-75% | % green | leave-one-out flips |\n|---|---|---|---|---|---|---|")
    for k, s in res["pattern"].items():
        L.append(f"| {k} | {s['n']} | {pct(s['median'])} | {pct(s['ci90'][0])} .. {pct(s['ci90'][1])} | {pct(s['q25'])} .. {pct(s['q75'])} | {s['hit']:.0%} | {', '.join(s.get('loo_flip_names', [])) or '-'} |")
    op = res["open_premium"]
    if op.get("n"):
        L.append(f"Open premium over IPO price: median {pct(op['median'])} (90% {pct(op['ci90'][0])}..{pct(op['ci90'][1])}, n={op['n']})")
    if res.get("baselines"):
        b = res["baselines"]["all_us_ipos_12m"]
        L.append("Baseline, all US IPOs >= $200M in the prior 12 months (from open): " + ", ".join(f"{h} {pct(s.get('median'))} n={s.get('n')}" for h, s in b.items()))
        sb = res["baselines"].get("same_vix_bucket_and_range_direction") or {}
        L.append(f"Baseline, same VIX bucket ({sb.get('vix_bucket')}) and range direction ({ {1: 'raised', -1: 'cut', 0: 'unchanged'}.get(sb.get('range_rev'), 'not known')}): " + ", ".join(f"{h} {pct((sb.get(h) or {}).get('median'))} n={(sb.get(h) or {}).get('n')}" for h in ("d5", "d30")))
    L += means(TK, "pattern")
    if res.get("signal_effects"):
        L.append("\n## Signal effects in the comparables (day-5 from open, + vs -)")
        for name, g in res["signal_effects"].items():
            L.append(f"- {name}: + {pct(g['+'].get('median'))} (n={g['+']['n']}) vs - {pct(g['-'].get('median'))} (n={g['-']['n']})")
        L.append("> **What it means (neutral):** which features went with better or worse day-5 moves among these comparables. "
                 "Gaps under ~5 points, or groups under ~8 deals, are noise; the verdict does not use this table.")
    ref = res["reference"]
    L.append("\n## Reference levels by open premium (historical reference level, not a target)\n| open premium | d5 median (n) | d30 median (n) |\n|---|---|---|")
    for r in ref["bins"]:
        a, b2 = r["bin"]
        L.append(f"| {a:+.0%} .. {'up' if b2 is None else f'{b2:+.0%}'} | {pct(r['d5'].get('median'))} ({r['d5']['n']}) | {pct(r['d30'].get('median'))} ({r['d30']['n']}) |")
    lv = ref["level"]
    L.append("Historical reference level: " + (lv if isinstance(lv, str) else f"opens at or above {lv['open_premium_at_or_above']:+.0%} over the IPO price had a negative day-5 median ({pct(lv['d5']['median'])}, 90% {pct(lv['d5']['ci90'][0])}..{pct(lv['d5']['ci90'][1])}, n={lv['d5']['n']})"))
    wl = ref.get("weak_level")
    if isinstance(wl, dict):
        L.append(f"Weak-evidence level (n >= {wl['d5']['n']}, interval not clear of zero): opens at or above {wl['open_premium_at_or_above']:+.0%} had a negative day-5 median ({pct(wl['d5']['median'])})")
    L += means(TK, "reference")
    L += render_extras(res, TK)
    L += bottom_line(res, TK)
    so = res.get("sources")
    if so:
        L.append("\n## Sources (every number above comes from these)")
        L.append(f"- Prospectus used: {so['target_filing']}\n- Financials: {so['financials']} ({so['xbrl']})\n- Filing index: {so['filing_index']}"
                 f"\n- Prices: {so['prices']}\n- List of past IPOs: {so['deal_list']}")
        L.append("- Comparables' prospectuses: " + "; ".join(f"[{c_['name'][:30]}]({c_['url']})" for c_ in so["comparables"] if c_.get("url")))
    if res["changes"]:
        L.append("\nComparable changes: " + "; ".join(f"{x['action']} {x['cik']} ({x['reason']}){'' if x['applied'] else ' [not applied]'}" for x in res["changes"]))
    L.append("\nFailed sources: " + (", ".join(f"{k} ({v})" for k, v in res["failed_sources"].items()) or "none"))
    L += ["Note: " + n for n in res["notes"]]
    return "\n".join(L)


def money(x):
    return "n/a" if x is None else f"${x / 1e9:,.1f}B" if abs(x) >= 1e9 else f"${x / 1e6:,.0f}M"


def render_extras(res, TK=None):
    """Archetype, closest peer, pricing simulation, valuation, caution levels and the reference checklist."""
    L = []
    TK = TK if TK is not None else takeaways(res)
    a = res.get("archetype")
    if a:
        L.append(f"\n## Archetype: {a['name']}")
        L.append("Why: " + "; ".join(a["why"] or []) + f". Matching: {a['matching']}"
                 + (f" (pool of this archetype: {a['pool_of_same_archetype']}" + ("; widened with same-industry IPOs because it was small)" if a["widened_to_industry"] else ")") if a["matching"] == "archetype" else ""))
        L += means(TK, "archetype")
    cp = res.get("closest_peer")
    if cp:
        T, P = cp["target"], cp["peer"]
        f = lambda x, k: money(x.get(k)) if k == "revenue" else ("n/a" if x.get(k) is None else f"{x[k]:.1f}x" if k == "p_s_at_ipo" else f"{x[k]:+.0%}")  # noqa: E731
        L.append(f"\n## Closest peer: {cp['name']} ({cp['ticker']}), first trade {cp['first_trade']}, similarity {cp['similarity']}")
        L.append("| metric | this IPO | peer at its IPO |\n|---|---|---|")
        for k, nm in [("revenue", "Revenue (latest period, annualized)"), ("growth", "Growth"), ("fcf_margin", "FCF margin"),
                      ("float_pct", "Float"), ("p_s_at_ipo", "Price / sales at IPO")]:
            L.append(f"| {nm} | {f(T, k)} | {f(P, k)} |")
        r = cp["returns_from_open"]
        L.append(f"Peer's path from the first open (opened {pct(cp['open_premium'], 0)} vs its IPO price): day 1 {pct(r['d1'])}, day 5 {pct(r['d5'])}, day 30 {pct(r['d30'])}, day 180 {pct(r['d180'])}")
        L += means(TK, "peer")
    ps = res.get("pricing_sim")
    if ps:
        L.append("\n## Pricing simulation (where the final price lands vs the first filed range)")
        if ps["status"] != "ok":
            L.append(ps["status"])
        else:
            L.append(f"{ps['simulations']:,} Monte Carlo draws over the {ps['neighbors_used']} most similar past deals (range width, S&P / Nasdaq / sector 20-day momentum, float, lead bank's pricing and day-30 record).")
            L.append("| outcome | probability | 90% interval |\n|---|---|---|")
            nm = {"below": "Below the range", "mid": "Inside the range, below the top", "top": "At the top", "above": "Above the range (raised range / Rule 430A)"}
            for k in PRICE_CATS:
                L.append(f"| {nm[k]} | {ps['probabilities'][k]:.0%} | {ps['ci90'][k][0]:.0%} .. {ps['ci90'][k][1]:.0%} |")
            if ps.get("headline"):
                h3 = ps["headline_probs"]
                how = (f"from {ps['revision_n']} recent deals whose range was **{ps['revision']}** before pricing (tested: beat the plain base rate in 6 of 6 years)"
                       if ps.get("method") == "base rate by range revision" else f"neighbors weighted {ps.get('alpha', 0):.0%}, trailing base rate {1 - ps.get('alpha', 0):.0%}")
                L.append(f"Most likely: **{ps['headline']}** the range (below {h3['below']:.0%} / inside {h3['inside']:.0%} / above {h3['above']:.0%}); {how}. "
                         "The probability column above is this model; the Monte Carlo line describes the neighbor model (shown, not used).")
            if ps.get("actual"):
                L.append(f"Actual: priced {ps['actual']}.")
            L.append(f"Not modelled: {ps['not_modelled']}.")
            L += means(TK, "pricing")
    v = res.get("valuation")
    if v:
        L.append("\n## Valuation check")
        if v["status"] != "ok":
            L.append(v["status"])
        else:
            L.append(f"**{v['overall']}** (at the {v['price_basis']}, ${v['price_used']:.2f}; n={v['n']} comparables at their own IPO price)")
            L.append("| measure | this IPO | comparables' median | rank | read |\n|---|---|---|---|---|")
            rk = lambda x: "n/a" if x is None else f"{x:.0%}"  # noqa: E731
            L.append(f"| Price / sales | {v['p_s']:.1f}x | {v['comps_p_s_median']:.1f}x | {rk(v['p_s_rank'])} | {v['p_s_label']} |")
            if v["growth_adj"] is not None:
                gm_ = v["comps_growth_adj_median"]
                L.append(f"| P/S per point of growth | {v['growth_adj']:.2f} | {'n/a' if gm_ is None else f'{gm_:.2f}'} | {rk(v['growth_adj_rank'])} | {v['growth_adj_label']} |")
            if v["rule_of_40"] is not None:
                r4 = v["comps_rule_of_40_median"]
                L.append(f"| Rule of 40 (growth % + FCF margin %) | {v['rule_of_40']:.0f} | {'n/a' if r4 is None else f'{r4:.0f}'} | - | {v['rule_of_40_label']} |")
            L.append(f"Price at which P/S would equal the comparables' median: ${v['price_at_comps_median_p_s']:.2f}; at their 75th percentile: ${v['price_at_comps_q75_p_s']:.2f}. These are what the comparables' multiples imply, not a fair value.")
            L += means(TK, "valuation")
    vo = res.get("value_at_open")
    if vo:
        L.append("\n## Valuation at the opening price (retail buys at the open)")
        if vo["status"] != "ok":
            L.append(vo["status"])
        else:
            L.append(f"Price / sales at the open, ranked against {vo['n']} past IPOs at their own open (median {vo['median_ps_at_open']:.1f}x; most expensive quarter from {vo['rich_ps_at_open']:.1f}x).")
            L.append("| if it opens | at | price / sales | rank among past opens |\n|---|---|---|---|")
            for g in vo["grid"]:
                L.append(f"| {g['open_premium']:+.0%} vs IPO price | ${g['open_price']:.2f} | {g['p_s']:.1f}x | {g['rank']:.0%}{' (most expensive quarter)' if g['rank'] >= 0.75 else ''} |")
            L.append(f"**Most-expensive-quarter line: an open above ${vo['rich_open_price']:.2f}** ({vo['rich_open_premium']:+.0%} vs ${vo['ipo_price']:.2f}). "
                     "Tested 2020-25: IPOs that opened above their line were less often up by day 180 in 5 of 6 years.")
            if vo.get("actual_open_premium") is not None:
                L.append(f"It opened {vo['actual_open_premium']:+.0%}: {vo['actual_p_s']:.1f}x sales, rank {vo['actual_rank']:.0%}{' - in the most expensive quarter' if vo['rich'] else ''}.")
        L += means(TK, "value_at_open")
    sim = res.get("simulation") or {}
    if sim:
        L.append("\n## Outcome simulation (10,000 draws of real past IPO paths, from the first open)")
        L.append("Each draw is one past IPO's whole path, so its day 1, week 1 and month 6 belong together. History, not a forecast.")
        for name, s in sim.items():
            L.append(f"\n**{name}** ({s['n_deals']} deals)\n| from the open | worst 10% | 25% | median | 75% | best 10% | chance up | >= +20% | <= -20% |\n|---|---|---|---|---|---|---|---|---|")
            for h, nm in SIM_H:
                x = s.get(h)
                if x:
                    L.append(f"| {nm} | {pct(x['p10'], 0)} | {pct(x['p25'], 0)} | {pct(x['median'], 0)} | {pct(x['p75'], 0)} | {pct(x['p90'], 0)} | {x['up']:.0%} | {x['up20']:.0%} | {x['down20']:.0%} |")
        L += means(TK, "simulation")
    rp, rw = res.get("reference_prices"), res.get("reference_prices_weak")
    L.append("\n## Reference checklist (from history, not advice or an order instruction)")
    lv = res["reference"]["level"]
    if rp:
        L.append(f"1. Opening-price caution level: past comparables that opened {lv['open_premium_at_or_above']:+.0%} or more above their IPO price had a clearly negative day-5 median. In this IPO's prices that is " + ", ".join(f"{k} ${p}" for k, p in rp.items()) + ".")
    elif rw:
        wl = res["reference"]["weak_level"]
        L.append(f"1. Opening-price caution level: no level with strong evidence. Weak evidence: opens {wl['open_premium_at_or_above']:+.0%} or more above the IPO price had a negative day-5 median; in this IPO's prices " + ", ".join(f"{k} ${p}" for k, p in rw.items()) + ".")
    else:
        L.append("1. Opening-price caution level: not enough evidence in the comparables to set one.")
    L.append("2. Re-run triggers: a new S-1/A (range raised, cut or shares changed) -> rerun `analyze`; the 424B4 (final price) -> rerun `analyze`, the pricing table becomes the actual; the first trade -> run `day1`.")
    L.append("3. On the first day the open can be far above the IPO price. A market order fills at whatever the open is; a limit order caps the price paid but may not fill. Any order in this pack goes through trader-risk and your typed yes.")
    return L


# ---------------------------------------------------------------- selftest (offline)

def selftest():
    conf = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    conf["bootstrap"]["resamples"] = 300
    mk = lambda **k: {"cik": k.get("cik", 1), "sic": k.get("sic", "7372"), "fund": k.get("fund", {}), "mkt": k.get("mkt", {}),  # noqa: E731
                      "mcap": k.get("mcap"), "deep": {"overview": k.get("text", "")}, "name": k.get("name", "x")}
    fund = {"rev0": 200e6, "rev1": 100e6, "gross": 150e6, "opinc": -20e6}
    t = mk(fund=fund, mcap=2e9, mkt={"vix": 15, "ipo_etf_20d": 0.03}, text="cloud security software for enterprise identity access")
    same = mk(cik=2, fund=dict(fund), mcap=2e9, mkt={"vix": 15, "ipo_etf_20d": 0.03}, text="cloud security software for enterprise identity access")
    far = mk(cik=3, fund={"rev0": 5e9, "rev1": 4.9e9, "gross": 1e9, "opinc": 4e8}, mcap=4e10, mkt={"vix": 32, "ipo_etf_20d": -0.08},
             text="frozen food distribution trucks warehouses grocery", sic="7389")
    filler = [mk(cik=10 + i, fund={"rev0": 1e8 * (i + 1), "rev1": 9e7 * (i + 1), "gross": 5e7, "opinc": 1e6 * (i - 2)},
                 mcap=1e9 * (i + 1), mkt={"vix": 14 + i, "ipo_etf_20d": 0.01 * i}, text=f"widget company number {i}") for i in range(5)]
    ranked = score_pool(t, [far, same] + filler, conf, with_text=True)
    assert ranked[0]["cik"] == 2, "identical company must rank first"
    assert ranked[0]["sit_score"] == 100.0, ranked[0]["sit_score"]
    assert ranked[0]["biz_score"] > 95, ranked[0]["biz_score"]
    assert ranked[-1]["cik"] == 3 or ranked[-1]["similarity"] < ranked[0]["similarity"]
    assert "security" in " ".join(ranked[0]["match_phrases"])
    # weighted median and bootstrap
    assert wquantile([1, 2, 3, 4], [1, 1, 1, 10], 0.5) == 4
    s = summarize([(x / 100, 1.0) for x in range(-20, 41)], conf)
    assert s["n"] == 61 and abs(s["median"] - 0.10) < 1e-9 and s["ci90"][0] <= s["median"] <= s["ci90"][1]
    assert summarize([(x / 100, 1.0) for x in range(-20, 41)], conf) == s, "seeded bootstrap must repeat"
    # point-in-time: nothing on or after the cutoff
    d0 = date(2024, 1, 2)
    bars = [(d0 + timedelta(i), 10 + i, 11 + i, 9 + i, 10.5 + i, 1000) for i in range(400)]
    y = {"bars": bars, "splits": []}
    full = outcomes(y, 10.0, d0)
    cut = outcomes(y, 10.0, d0, cutoff=d0 + timedelta(10))
    assert full["d30"] and full["y1"] and "today" in full
    assert cut["d5"] and "d30" not in cut and "y1" not in cut and "today" not in cut
    y2 = {"bars": bars, "splits": [(d0 + timedelta(50), 2.0)]}
    assert abs(outcomes(y2, 10.0, d0)["ipo_adj"] - 5.0) < 1e-9, "IPO price must follow later splits"
    # reference-level guard
    few = [{"similarity": 1, "out": {"open_prem": 0.6, "d5": {"open": -0.1}, "d30": {"open": -0.2}}} for _ in range(10)]
    assert reference_levels(few, conf)["level"] == "not enough evidence"
    many = few * 2 + [{"similarity": 1, "out": {"open_prem": 0.3, "d5": {"open": 0.05}, "d30": {"open": 0.04}}} for _ in range(20)]
    lv = reference_levels(many, conf)["level"]
    assert isinstance(lv, dict) and lv["open_premium_at_or_above"] == 0.35, lv   # first grid step above the +30% group
    # verdict rules
    assert verdict({"n": 5}, 0.02, conf) == ("MIXED", "low")
    assert verdict({"n": 25, "median": 0.08, "hit": 0.7, "ci90": [0.02, 0.12], "loo_flip_names": []}, 0.02, conf) == ("FAVORABLE", "high")
    assert verdict({"n": 25, "median": -0.08, "hit": 0.3, "ci90": [-0.12, -0.01]}, 0.02, conf)[0] == "UNFAVORABLE"
    # cover parser
    cov = parse_cover("We are offering 12,500,000 shares of our Class A common stock. The initial public offering price is $21.00 per share. "
                      "We have granted the underwriters an option to purchase up to 1,875,000 additional shares. Goldman Sachs & Co. LLC Morgan Stanley J.P. Morgan")
    assert cov["price"] == 21.0 and cov["offered"] == 12_500_000 and cov["greenshoe"] == 1_875_000
    assert cov["banks"][:2] == ["Goldman Sachs", "Morgan Stanley"]
    # network allowlist: only SEC EDGAR and Yahoo Finance over HTTPS
    for bad in ("http://www.sec.gov/x", "https://other.example.com/x", "ftp://www.sec.gov/x"):
        try:
            http_get(bad)
            raise AssertionError(f"fetched {bad}")
        except ValueError:
            pass
    # point-in-time modes: pre-pricing hides the final prospectus filed on the first-trade day, at-open keeps it
    fl = [("S-1/A", "2025-07-28", "a", "x"), ("424B4", "2025-07-31", "b", "y"), ("8-K", "2025-08-05", "c", "z")]
    assert [f[0] for f in cut_filings(fl, date(2025, 7, 31), "pre-pricing")] == ["S-1/A"]
    assert [f[0] for f in cut_filings(fl, date(2025, 7, 30), "at-open")] == ["S-1/A", "424B4"]
    assert cut_filings(fl, None) == fl
    # multi-class share counts: a stated total is used once, per-class lines are summed
    t3 = ("Class A common stock to be outstanding immediately after this offering 47,800,000 shares. Class B common stock to be outstanding "
          "immediately after this offering 334,273,197 shares. Class C common stock to be outstanding immediately after this offering None. "
          "Total Class A common stock, Class B common stock, and Class C common stock to be outstanding immediately after this offering 382,073,197 shares")
    assert parse_deep(t3)["outstanding"] == 382_073_197, parse_deep(t3)["outstanding"]
    t4 = ("Common stock to be outstanding immediately after this offering Class A common stock: 202,550,578 shares (or 207,650,578 shares). "
          "Class B common stock: 19,989,537 shares.")
    assert parse_deep(t4)["outstanding"] == 202_550_578 + 19_989_537, parse_deep(t4)["outstanding"]
    assert parse_cover("PRICE $23.00 A SHARE Price to Public")["price"] == 23.0
    assert parse_cover("We expect the initial public offering price to be $135.00 per share.")["range"] == [135.0, 135.0]
    assert parse_cover("an assumed price range of $25.00 to $28.00 per share")["range"] == [25.0, 28.0]
    # archetypes, in rule order
    a = lambda **k: archetype({"sic": k.get("sic", "7372"), "fund": k["fund"], "deep": {"nrr": k.get("nrr")}}, conf)[0]  # noqa: E731
    assert a(fund={"rev0": 2e9, "rev1": 1e9, "capex": 4e8}) == "hyper_growth"
    assert a(fund={"rev0": 3e8, "rev1": 2e8, "gross": 2.4e8}, nrr=120, sic="7389") == "saas"
    assert a(fund={"rev0": 3e8, "rev1": 2e8, "gross": 2.4e8}) == "saas", "software SIC counts when NRR is not disclosed"
    assert a(fund={"rev0": 5e8, "rev1": 4e8, "gross": 2e8, "cfo": 6e7, "capex": 1e7}, sic="3829") == "profitable"
    assert a(fund={"rev0": 5e8, "rev1": 4.9e8, "gross": 1e8, "cfo": -1e7}, sic="5812") == "consumer"
    assert a(fund={}, sic="2834") == "unclassified"
    # price categories vs the first range
    pc = lambda p: price_category({"cover": {"price": p}, "deep": {"range_first": {"range": [10.0, 12.0]}}})  # noqa: E731
    assert (pc(9), pc(11), pc(12), pc(13)) == ("below", "mid", "top", "above")
    # pricing Monte Carlo: deterministic, probabilities sum to 1
    nb = [{"cik": 100 + i, "name": f"d{i}", "filed": "2024-01-0%d" % (1 + i % 9), "cover": {"price": [9, 11, 12, 13][i % 4], "banks": ["Goldman Sachs"]},
           "deep": {"range_first": {"range": [10.0, 12.0]}}, "range": [10.0, 12.0], "float_pct": 0.1 + 0.01 * i,
           "mkt": {"spx_20d": 0.01 * (i % 5), "nasdaq_20d": 0.0, "sector_20d": 0.0}} for i in range(24)]
    tgt = {"cik": 1, "range": [20.0, 24.0], "cover": {"banks": ["Goldman Sachs"]}, "deep": {}, "float_pct": 0.12, "mkt": {"spx_20d": 0.02}}
    sim1, sim2 = pricing_sim(tgt, nb, conf, date(2025, 1, 1)), pricing_sim(tgt, nb, conf, date(2025, 1, 1))
    assert sim1["status"] == "ok" and abs(sum(sim1["probabilities"].values()) - 1) < 1e-9 and sim1["probabilities"] == sim2["probabilities"]
    # valuation: far above every comparable's multiple reads overvalued
    vt = {"fund": {"rev0": 1e9, "rev1": 8e8}, "cover": {"price": 100.0}, "deep": {"outstanding": 1e9}, "range": None}
    vcs = [{"mcap": 5e9 + 1e8 * i, "fund": {"rev0": 1e9, "rev1": 8e8}} for i in range(10)]
    vv = valuation(vt, vcs, conf)
    assert vv["overall"].startswith("OVERVALUED") and vv["p_s"] == 100.0
    assert reference_prices({"cover": {"price": 20.0}}, {"open_premium_at_or_above": 0.25}) == {"final": 25.0}
    assert calibration([{"flip": "FAVORABLE", "flip_conf": "high", "actual_d5_open": 0.1, "hold": "MIXED", "hold_conf": "low", "actual_d180_open": -0.2}])["flip"]["hit_rate"] == 1.0
    # verdict against the base rate: 60% of comparables up, base 20% up -> shrinks below 0.5 with a strong prior
    vc = dict(conf, verdict=dict(conf["verdict"], method="shrunk", shrink_k=40, delta=0.05, tau_years=None, conf_bands=[0.1, 0.2]))
    comps_ = [{"similarity": 10, "first_trade": "2024-06-01", "out": {"d5": {"open": 0.1 if i < 6 else -0.1}}} for i in range(10)]
    base_ = {"sample": [["2024-01-01", 0.05 if i < 20 else -0.05, None, "mid"] for i in range(100)]}
    (call, _), info = verdict_vs_base(comps_, base_, "d5", date(2025, 1, 1), vc)
    assert abs(info["comps_p_gain"] - 0.6) < 1e-9 and info["p_gain"] < 0.5 and call == "UNFAVORABLE", info
    vx = dict(conf, verdict=dict(vc["verdict"], method="excess", v1_dh=0.1))
    assert verdict_vs_base(comps_, base_, "d5", date(2025, 1, 1), vx)[0][0] == "FAVORABLE", "60% vs 20% base clears a 10-point gap"
    # pricing blend stays a distribution and adds a three-way headline
    bp = {"status": "ok", "probabilities": {"below": 0.0, "mid": 0.2, "top": 0.3, "above": 0.5}}
    blend_pricing(bp, {"buckets": {"below": 0.25, "mid": 0.25, "top": 0.25, "above": 0.25}, "n_buckets": 40},
                  dict(conf, pricing=dict(conf["pricing"], base_alpha=0.5)))
    assert abs(sum(bp["probabilities"].values()) - 1) < 1e-9 and bp["probabilities"]["below"] == 0.125 and bp["headline"] == "inside"
    # revision pricing: a raised range points to the deals that were raised before
    recs_ = [{"bucket": "above", "revision": "raised"}] * 8 + [{"bucket": "mid", "revision": "unchanged"}] * 30 + [{"bucket": "below", "revision": "cut"}] * 6
    ps_ = {"status": "ok", "probabilities": {}}
    revision_pricing({"deep": {"range_first": {"range": [25.0, 28.0]}, "range_last": {"range": [30.0, 32.0]}}}, recs_, ps_)
    assert ps_["revision"] == "raised" and ps_["headline"] == "above" and abs(sum(ps_["probabilities"].values()) - 1) < 1e-9, ps_
    assert range_revision([10, 12], [10, 12]) == "unchanged" and range_revision([10, 12], [8, 9]) == "cut" and range_revision(None, [1, 2]) is None
    # valuation at the open: the most-expensive-quarter line is that quarter's multiple, converted to this deal's price
    tr_ = [{"mcap": 1e9, "fund": {"rev0": 1e8}, "out": {"open_prem": 0.1 * i}} for i in range(40)]   # 10x .. 49x sales at the open
    vo_ = value_at_open({"fund": {"rev0": 1e8}, "deep": {"outstanding": 1e8}, "cover": {"price": 10.0}}, tr_, conf)
    assert vo_["status"] == "ok" and abs(vo_["rich_ps_at_open"] - 39.0) < 1e-6 and abs(vo_["rich_open_price"] - 39.0) < 1e-6, vo_
    # simulation: draws keep each past path whole and are repeatable with the seed
    paths = [(1.0, {"d1": {"open": 0.01 * i}, "d5": {"open": 0.02 * i}, "d180": {"open": -0.01 * i}}) for i in range(-10, 11)]
    s1_, s2_ = simulate({"x": paths}, conf, draws=2000), simulate({"x": paths}, conf, draws=2000)
    assert s1_ == s2_ and abs(s1_["x"]["d5"]["up"] - s1_["x"]["d1"]["up"]) < 1e-9 and s1_["x"]["d180"]["up"] < 0.6
    # signal steps: a group that rose more often than the training set moves p up, an unseen group does nothing
    tr = [{"bucket": "above" if i < 40 else "mid", "mkt": {}, "out": {"d5": {"open": 0.1 if (i < 30 or i >= 80) else -0.1}}} for i in range(100)]
    p_up, st_ = signal_p(tr, {"priced": "above"}, "d5", 0.5, conf, use=["priced"])
    p_in, _ = signal_p(tr, {"priced": "inside"}, "d5", 0.5, conf, use=["priced"])
    assert p_up > 0.5 > p_in and st_["priced"]["n"] == 40, (p_up, p_in, st_)
    assert signal_p(tr, {"priced": "below"}, "d5", 0.4, conf, use=["priced"])[0] == 0.4
    assert signal_x({"bucket": "top", "mkt": {"vix": 25, "ipo_etf_20d": -0.01}}, 0.3) == {"priced": "inside", "ipo_etf": "down", "vix": ">=20", "open": OPEN_GROUPS[2]}
    print("selftest: all checks passed (similarity, bootstrap, point-in-time filter, split adjustment, reference-level guard, verdicts, base-rate verdicts, parser, multi-class shares, calibration, archetypes, price categories, pricing Monte Carlo, pricing blend, signal steps, valuation, reference prices)")


# ---------------------------------------------------------------- CLI

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    if "--selftest" in sys.argv:
        selftest()
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("analyze", "comps"):
        p = sp.add_parser(name)
        p.add_argument("query")
        p.add_argument("--facts", help="JSON of S-1 numbers (rev0, rev1, gross, opinc, cfo, capex, cash, debt) for an IPO with no 10-Q yet")
        p.add_argument("--drop", action="append", default=[], help="CIK:reason, remove a comparable")
        p.add_argument("--add", action="append", default=[], help="CIK:reason, add a comparable the score missed")
        p.add_argument("--json", action="store_true")
        p.add_argument("--save", action="store_true", help="also write trader/reports/ipo-<TICKER>-<date>.md and its -summary.md")
        p.add_argument("--summary", action="store_true", help="print the short summary report instead of the full one")
        p.add_argument("--coverage", help='order-book coverage from the news, e.g. "8x; Bloomberg 2026-09-09; Reuters 2026-09-09" (logged for future testing)')
        p.add_argument("--no-log", action="store_true", help="do not append this run to the forward paper log")
        p.add_argument("--as-of", help="replay as of YYYY-MM-DD (point-in-time: no filing or price on/after it; never logged)")
        p.add_argument("--mode", choices=MODES, default="at-open", help="with --as-of: pre-pricing hides the final prospectus; at-open allows it")
    sp.add_parser("forward")
    sp.add_parser("regress")
    p = sp.add_parser("day1")
    p.add_argument("query")
    p.add_argument("--json", action="store_true")
    p = sp.add_parser("backtest")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true")
    sp.add_parser("clean")
    a = ap.parse_args()
    if a.cmd == "clean":
        print(f"Removed {prune_cache(all_files=True)} cached files from {CACHE}")
        return
    pruned = prune_cache()
    log = (lambda *x: print(*x, file=sys.stderr)) if getattr(a, "json", False) else print
    if pruned:
        log(f"(cache: removed {pruned} files older than {CACHE_DAYS} days)")
    if a.cmd == "regress":
        sys.exit(0 if regress() else 1)
    if a.cmd == "forward":
        print(json.dumps(forward_score(), indent=1, default=str))
        return
    if a.cmd in ("analyze", "comps"):
        res = analyze(a.query, a.facts, a.drop, a.add, log=log, quick=(a.cmd == "comps"), as_of=d_(a.as_of) if a.as_of else None, mode=a.mode)
        if a.cmd == "analyze" and not a.no_log and not a.as_of and res["target"]["status"] != "trading":
            forward_log(res, a.coverage)
        text = render(res)
        short = summary_report(res) if a.cmd == "analyze" else None
        if a.json:
            print(json.dumps(res, indent=1, default=str))
        else:
            print(short if a.summary and short else text)
        if a.save:
            REPORTS.mkdir(parents=True, exist_ok=True)
            tag = re.sub(r"[^A-Za-z0-9.-]", "", str(res["target"].get("ticker") or res["target"]["cik"]))[:12] or "ipo"   # safe filename
            stem = f"ipo-{tag}-{d_(a.as_of) if a.as_of else TODAY}"
            f = REPORTS / f"{stem}.md"
            f.write_text(text, encoding="utf-8")
            log(f"Saved {f}")
            if short:
                (REPORTS / f"{stem}-summary.md").write_text(short + f"\n\nFull report: {f.name}\n", encoding="utf-8")
                log(f"Saved {REPORTS / (stem + '-summary.md')}")
    elif a.cmd == "day1":
        out = day1(a.query)
        print(json.dumps(out, indent=1, default=str))
    elif a.cmd == "backtest":
        lim = None if a.all else (a.limit or cfg()["backtest"]["limit"])
        out = backtest(lim, log=log)
        if a.json:
            print(json.dumps(out, indent=1, default=str))
        else:
            print(json.dumps(out["calibration"], indent=1))
            print(f"Saved {BACKTEST_FILE}")


if __name__ == "__main__":
    main()
