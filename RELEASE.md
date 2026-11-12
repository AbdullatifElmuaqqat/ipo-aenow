# Releases

**This folder is PROD: a frozen copy, updated only when a new version is finished and checked.**
Day-to-day work happens in the dev copy, `Trading/.claude/skills/ipo-aenow/` (the skill Claude actually runs).

| version | date | what changed | checks |
|---|---|---|---|
| v4 | 2026-11-11 | Renamed ipo-analyst -> ipo-aenow; network allowlist; S-1 parser, pricing by range revision, valuation at the open, hold = base rate, outcome simulation, five-question summary report, takeover prices, replay modes, regression set | selftest PASS, regress PASS, walk-forward 2020-25, Figma / SpaceX replays |

## Rules for updating PROD
1. Change and test only in dev.
2. A new idea that changes a prediction is written down with its pass rule **before** it is tested, and is
   switched on only if it passes a walk-forward test.
3. Before a release, in dev: `ipo.py --selftest` and `ipo.py regress` both pass, and one full report renders.
4. Copy the dev skill files into `skill/`, add new evidence to `evidence/`, update `ABOUT.md`, add a row above.
5. Never copy `trader/` (private: SEC contact, logs, orders).

Note: `skill/scripts/ipo.py` expects to live in `<project>/.claude/skills/ipo-aenow/scripts/` (it finds
`trader/` from there). This folder is for reading and sharing; to run a PROD version, copy `skill/` into a
project's `.claude/skills/ipo-aenow/`.
