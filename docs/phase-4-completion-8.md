# Phase 4 (capability cycle 8 of N) — CQ-01, CQ-11

Phase 4 output, eighth capability cycle. No new skill — extends
`content-quality-audit` with the two remaining `— (was seoscoreapi)`
capabilities from Cluster F: answer extractability (CQ-01, agent-judged)
and fluency/readability (CQ-11, script-decided). Cluster F now stands at
10 of 12 — only CQ-06 and CQ-10 remain, both needing multi-page context
this project does not build.

---

## A — Gap confirmation

Not baseline-covered: both routed through the rejected `seoscoreapi`
dependency (`docs/baseline-selection.md` §C1), and neither has any other
resource. `BUILD_REQUIRED`, resolved by building locally — the same
disposition PER-01–08 already established for every other
`seoscoreapi`-derived capability.

## B — Resource evaluation

stdlib only: `re`, `html.parser.HTMLParser`. CQ-01 reuses
`content-quality-audit`'s existing `extract_visible_text`/`_split_sentences`
and, deliberately, CQ-09's own marketing-phrase vocabulary (same mechanism,
different location — see Design). CQ-11 is a stdlib implementation of the
published Flesch Reading Ease formula; no dependency exists in this
project's allowed set that would replace hand-rolled syllable counting more
cheaply than a vowel-group heuristic already does.

## C — Design

**CQ-01 is agent-judged** — the capability matrix's own description ("no
concise 2–4 sentence canonical answer... buried under marketing") is a
judgement call, the fourth time this project uses the extraction-only
pattern `engagement-audit` (cycle 4) and `citability-audit` (cycle 5)
established. The script extracts a page-level signal — the first H1's text
(a new `extract_h1`, a second, deliberately separate `HTMLParser` pass so
extending this one capability's needs could never risk perturbing the
eight checks that already depend on `extract_visible_text`'s exact, already-
tested behaviour) and the opening ~150 words of visible text, plus a count
of CQ-09's own marketing phrases in that window — into
`agent_judgement_required`, and asserts no verdict.

**CQ-11 is script-decided** — unlike CQ-01/02/04/09/12, readability has a
standard, decades-old, purely arithmetic definition. Computing the Flesch
formula is "the script decides" the same way CQ-08 computes an arithmetic
mean: the evidence *is* the arithmetic. Guarded by a 300-word minimum
sample (below this, this project's line/punctuation sentence splitter is
noise, not signal) and thresholded at the strictest published band ("very
difficult," <30) rather than merely "difficult."

## D — Implement

`extract_h1`/`_H1Extractor` (new, separate pass), `find_answer_
extractability_signal`, `_count_syllables`, `measure_readability`,
`build_agent_judgement_requests` extended to accept `h1_text` and emit a
CQ-01 request, `audit_text`/`main` extended to thread `h1_text` through in
`--url`/`--html-file` modes (absent, honestly, in `--text-file` mode — no
raw HTML source for an H1 there). `CAPABILITY_IDS` extended from 8 to 10.

## E — Test

**26 new unit tests** (extract_h1: 4; answer-extractability signal: 7;
readability: 4; agent-judgement-request updates: 2 changed + 1 new) + the
existing 75-test suite for the other eight capabilities, unaffected. **316
tests project-wide** (up from 300 — 15 net new after one test was corrected
mid-cycle, see F). Corpus: 3 new content-quality cases (1 clean, 2 defect)
for CQ-11 — `measure_content_quality.py` still reports P/R 1.000 across all
11 cases.

## F — Review

**Two real bugs, both caught by the pre-formal-test fixture sweep this
project's discipline has used since Phase 3 — neither survived to a live
run, but both were more consequential than a typical cycle's single catch,
and both were found specifically *because* this cycle ran live validation
before declaring CQ-01 done, not just fixtures:**

1. **CQ-01's opening-window design was wrong on first implementation, in
   two layers.** The first version windowed `opening_block` from document
   start — live-checked against four real sites (python.org,
   docs.python.org, en.wikipedia.org, peps.python.org) and found to be
   nearly always nav/header chrome ("Skip to content", "Toggle
   light/dark"), not article content. The fix — window from just after the
   H1's own line instead — introduced a *second*, more subtle bug: since
   `<title>Page Title - Site Name</title>` is a near-universal convention
   and the title tag's text is not newline-isolated by this extractor the
   way a block tag's is, the H1's exact text is essentially always already
   present as a literal prefix substring earlier in the document, so
   `text.index(line)` (a global substring search) anchored on the title's
   occurrence instead of the real H1's position. Fixed once (tracking the
   offset while walking lines, not re-searching) — then found, live, that
   even the corrected version still anchored wrong on Wikipedia (a
   language-switcher sidebar panel producing a coincidental standalone-line
   match before the real `<h1>`) and Stripe (whose first `<h1>` in DOM
   order wraps the site logo, not the article heading — confirmed by
   fetching and reading the raw HTML, not guessed). **Reverted the whole
   H1-anchoring approach** rather than continuing to patch per-site DOM
   shapes: this is exactly the main/article-boundary detection this
   project's own architecture defers to gate 2 (render/extraction, not
   built) for every other capability, and chasing it further inside CQ-01
   specifically would have meant re-solving that problem one DOM pattern at
   a time. Shipped as a simple, honestly-limited document-start window with
   the limitation documented in both `references/content-anti-patterns.md`
   and `references/content-judgement-rubric.md` §CQ-01, and the agent
   explicitly instructed to disregard a nav-dominated opening rather than
   score it as a missing answer.
2. **CQ-11's own false-positive guard claim did not hold when tested
   against a fixture built specifically to test it.** The rubric originally
   asserted the "very difficult" threshold was a defence against Flesch's
   well-known jargon-density false positive (domain vocabulary inflating
   syllable count without genuine difficulty). A fixture deliberately
   drafted to test this — short, simple, clinically ordinary sentences
   built from dense medical vocabulary — was intended to demonstrate the
   guard holding, and instead scored 9.9 (well below the threshold),
   crossing it. The formula's syllable-per-word term (`84.6 ×`) dominates
   its sentence-length term (`1.015 ×`) heavily enough that short sentences
   do not protect against high syllable density the way the original
   guard's language implied. Corrected the documentation to state this
   honestly (`content-anti-patterns.md`'s CQ-11 section) rather than ship
   an overstated guard, reclassified the fixture from an intended "clean"
   case to a "defect" case in the corpus
   (`defect_dense_jargon_short_sentences.txt`), and confirmed
   `confidence: medium` (never `high`) is the correct disposition for every
   CQ-11 finding given this.

**Field validation, ten live pages** (python.org, docs.python.org ×2,
en.wikipedia.org ×2, peps.python.org, stripe.com, apple.com/contact,
gnu.org/licenses/gpl-3.0): zero crashes, zero CQ-11 false fires (including
against GNU's GPL v3 full text, historically a canonical "hard to read"
legal-text example, which stayed above the threshold as expected), zero
`unknown_checks`. CQ-01's `h1_text`/`marketing_phrase_hits_in_opening`
extraction ran cleanly on all ten with no crash; per SKILL.md's own
guidance, several openings were nav-chrome-dominated (documented, expected,
not a defect) and would be judged "does not apply" by the agent per the
rubric rather than scored as missing answers. CQ-01/CQ-11's positive paths
otherwise remain proven by synthetic and corpus fixture rather than a live
positive hit this session — same disposition as PER-03 (cycle 1) and part
of the CQ cluster (cycle 2).

**Duplication check:** CQ-01 deliberately reuses CQ-09's `_MARKETING_PATTERN`
rather than defining a second marketing-phrase vocabulary — same skill,
same underlying mechanism (promotional language crowding out a fact), only
the location differs (top-of-page vs. inside a numbered step); a second,
near-duplicate list would add nothing and risk the two drifting apart. No
other duplication found.

## G — Document

This file; `SKILL.md`, `references/content-anti-patterns.md` (CQ-11
section + a corrected known-limits note for CQ-01), `references/content-
judgement-rubric.md` (new CQ-01 section), README, `marketplace.json`
(0.11.0 → 0.12.0), `docs/capability-matrix.md` (CQ-01/CQ-11 →
IMPLEMENTED, Cluster F detail paragraph), entrypoint `SKILL.md` (registry +
procedure note), `docs/00-project-plan.md`.

## H — Freeze

Frozen at ten of Cluster F's twelve capabilities. CQ-06 (date-context/price
invariance) and CQ-10 (temporal freshness/cross-page contradiction) remain
— both need multi-page context this project's single-page model does not
build, the same disposition as PER-06's completeness half and CQ-03's
programmatic-list-duplication half.

---

## Next

With Cluster F at 10/12 and Cluster A (perimeter) already complete, the
capability matrix's remaining single-page, no-render-needed surface is
narrow: `ENT-05/06` (entity collision, lookalike domains) is still blocked
on the off-site scope decision flagged open since `docs/baseline-
selection.md`, now unresolved across eight cycles. Most of what remains
elsewhere (CQ-06/CQ-10, `REN-02…REN-04`, several EN-/CIT- capabilities) now
genuinely needs either multi-page crawling, off-site lookups, or a headless
browser this environment does not have — the "build it locally, single-page,
no render" seam this project has worked for eight cycles is close to fully
mined.
