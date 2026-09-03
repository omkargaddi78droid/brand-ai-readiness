# Project Plan — Brand AI-Readiness Audit Marketplace

Status: **Phases 0.1–4 (17 capability cycles: PER-03; CQ-03/05/07/08;
ENT-01/02/03/04; EN-01/03/06/09; CIT-01/02/04/06; PER-05/06/07/08;
CQ-02/04/09/12; CQ-01/CQ-11; ENT-09; RET-08; RET-01; RET-04; RET-07;
RET-02/03/05/06; PER-08/ENT-04/CIT-07) complete. Cluster A (perimeter) is
now the first cluster fully done at all capabilities including both PER-08
halves, 8/8. **Cluster D (retrieval readiness) is the second cluster
fully done, 8/8.** `content-quality-audit` stands at 10/12, `entity-audit`
at 5/9 (ENT-04 now fully `IMPLEMENTED` rather than partial; ENT-05/06 now
`DEFERRED`, decision closed — see below), `citability-audit` at 5/13
(CIT-07 added cycle 18). **Six worker skills**,
`retrieval-readiness-audit` (Cluster D)
complete at all 8 capabilities (4 script-decided, 4 agent-judged). A
user-directed research pass in cycle 10 found the project had been
optimizing against `prompt.txt`'s internal capability backlog rather than
the actual graded spec (`problem-statement.txt`), and that the
entrypoint's composed, multi-skill report had never once been produced
end-to-end — see §6a. **The orchestrator end-to-end validation pass is now
complete** (`docs/phase-4-completion-15.md`): two real composed reports
produced against unfamiliar small-business sites, a real ENT-04
`www.`-canonical false-positive bug found and fixed (443→448 tests with
`tests/test_orchestrator.py`), no genuine cross-skill redundancy found
(INF-08 stays `NOT_STARTED`, checked not speculative), runtime measured at
~6.5 min combined for both sites (well under the 5-min/site ceiling), and
two real-but-low-severity generalization limitations documented for a
future cycle (CIT-06 testimonial exclusion, RET-05 signal quality on
chrome-heavy pages). **A second round against two more unfamiliar sites**
(`docs/phase-4-completion-16.md`) corroborated all of the above with no
code changes needed, and produced this project's first-ever live positive
case of PER-03 (a Cloudflare-fronted site blocking `ChatGPT-User` at the
edge while its `robots.txt` allows it — 9 live sites in PER-03's original
cycle had shown none), plus a real RET-07 finding and a new CIT-04
unsourced-third-party-claim pattern. **Cycle 17** fixed both documented
generalization gaps (CIT-06 testimonial exclusion via quote-span
detection; RET-05 signal quality via nav-block de-duplication plus a
second, live-discovered root cause — short all-caps menu-style headings),
live-reverified against the exact real pages that exposed each bug, and
formally resolved the 14-cycle-open ENT-05/06 scope decision: stays
strictly on-domain, both `DEFERRED`. **Cycle 18** shipped three
independent, previously-unblocked extensions — PER-08's llms.txt/sitemap
URL-set agreement (catching a `<sitemapindex>` false-positive class live,
on `vercel.com`/`supabase.com`), ENT-04's sitemap-scoped crawl-wide fork
detection, and CIT-07 (citation-position weighting) — plus this project's
first actually-produced-and-inspected submission zip (184 KB, verified to
unzip cleanly and run its entrypoint) and a first `skills-ref validate`
pass (all 6 skills clean). 482/482 tests pass. Awaiting instruction on
what to work on next.**

This document is the roadmap. It defines what each phase adds, what it explicitly does
*not* add, and the exit gate that must be satisfied before the next phase may start.
It does not implement anything.

---

## 0. Deliverable, in one sentence

A zipped directory containing `marketplace.json`, a `README.md`, and N skill folders —
each an agentskills.io-compliant `SKILL.md` — where exactly one skill is the entrypoint
that audits an arbitrary URL and emits one JSON report of evidence-backed findings plus
prioritized suggested actions, covering both AI discoverability and on-site engagement.

**What is graded is the marketplace source, not any report it produces.** The instructions,
checks, decomposition, and composition logic *are* the product. This changes engineering
priorities: a `SKILL.md` that reasons crisply about a failure mode is worth more than a
clever script that is never read.

---

## 1. Phase ledger

| Phase | Name | Output | Gate |
|---|---|---|---|
| 0.1 | Requirements extraction | `docs/competition-requirements.md` | **DONE** |
| 0.2 | Research → capability inventory | `docs/research-summary.md`, `docs/capability-matrix.md` | **DONE** |
| 0.3 | Skill-engineering principles | `docs/skill-engineering-principles.md` | **DONE** |
| 0.4 | Baseline selection | `docs/baseline-selection.md` | **DONE** |
| 1 | Baseline forensic analysis | `docs/baseline-analysis.md`, `-capabilities.md`, `-gaps.md` | **DONE** |
| 2 | Baseline wrapper | `brand-ai-readiness-audit/` skeleton, `marketplace.json`, `perimeter-access-audit`, finding contract, 50 tests | **DONE** — see `docs/phase-2-completion.md` |
| 3 | Baseline testing | 23-case corpus, `tests/measure_detection.py`, `docs/baseline-test-report.md` | **DONE** — P/R 1.000 on the corpus; 3 field false positives found and fixed; 6 of 7 baseline questions answered by execution |
| 4+ | Incremental capability addition | One capability per phase | Per-capability gate A–H (see §4) |
| N-2 | Skill decomposition | Final skill boundaries | Every skill has a non-overlapping responsibility |
| N-1 | Orchestrator | Entrypoint skill | Composes, dedupes, scores; reimplements nothing |
| N | Final validation | Adversarial fixture run, packaging check | Runtime < 5 min, zip < 50 MB, manifest valid |

Each phase ends with a completion note and a **STOP**. No phase auto-continues.

---

## 2. Three findings from Phase 0.1 that reshape the plan

These come from reading the problem statement against the research PDF. They are stated
here because they change the roadmap, not just the requirements doc.

**(a) The research is ~90% discoverability. The rubric is 50% engagement.**
Of the 47 researched categories, roughly two touch on-site engagement
(`conversion-path-friction-audit`, partly `multimodal-accessibility-audit`). The problem
statement gives equal billing to *"why visitors who do arrive don't stay"* — orientation,
context retention, friction, mobile usability. Building the research backlog as written
would produce a submission that fails half the rubric. **Phase 0.2 must add an engagement
capability cluster that the research does not supply**, and it will be almost entirely
build-from-scratch.

**(b) `seoscoreapi` is a hosted external API and is probably disqualifying.**
The research assigns it four categories (answer extractability, multimodal accessibility,
atomic paragraphs, fluency). But the rules require the manifest to be *self-contained —
no external service needed to resolve it*, and demand determinism and a <5 min runtime.
A third-party API adds a key, a network dependency, rate limits, and non-determinism.
Phase 0.4 must verify its terms; the default disposition is **REJECT and reimplement
those four checks locally** — they are all cheap heuristics over extracted text.

**(c) "Locally hosted LLMs for zero-shot classification" is out.**
The research proposes lightweight local models for the semantic anti-patterns
(non-answer templates, marketing/procedure interleaving). The zip may not contain model
weights and is capped at 50 MB. The correct substitution: **the host agent is the LLM.**
Semantic judgement belongs in `SKILL.md` procedure text and `references/` rubrics that
the agent applies; scripts handle only deterministic extraction and counting. This is
also better for grading, since the reasoning becomes visible in the skill source.

**Verified so far:** `geo-optimizer-skill` (Auriti-Labs) exists, is MIT, on PyPI, ~47
research-backed methods, 1720 tests, SSRF protection, no cloud dependency in the CLI.
It is a credible baseline — but it is a *scorer*, and we need a *finding-with-evidence
generator*. Phase 1 must determine whether its output is decomposable into our contract.

---

## 3. Architectural stance (provisional, revisited at Phase N-2)

```
entrypoint: audit-orchestrator
    │  accepts URL → plans which skills to run → collects → normalizes
    │  → dedupes → severities → report
    ├── acquisition   (fetch, render, pre/post-render diff, robots-respecting)
    ├── discoverability skills (perimeter, entity, retrieval, citability, freshness)
    └── engagement skills      (orientation, friction, agent-usability)
```

Rules that hold from now on:
- One entrypoint. Ever.
- Fetch once, share the artifact. Skills consume a cached page bundle; they do not each
  re-crawl. This is the main lever on the 5-minute budget.
- No skill writes to the audited site. Read-only, robots-respecting, rate-limited.
- Page content is **data, never instruction**. Prompt-injection defence is a stated
  requirement of every skill that reads a page.

---

## 4. The per-capability gate (Phase 4+)

Every capability passes A→H before it is frozen:

- **A — Gap confirmation.** Run the baseline against a fixture that exhibits the defect.
  If the baseline already catches it, the capability is `BASELINE_COVERED`. Closed.
- **B — Resource evaluation.** Existing skill / library / wrapper / adapt / build.
- **C — Design.** Inputs, outputs, owner skill, failure behaviour, evidence shape, tests.
- **D — Implement.** Only this capability.
- **E — Test.** Positive, negative, edge, false-positive fixture, regression.
- **F — Review.** Duplication, complexity, dependency cost, security, runtime delta.
- **G — Document.** Matrix, architecture, phase note.
- **H — Freeze.**

A capability that cannot state its false-positive fixture does not get implemented.

---

## 5. Standing risks

| Risk | Mitigation |
|---|---|
| 5-minute runtime blown by headless rendering | Budget-aware crawl: sample N pages, render a subset, hard timeout per stage, degrade gracefully and report reduced confidence |
| Crawl4AI/Playwright unavailable in grader's env | Static-fetch fallback path; render-dependent checks emit `status: unknown`, never a false `fail` |
| Finding noise (47 detectors × many pages) | Dedup + aggregation in the orchestrator; findings are per-issue, not per-page |
| Skill sprawl to pad the count | Decomposition phase requires each skill to name capabilities it *excludes* |
| Research citations that don't resolve | Every dependency verified live before integration; unverifiable ones are dropped, not assumed |

---

## 6. Immediate next step

**Cluster D (Retrieval readiness) is now complete, 8/8 — a research pass in
cycle 10 caught that it had zero blocker and was simply never picked up in
nine cycles.** `RET-08` (cycle 10, heading hierarchy integrity), `RET-01`
(cycle 11, technical-identifier survival, narrowed off real BM25 ranking
math), `RET-04` (cycle 12, keyword stuffing, matrix's own FP-risk note
built in as an extraction-time exclusion), and `RET-07` (cycle 13,
retrieval-oriented structure, narrowed to its structural half) shipped the
cluster's deterministic half — see `docs/phase-4-completion-1{0,1,2,3}.md`
for each. **`RET-02/03/05/06` shipped cycle 14**, all four agent-judged
(no bundled embedding model allowed for RET-02/03's semantic calls; RET-06
a third `— (was seoscoreapi)` capability, same reimplement-locally-via-
rubric disposition as CQ-01/CQ-11 in cycle 8), completing the cluster.
Live validation this cycle also caught and fixed a real, project-relevant
bug that predated it: `retrieval-readiness-audit`'s two text-extraction
parsers inserted no separator at block-level tag boundaries, producing
run-together word artifacts (438 on gymshark.com) that RET-01/04's own
prior cycles never surfaced because their checks don't depend on clean
word-level tokenization the way RET-02/05's statistics do — fixed to match
`entity-audit`/`content-quality-audit`'s existing, already-correct
`_BLOCK_TAGS` pattern (see `docs/phase-4-completion-14.md`). What's left
elsewhere: `ENT-05/06`'s off-site scope decision, open since cycle 9, was
resolved cycle 17 — stays strictly on-domain, both capabilities `DEFERRED`,
not built (`docs/capability-matrix.md`); `REN-*` needs a headless browser,
unavailable in this environment; most remaining `CQ-06/CQ-10`, `ENT-07/08`,
`EN-*`, `CIT-*` capabilities need multi-page context or off-site lookup.

## 6a. The grading-rubric research pass (cycle 10, before RET-08)

A user-directed research task ("research/brainstorm the best next steps
considering the problem statement") found three things worth recording
permanently, not just in this cycle's completion note:

1. **`problem-statement.txt` is the only graded spec.** `prompt.txt` — the
   phased build-process document this whole project plan derives from — is
   self-authored internal scaffolding, not a requirement. Its "~47/71
   capability categories" is explicitly framed there as backlog scope, not a
   target. The actual rubric (6 unweighted criteria) rewards detection
   accuracy, suggested-action quality, composed-report output design, skill-
   format hygiene, clean marketplace composition ("not padding"), and
   generalization to unseen sites — never capability count.
2. **The graded artifact — the entrypoint's composed, multi-skill report —
   has never once been produced end-to-end**, across all ten cycles.
   Confirmed directly: no `tests/test_orchestrator.py`; every existing test
   or measurement script calls `compose_report.compose()` with only one real
   skill's output at a time; `compose_report.py` has zero deduplication
   logic; every live-validation run in this project's history invoked one
   worker script directly, never the orchestrator; runtime has never been
   measured end-to-end against the stated 5-minute ceiling; live validation
   has only ever targeted large, well-engineered sites (python.org,
   Wikipedia, Apple, docs.python.org, PEP 8, BBC, Guardian, Stripe, GNU),
   never a small or messy real-world site, which is exactly what
   "generalization to unseen sites" will be judged against.
3. Submission zip size is a non-issue (1.6 MB against a 50 MB cap, confirmed
   this cycle) — not worth tracking as a risk going forward.

**Decided order (user's explicit choice): Cluster D capability work first,
then a dedicated orchestrator/report validation pass** — run real end-to-end
audits composing multiple worker skills together against unfamiliar sites,
read the composed report as a non-expert would, measure real runtime, add
`tests/test_orchestrator.py`, and build INF-08 (dedup) if cross-skill
redundancy shows up. **Cluster D is now fully shipped** (RET-08 cycle 10,
RET-01 cycle 11, RET-04 cycle 12, RET-07 cycle 13, RET-02/03/05/06 cycle
14), **and the orchestrator/report validation pass that follows it is now
also complete** (`docs/phase-4-completion-15.md`) — real composed reports
against `creswellbakery.com` and `jimmyjoesplumbing.com`, a real ENT-04
`www.`-canonical false-positive bug found and fixed, `tests/
test_orchestrator.py` shipped, no cross-skill redundancy found (checked,
INF-08 stays deferred), runtime measured well under the 5-minute ceiling.

**Fourteen capability cycles done this phase**, each with its own completion note:

- **PER-03 (edge/CDN blocking)** — `docs/phase-4-completion.md`. Built locally rather
  than integrated with the baseline (Phase 3 already established the baseline is
  untestable offline). Never probes an agent robots.txt already disallows, enforced in
  code. A live run found a real bug fixtures could not: `probe_with_user_agent` silently
  returned a bare string instead of the documented tuple on two of three paths.
- **CQ-03/05/07/08 (deterministic content anti-patterns)** — `docs/phase-4-completion-2.md`,
  new skill `content-quality-audit`. Five real bugs found by running detectors against
  realistic fixtures before writing formal tests: two were the same substring-matching
  failure class as PER-03's robots.txt bug (`"per"` inside `"period"`, `"this week"`
  inside `"this weekend"`) — now a named, tracked failure class in this project, not a
  one-off, with every phrase list matched `\b...\b`.
- **ENT-01/02/03/04 (schema/entity identity)** — `docs/phase-4-completion-3.md`, new
  skill `entity-audit`. A live run against apple.com found a more consequential bug than
  either prior cycle's: overriding `HTMLParser.handle_startendtag` without delegating to
  `handle_starttag` silently dropped canonical-link and JSON-LD extraction for every
  self-closed tag (`<link ... />`), a common real pattern. Fixed by restoring
  `HTMLParser`'s documented default (starttag then endtag). Checked the sibling skill
  for the same pattern and recorded why it was safe there rather than assuming so. This
  cycle's field validation also found six genuine, hand-verified positives across seven
  live sites — the first cycle where live validation surfaced real defects rather than
  only confirming clean sites.

- **EN-01/03/06/09 (on-site engagement)** — `docs/phase-4-completion-4.md`, new skill
  `engagement-audit`, the first engagement-cluster skill and the first agent-judged
  capabilities actually built (EN-01/EN-03: script extracts structural signals only,
  emits no verdict; the agent judges against a calibrated rubric with worked examples
  before hand-authoring a finding). A live run found a cross-cutting bug affecting
  every page-fetching skill at once: `urllib.request` never auto-decompresses gzip, and
  python.org's CDN gzips regardless of client negotiation — every extracted-text field
  from that host was binary garbage on every prior cycle that touched it. Fixed in all
  four fetch functions across the project; **retroactively corrected a wrong claim in
  cycle 3's completion doc**, whose own manual `curl` verification was fooled by the
  same issue.

- **CIT-01/02/04/06 (citability)** — `docs/phase-4-completion-5.md`, new skill
  `citability-audit`. `REN-02…REN-04` checked (no headless browser in this
  environment) and deferred again, this time on evidence. The about-page detector
  (CIT-01) accumulated three independent real bugs in one cycle — more than any prior
  single detector — each found by checking a site whose conventions differed from the
  mainstream commercial sites earlier cycles happened to sample: a bare relative link
  with no leading slash, MediaWiki's `Namespace:About` convention (Wikipedia and the
  whole MediaWiki ecosystem), and Sphinx's `<link rel="author">`-in-`<head>` convention
  with an extension-suffixed path (docs.python.org). Fixing the third required a design
  decision — keep `<link>` hrefs separate from `<a>` hrefs, so a stylesheet `<link>`
  can't silently suppress a real CIT-02 finding — made and tested before it could ship
  wrong, not after.

- **PER-05/06/07/08 (perimeter, Cluster A complete)** — `docs/phase-4-completion-6.md`.
  No new skill, extends `perimeter-access-audit`. First cycle where every real problem
  was caught by the project's own test infrastructure before a live request went out,
  rather than by field validation — including one genuine unknown-vs-absent collapse
  in PER-08 (the same class of bug as rule 6 below, this time inside the project's own
  code rather than a third-party parser), and a reminder that a "false positive" during
  measurement can mean the *corpus* was mis-isolated, not the detector: several PER-06
  fixture cases were quietly also tripping PER-08 because they never supplied a
  robots.txt referencing their sitemap.

- **CQ-02/04/09/12 (content-quality agent-judged half)** — `docs/phase-4-completion-7.md`.
  No new skill, extends `content-quality-audit` — the agent-judged
  extraction-plus-rubric pattern proven a third time (cycles 4, 5, now 7), reusing
  `compose_report.py`'s `agent_judgement_required` handling unchanged. One bug, caught
  by the pre-formal-test fixture sweep rather than live: the granularity-mismatch
  context-word list had only noun forms ("weight"), missing the verb forms real
  product copy uses ("weighs") — the same "enumerated pattern list is a hypothesis"
  lesson as rule 7 below, this time caught before a live run rather than during one.
  Also caught by the project's own manifest-hygiene tests, not manual counting: the
  skill's frontmatter description first drafted over the 1,024-char spec limit,
  trimmed before the phase's regression pass completed.

- **CQ-01/CQ-11 (Cluster F's last `seoscoreapi`-derived capabilities)** —
  `docs/phase-4-completion-8.md`. No new skill, extends `content-quality-audit`.
  The costliest cycle yet for "trusted but wrong on first try": CQ-01's opening-
  text window was wrong twice in sequence (nav/header chrome ahead of a
  document-start window; then, after windowing from the H1 instead, a
  `<title>`-derived substring collision, fixed once; then, even after that fix,
  a live-only failure on two more sites — Wikipedia's language-switcher panel and
  Stripe's logo-as-`<h1>` — that could not be patched without re-solving the
  main-content-boundary-detection problem this project's architecture already
  defers to an unbuilt gate-2 skill for everything else). Reverted to a simple,
  honestly-limited document-start window rather than keep chasing DOM shapes.
  Separately, CQ-11's own false-positive-guard claim was falsified by a fixture
  built specifically to test it — dense medical jargon in short, simple
  sentences still crossed the "very difficult" threshold, disproving the
  original claim that the strict band defended against jargon-driven false
  positives. Corrected the documentation rather than ship an overstated guard,
  and reclassified the fixture from an intended "clean" case to a "defect" case
  in the corpus.

- **ENT-09 (taxonomy consistency)** — `docs/phase-4-completion-9.md`. No new
  skill, extends `entity-audit` with its first agent-judged capability. The
  only real finding this cycle was a documentation bug, not a code bug: ENT-09
  had been grouped with ENT-07/08 as needing off-site or cross-page reasoning
  across three prior completion notes (cycles 6, 7, 8), when its own
  capability-matrix wording is unambiguously same-page — caught by re-reading
  that wording against the exclusion list before starting Gate A rather than
  trusting the prior framing. Zero code bugs found by either the fixture
  sweep or live validation, the first cycle since Phase 3 with neither.

- **RET-08 (heading hierarchy integrity, Cluster D's first capability)** —
  `docs/phase-4-completion-10.md`. New skill, `retrieval-readiness-audit` —
  the sixth worker skill. Preceded by a user-directed research pass (§6a)
  that found Cluster D itself, not any single capability, was the thing nine
  cycles had missed. Scoped narrowly to two fully static, near-zero-FP
  sub-defects (a skipped heading level, an empty heading) — the capability
  matrix's own "decorative heading" half of RET-08 excluded as needing
  render/CSS inspection, the same gate-2 boundary this project draws
  everywhere else. Zero code bugs; one genuine live positive hit
  (stripe.com/pricing's FAQ section skips from h1 straight to h3, no h2 in
  between). This cycle also bundled three cheap documentation-hygiene fixes
  the research pass surfaced: `capability-matrix.md`'s stale "62
  capabilities" header (actual row count: 84), its stale Cluster E status
  column (CIT-01/02/04/06 had read NOT_STARTED since cycle 5 despite
  `citability-audit` implementing them — the table was never updated when
  the narrative moved on), and CIT-07's fully unexplained gap (absent from
  both the matrix and `citability-audit`'s own Excludes — now tracked in
  both, deliberately not built).

- **RET-01 (technical-identifier survival, BM25 exact-match retention
  narrowed)** — `docs/phase-4-completion-11.md`. No new skill, extends
  `retrieval-readiness-audit` with its second capability. Narrowed on
  purpose from the matrix's broad "Detects" wording (SKUs, model numbers,
  statute names) to exactly the deterministic, near-zero-FP slice: a
  JSON-LD `Product.sku`/`mpn`/`gtin*` value missing from the page's own
  extracted visible text. No real BM25 ranking math, no `bm25s` dependency —
  reuses `entity-audit`'s JSON-LD-extraction pattern reimplemented locally.
  "Model numbers in prose" and "statute names" both need a free-text
  heuristic with real FP risk and were deliberately deferred, not attempted
  without a fixture built to break them first. Zero code bugs; one genuine
  live positive, independently verified: lego.com's product pages declare a
  JSON-LD `sku` that never appears outside a `<script>`/`<style>` block
  anywhere on the page — confirmed by a script-stripped substring check run
  outside the skill's own code, not just its report. No live "survives"
  case was found this cycle (every real product page tested exhibited the
  same gap); the silent path's correctness rests on the synthetic fixture
  pair, flagged as such rather than silently assumed proven.

- **RET-04 (keyword stuffing)** — `docs/phase-4-completion-12.md`. No new
  skill, extends `retrieval-readiness-audit` with its third capability. The
  matrix's own FP-risk note ("fires on legitimately repetitive pages — spec
  tables, glossaries; exclude structured regions before counting") was
  designed in from the start, per the plan's own instruction, rather than
  discovered live: `table`/`dl`/`ul`/`ol`/`select` regions are excluded at
  extraction, before any n-gram is counted, not filtered after the fact.
  4-word n-gram, ≥5 occurrences, ≥8% prose density, stopword-only grams
  excluded, an 80-word prose floor below which the check stays silent
  (stated as a known limitation, not hidden). `advertools` rejected as an
  actual dependency, same disposition as `bm25s` for RET-01. Zero code bugs.
  Live-validated against 7 real pages including two deliberately chosen for
  the exact FP risk the matrix warned about — `en.wikipedia.org/wiki/
  Glossary_of_chess` (`<dl>`-heavy) and `docs.python.org/3/library/re.html`
  (dense, naturally repetitive terminology) — both stayed silent, zero false
  positives across all seven. No live true positive was found: reputable,
  well-indexed sites generally avoid keyword stuffing because ranking
  already penalizes it, consistent with rather than contrary to this
  capability's own premise. The detection path's correctness rests on the
  synthetic fixture pair, the same disposition RET-01 stated for its own
  missing live case.

- **RET-07 (retrieval-oriented structure)** — `docs/phase-4-completion-13.md`.
  No new skill, extends `retrieval-readiness-audit` with its fourth
  capability, completing Cluster D's deterministic half. Narrowed to the
  fully structural question the matrix's own wording allows without a
  semantic judgement: does a substantial page (≥300 words) have zero of
  three named aids (headings, Q&A framing, definition blocks) present at
  all. **A real bug this time, caught by live validation, not a fixture**:
  the first implementation reused RET-04's structured-region-excluded word
  count for RET-07's own floor, which silently zeroed out on
  `paulgraham.com`'s table-laid-out essay pages (old-school HTML, tables
  used for visual layout) and suppressed the check entirely on exactly the
  headingless-prose pages it exists to catch. Fixed by switching to RET-01's
  full-visible-text corpus, which has no reason to inherit RET-04's own FP
  guard — a reminder that sharing an extraction corpus across capabilities
  is only safe when their false-positive guards actually agree. After the
  fix: two genuine live positives, `paulgraham.com`'s essays (as intended)
  and an unplanned second one on `python.org/about/` itself — 1445 words
  with zero heading elements anywhere, independently confirmed with a plain
  `grep` outside the skill's own code, on a site this project has otherwise
  treated as a model of good markup in prior cycles' live validation.

- **RET-02/03/05/06 (dense/semantic coverage, query-intent coverage,
  terminology balance, chunk quality — all agent-judged)** —
  `docs/phase-4-completion-14.md`. No new skill, extends
  `retrieval-readiness-audit` with its fifth through eighth capabilities,
  completing Cluster D at 8/8 — the second fully-complete cluster after
  Cluster A. All four use this project's proven `agent_judgement_required`
  pattern (seventh use, after `content-quality-audit`'s five, `engagement-
  audit`'s two, `citability-audit`'s one, `entity-audit`'s one): a new
  `references/retrieval-judgement-rubric.md` with calibration examples per
  capability. **A real bug found live, not in a fixture, affecting
  already-shipped RET-01/04 too**: this skill's two text-extraction parsers
  inserted no separator at block-level tag boundaries, so adjacent elements'
  text ran together into corrupted words — 438 artifacts on gymshark.com,
  present since cycle 11 but never surfaced because RET-01/04's own checks
  don't depend on clean word-level tokenization the way RET-02/05's
  word-count and phrase-frequency statistics do. Fixed to match
  `entity-audit`/`content-quality-audit`'s already-correct `_BLOCK_TAGS`
  pattern; confirmed by direct comparison to reduce the residual artifact
  rate to exact parity with `content-quality-audit`'s own extractor on the
  same live page (45 remaining in both — the shared, accepted, inline-tag
  limitation every text extractor in this project already carries). Live
  validation also produced a genuinely useful real-world confirmation of
  RET-06's calibration: all 10 long-paragraph candidates found on Python's
  own `re` module docs were correctly long-but-atomic, matching the
  rubric's own "no finding" worked example exactly.

- **Orchestrator end-to-end validation pass** (not a capability cycle) —
  `docs/phase-4-completion-15.md`. First-ever real, composed multi-skill
  report, produced twice against unfamiliar small-business sites
  (`creswellbakery.com`, `jimmyjoesplumbing.com`), all four skills'
  `agent_judgement_required` entries resolved together in one real session.
  **A real, high-severity bug found and fixed**: `entity-audit`'s ENT-04
  off-domain-canonical check compared hosts without stripping `www.` —
  `citability-audit`'s own CIT-02 already had this exact guard, entity-audit
  simply never adopted it, and it fired as a false `high` on every sampled
  page of both real sites (6 of 9 pre-fix `high` findings, all false). Fixed
  with `entity-audit`'s own `_strip_www()`, 2 new tests. `tests/
  test_orchestrator.py` shipped (5 tests, 443 → 448). No genuine cross-skill
  redundancy found in either composed report (checked directly, not
  assumed) — INF-08 stays `NOT_STARTED`. Runtime measured directly for the
  first time: ~6.5 minutes combined for both sites' full sequences, well
  under the 5-minute-per-site ceiling. Two real, low-severity generalization
  limitations documented (not fixed, per this pass's own scope discipline):
  `citability-audit`'s CIT-06 has no customer-testimonial exclusion, and
  `retrieval-readiness-audit`'s RET-05 sample-sentence/acronym-count signal
  degrades on chrome-heavy small-site pages.

**A pattern is now established across fifteen consecutive cycles**: real bugs come from
running the code against realistic input, not from reasoning about it in advance —
including twice from a project-owned bug repeating in a second detector (substring
matching, cycle 2), once from a single bug silently affecting every skill that shared
the same kind of code (gzip decoding, cycle 4), once from an enumerated pattern list
that had only ever been checked against mainstream commercial sites (about-page
conventions, cycle 5), twice from the project's own test/fixture infrastructure
catching everything before a live run was even needed (cycles 6 and 7), and, this
cycle, from a heuristic that had to be tried, found wrong live, fixed, found wrong
live again on different sites, and finally reverted rather than patched a third time —
plus a stated false-positive guard that a fixture built specifically to test it
disproved outright (cycle 8). Proof the discipline generalises, not just a lucky
streak, and that fixture sweeps and live validation are catching different,
complementary bug classes rather than the same one twice. Standing rules, now twelve:
(1) fixture pairs first, (2) run against realistic/live input before trusting the
fixtures, (3) `python3 -W error::ResourceWarning` in the verification command, (4) any
word/phrase list matched with `\b...\b`, never bare substring containment, (5) any
`HTMLParser` subclass that overrides `handle_startendtag` either delegates to
`handle_starttag`/`handle_endtag` or states in a comment why it deliberately does not,
(6) a manual `curl`/browser check is not independent verification of a fetch bug if it
uses the same defaults the tool does — checking `urllib`-fetched content with plain
`curl` (no `--compressed`) verifies nothing about decompression, (7) an enumerated
pattern list (URL slugs, bot names, template syntaxes, context-word lists) is a
hypothesis until checked against realistic input with genuinely different phrasing —
verb forms as well as noun forms, a wiki as well as a mainstream commercial site, (8)
"confirmed absent" and "status unknown" are different states for every capability that
gates on another capability's result (PER-08 on PER-06, ENT-02 on ENT-01) — collapsing
them into one silent branch drops a genuine unknown; (9) untrusted remote input
(sitemap.xml, any future fetched structured format) parses with the narrowest tool
that can't be exploited by it — a regex over a full parser wherever a regex suffices,
as already practiced for JSON-LD and HTML; and (10) a stated false-positive guard is a
claim, not a fact, until a fixture built specifically to break it is run against the
code — CQ-11's cycle-8 "very difficult" band was believed to defend against jargon-
dense-but-clear prose, and a fixture drafted to demonstrate exactly that instead
disproved it, on the first real test. When a heuristic keeps needing a new patch for a
new site's DOM shape, the fix is not the next patch — it is reverting to the simplest
honestly-limited version and documenting the limitation, especially when the deeper
problem (main-content boundary detection, CQ-01's cycle-8 case) is one this project's
own architecture already defers to an unbuilt gate elsewhere. And (11), new this
cycle: a scope claim repeated across several completion notes is not thereby
verified — ENT-09 was called blocked by off-site/cross-page reasoning in cycles 6,
7 and 8 by inheriting cycle 6's framing each time, when the capability matrix's own
one-line wording for it ("contradicting its own body text") said same-page all
along. Re-read the primary source (the capability matrix row, not the prior cycle's
summary of it) before accepting a capability as blocked — confirmed again one cycle
later, at cluster scope this time: §6's "next step" had re-derived "what's left" from
narrative summary for four straight cycles (6-9), never re-reading the matrix itself,
and missed that all of Cluster D (eight capabilities) had zero blocker the whole time.
And (12), new the orchestrator validation pass: a false-positive guard added to one
skill for a specific comparison (`citability-audit`'s CIT-02 stripping `www.` before
comparing hostnames, cycle 3) is not thereby applied anywhere else the same comparison
recurs — `entity-audit`'s ENT-04 did the identical host comparison for canonical
checking without the guard, five cycles later, and shipped a `high`-severity false
positive on the single most common canonical pattern on the real web, invisible to
every fixture because no fixture had ever paired a `www.`/bare-domain canonical with
the off-domain check. When a guard is added for a false-positive class in one skill,
grep every sibling skill for the same raw comparison before calling the class handled
project-wide.

Awaiting go-ahead.
