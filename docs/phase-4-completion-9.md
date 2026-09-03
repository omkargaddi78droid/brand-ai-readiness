# Phase 4 (capability cycle 9 of N) — ENT-09

Phase 4 output, ninth capability cycle. No new skill — extends
`entity-audit` with its first agent-judged capability: taxonomy
consistency (a declared category/breadcrumb contradicting the page's own
body text).

---

## A — Gap confirmation

Not baseline-covered: no resource in the capability matrix
(`entity-checks.md`'s scope-narrowing note and the matrix both list ENT-09
as `NOT_STARTED`, no baseline equivalent). `BUILD_REQUIRED`, resolved by
building — but first, a documentation error had to be caught and corrected:
`entity-audit`'s own `SKILL.md` and `scripts/check_entity.py` module
docstring both grouped ENT-09 with ENT-07 (cross-domain attribution) and
ENT-08 (NAP consistency) as needing "off-site reasoning or cross-page
comparison," and `docs/00-project-plan.md`'s "Immediate next step" section
repeated across cycles 6, 7 and 8 that `ENT-05/06` was blocked on an
unresolved off-site scope decision without separately naming ENT-09 as an
available alternative. The capability matrix's own wording for ENT-09 —
"a page's assigned category tag contradicting **its own body text**" — is
unambiguously same-page: no crawl, no off-site lookup, nothing this
project's single-page model doesn't already do for every other gate-3
check. This was a documentation bug carried across three completion notes,
not a real blocker — caught by re-reading the capability matrix's exact
wording against the SKILL.md's exclusion list before starting Gate A,
rather than trusting the prior cycles' framing.

## B — Resource evaluation

stdlib only: `re`, reusing the existing `_PageParser`/`parse_page` JSON-LD
and visible-text extraction already built for ENT-01–04. No new
dependency, no new HTML parser pass.

## C — Design

**ENT-09 is agent-judged — the first agent-judged capability in
`entity-audit`.** Every other capability in this skill compares two
structured or pattern-matched values where agreement is unambiguous once
extracted (a rating number, a set of hrefs). "Does this category relate to
this text" is not: a category of "Laptops" and body text saying only
"notebook computers" share zero keywords and yet agree completely. Per this
project's Phase 0.1(c) stance (the host agent is the LLM; semantic
judgement belongs in `SKILL.md` procedure text and rubrics), the script
extracts a declared category label plus a text excerpt only, into
`agent_judgement_required`, and asserts no verdict — the same
extraction-only pattern this project has now proven four times
(`content-quality-audit` cycles 4/5/7, `engagement-audit`/`citability-
audit` cycles 4/5).

**Three extraction sources, deduplicated:** `Product.category` and
`articleSection` read directly off any JSON-LD node; a `BreadcrumbList`
walked to its deepest `position` entry, handling both real-world shapes for
`item` (a bare URL string, or a nested object carrying its own `name`).

**The false-positive guard is the zero-overlap threshold itself, not a
second filter bolted on.** Only a label sharing *no* keyword at all with
the page's visible text becomes a candidate — any shared keyword is treated
as agreement and never reaches the agent. This is deliberately the
strictest possible threshold: a partial-overlap case is far more likely to
be a legitimate related term than a real mismatch, so the candidate set is
kept to the cases with no lexical basis for agreement at all. Two further
guards, both reused from established precedent rather than invented fresh:
a 50-word minimum on visible text (CQ-11's "short sample is noise"
principle, cycle 8) and an explicit generic-label exclusion list ("Home",
"Blog", "General" — the same category of guard as CQ-07's single-word-label
exclusion).

## D — Implement

`_keywords` (reimplemented from `content-quality-audit`'s CQ-08, per this
skill's "independently runnable" convention), `_breadcrumb_labels`,
`extract_category_labels`, `find_taxonomy_judgement_candidates`,
`build_agent_judgement_requests` (new to this skill), `audit_html`/
`_unknown_output` extended to carry `agent_judgement_required`.
`CAPABILITY_IDS` extended from 4 to 5.

## E — Test

**15 new unit tests** + the existing 40-test suite for ENT-01–04, unaffected
except where the output-shape change (`agent_judgement_required` added)
required no changes at all — the same pattern proven safe in
`content-quality-audit` cycles 4–5 and 7. **331 tests project-wide** (up
from 316). No dedicated measured corpus for ENT-09: agent-judged
capabilities have no script verdict to measure this way, consistent with
`engagement-audit`'s EN-01/EN-03, `citability-audit`'s CIT-04, and
`content-quality-audit`'s CQ-01/02/04/09/12.

## F — Review

**Zero bugs this cycle** — the first cycle since Phase 3 with neither a
fixture-sweep catch nor a live-validation catch in the detection logic
itself. The one real correction this cycle made was the documentation error
described in Gate A (ENT-09 wrongly grouped with ENT-07/08 across three
prior completion notes), not a code defect.

**Field validation, five live pages** (python.org, docs.python.org,
en.wikipedia.org, apple.com/contact, peps.python.org) plus two site
homepages checked for markup shape (bbc.com/news, theguardian.com): zero
crashes, zero `unknown_checks`, zero ENT-09 candidates — every one of these
pages carries no `Product.category`/`articleSection`/`BreadcrumbList`
signal at all (homepages and reference documentation pages are not
categorized content), so ENT-09 correctly stayed silent rather than forcing
a check on a page it has nothing to check. This is a genuine negative-path
live validation, not a skipped one: it confirms the "nothing to check"
branch behaves correctly on real markup, including sites this project has
already exercised other capabilities against. A sixth site
(gnu.org) and a seventh (polygon.com) were unreachable in this session's
network sandbox — noted, not treated as a passing result.

**No live positive hit this session** — the sampled pages happen not to
carry category/breadcrumb JSON-LD. Same disposition already established and
accepted for capabilities without one (PER-03 cycle 1; part of the CQ
cluster cycle 2; CQ-01/CQ-11's positive paths cycle 8): the positive path is
proven by unit-test fixtures built from real-world schema.org shapes
(`Product.category` as used by e-commerce sites, `articleSection` as used
by news `NewsArticle`/`BlogPosting` markup, `BreadcrumbList` with both the
bare-URL and nested-object `item` forms actual sites use), not asserted
untested.

**Duplication check:** `_keywords` is a second, independent copy of
`content-quality-audit`'s CQ-08 implementation — reimplemented per
`skill-engineering-principles.md` §5.3 and this skill's own existing
`_PageParser` docstring precedent (already reimplements
`content-quality-audit`'s text-extraction pattern for the same stated
reason), not imported. No other duplication found.

## G — Document

This file; `SKILL.md`, `references/entity-checks.md` (new ENT-09 section),
`references/entity-judgement-rubric.md` (new), README, `marketplace.json`
(0.12.0 → 0.13.0), `docs/capability-matrix.md` (ENT-09 → IMPLEMENTED,
Cluster C detail paragraph corrected), entrypoint `SKILL.md` (registry +
procedure note), `docs/00-project-plan.md`.

## H — Freeze

Frozen at one capability, six worked calibration examples in the rubric
(three warranting a finding, three not). `entity-audit` now stands at 5 of
9 in-scope capabilities (ENT-05/06/07/08 remain — ENT-05/06 still blocked
on the off-site scope decision, unresolved across nine cycles now; ENT-07/08
genuinely need off-site reasoning or multi-page comparison this project
does not build).

---

## Next

With ENT-09 done, the "single-page, on-domain, no-render" seam this project
has mined for nine cycles is close to exhausted: `docs/capability-matrix.md`
shows the remaining `NOT_STARTED`/`PARTIALLY_COVERED` capabilities are now
overwhelmingly `REN-*` (needs a headless browser, unavailable in this
environment), off-site (`ENT-05/06`, `CIT-13`, still-unresolved scope
decision), or multi-page (`CQ-06/CQ-10`, `ENT-04`'s crawl-wide half,
`ENT-07/08`, most of the remaining `EN-*`/`CIT-*` capabilities). The
concrete unblocked options left are narrow: `ENT-04`'s crawl-wide half if a
sitemap-fetch is judged in-scope for a single skill invocation, or
resolving the ENT-05/06 off-site scope decision itself (a real product
choice, not an engineering one — flagged for the user, not decided here).
Otherwise, Phase 4's single-page-no-render backlog is effectively done, and
continuing further means either Phase N-2 (skill decomposition) and N-1
(orchestrator hardening) work, or a scope decision on rendering/off-site
lookups that only the user can make.
