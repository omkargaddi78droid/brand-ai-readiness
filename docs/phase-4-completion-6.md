# Phase 4 (capability cycle 6 of N) — PER-05, PER-06, PER-07, PER-08

Phase 4 output, sixth capability cycle. Cluster A (perimeter) is now
complete: 8 of 8 capabilities. No new skill — extends
`perimeter-access-audit`, the same skill since Phase 2.

---

## A — Gap confirmation

Not baseline-covered by anything usable: `docs/baseline-capabilities.md`
marks PER-06 "Full" via `geo access`, but Phase 3 already established the
baseline is untestable offline and its recommendations carry no evidence we
can normalise. `BUILD_REQUIRED`, resolved by building — the last
build-required items in Cluster A.

Before starting, `REN-02…REN-04` was re-checked (per cycle 5's decision to
revisit only with new evidence) — still no headless browser in this
environment, nothing changed. Confirmed the deferral stands rather than
re-assuming it.

## B — Resource evaluation

stdlib only: `re` (newly imported into `check_perimeter.py` — it had never
needed it before this cycle), plus the fetch machinery already in the file.
No new dependency. PER-06 deliberately does not reach for `xml.etree.
ElementTree` — see §C.

## C — Design

**Extends an existing skill rather than adding a sixth.** All four
capabilities are Cluster A, gate 1, same "first, cheapest, veto-item" role as
PER-01–04. One skill per cluster, sixth time this convention has held.

**PER-05 and PER-07 calibrated exactly like PER-04**: `low` severity,
`proactive` track, because neither llms-full.txt nor `.md` negotiation has
measured evidence of citation impact — the same discipline
`docs/baseline-gaps.md` §2 established for llms.txt, applied without
modification to its two newer, even-less-adopted cousins.

**PER-06 parses sitemap.xml with a regex, deliberately not
`xml.etree.ElementTree`.** The sitemap is fetched from the audited site —
untrusted input — and a regex has no entity-expansion attack surface at all,
so "billion laughs" and external-entity attack classes a fuller XML parser
can be vulnerable to are structurally not a concern. This is the third time
this exact reasoning has governed a parsing choice in this marketplace
(JSON-LD stayed on `json.loads`, HTML stayed on a restricted `HTMLParser`),
now stated as a standing pattern rather than three independent decisions.

**PER-08 only evaluates once PER-06 confirms a sitemap exists** — the same
one-root-cause-one-finding discipline as PER-02 (vs. three PER-01 findings)
and ENT-02 (vs. a redundant ENT-01 pairing).

## D — Implement

`evaluate_llms_full_txt`, `evaluate_sitemap` (+3 finding builders: missing,
malformed, empty), `evaluate_md_negotiation`, `evaluate_sitemap_discoverability`,
`md_variant_url`, CLI flags (`--llms-full-file/-absent`,
`--sitemap-file/-absent`, `--md-file/-absent`), `audit()` extended to 11
parameters with the six pre-existing ones defaulting so no caller written
before this cycle needed to change.

## E — Test

**29 unit tests** (`test_perimeter_extras.py`) + **14-case measured corpus**
(`perimeter_extras_cases.json`, kept deliberately separate from the
PER-01/02/04 corpus — see §F) + the existing 252-test suite from cycles 1–5,
adjusted only where the `audit()` signature change required it. **281 tests
total project-wide.**

## F — Review

**Four real problems, none live this time — all caught by running the new
code against its own fixtures and by the project's existing test
infrastructure, before a single live request went out:**

1. **Missing `import re`.** `check_perimeter.py` had never needed regex
   before this cycle (robots.txt parsing uses `urllib.robotparser`, not
   patterns). The four new detectors do. Caught immediately by the test
   suite's own import — `NameError` on the first run, fixed in one line.
2. **The pre-existing PER-01/02/04 corpus broke.** `audit()`'s new optional
   parameters default to `"unavailable"`, so every one of the 23 existing
   corpus cases correctly started reporting PER-05/06/07/08 as `unknown` —
   accurate, but outside what that corpus was ever designed to measure.
   Rather than retrofitting 23 fixture cases with inputs for capabilities
   they predate, `measure_detection.py`'s comparison was scoped to exclude
   capability ids that corpus was never built to exercise — the corpus
   keeps testing exactly what it always tested.
3. **PER-08 collapsed two different unknowns into one silent bucket.**
   `sitemap_status="unavailable"` (couldn't determine whether a sitemap
   exists) and `sitemap_status="absent"` (confirmed no sitemap) were both
   originally treated as "nothing to check" — correct for the second,
   wrong for the first, which is a genuine unknown this project's own
   "unknown is first-class" principle says must be reported. Caught by a
   test asserting the *specific* unknown capability set a bare `audit()`
   call should produce, which didn't match until this was fixed.
4. **My own measurement harness, not the code, mis-isolated several
   corpus cases.** `clean-valid-sitemap` and three siblings supplied a
   sitemap without also supplying a robots.txt that references it, so
   PER-08 correctly fired alongside the PER-06 finding each case meant to
   test in isolation — and `defect-per08-not-applicable-no-sitemap` was
   mislabeled `clean` when `sitemap_status="absent"` correctly triggers a
   real PER-06 finding. Fixed by adding an isolating `robots_with_sitemap`
   fixture to the PER-06-only cases and relabeling the mislabeled one — a
   reminder that "false positive" during measurement can mean the
   *corpus* is wrong, not the detector, and both must be checked before
   assuming which.

**Field validation still ran, and still mattered**: confirmed live against a
real, 857-`<url>` sitemap (apple.com, standard default namespace) that the
happy path genuinely works at real-world scale, not just on a three-entry
fixture; confirmed two sites correctly report PER-06 `unknown` (403/406) file
rather than `missing` (404) when the sitemap is blocked rather than absent;
confirmed apple.com's robots.txt genuinely references its sitemaps (five
`Sitemap:` directives), so PER-08 correctly stays silent there. No live bug
this cycle — the discipline of testing before shipping caught everything
first, which is itself worth recording: five of six cycles found their bug
live; this one didn't have to.

## G — Document

This file; `SKILL.md`, `references/ai-bot-taxonomy.md` (new section),
README, `marketplace.json` (0.9.0 → 0.10.0), `docs/capability-matrix.md`
(PER-05/07 → IMPLEMENTED, PER-06/08 → PARTIALLY_COVERED — each has a
crawl-wide or cross-source half still out of scope), `docs/00-project-plan.md`.

## H — Freeze

Cluster A (PER-01…PER-08) is now frozen in full — the first cluster in this
project to reach 100% of its matrix-listed capabilities. Re-open only for:
PER-06's crawl-wide completeness half (needs a crawl to compare the sitemap
against), PER-08's llms.txt/sitemap URL-set disagreement half (needs parsing
and diffing two URL sets), or PER-07 upgraded from path-suffix negotiation to
real `Accept`-header content negotiation (needs a second request variant this
cycle didn't build).

---

## Field validation

Seven live sites (python.org, github.com, stripe.com, nytimes.com,
gsmarena.com, rtings.com, apple.com), read-only, `--no-edge-probe` to keep
requests to the five new/existing well-known-path fetches.

| Finding | Verified against |
|---|---|
| `apple.com`: no PER-06/07/08 findings | Its `/sitemap.xml` has 857 real `<url><loc>` entries under the standard namespace; its robots.txt has five genuine `Sitemap:` directives |
| `python.org`, `stripe.com`: PER-06 sitemap-missing | Plain 404 at `/sitemap.xml`, confirmed by direct fetch |
| `github.com`: PER-06 `unknown` | `/sitemap.xml` returns HTTP 406, not 404 — correctly not reported as "missing" |
| `nytimes.com`: PER-06 `unknown` | `/sitemap.xml` returns HTTP 403 — same distinction |
| All seven: PER-07 fires | None serve a `.md` variant at any tested path — consistent with this being a genuinely rare, emerging convention, as PER-07's own `low`/`proactive` calibration already assumes |

## Next

Cluster A is done. Remaining fronts, per the capability matrix's own
front-loading order and this project's now seven-cycle-tested pattern of
avoiding rendering work until a headless browser is actually available:
`CQ-02/04/09/12` (agent-judged content checks, extending
`content-quality-audit` the way EN-01/03 and CIT-04 extended their skills),
or `ENT-05/06` (entity collision, lookalike domains — needs the off-site
scope decision `docs/baseline-selection.md` flagged as still open). Both are
buildable without rendering; `REN-02…REN-04` stays deferred until the
environment changes.
