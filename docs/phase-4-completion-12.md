# Phase 4 (capability cycle 12 of N) — RET-04

Phase 4 output, twelfth capability cycle. Extends `retrieval-readiness-audit`
(Cluster D) with its third capability. Direct continuation of the approved
plan's priority order: RET-08 (cycle 10), RET-01 (cycle 11), RET-04 (this
cycle), then RET-07, then the agent-judged RET-02/03/05/06.

---

## A — Gap confirmation

`RET-04` still reads `NOT_STARTED` in the capability matrix as of the start
of this cycle, with `advertools` named as its resource and an explicit
false-positive risk note attached ("fires on legitimately repetitive pages
— spec tables, glossaries; exclude structured regions before counting").
`BUILD_REQUIRED`.

## B — Resource evaluation

stdlib only: `html.parser.HTMLParser`, `re`, `collections.Counter`. No new
dependency — `advertools` rejected per this project's now-standard
disposition toward matrix-named third-party resources.

## C — Design

**Extends the existing skill.** Third capability in `retrieval-readiness-
audit`, same MECE boundary as RET-01/08.

**The FP-risk note designed in from the start, not discovered live.** Unlike
several earlier cycles where a false-positive guard was written first and
only later tested against a fixture built to break it (CQ-11's Flesch-
threshold claim, disproven in cycle 8), RET-04's own capability-matrix entry
already names the exact risk and the exact fix: spec tables and glossaries
repeat structurally, so structured regions must be excluded before counting
starts. This cycle takes that literally as the design: a new extraction
pass, `extract_prose_text()`, excludes `<table>`, `<dl>` (the standard
glossary/definition-list element), `<ul>`, `<ol>` and `<select>` content
before any n-gram is ever counted — the exclusion is structural, not a
post-hoc filter on already-counted matches.

**N-gram shape and thresholds, chosen and justified up front.** A 4-word
window (long enough that exact repetition stops looking like normal topical
focus), a minimum of 5 occurrences, a minimum density of 8% of prose words
(`occurrences × 4 ÷ total_prose_words`), both required together (density
alone would flag a short but genuinely on-topic phrase; count alone would
flag long pages that simply discuss a real topic often), n-grams composed
entirely of stopwords excluded (grammatical filler repeats constantly and
carries no topical signal), and a minimum 80-word prose floor below which
the check stays silent regardless (density is not a stable statistic on a
very short page). Each threshold's rationale is recorded in
`references/retrieval-readiness-checks.md` rather than left as a bare
constant.

**Dependency decision, reaffirmed not re-litigated.** `advertools` rejected
for the same reason recorded for `bm25s`/RET-01 in cycles 10–11:
`test_scripts_import_no_third_party_packages` holds project-wide with zero
exceptions across eleven prior cycles, and this capability is a
straightforward n-gram frequency count needing no scraping/analytics
library at all.

## D — Implement

`_ProseTextExtractor`/`extract_prose_text()` (visible text with structured
regions excluded — a third, separate single-purpose parser alongside
`_HeadingExtractor` and `_JsonLdTextParser`, same "one parser per concern"
discipline), `_tokenize_words()`, `find_keyword_stuffing()` (RET-04's
Finding, aggregated across every phrase over threshold into one finding,
sorted by occurrence count for a stable, deterministic order). Wired into
`audit_html()` alongside RET-01/RET-08's existing checks. `CAPABILITY_IDS`
extended to `["RET-01", "RET-04", "RET-08"]`.

## E — Test

**17 new unit tests** (46 → 63 in `tests/test_retrieval_readiness.py`):
`ExtractProseTextTests` (table/list/dl/select exclusion, nested-structured-
region handling, script/style still excluded), `KeywordStuffingTests`
(stuffed-prose fires, varied natural prose stays silent, the minimum-word
floor, stopword-only grams never counting, below-minimum-occurrence stays
silent, determinism), `KeywordStuffingStructuredRegionExclusionTests`
(a phrase repeated only inside a spec table stays silent; the same page
still fires when the repetition is in real prose alongside the table), plus
one new `ContractComplianceTests` case. **394 tests project-wide** (up from
377).

Two fixture-design mistakes were caught and fixed before the suite was
trusted, worth recording since they're a real instance of this project's
own "fixtures are not enough" discipline catching itself: an early "clean"
table fixture used `' '.join(['ordinary prose text here'] * 30)` as filler
outside the table — that repeated 4-word phrase was itself stuffing,
independent of the table exclusion being tested, and it fired for the wrong
reason. Caught by checking `extract_prose_text()`'s actual output before
trusting the finding, not by the test passing. Fixed by using genuinely
varied filler sentences (`KeywordStuffingTests._VARIED_PROSE`) everywhere a
"should stay silent" fixture needed padding, not a repeated string.

No dedicated measured corpus/`measure_retrieval_readiness.py` script this
cycle either — the same deferred gap as RET-08 and RET-01, now three
capabilities deep without one. Flagged again rather than silently repeated
a third time without comment; a future cycle building this skill's fourth
capability should close it.

## F — Review

**Zero code bugs** — both fixture-design mistakes above were caught before
the formal suite, not after, and both were fixtures, not production logic.

**Live validation, seven real pages, deliberately including the exact
risk case the matrix warned about.** `docs.python.org/3/library/re.html`
(dense, naturally repetitive regex terminology), `en.wikipedia.org/wiki/
Glossary_of_chess` (a literal glossary page, `<dl>`-heavy — as close to a
purpose-built adversarial case as a real page gets), `peps.python.org/
pep-0008/` (repeated code syntax), lego.com's and gymshark.com's product
pages, and two finance pages (nerdwallet.com — clean; investopedia.com —
404'd, harmlessly reported `unknown`, not a crash). **Zero crashes, zero
false positives** across all seven, including both pages chosen
specifically because they were expected to be the hardest test of the
structured-region exclusion.

**No live true positive was found.** Consistent with, not contrary to, the
mechanism this capability describes: reputable, well-indexed sites
generally avoid keyword stuffing precisely because search/AI ranking
already penalizes it. The detection path's correctness for a genuinely
stuffed page rests on the synthetic fixture pair
(`test_a_repeated_phrase_at_high_density_fires` and its structured-region-
exclusion counterpart) rather than a live confirmation — stated here
plainly, the same disposition `docs/phase-4-completion-11.md` took for
RET-01's own missing live "survives" case.

**Duplication check:** none. `_ProseTextExtractor` is a new, narrowly-scoped
parser; `find_keyword_stuffing` has no existing analog elsewhere in this
project.

## G — Document

This file; `SKILL.md` (description, checks table, Excludes, output example,
failure modes), `references/retrieval-readiness-checks.md` (new RET-04
section with full threshold rationale and live-validation detail),
`docs/capability-matrix.md` (RET-04 → IMPLEMENTED, Cluster D detail
paragraph updated), `marketplace.json` (0.15.0 → 0.16.0), `README.md`
(skill description, test count), entrypoint `SKILL.md` (registry row),
`docs/00-project-plan.md` (status line, §6, completion-notes list,
standing-rules cycle count).

## H — Freeze

Frozen at three capabilities. `retrieval-readiness-audit` stands at 3 of 8
in Cluster D. Per the approved plan's priority order: RET-07 (retrieval-
oriented structure) is next, then the agent-judged RET-02/03/05/06.

---

## Next

Continue Cluster D (RET-07 next), or move to the orchestrator/end-to-end-
report validation pass once Cluster D's deterministic capabilities are
reasonably progressed — full scope for that pass recorded in
`docs/00-project-plan.md` §6a.
