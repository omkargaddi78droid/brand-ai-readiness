# Phase 4 — orchestrator end-to-end validation pass

Not a capability cycle: no new capability is added to the matrix by this
pass. This is the validation pass that had never been run across all
fourteen prior cycles — the entrypoint's actual composed, multi-skill
report, produced end to end against real, unfamiliar sites, then read
against the grading rubric. Adapted from the usual Gate structure since
there is no new capability to gate.

---

## What was tested

Two real, live, small-business sites — nothing like the large tech/docs/
e-commerce sites every prior cycle validated against:

- **creswellbakery.com** — a Squarespace-templated bakery site (Creswell,
  OR).
- **jimmyjoesplumbing.com** — a local plumbing company site (Mesa, AZ),
  also Squarespace-templated.

Both fetchability-confirmed with `curl` before use, per this project's
standing practice, after discarding the prior session's five guessed-and-
unverified candidate hostnames entirely, as instructed — site selection was
redone from scratch via web search for real small-business site examples
(bakeries, plumbing companies), then `curl`-probed.

For each site: `perimeter-access-audit` once against the root, then all
five page-level skills (`content-quality-audit`, `entity-audit`,
`engagement-audit`, `citability-audit`, `retrieval-readiness-audit`) once
per sampled page — home + 2 subpages (`/about-us` + `/menu` for the
bakery, `/about-us` + `/drain-cleaning` for the plumber) — 15 invocations
per site, 30 total, all exit 0, zero crashes. Every `agent_judgement_
required` entry from all four judgement-emitting skills was read against
its own rubric and resolved (78 entries total: 18 trivially empty-
candidate, 60 requiring an actual judgement call), then both reports
composed with `compose_report.py` — the first time this project's
orchestrator has ever merged more than one real skill's output, and the
first time all four skills' agent-judged capabilities were resolved
together in one real session.

## What the two composed reports actually found

**creswellbakery.com**: 16 findings (14 defects, 2 proactive), 0 critical,
3 high, 9 medium, 4 low, 0 unknown checks. Real, genuine defects: three
EN-09 unlabelled form fields (high), six ENT-01 incomplete LocalBusiness/
Organization JSON-LD nodes, three ENT-02 missing knowledge-graph links, one
CIT-06 unqualified-superlative cluster, one RET-08 skipped heading level,
plus the two PER-04/PER-07 proactive suggestions every clean-perimeter site
gets.

**jimmyjoesplumbing.com**: 20 findings (18 defects, 2 proactive), 0
critical, 0 high, 13 medium, 7 low, 0 unknown checks. Real defects: two
CIT-04 unsourced load-bearing claims (a plumbing-code pressure threshold
cited with no source, and a sitewide "4.8 star / 51 reviews" badge that
never links to its source), two EN-01 findings (home and drain-cleaning
pages both have an empty `<h1>` and 150 words of pure duplicated nav-menu
chrome before any orienting sentence — independently corroborated by
RET-08's own, separately-derived "empty heading element" finding on the
same `<h1>`), six ENT-01, three ENT-02, two CIT-06, three RET-08, plus the
two PER-04/PER-07 proactive suggestions.

Both sites: perimeter access open, no gate-1 block, no `unknown_checks` on
either report.

## A real bug found and fixed (not scoped-out)

**`entity-audit`'s ENT-04 off-domain-canonical check did not strip a
`www.` prefix before comparing hosts** — `entity-audit/scripts/
check_entity.py`, `find_canonical_issues()`. Every `www.` ⟷ bare-domain
canonical relationship (an extremely common, entirely benign pattern —
`citability-audit`'s own CIT-02 already explicitly guards against treating
it as a domain switch, with a comment and a dedicated test) was reported
as a `high`-severity off-domain canonical defect. This fired on **every
single sampled page on both sites** — 6 of the pre-fix report's 9 combined
`high`-severity findings were this one false positive, repeated per page.

Fixed by adding the same `_strip_www()` helper `citability-audit` already
carries, applied to both sides of the host comparison. **2 new tests**
(`test_www_prefix_alone_is_not_off_domain`, `test_bare_domain_canonical_
from_www_page_is_not_off_domain`) in `tests/test_entity_audit.py`. Both
reports recomposed after the fix: bakery `high` count dropped 6 → 3
(the three genuine EN-09 findings), plumbing `high` count dropped 3 → 0
(every plumbing ENT-04 hit was this exact false positive, none real).
This is exactly the kind of bug this project's standing discipline exists
to catch — a real, high-severity false-positive class invisible to every
fixture this project has ever written, found only by running against real
sites with real `www.`-canonicalized pages.

## Non-expert readability pass

Read every finding's evidence, mechanism, and suggested-action summary as
a first-time reader. Findings are, on the whole, concrete, quotable, and
actionable — no vague adjectives standing in for evidence, severities
argue for themselves via `mechanism`.

**One real clarity gap found, documented, not fixed**: `citability-audit`'s
CIT-06 (unqualified superlatives) has no exclusion for quoted customer
testimonials. On `creswellbakery.com/about-us` it flagged "The BEST bacon
I have ever had" and "they make the best cinnamon rolls in the county" —
direct customer review quotes, not brand claims — as unverifiable claims
needing a citation, with a suggested action ("the fastest becomes 'the
fastest: 940 Mbps average, per [source]'") that is nonsensical applied to
someone's personal opinion. This is the first live site tested with
scraped customer testimonials sitting in visible text, so the gap had
never surfaced before. Left as a documented, real, low-severity precision
limitation rather than patched speculatively: a robust fix needs a design
decision (e.g., detecting proximity to a review-attribution line like
"- Jose L, ★★★★★ Google Review", which this skill does not currently
parse as a distinct signal) that is its own scoped piece of work, not a
one-line guard worth rushing into this pass.

**A second generalization limitation recorded, not fixed**: `retrieval-
readiness-audit`'s RET-05 `sample_sentences` and `acronym_count` signals
degrade badly on small, chrome-heavy template sites — sample sentences
came back as page-footer fragments ("Copyright ©", "Our Blog", "Location")
with no representative prose in them at all, and `acronym_count` reached
implausible values (39 on the bakery's menu page) almost certainly from
all-caps UI labels and price tokens rather than real acronyms. No finding
was manufactured from unreliable signal (per the rubric's own precision-
over-recall standard) on either site, but the signal-quality gap itself is
worth a future refinement cycle.

## Cross-skill redundancy check

**Checked and confirmed absent — a real, checked negative result, not
silence.** Read the full merged `findings` list on both composed reports
looking for two findings (different `owner_skill`/`capability_id`)
describing the same underlying defect on the same page. `ENT-01` and
`ENT-02` both come from the same JSON-LD node (`entity-audit` itself) but
are legitimately distinct capabilities (property completeness vs.
knowledge-graph grounding) — same-skill, not the cross-skill case INF-08
targets. The plumbing site's `EN-01` (engagement-audit, empty `<h1>` /
chrome-swamped orientation) and `RET-08` (retrieval-readiness-audit, empty
heading element) findings both trace back to the same underlying empty
`<h1>` tag, but they report genuinely different things about it — EN-01
judges visitor orientation, RET-08 judges document-outline integrity — and
each is independently useful evidence corroborating the other, not a
duplicate. **INF-08 (deduplication & aggregation) stays `NOT_STARTED`** in
`docs/capability-matrix.md`, with this checked-negative-result noted there
rather than left silent.

## Runtime

Both sites' full sequence (gate 1 → 15 page-level invocations → judgement
resolution → compose), timestamped: **~6.5 minutes combined for both
sites**, well inside the `< 5 minutes ... for a typical website` ceiling
per site. All 30 script invocations completed in seconds each; the
dominant time cost was judgement authoring (reading rubrics and observation
signals for 78 `agent_judgement_required` entries across both sites), which
scales with how many real candidates a page surfaces, not with script
execution time. The deterministic/scripted layer itself is not a runtime
risk at this scale.

## Generalization notes

- Both real, previously-unseen sites completed with zero crashes across
  all 30 invocations and zero `unknown_checks` on either composed report —
  a solid generalization signal for the deterministic layer.
- `CQ-01` and `EN-01`'s raw extraction windows are dominated by navigation
  chrome far more severely on small, heavily-templated sites than on any
  large site tested in prior cycles — `jimmyjoesplumbing.com`'s first 150
  words were a duplicated nav menu on every sampled page. `CQ-01`'s own
  rubric already anticipates this exact failure shape and correctly says
  "cannot judge, say nothing"; `EN-01`'s rubric treats a missing/empty
  `<h1>` on an actual landing page as itself the evidence, so it correctly
  still fired — the two rubrics' different handling of the same underlying
  extraction limitation is itself a deliberate, documented distinction
  (verified above it is not an unowned inconsistency), not a bug.
- See the two documented-not-fixed items above (CIT-06 testimonials,
  RET-05 signal quality on chrome-heavy pages) — both are real limitations
  this pass's own standing discipline (live sites over fixtures) surfaced
  for the first time.

## `tests/test_orchestrator.py` — new file, the concrete deliverable

5 new tests, offline and deterministic (in-process skill-function calls
with inline fixture text/HTML, no network, no dependency on the two real
sites' live JSON):

- `MultiSkillMultiPageCompositionTests` (3 tests) — a real compose across
  three distinct skills (`perimeter-access-audit`, `content-quality-audit`,
  `entity-audit`) with `content-quality-audit` run across two distinct
  pages, producing a `validate_floor_shape`-clean report; confirms findings
  from every skill and both pages are present and correctly page-
  attributed; confirms severity/ordering correctness **across** skills
  (a `perimeter-access-audit` `critical` finding correctly sorts ahead of
  every `medium`/`low` finding from the other two skills, defects before
  proactive suggestions, sequential `F-00N` ids) — extending `sort_
  findings`'s existing per-skill-only test coverage to a genuinely mixed
  set, per this pass's own mandate.
- `UnresolvedJudgementAlongsideCleanSkillsTests` (1 test) — one skill
  (`engagement-audit`) left with an unresolved `agent_judgement_required`
  entry, composed alongside three other skills' fully clean output:
  produces exactly one `unknown_checks` entry, and every other skill's
  real findings (including `entity-audit`'s missing-canonical finding)
  compose through untouched.
- `Inf08NotBuiltTests` (1 test) — documents and locks in the current,
  correct behaviour in INF-08's absence: two distinct skills' findings
  about unrelated defects on the same page both survive composition
  unmerged and unsuppressed.

**448/448 tests pass project-wide** (441 → 443 from the ENT-04 fix's 2
new tests → 448 from this file's 5).

## INF-08 — explicitly deferred, not built

Per Part 3's own instruction: build only if genuine cross-skill redundancy
is found in real composed output. None was (see above). `docs/capability-
matrix.md`'s INF-08 row stays `NOT_STARTED`, now carrying this pass's
checked-negative-result note instead of the prior generic description
alone.

## Other close-out items

- **`docs/capability-matrix.md`'s Cluster H corruption fixed**: the
  INF-08/INF-09 row-bleed identified at the end of the prior session
  (garbled `NO| INF-09 | ... |T_STARTED |` line) rewritten as a clean
  4-column INF-08 row, duplicate INF-09 fragment removed.
- **Zip size re-checked**: 1.9 MB raw / 292 KB zipped (excluding
  `__pycache__`), against the 50 MB cap — still a non-issue, unchanged in
  kind since cycle 10's 1.6 MB reading.
- **README.md vs `problem-statement.txt` drift check**: structure (Skills
  → composition → report shape → design rules → layout → tests) still
  matches the submission ask; only the stale test count (441 → 448) needed
  a fix.
- `marketplace.json`: `0.18.0` → `0.18.1` (the ENT-04 behavioural fix
  warrants a patch bump; this pass added no new capability, so no minor
  bump).

---

## Next

Per `docs/00-project-plan.md` §6a's ordering, this closes the last
explicitly-planned item. Remaining open work is whatever the two
documented-not-fixed limitations above (CIT-06 testimonial exclusion,
RET-05 signal quality on chrome-heavy pages) warrant as their own future,
properly-scoped cycles — neither is load-bearing enough to have blocked
this pass, and rushing either in here risked exactly the kind of
speculative, unjustified build this project's own standing rules warn
against.
