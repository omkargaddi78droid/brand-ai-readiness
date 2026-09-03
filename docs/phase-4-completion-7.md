# Phase 4 (capability cycle 7 of N) — CQ-02, CQ-04, CQ-09, CQ-12

Phase 4 output, seventh capability cycle. No new skill — extends
`content-quality-audit` with its four agent-judged capabilities, the ones
the capability matrix named as judgement calls from Phase 0.2 onward and
every prior cycle deferred building.

---

## A — Gap confirmation

Not baseline-covered: `docs/baseline-capabilities.md` marks these as
build-from-scratch (CQ-01/CQ-06/CQ-11 route through the rejected
`seoscoreapi` dependency; CQ-02/04/09/12 have no baseline equivalent at all).
`BUILD_REQUIRED`, resolved by building — closing out Cluster F's
agent-judged half, the same way cycles 4 and 5 closed out `engagement-audit`
and `citability-audit`'s.

## B — Resource evaluation

stdlib only: `re`, reusing `content-quality-audit`'s existing
`extract_visible_text`/`_split_sentences`. No new dependency.

## C — Design

**Extends the existing skill, third time this pattern has been used.** The
capability matrix flagged CQ-02/04/09/12 as agent-judged since Phase 0.2;
`engagement-audit` (cycle 4) and `citability-audit` (cycle 5) already proved
the pattern — script extracts candidate sentences into
`agent_judgement_required`, emits no verdict, a `references/` rubric with
worked calibration examples resolves it. This cycle is the third proof, not
a new invention, and reuses the identical `agent_judgement_required`
resolution machinery already built into `compose_report.py` — no changes
needed there.

**Four extraction functions, each scoped narrowly on purpose:**

- **CQ-02** matches a fixed hedge-phrase list ("it depends", "results may
  vary") and captures the preceding sentence as the implied question — the
  phrase alone never says whether the topic is genuinely variable (a real
  answer) or the fact was omitted (a non-answer); that split is exactly what
  the agent judges.
- **CQ-04** requires a vague magnitude word ("large", "substantial") **and**
  a spec-context word ("weight", "size") in the same sentence **and** no
  number at all — three conditions, not one, to keep the candidate set
  precise rather than firing on every "large" in the page.
- **CQ-09** is scoped to numbered step-*lines* specifically (`Step 2:`,
  `3.`) containing marketing language — the same phrase on an ordinary
  marketing page is not a procedure-interleaving defect at all, so the
  pattern is anchored to step-shaped text, not just phrase presence.
- **CQ-12** reports a page-level count/quote triple, not per-sentence
  candidates — deliberately no ratio computed by the script, since whether a
  given filler density is a real problem depends on the surrounding
  substance the script has no way to weigh.

## D — Implement

`find_non_answer_candidates`, `find_granularity_candidates`,
`find_procedure_marketing_candidates`, `measure_filler_density`,
`build_agent_judgement_requests`, `audit_text`/`_unknown_output` extended to
carry `agent_judgement_required`. `CAPABILITY_IDS` extended from 4 to 8.

## E — Test

**19 new unit tests** + the existing 39-test suite for CQ-03/05/07/08,
unaffected + the project's existing 281-test suite, unaffected except where
the output-shape change (`agent_judgement_required` added) required no
changes at all — `measure_content_quality.py` already stripped that key
before composing, a pattern already proven by cycles 4–5. **300 tests total
project-wide.** No dedicated measured corpus for CQ-02/04/09/12: agent-judged
capabilities have no script verdict to measure this way, consistent with
`engagement-audit` and `citability-audit`'s EN-01/EN-03/CIT-04.

## F — Review

**One real bug, caught during the pre-formal-test fixture sweep (the
discipline every cycle has used since Phase 3), zero live bugs:**

`_SPEC_CONTEXT_WORDS` originally listed only noun forms (`weight`, `size`),
missing the verb forms (`weighs`, `measures`, `holds`) real product copy
overwhelmingly uses — "The device weighs a substantial amount" produced zero
candidates on the first smoke test, because "weighs" matched nothing in the
context list even though "weight" was right there as a near-miss. Found by
running the extractor against a synthetic positive fixture before writing
any formal test, fixed by adding the verb forms, confirmed against both the
original miss and the still-correctly-silent "large selection of products"
negative case (no spec-context word at all, correctly stays silent).

**Field validation, seven live pages** (python.org, Wikipedia, Stripe
pricing, Apple contact, docs.python.org, Apple support, PEP 8): zero
crashes, zero false positives, one genuine, sensible CQ-04 candidate on
Stripe's pricing page ("large payments volume" — a plausible case for either
verdict, exactly what a candidate extraction is supposed to produce rather
than a script assertion), one correctly-small CQ-12 count on docs.python.org
(1 filler phrase in 8,218 words — matches the rubric's own "negligible,
no finding" calibration example almost exactly). CQ-02/CQ-09 found no
candidates in this sample; checked directly why for one candidate page
(Apple's iPhone-backup support article) — it has zero `<li>` elements in its
static HTML at all, meaning its step structure is JS-rendered and invisible
to a static fetch, the same REN-cluster limitation already documented
project-wide, not a defect in CQ-09's own logic. CQ-02/09's positive paths
remain proven by synthetic fixture, same disposition as any capability
without a live positive hit this session (PER-03 in cycle 1, CQ cluster
partially in cycle 2).

**Duplication check:** none — the four functions reuse
`extract_visible_text`/`_split_sentences` already in the file rather than
reimplementing text handling, and the marketing-phrase and filler-phrase
lists are new, distinct vocabularies from CQ-06's superlative list and
`citability-audit`'s own superlative list (different capability, different
mechanism — CQ cluster is about page-internal consistency, CIT cluster is
about external citability, so a shared list would blur that boundary rather
than reduce real duplication).

## G — Document

This file; `SKILL.md`, `references/content-judgement-rubric.md` (new),
README, `marketplace.json` (0.10.0 → 0.11.0), `docs/capability-matrix.md`
(CQ-02/04/09/12 → IMPLEMENTED), entrypoint `SKILL.md` (registry + procedure
note), `docs/00-project-plan.md`.

One correction made in-flight, not after: the skill's frontmatter
`description` first drafted at 1,196 characters, over the 1,024-char spec
limit (M9) — caught immediately by this project's own manifest-hygiene test
suite, not by manual counting, and trimmed to 773 characters before this
phase's regression pass completed.

## H — Freeze

Frozen at four capabilities, six worked calibration examples each context
(24 total in the rubric). Cluster F (content anti-patterns) now stands at
8 of 12 capabilities — CQ-01/06/10/11 remain, needing either the rejected
`seoscoreapi` dependency reimplemented locally (CQ-01, CQ-11) or multi-page/
scoring-model context this project does not build (CQ-06, CQ-10).

---

## Field validation

Seven live pages, read-only, single GET each — see §F for the specific
findings and verification. No corrections needed to any live result; the one
bug this cycle produced (§F) was caught and fixed before any live request
was made, the same outcome as cycle 6.

## Next

Two fronts remain buildable without rendering, per the capability matrix and
this project's now eight-cycle-tested "check before assuming" discipline:
`ENT-05/06` (entity collision, lookalike domains — needs the off-site scope
decision `docs/baseline-selection.md` flagged as still open and never
resolved across seven cycles), or `CQ-01`/`CQ-11` (answer extractability,
fluency — both currently `— (was seoscoreapi)` in the matrix, reimplementable
locally the same way PER-01–08 replaced their baseline dependency).
`REN-02…REN-04` remains deferred pending a headless browser actually being
available in this environment.
