# Phase 4 (cycle 17) — CIT-06/RET-05 fixes + ENT-05/06 scope closure

Fixes two generalization gaps corroborated twice across four real sites in
the orchestrator validation pass (`docs/phase-4-completion-15.md`, `-16.md`)
and closes a scope decision left open since cycle 9. Not a new-capability
cycle in the usual sense — no row moves from `NOT_STARTED` to `IMPLEMENTED`
except by the ENT-05/06 closure below, which is a decision, not a build.

---

## A — CIT-06 (`citability-audit`): exclude quoted customer testimonials

**Bug**: `find_unverifiable_superlatives` treated a customer's own quoted
opinion the same as the brand's marketing copy — "The BEST bacon I have
ever had" (creswellbakery.com) and "Many are considered to be the best of
their kind" (carpenterlourie.com, a *middle* sentence of a longer quoted
testimonial with no quote marks of its own) both fired, each producing the
nonsensical suggested action "cite a sourced number" for someone's personal
opinion.

**Fix**: a new `_quoted_spans()` helper finds quote-mark-delimited spans
(straight `"..."` or curly `"..."`, 20-3000 chars — generous enough for a
real ~1000-word testimonial seen live) across the *whole page text first*,
then excludes any superlative-matching sentence that is a substring of one
of those spans. This handles both the single-sentence-quote case and the
multi-sentence case in one mechanism — a middle sentence with no quote
marks of its own is still inside the span its paragraph's opening/closing
quote marks define. Deliberately excludes single quotes/apostrophes from
the pattern (too collision-prone with contractions/possessives).

**4 new tests** in `tests/test_citability_audit.py`
(`UnverifiableSuperlativeTests`): a single quoted testimonial, a middle
sentence of a multi-sentence quote, a straight-quoted testimonial, and a
brand-authored superlative that still fires correctly alongside an
excluded quoted one (false-positive control).

**Live re-validation**, the exact two pages that exposed the bug:

| Page | Before | After |
|---|---|---|
| `creswellbakery.com/about-us` | 1 finding, 3 sentences (1 brand, 2 testimonial) | 1 finding, 1 sentence (brand only) |
| `carpenterlourie.com/testimonials/` | 1 finding, 2 sentences (1 brand, 1 testimonial) | 1 finding, 1 sentence (brand only) |

Both pages now report only the genuine brand-authored superlative; the
testimonial quotes are correctly suppressed.

## B — RET-05 (`retrieval-readiness-audit`): signal quality on chrome-heavy pages

**Two distinct root causes**, both found via mandatory live re-validation
against the real sites that first surfaced the bug — the second was not
anticipated going in and was found specifically *because* the fix was
checked against real data rather than trusted from the fixture alone.

**B1 — verbatim-repeated nav blocks** (the originally diagnosed cause):
small templated sites repeat an entire nav/menu block 2-3 times (desktop
state, expanded state, mobile "Folder:" state), each its own
block-boundary-newline-split entry in `_split_sentences`'s output. Fix:
de-duplicate exact-repeat entries before computing `acronym_count`/
`long_word_ratio`, and prefer sentences ≥8 words for `sample_sentences`
over the previous pure opening/middle/closing positional pick.

**B2 — distinct short all-caps headings** (found live, not anticipated):
`creswellbakery.com/menu`'s `acronym_count: 39` barely moved after B1's
fix (still 39) because its short-caps fragments are *not* duplicates —
each menu item ("CHIPOTLE HAM BRIOCHE SANDWICH", "CIABATTA BACON SANDWICH")
is distinct text contributing new short-caps words ("HAM", "BACON") the
acronym pattern can't tell from a real acronym. Fix: a
`_is_shouted_chrome_sentence()` guard excludes a sentence's acronym
contribution when the *entire* sentence (≤6 words) is uppercase — a shape
real acronym usage never takes (the rubric's own calibration example,
"The API leverages OAuth2 PKCE flows...", is 15+ words of ordinary
mixed-case prose with isolated acronyms in it, not an all-caps sentence).

**4 more new tests** (`TerminologyBalanceCandidateTests`): the verbatim-
repeat case, the distinct-short-headings case, a real-acronym-in-ordinary-
prose regression guard (the rubric's own calibration sentence), and the
sample-sentence-preference case. One earlier-cycle test's exact expected
count was updated from `2` to `0` once B2 shipped — a correct behaviour
refinement (`BOOK A CLASS` was never a real acronym at either count),
not a regression.

**Live re-validation**, all pages that exposed either shape of the bug:

| Page | `acronym_count` before | after |
|---|---|---|
| `yogaoffeast.com/` | 14 | 2 |
| `yogaoffeast.com/the-studio` | 14 | 7 |
| `yogaoffeast.com/weeklyclasssched` | 9 | 2 |
| `creswellbakery.com/menu` | 39 | 1 |
| `creswellbakery.com/` | 6 | 1 |
| `creswellbakery.com/about-us` | 13 | 2 |

`sample_sentences` on every page above now returns real, substantive
prose — no more `"Copyright ©"`, `"Back"`, or bare price fragments.

## C — ENT-05/06: scope decision resolved, both `DEFERRED`

Open since cycle 9 (`docs/capability-matrix.md`'s own Detail note: "scope
decision required in Phase 4, still open as of cycle 9"). Two off-site
paths were weighed and both rejected:

1. A bundled script calling an external search API — rejected: conflicts
   with this project's "self-contained, no external service" and
   "portable" design rules (`README.md`).
2. An agent-executed search per page, extending the existing
   `agent_judgement_required` pattern one step further (the agent itself
   runs one bounded lookup, judged against a strict rubric) — considered
   as a genuine third option, explicitly declined: not worth the added
   runtime and complexity for two capabilities whose FP risk is already
   judged "very high" in the matrix's own words (a wrong impersonation
   accusation is a serious false positive no corroborating signal fully
   neutralises without a search this project has now decided not to
   perform).

**Decision: stay strictly on-domain.** `ENT-05` and `ENT-06` move from
`NOT_STARTED` to `DEFERRED` in `docs/capability-matrix.md`, alongside
`ENT-10`/`CIT-11` (needs a capability this project's architecture doesn't
have) — closing a 14-cycle-old open question as a decision, not silence.

No code changes for this route.

## D — Test suite

441 → 452 (route A, 4 tests) → 456 (route B, 4 tests). **456/456 pass**,
`python3 -W error::ResourceWarning -m unittest discover -s tests`, clean.

## E — Document

This file; `docs/capability-matrix.md` (ENT-05/06 rows, Detail paragraph
rewritten to record the resolved decision); `docs/00-project-plan.md`
(status line, §6 "what's left" line for ENT-05/06).

---

## Next

Route 3 (cycle 18) per `~/.claude/plans/clever-pondering-falcon.md`: three
small, independent, previously-unblocked capability extensions — PER-08's
llms.txt/sitemap agreement half, ENT-04's sitemap-scoped crawl-wide
duplicate detection, and CIT-07 (citation-position weighting) — followed by
actually cutting and validating a real submission zip.
