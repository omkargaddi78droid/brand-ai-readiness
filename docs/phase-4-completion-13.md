# Phase 4 (capability cycle 13 of N) — RET-07

Phase 4 output, thirteenth capability cycle. Extends `retrieval-readiness-
audit` (Cluster D) with its fourth capability, completing the cluster's
fully deterministic half. Direct continuation of the approved plan's
priority order: RET-08 (cycle 10), RET-01 (cycle 11), RET-04 (cycle 12),
RET-07 (this cycle), then the agent-judged RET-02/03/05/06.

---

## A — Gap confirmation

`RET-07` still reads `NOT_STARTED` in the capability matrix as of the start
of this cycle. `BUILD_REQUIRED`.

## B — Resource evaluation

stdlib only: `html.parser.HTMLParser`. No new dependency. Reuses
`extract_headings()` (RET-08) and `extract_json_ld_and_text()` (RET-01)
already built in this skill.

## C — Design

**Extends the existing skill.** Fourth capability in `retrieval-readiness-
audit`, same MECE boundary as RET-01/04/08.

**Narrowed to the fully structural half of the matrix's own wording.** The
matrix names three independently-sufficient aids ("Absent headings, Q&A
framing, or definition blocks that make chunks self-contained") whose
collective absence is the failure mode. Whether existing chunks are
*actually* self-contained once a heading is present — the text under
"Pricing" might still say "as mentioned above" and depend on earlier
context — is a semantic judgement this script does not attempt, the same
class of exclusion RET-02/03/05 already carry in this cluster. What ships:
does a substantial page (≥300 words of visible text) have *none* of the
three named aids at all. Any single one present is enough to stay silent —
a page built entirely around FAQ/definition-list structure with no
traditional headings is well-structured, not a defect, so the check must
never require headings specifically, only require at least one of the
three.

**Detection design for each of the three aids:**
- Headings: `len(extract_headings(html)) > 0` — already-built.
- Q&A framing: any heading text ending in `?`, or a JSON-LD node whose
  `@type` includes `FAQPage`/`QAPage` — reuses `extract_headings()` and
  `extract_json_ld_and_text()`'s nodes, no new full-page parse for this
  half.
- Definition block: a new, minimal `_DefinitionBlockDetector` — does the
  page contain at least one `<dt>` and at least one `<dd>` anywhere,
  deliberately not required to pair up within the same `<dl>` (real pages
  nest inconsistently; presence anywhere is the load-bearing signal).

**300-word floor**, same shape and same rationale as RET-04's 80-word
floor: a short page (a contact page, a single-product landing page)
legitimately has no headings without that being a defect — there isn't
enough content for a document outline to matter yet.

## D — Implement

`_DefinitionBlockDetector`/`has_definition_block()`, `has_qa_heading_
framing()`, `has_qa_schema()`, `find_missing_retrieval_structure()`
(RET-07's Finding). Wired into `audit_html()` alongside RET-01/04/08's
existing checks. `CAPABILITY_IDS` extended to `["RET-01", "RET-04",
"RET-07", "RET-08"]`.

**A real bug caught mid-cycle, before formal tests were even written**: the
first draft passed `extract_prose_text()`'s word count (RET-04's own
structured-region-excluded corpus) into `find_missing_retrieval_structure`.
Manual smoke-testing against a synthetic table-heavy fixture produced 0
prose words for a page that genuinely had substantial content, because the
entire body happened to sit inside a `<table>`. Root-caused before writing
a single formal test: RET-04's exclusion is correct for *that*
capability's own FP guard, but RET-07 has no reason to inherit it — a page
laid out in tables for purely visual reasons (common in older HTML) still
has real, substantial, chunkable content. Fixed by switching RET-07 to
`extract_json_ld_and_text()`'s full visible-text corpus (RET-01's, which
excludes only script/style/code) before writing any tests against the
final design.

## E — Test

**22 new unit tests** (63 → 85 in `tests/test_retrieval_readiness.py`):
`DefinitionBlockTests` (dt/dd pairing not required, either tag alone is
insufficient), `QaFramingTests` (heading-`?` detection, `FAQPage`/`QAPage`
schema detection), `MissingRetrievalStructureTests` (no-structure fires;
any one of the three aids present stays silent, tested independently for
each; the word-count floor; determinism; two `audit_html`-level end-to-end
cases), plus one new `ContractComplianceTests` case. A 300+-word,
genuinely-varied prose fixture (`_LONG_VARIED_PROSE`, 23 distinct sentences,
no repeated 4-word phrase) was purpose-built so RET-07's own tests never
accidentally trip RET-04 — the same "filler must be varied, not repeated"
lesson cycle 12 already learned, applied proactively here rather than
re-discovered by a failing test. **416 tests project-wide** (up from 394).

No dedicated measured corpus/`measure_retrieval_readiness.py` script this
cycle either — the same deferred gap as RET-08/RET-01/RET-04, now four
capabilities deep. Flagged again; Cluster D's deterministic half is now
complete, which makes this the natural point for a future cycle to close
the gap before adding the agent-judged capabilities.

## F — Review

**Zero code bugs in the final design** — the one real bug (the shared
word-count corpus) was caught and fixed before formal tests existed, not
after.

**Live validation, five real pages, two genuine positives.**
`paulgraham.com/simply.html` and `/read.html` (headingless, table-laid-out
essay pages — fire, confirming the corpus-sharing bug fix actually works
on the real page shape it was fixed for), `en.wikipedia.org/wiki/
Glossary_of_chess` and `docs.python.org/3/library/re.html` (both well-
headed, stay silent as expected). **`python.org/about/` produced an
unplanned second genuine positive**: 1445 words of visible text with zero
`<h1>`-`<h6>` tags anywhere in the raw markup — independently confirmed
outside this skill's own code with a plain `grep -oE "<h[1-6][ >]"
/tmp/pyabout.html`, which returned nothing. python.org's own About page
uses styled `<div>` elements for its visual section titles rather than
real heading markup — exactly the retrieval-structure gap this capability
exists to name, found on a site this project has treated as a model of
good markup in every prior cycle's live validation (`docs.python.org`, PEP
pages). Zero crashes, zero false positives.

**Duplication check:** none. `_DefinitionBlockDetector` is new and narrow;
`find_missing_retrieval_structure` composes existing extraction
(`extract_headings`, `extract_json_ld_and_text`'s nodes) rather than
duplicating any of it.

## G — Document

This file; `SKILL.md` (description, checks table, Excludes, output
example, failure modes), `references/retrieval-readiness-checks.md` (new
RET-07 section including the corpus-sharing bug and both live positives),
`docs/capability-matrix.md` (RET-07 → IMPLEMENTED, Cluster D detail
paragraph updated), `marketplace.json` (0.16.0 → 0.17.0), `README.md`
(skill description, test count), entrypoint `SKILL.md` (registry row),
`docs/00-project-plan.md` (status line, §6, completion-notes list,
standing-rules cycle count).

## H — Freeze

Frozen at four capabilities. `retrieval-readiness-audit` stands at 4 of 8
in Cluster D — its entire deterministic half now shipped. RET-02, RET-03,
RET-05, RET-06 remain, all agent-judged: no bundled embedding model
allowed (explicit in the matrix for RET-02/03); RET-06 is a third
`— (was seoscoreapi)` capability, the same reimplement-locally-via-rubric
disposition as CQ-01/CQ-11 in cycle 8.

---

## Next

Continue Cluster D with the agent-judged RET-02/03/05/06 (extraction-only +
`references/` rubric pattern, proven six times already in this project), or
move to the orchestrator/end-to-end-report validation pass now that
Cluster D's deterministic capabilities are complete — full scope for that
pass recorded in `docs/00-project-plan.md` §6a.
