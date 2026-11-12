# Security review (v4, 2026-11-11)

Scanned with NVIDIA SkillSpector 2.12 (`skillspector scan skill --no-llm`) and by hand. Score 86/100; every
remaining finding was reviewed:

| finding | what it is | status |
|---|---|---|
| CRITICAL TT3: environment value reaches a network call | `SEC_USER_AGENT` (your SEC contact) goes in the User-Agent header. SEC requires it on every EDGAR request. It is not a secret, and the code sends it only to `*.sec.gov` | accepted, by design |
| MEDIUM E1 x5: external transmission | HTTPS GETs of public data from SEC EDGAR and Yahoo Finance | accepted; host allowlist in `http_get` refuses anything else |
| MEDIUM LP3: no tool scope declared | the skill runs one Python script and reads / writes its own files; listed in `SKILL.md` -> "Security and scope" | accepted (declaring auto-granted tools would widen permissions) |
| MEDIUM EA2: autonomous decision making | the flagged text is the rule that the skill never places, sizes or approves an order | false positive |

Hand checks:
- No `eval` / `exec` / `subprocess` / `os.system` / `pickle`; no TLS verification turned off; no code downloaded or run.
- Network: HTTPS only, to `www.sec.gov`, `data.sec.gov`, `efts.sec.gov`, `query1/2.finance.yahoo.com`; tested in `--selftest`.
- Files: writes only its cache and `trader/` in the project; report filenames are sanitized.
- No credentials, e-mail addresses, personal names or local paths in this repository; `trader/` is git-ignored.

Report a problem by opening an issue.
