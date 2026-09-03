# Phase 4 (capability cycle 11 of N) — RET-01

Phase 4 output, eleventh capability cycle. Extends `retrieval-readiness-audit`
(Cluster D, shipped cycle 10) with its second capability. Direct continuation
of cycle 10's Gate H "Next" note and the user's explicit ordering choice:
Cluster D capability work first, orchestrator validation pass second.

---

## A — Gap confirmation

`RET-01` still reads `NOT_STARTED` in the capability matrix as of the start
of this cycle, with `bm25s`/`rank_bm25` named as its resource. `BUILD_REQUIRED`.

## B — Resource evaluation

stdlib only: `html.parser.HTMLParser`, `json`, `re`. No new dependency —
`bm25s`/`rank_bm25` rejected per cycle 10's dependency decision, reaffirmed
here rather than re-litigated (see Design).

## C — Design

**Extends the existing skill, not a new one.** `retrieval-readiness-audit`'s
own MECE boundary (page structure/text serving retrieval, distinct from
content-quality's anti-patterns or entity-audit's identity checks) already
covers RET-01 — it is the same skill's second capability, not a new concern.

**Narrowed scope, the load-bearing design decision this cycle.** The
capability matrix's "Detects" column for RET-01 names product SKUs, model
numbers, statute names, and technical terms broadly. Re-reading it for the
actual failure mode shows a binary presence/absence check, not a relevance
score — real BM25 ranking math is not what this capability's stated defect
needs. Built: does a JSON-LD `Product.sku`/`mpn`/`gtin*` value survive into
the page's extracted visible text. Not built, deliberately: "model numbers
in `<title>`" and "statute names in prose," both of which need a free-text
pattern heuristic (what does a model number or statute citation *look like*
in ordinary text) with real false-positive risk this project's discipline
says should not ship without a fixture built specifically to break it first
— the same bar CQ-11's Flesch-threshold claim failed to clear in cycle 8.
Deferred to a future cycle, tracked in `SKILL.md`'s Excludes and the
reference doc, not silently dropped.

**Dependency decision, reaffirmed not re-litigated.** `bm25s`/`rank_bm25`
rejected as an actual dependency for the same reason recorded in cycle 10:
`test_scripts_import_no_third_party_packages` holds project-wide with zero
exceptions across ten prior cycles, and RET-01 as scoped above needs no
ranking math at all — a straightforward presence/absence check.

**Extraction reused, not imported.** JSON-LD-block collection and lightly-
scoped visible-text extraction mirror `entity-audit`'s `_PageParser`
(script/style/code/pre excluded, `handle_startendtag` delegates to
`handle_starttag`/`handle_endtag` per this project's standing rule),
reimplemented locally as `_JsonLdTextParser`/`extract_json_ld_and_text()`
rather than imported, per this project's independently-runnable-skill
convention. Kept as a second, separate parser from `_HeadingExtractor`
rather than merged into one class — same "don't grow one parser's blast
radius to cover an unrelated concern" reasoning `content-quality-audit`
used to keep its H1 pass separate from its own visible-text pass.

## D — Implement

`_JsonLdTextParser`/`extract_json_ld_and_text()` (JSON-LD nodes + visible
text), `_flatten_json_ld()` (`@graph` unwrapping, same logic as
entity-audit's copy), `extract_technical_tokens()` (Product-typed nodes'
`sku`/`mpn`/`gtin*` fields, deduplicated), `_token_survives()`
(word-boundary-guarded, case-insensitive substring match — a token can never
be satisfied by being a substring of a longer alphanumeric run),
`find_token_survival_gaps()` (RET-01's Finding, aggregated across all
missing tokens on the page into one finding). Wired into `audit_html()`
alongside RET-08's existing checks. `CAPABILITY_IDS` extended to
`["RET-01", "RET-08"]`.

## E — Test

**21 new unit tests** (25 → 46 in `tests/test_retrieval_readiness.py`):
`ExtractJsonLdAndTextTests` (JSON-LD/text separation, `@graph` flattening,
malformed-JSON-LD silent skip, script/style exclusion), `ExtractTechnical
TokensTests` (Product-type scoping, multi-field extraction, dedup, non-
string/empty-value guards), `TokenSurvivalTests` (survives/missing fixture
pair, case-insensitivity, the substring-boundary guard specifically —
`"WID-123"` inside `"WID-1234"` must not count as surviving), plus two new
`ContractComplianceTests` cases. **377 tests project-wide** (up from 356).

No dedicated measured corpus/`measure_retrieval_readiness.py` script this
cycle either — the same gap cycle 10 flagged and deferred for RET-08, now
also true of RET-01. Still deferred for the same reason: keep this cycle's
scope to capability coverage, not a full measurement-harness build. A future
cycle building out `retrieval-readiness-audit`'s third capability should
add one rather than let the gap compound a third time.

## F — Review

**Zero bugs.** The detection logic worked correctly on first write, verified
against a synthetic fixture pair (`sku` present in text vs. present only in
an `<img alt>` or JSON-LD block) before the formal test suite was even
written.

**Live validation, real product pages, with independent verification.**
Most e-commerce sites bot-block plain fetches (Newegg, Best Buy, Target,
H&M, Home Depot, Uniqlo, Wayfair, Chewy, Moosejaw — all returned 403/429/
empty). lego.com's product pages (`millennium-falcon-75192`, `orchid-10311`)
returned 200 with valid `Product` JSON-LD and both fired
`RET-01-token-not-in-text`. Checked independently, outside this skill's own
code: fetched the same page with a fresh `curl`, stripped `<script>`/
`<style>` blocks with a separate regex pass, and confirmed the JSON-LD `sku`
value (`"6175771"`) appears 65 times in the raw HTML but zero times outside
script/style — genuinely never in visible text — while the LEGO set number
shown in the URL and product name (`"75192"`) appears 959 times in real
text. LEGO's structured data and its customer-facing text use two different
identifiers for the same product, and only the customer-facing one is
retrievable by exact match — exactly the defect this capability exists to
catch, on a real production page, not a constructed example.

**Gap, stated rather than hidden:** no live "survives" (silent) case was
found — every real, fetchable product page tested this cycle happened to
exhibit the gap. The silent path's correctness rests on the synthetic
fixture pair rather than a live confirmation. Noted in
`references/retrieval-readiness-checks.md` rather than left implicit.

**Duplication check:** none. `_JsonLdTextParser` is a new, narrowly-scoped
parser; `extract_technical_tokens`/`find_token_survival_gaps` have no
existing analog elsewhere in this project.

## G — Document

This file; `SKILL.md` (description, capability table, Excludes, output
example, failure modes), `references/retrieval-readiness-checks.md` (new
RET-01 section with the narrowing rationale and live-validation detail),
`docs/capability-matrix.md` (RET-01 → IMPLEMENTED, Cluster D detail
paragraph and Tests note updated), `marketplace.json` (0.14.0 → 0.15.0),
`README.md` (skill description, test count), entrypoint `SKILL.md`
(registry row), `docs/00-project-plan.md` (status line, §6, completion-notes
list, standing-rules cycle count).

## H — Freeze

Frozen at two capabilities. `retrieval-readiness-audit` stands at 2 of 8 in
Cluster D. Per the approved plan's priority order: RET-04 (keyword
stuffing) is next — needs a real spec-table/glossary false-positive fixture
designed in from the start, per the matrix's own explicit FP-risk note —
then RET-07 (retrieval-oriented structure), then the agent-judged
RET-02/03/05/06.

---

## Next

Continue Cluster D (RET-04 next), or move to the orchestrator/end-to-end-
report validation pass once Cluster D's deterministic capabilities are
reasonably progressed — full scope for that pass recorded in
`docs/00-project-plan.md` §6a.
