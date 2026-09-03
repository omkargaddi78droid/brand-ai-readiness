# Phase 4 (capability cycle 14 of N) — RET-02/03/05/06

Phase 4 output, fourteenth capability cycle. Extends `retrieval-readiness-
audit` with its fifth through eighth capabilities — all four agent-judged
— completing Cluster D (Retrieval readiness) at 8/8, the second fully
complete cluster after Cluster A (perimeter).

---

## A — Gap confirmation

RET-02, RET-03, RET-05 and RET-06 all still read `NOT_STARTED` in the
capability matrix as of the start of this cycle. `BUILD_REQUIRED`.

## B — Resource evaluation

stdlib only: `html.parser.HTMLParser`, `re`, `collections.Counter`. No new
dependency, no embedding model (explicitly prohibited by the matrix for
RET-02/03; extended to RET-05/06 by the same reasoning — none of the four
needs vector math, only extraction and judgement).

## C — Design

**Extends the existing skill.** Fifth through eighth capabilities in
`retrieval-readiness-audit`, completing Cluster D in the same skill that
shipped its deterministic half (RET-01/04/07/08, cycles 10-13).

**All four ship agent-judged, the `agent_judgement_required` pattern
proven six times already** (`content-quality-audit`'s CQ-01/02/04/09/12,
`engagement-audit`'s EN-01/03, `citability-audit`'s CIT-04, `entity-audit`'s
ENT-09). Each names a genuinely semantic question no structural pattern
match can safely answer:

- **RET-02** (dense/semantic coverage & synonym variation): whether a
  repeated phrase means the page's core topic is expressed only one way,
  or whether real variation exists elsewhere — "does a synonym exist
  anywhere" is not a fixed-vocabulary lookup a script can safely assert.
- **RET-03** (query-intent coverage): what the "obvious question forms" for
  an arbitrary brand's category even are — this needs the agent's own
  world knowledge of that category, which the script has no access to at
  all.
- **RET-05** (domain-specific terminology balance): whether language is
  genuinely imbalanced — a raw jargon-word ratio alone would flag any
  legitimately technical page that is in fact fine; the judgement is about
  whether plain-language framing surrounds the jargon, which needs reading.
- **RET-06** (chunk quality / atomic paragraphs): whether a long paragraph
  actually blends distinct ideas — length is a filter for candidacy, never
  the verdict; a long paragraph on one coherent idea is not a defect.

**Each extraction is deliberately partial, not a full-page dump.** A
dominant phrase, a stated topic, jargon-density stats, a flagged
paragraph — never the whole page. The agent is instructed to read the live
page before judging, not decide from the extraction alone (this project
does not bundle a full-page context into every judgement request; the
agent already has the page open from the fetch step).

**RET-06's 80-word/5-sentence candidate floor** mirrors RET-04's own
word-count floor in shape: below it, "long enough to plausibly blend
ideas" is not a meaningful filter.

**A new reference file**, `references/retrieval-judgement-rubric.md`, with
a "The question" / "When this capability does not apply" / "Calibration:
[positive] / [negative]" / "Writing the finding" structure per capability
— the same shape `citability-audit`'s and `engagement-audit`'s own rubric
files already use, for a reader already familiar with this project's
convention.

## D — Implement

`_ParagraphExtractor`/`extract_paragraphs()` (a fifth, separate single-
purpose parser — each `<p>` element's own text, needed because RET-06
judges paragraph-level chunk quality, which needs paragraph boundaries
preserved unlike every other extraction in this file), `_count_ngrams()`
(generalized out of RET-04's own inline n-gram loop, now shared by RET-02
and RET-04 rather than duplicated), `_split_sentences()` (reimplemented
locally, matching `content-quality-audit`'s/`citability-audit`'s own
copies), `find_semantic_coverage_candidates()` (RET-02),
`find_query_intent_candidates()` (RET-03),
`find_terminology_balance_candidates()` (RET-05),
`find_chunk_quality_candidates()` (RET-06), and
`build_agent_judgement_requests()` composing all four into the standard
`agent_judgement_required` shape. `CAPABILITY_IDS` extended to all eight
`RET-01`...`RET-08`. `audit_html()` and `_unknown_output()` extended to
carry `agent_judgement_required`, matching every other agent-judged skill's
output contract.

**A real bug found and fixed mid-cycle, not scoped-out**: see Review below
— this is significant enough to belong in Implement too, since it required
changing two already-shipped parsers (`_JsonLdTextParser`,
`_ProseTextExtractor`), not just this cycle's new code.

## E — Test

**31 new unit tests** (85 → 116 in `tests/test_retrieval_readiness.py`,
some renumbering from the block-boundary fix's own tests):
`BlockBoundaryTests` (the fix itself — adjacent block tags stay separate
words, inline tags are documented as not required to), `ExtractParagraphs
Tests`, `SemanticCoverageCandidateTests`, `QueryIntentCandidateTests`,
`TerminologyBalanceCandidateTests`, `ChunkQualityCandidateTests`,
`BuildAgentJudgementRequestsTests`. Three fixture-design mistakes caught
before trusting the suite, the same "check what the fixture actually
produces, not what you assumed it would" discipline this project has now
hit in three consecutive cycles (12, 13, and this one): a semantic-coverage
test fixture had a genuine tie between two competing 3-word phrases
(`"pricing model is"` vs `"model is simple"`, both count 3) and the test
assumed the wrong winner rather than checking the actual, correctly
deterministic tie-break; a chunk-quality test paragraph was 74 words,
6 short of the 80-word floor; both fixed by checking real output before
asserting expected output. **441 tests project-wide** (up from 416).

## F — Review

**A real, project-relevant bug found live, not in a fixture, affecting
already-shipped RET-01/04 too, not just this cycle's new work.** While
sanity-checking RET-02/05's extracted observations against real pages,
`gymshark.com`'s `visible_text` showed 438 run-together word artifacts
(`"...kPa..."`, `"...nGe..."`-shaped tokens). Root cause: `_JsonLdText
Parser` and `_ProseTextExtractor` (both shipped cycle 11) inserted no
separator into the text stream at block-level tag boundaries, so
`</h1><p>` produced one merged word instead of two whenever the source
HTML had no whitespace between adjacent tags — which real hand-written
test fixtures almost always have (indentation), but real, minified
production markup often does not. This had been present since cycle 11
(RET-01) and cycle 12 (RET-04) but neither surfaced it, because neither
capability's detection logic depends on clean word-level tokenization the
way RET-02's phrase-frequency counting and RET-05's word-length/acronym
ratios do — the corruption was there all along, just invisible to checks
that only needed substring containment or n-gram counting at 4+ words
(rarely spanning a corrupted boundary). Fixed by adding the same
`_BLOCK_TAGS` set and insertion mechanism `entity-audit`'s `_PageParser`
and `content-quality-audit`'s `_VisibleTextExtractor` already carry — not
a new invention, a known-correct pattern this skill had simply never
adopted. Confirmed fixed by direct comparison: this skill's residual
artifact rate on gymshark.com dropped to 45, the exact same number
`content-quality-audit`'s own already-shipped, already-trusted extractor
produces on the identical page — proof this brings the skill to parity
with the project's existing bar, not a new, unverified standard. The
remaining 45 are inline-tag (`<span>`/`<a>`/`<strong>`) artifacts, a
shared, accepted, project-wide limitation, not a regression.

**All 441 tests still passed after the fix** — the change only affects
whitespace/newline placement in extracted text, which every existing test
either doesn't depend on or already tolerates via `_tokenize_words`'
whitespace-insensitive tokenization.

**Live validation, real pages, no crashes.** `docs.python.org/3/library/
re.html`, `stripe.com/pricing`, `python.org/about/` — all four
`agent_judgement_required` entries produced sane, readable observations on
every page (verified directly, not assumed): Stripe's real FAQ headings
correctly populated RET-03's `existing_qa_headings`; RET-06 on Python's own
regex docs flagged 10 candidate paragraphs, and reading every one
confirmed all ten are genuinely long-but-atomic — a real-world match for
the rubric's own "long but atomic, no finding" calibration example, found
without having to construct it synthetically.

**Duplication check**: `_count_ngrams()` was extracted out of RET-04's
previously-inline n-gram loop specifically to avoid a second, near-
identical implementation for RET-02 — the one deliberate refactor this
cycle made to an already-shipped capability's code, kept behavior-
identical (RET-04's own 63 pre-existing tests all still passed unchanged).

## G — Document

This file; `SKILL.md` (description trimmed to fit the 1024-char frontmatter
cap after the first draft ran over, judgement-resolution Procedure steps,
checks table with a "Who decides" column, Excludes, output example with an
`agent_judgement_required` sample, failure modes), new
`references/retrieval-judgement-rubric.md` (all four capabilities'
calibration examples), `docs/capability-matrix.md` (RET-02/03/05/06 →
IMPLEMENTED, Cluster D detail paragraph, cycle count), `marketplace.json`
(0.17.0 → 0.18.0), `README.md` (skill description, test count, both
design-rules bullets naming agent-judged capabilities), entrypoint
`SKILL.md` (registry row, judgement-step note), `docs/00-project-plan.md`
(status line, §6, completion-notes list, standing-rules cycle count).

## H — Freeze

Frozen at eight capabilities. **`retrieval-readiness-audit` stands at 8 of
8 — Cluster D is complete**, the second fully-shipped cluster after
Cluster A (perimeter, 8/8). No dedicated measured corpus exists for any of
this skill's eight capabilities — a gap flagged and deferred across four
consecutive cycles (10-13) for the deterministic half, and structurally
inapplicable to the agent-judged half the same way it is for every other
agent-judged capability in this project (their calibration lives in
worked rubric examples, not a script-measured corpus).

---

## Next

Per the user's original explicit ordering (§6a): the orchestrator/
end-to-end-report validation pass, now that Cluster D's capability work is
complete. Full scope recorded in `docs/00-project-plan.md` §6a — real
multi-skill composed audits against unfamiliar sites, a non-expert read of
the composed report, measured real runtime against the 5-minute ceiling,
`tests/test_orchestrator.py`, and INF-08 (dedup) if cross-skill redundancy
is found.
