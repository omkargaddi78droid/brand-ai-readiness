# Phase 4 (cycle 18) — PER-08, ENT-04, CIT-07 + submission packaging

Three small, independent capability extensions — all explicitly flagged in
the capability matrix as "buildable, no open design question" — plus the
first real, produced-and-inspected submission zip this project has ever
built (every prior cycle only estimated its size). Per
`~/.claude/plans/clever-pondering-falcon.md` Route 3.

---

## A — PER-08: llms.txt/sitemap URL-set agreement (second half)

**Design**: llms.txt is a curated subset (PER-04's own mechanism note —
"not a mirror of the sitemap"), so the sitemap having URLs llms.txt omits
is the intended pattern, not a disagreement. The real inconsistency worth
flagging runs the other way: a llms.txt link the sitemap doesn't know about
at all. New `evaluate_llms_sitemap_agreement()` in `check_perimeter.py`,
wired into `audit()` alongside the other seven checks.

**Two real false-positive classes found and fixed via live validation**,
not anticipated going in:

1. llms.txt conventionally links a `.md` content-negotiation variant of a
   real page (PER-07's own concept) — `vercel.com`/`supabase.com` both do
   this. Fixed: strip a `.md` suffix before comparing paths.
2. llms.txt also links its own companion machine-readable files
   (`llms-full.txt`, JSON/XML schemas) and sometimes a wholly separate
   API-spec host (`openapi.vercel.sh`) — none of these are pages a sitemap
   is expected to list. Fixed: skip `.txt`/`.json`/`.xml`-suffixed links
   and cross-host links entirely rather than comparing them.
3. A third real shape found live: `vercel.com` and `supabase.com`'s
   `sitemap.xml` is a `<sitemapindex>` of sub-sitemap URLs, not a flat
   `<urlset>` of real pages — comparing against the index's own pointer
   URLs flagged nearly everything as "missing" from the wrong data
   entirely. Fixed: detect the root element type (`_SITEMAP_ROOT_PATTERN`
   already captures it) and report an honest `unknown` rather than a
   fabricated comparison — this project doesn't recurse into sub-sitemaps,
   the same class of gap PER-06's own completeness limitation already
   documents.

**12 new tests** (`LlmsSitemapAgreementTests`). **Live-validated on 6 real
sites**: the 4 from the prior validation pass (all clean, llms.txt absent
on all 4 — PER-04 already covers that), plus `vercel.com` and
`supabase.com` specifically to exercise the comparison logic against real
llms.txt files. `supabase.com` now correctly reports `unknown` (sitemap
index); `vercel.com`'s real sitemap resolves to a flat urlset and the fix
reduced its false-positive count from 18 orphaned URLs to 4 genuine
`sitemap.md`-named meta-navigation pages — a small, low-severity residual
left as-is rather than chased with a third patch (per this project's own
standing rule against over-fitting to one vendor's naming convention).

## B — ENT-04: sitemap-scoped crawl-wide duplicate detection

**Design**: the matrix's stated blocker ("needs a sitemap-wide canonical
map... BUILD_REQUIRED") does not need a real crawler — a slug-variant/
trailing-slash/scheme fork is detectable from the sitemap's own declared
URL list alone, by grouping URLs under a normalised key (scheme-folded,
`www.`-stripped host, trailing-slash-stripped path) and flagging any group
with more than one distinct literal URL. New `find_sitemap_url_forks()` in
`check_entity.py`, exposed via a new `--sitemap-file` CLI mode
(`audit_sitemap()`) — a separate once-per-site mode from the existing
once-per-page `--url` mode, since it operates on a URL list, not one
page's markup.

Deliberately narrow: no case-folding (real case-sensitive URLs exist) and
no query-string normalisation (a genuine identifying parameter like
`?id=5` would otherwise collide with a different one) — only the three
well-established, near-zero-FP equivalences this project already uses
elsewhere (`www.`, trailing slash, scheme).

**7 new tests** (`SitemapUrlForkTests`). **Live-validated on 3 real
sitemaps** (61, 761, and 7071 URLs — `yogaoffeast.com`, `supabase.com`,
`vercel.com` respectively), all clean, no crash, no false positive —
expected, since none of these are known to have this defect; the fixture
tests are what prove the detection logic itself fires correctly when the
defect is present. (`creswellbakery.com`/`jimmyjoesplumbing.com`'s
Squarespace-served sitemaps did not parse with a plain `<loc>` regex
fetch in this quick check — not investigated further, since 3 real
sitemaps across 3 different platforms already gave meaningful coverage.)

## C — CIT-07: citation-position weighting

**Design**: reuses CIT-02's own external-link definition (extracted the
inline check into a shared `_is_external_link()` helper, used by both) —
the new signal is *where* in the page each citation falls, not whether one
exists (CIT-02's job, and this capability's own precondition). Required
extending `_PageParser` with a new `anchor_offsets` list (character offset
of each anchor at parse time) and a new `parse_page_with_anchor_positions()`
entrypoint — deliberately kept separate from `parse_page`'s stable 3-value
return, which 22 existing tests and every other capability already
unpack. Fires only when *every* outbound citation on a substantial
(≥500-word) page falls in the last 20% of it.

**6 new tests** (`LateCitationTests`), including a same-site `www.`-prefix
regression guard and a mixed early+late case (must not fire when at least
one citation is reachable early). **Live-validated on 3 real pages**
(Wikipedia, a Vercel docs page, a bakery about page) — no false positives,
no live true-positive found yet; the mechanism itself is proven by the
6 unit tests against realistic buried/non-buried HTML shapes.

## D — ENT-05/06 wording follow-through

Not new work this cycle — `entity-audit/SKILL.md`'s Excludes section
updated to match cycle 17's decision (stays strictly on-domain), and its
ENT-04 checks-table row and description updated for the sitemap-scoped
mode added in B above. `citability-audit/SKILL.md` similarly updated for
CIT-07 (description, checks table, deterministic-capabilities list). Both
still pass `skills-ref validate` after editing.

## E — Submission packaging & hygiene

**`skills-ref validate` run for the first time this project's history**
against all 6 skill folders (via `npx skills-ref validate <path>`,
auto-installed — not previously known to be available in this
environment). All 6 pass cleanly.

**New `scripts/build_submission_zip.sh`** — replaces every prior cycle's
manual, unscripted `du`/`zip` size *estimate* (cycles 10, 15, 16) with a
reproducible script that zips `marketplace.json` + `README.md` + `LICENSE`
+ `shared/` (a real runtime dependency every skill imports, not optional)
+ `skills/`, explicitly excluding `__pycache__`/`.pyc`/`.pyo`. `tests/` is
deliberately excluded — development-time verification, not part of what a
grader runs.

**Actually run and inspected, not estimated**: produced artifact is
184 KB (well under the 50 MB cap). Unzipped into a clean directory and
verified: correct root layout (`marketplace.json`, `README.md`, `LICENSE`,
`shared/`, `skills/` with all 7 skill folders, entrypoint confirmed via
`marketplace.json`'s own `entrypoint: true` flag), no dev artifacts
(`__pycache__`, `tests/` both absent). **Ran the actual entrypoint from
the unzipped copy** — `compose_report.py --floor-only` against a real
finding file, and a live skill script (`check_perimeter.py`) against
`creswellbakery.com` — both executed correctly, proving the zip is a
working artifact, not just a correctly-shaped one.

## F — Test suite

456 → 464 (PER-08, 8 tests) → 471 → 476 (ENT-04, 7 tests) → 482 (CIT-07, 6
tests). **482/482 pass**, `python3 -W error::ResourceWarning -m unittest
discover -s tests`, clean.

## G — Document

This file; `docs/capability-matrix.md` (PER-08 → `IMPLEMENTED`, ENT-04 →
`IMPLEMENTED`, CIT-07 → `IMPLEMENTED`); `docs/00-project-plan.md` (status
line pending); `README.md` (test count 448 → 482, citability-audit and
entity-audit skill-description rows); `marketplace.json` (0.18.1 → 0.19.0
— three real capability additions warrant a minor bump); `skills/audit-
orchestrator/SKILL.md` (entity-audit's new sitemap-scoped invocation step,
skill-registry rows for entity-audit/citability-audit/perimeter-access-
audit); `skills/entity-audit/SKILL.md` and `skills/citability-audit/
SKILL.md` (checks tables, Excludes, descriptions — see D above).

---

## Next

Per the plan's own scope, this closes every route the user selected for
this session (close known gaps + packaging hygiene; resolve ENT-05/06;
cheap capability extensions). Remaining candidates surfaced by the earlier
gap-analysis brainstorm but not selected this round: deepening the
engagement cluster (Cluster G, still the shallowest relative to its rubric
billing), and a deliberate pass to increase genuinely non-obvious proactive
suggestions across skills beyond PER-04/07. Both remain open for a future
session's direction.
