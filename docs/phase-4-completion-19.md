# Phase 4 completion — cycle 19

## What changed

Two hard constraints were confirmed with the judges (see
`docs/capability-matrix.md`'s "Hard constraints" section):

1. No headless/headless-adjacent browsers anywhere, including as an
   optional fallback. This makes permanent what Cluster B had left open
   pending evidence ("no headless browser in this environment, revisit only
   with new evidence" — cycles 6/7/9): there will not be one.
2. Off-site querying of named public sites (Reddit, Quora, forums, review
   sites) for brand visibility/mentions is allowed, robots.txt-respecting,
   as long as the verdict is computed locally — no third-party scoring API.
   This reopens ENT-05/ENT-06/CIT-13, previously `DEFERRED` on the wrong
   reason (their old rejection cited "external-API dependency," which does
   not describe direct HTTP GETs to public pages).

This cycle builds the first of the two: Cluster B, shipped as a new skill.

## `static-extraction-audit` — new skill, Cluster B (Gate 2)

Nine capabilities, all script-decided, redefined against static HTTP +
parsing only (raw HTML, JSON-LD, and any embedded hydration-state JSON a
framework ships in its own response — `__NEXT_DATA__`, `__NUXT_DATA__`).
No `crawl4ai`, no Playwright, no browser dependency anywhere:

- **REN-01** — fetch foundation (infrastructure only, no finding).
- **REN-02** — hydration-state coverage diff: a text fragment inside an
  embedded hydration JSON blob absent from visible text.
- **REN-04** — price-render gating: a JSON-LD `Offer.price` not restated
  in visible text, currency/comma-tolerant numeric match.
- **REN-05** — real-time availability exposure: a volatile `availability`
  field with no freshness signal anywhere on the page.
- **REN-06** — semantic HTML5 boundary: no `<main>`/`<article>` on a
  substantial (150+ word) page. Never actually needed a browser.
- **REN-07** — boilerplate/content ratio: under 30% of visible text falls
  inside an existing `<main>`/`<article>` boundary.
- **REN-08** — multimodal accessibility: missing/empty `alt` on a
  non-decorative `<img>`; `<video>`/`<audio>` with no `<track>`.
- **REN-10** — NAP render asymmetry, narrowed to phone numbers: a number
  assembled in inline `<script>` text, absent from visible text.
- **REN-11** — PDF-only fact lock: always a `proactive` suggestion, never
  a confirmed defect — this project has no PDF-parsing library, so it can
  only note a PDF link exists, not verify its content.

**Not built, documented not silently dropped:** REN-03 (pagination/
infinite-scroll — the only static proxy is weak enough to risk this
project's FP bar without a fixture built to prove it first) and REN-09
(image-of-text facts — needs OCR/vision, a capability this project does
not have; unrelated to the browser constraint).

## Verification

- 59 new unit tests (`tests/test_static_extraction_audit.py`), covering
  every extraction function and finding function as a positive/negative
  pair, plus contract compliance, determinism, page-attribution and SSRF
  guard tests — same shape as `retrieval-readiness-audit`'s own test file.
- New 10-case labelled corpus (`tests/corpus/static_extraction_cases.json`
  + `tests/corpus/static_extraction/*.html`), measured by
  `tests/measure_static_extraction.py`: **precision 1.000, recall 1.000**
  (9 true positives across 8 defect cases — REN-08 contributes two findings
  in one case — 0 false positives, 0 false negatives, 0 composition
  errors).
- Full suite: 541/541 passing (up from 482).
- Live-validated against 4 real sites (vercel.com, chewy.com, docs.python.org,
  nextjs.org): correctly found REN-06 (no `<main>`/`<article>`) on
  vercel.com and docs.python.org's landing pages, REN-08 (missing alt) on
  chewy.com, no false crashes across any of them. nextjs.org's own site
  surfaced a genuine, now-documented limitation: Next.js's App Router
  streams hydration state as RSC "flight data"
  (`self.__next_f.push([...])`), not a `__NEXT_DATA__` script block — REN-02
  correctly reports nothing found (not a false `unknown`/crash) on those
  pages rather than mis-parsing the flight format; documented in
  `references/static-extraction-checks.md`, not silently wrong.

## Wiring

- Registered in `marketplace.json` (7th skill entry).
- Registered in `audit-orchestrator`'s SKILL.md skill registry table and
  Procedure section (a `--skill static-extraction-audit ...` line added to
  the worked `compose_report.py` example) — `compose_report.py` itself
  needed no code change, since it already takes an arbitrary `--skill NAME
  PATH` list rather than a hardcoded skill roster.

## Capability matrix

REN-01/02/04/05/06/07/08/10/11 move from `NOT_STARTED` to `IMPLEMENTED`.
REN-03/09 stay `NOT_STARTED`, documented. `INF-03` (render layer) stays
`REJECTED` — permanent, per hard constraint 1. `INF-04` (page bundle
artifact) stays `NOT_STARTED` — this skill still fetches independently
like every other skill in this marketplace; no shared bundle object exists.

## Next

Phase 2 of this cycle's plan: ENT-05/ENT-06 (entity-audit) and CIT-13
(citability-audit), the off-site brand-visibility additions unblocked by
hard constraint 2. Not started this cycle.
