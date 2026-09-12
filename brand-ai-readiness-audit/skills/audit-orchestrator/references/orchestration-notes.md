# Why the orchestration works this way

Reference for `audit-orchestrator`. `SKILL.md`'s own `## Procedure` section
is the literal, runnable steps; this file is the rationale behind the two
infrastructure decisions those steps lean on, so `SKILL.md` itself can stay
focused on what to run rather than why it was built that way.

---

## Why a deterministic page sample, not a hand-picked one

Before `shared/page_sample.py` existed, page selection for every per-page
skill was a prose instruction: "pick a small, representative sample of
pages... not every URL on the site." That phrasing sounds reasonable and
produces a real, silent failure: a human or an LLM picking "interesting"
pages tends to pick *different* pages from each other — a pricing page, an
About page, a flagship product page, one blog post — because that is what
"interesting" means to a chooser trying to cover variety. The one thing that
selection process reliably fails to do is put two pages from the *same
template family* into the sample together.

That failure matters specifically because `content-quality-audit`'s CQ-13
(near-duplicate/template dilution) and `entity-audit`'s ENT-07/ENT-08
(cross-domain service attribution, address clustering) all need at least two
same-template pages in the sample to have anything to compare. A
variety-seeking sample defeats exactly the checks it was meant to make
possible. `sample_pages.py` fixes this by clustering sitemap URLs by
template shape first (`template_key()` — "/blog/2024/my-post" and
"/blog/2023/other-post" both collapse to "/blog/\*/\*") and then allocating
the page budget proportionally *across clusters*, so the sample spans the
site's page *kinds* — including, deliberately, more than one member of the
same kind where the site has enough of them.

## Why the sample is priority-ordered and the per-page loop is deadline-gated

A fixed 25-page sample audited in whatever order the template-clustering
allocation happened to emit meant two failure modes at once: a slow/large
site could blow well past the runtime budget running every skill against
every page, and a fast/small site that finished early got a shallower audit
than it could have afforded. Raising the sample to 30 pages
(`sample_pages.py --budget 30`) and letting the per-page loop in `SKILL.md`
step 5 stop at a wall-clock deadline (280s) instead of a fixed page count
fixes both — a fast host gets through more of the 30, a slow host still
gets through the pages that matter most, and neither ends the run with an
arbitrary, order-of-emission-dependent partial sample.

That last part only works if "the pages that matter most" are audited
*first*. `shared/page_sample.py`'s `rank_sample_urls` reorders `sample_urls`
by `page_priority` — the homepage and forced process pages first, then
claim-bearing pages (pricing/specs/policies/how-to guides, the same
categories `SKILL.md`'s own prose already named), then dated/announcement
pages, then everything else — so a run cut short by the deadline check still
audited the highest-value pages rather than whichever 25 or 30 the sampler
happened to list first. This was designed once as a two-wave scheme (a
fixed-size first pass plus a top-up second pass from leftover URLs, gated by
an exclude-list) and then deliberately simplified to one ranked pass with one
deadline check — the two-wave version's extra bookkeeping (a second
`sample_pages.py` invocation, `--exclude-file`, wave-2 budget-from-pace
arithmetic) bought nothing that priority-ordering plus a stop condition
doesn't already get more simply.

The wall-clock budget itself is tracked in a **file**
(`/tmp/audit/start_epoch`), not a shell variable, because `SKILL.md`'s
Procedure is prose any `agentskills.io`-compliant agent can execute
(`marketplace.json`), potentially in a harness that does not persist a shell
session across separate `bash` tool calls — a plain shell variable would
silently not exist by the time a later step tries to read it. A file
survives that regardless of which kind of harness runs this Skill.

The 280s deadline check now also gates the six `--sample-file` bulk
invocations, not just per-page ones — each self-caps internally at 90s via
`StageBudget`, but that bounds one invocation's own cost, not how many of the
six still run after the per-page loop already used most of the budget, so
without the outer check the worst case was ~540s of extra, unmeasured time.
`compose_report.py --start-epoch-file` also now reports
`total_elapsed_seconds`, computed from the same `start_epoch` file, so any
overrun still possible from agent-reasoning turns between calls (not
measurable from inside a script) is at least visible in the report instead of
silently absorbed.

## Why judgement-resolution has its own, smaller cap

The 280s/30-page budget above gates *fetching* — it says nothing about the
cost of resolving what a fetch turns up. Sixteen agent-judged rubric items
span five skill families (content-quality-audit ×6, entity-audit ×3,
engagement-audit ×4, citability-audit ×2, retrieval-readiness-audit ×4 —
static-extraction-audit contributes 0, every one of its capabilities is
script-decided). At a 30-page fetch budget, an uncapped run could produce
hundreds of judgement candidates: mechanical, rubric-driven LLM reasoning
that turned out to be the dominant cost of a run — a live run's
`coverage.stages` showed each fetch stage finishing in 11-19s against its
90s cap, yet the run's `total_elapsed_seconds` was 1178.3s (~19.6 min), the
gap being judgement resolution with no timer or cap of its own.

Rather than build a second wall-clock deadline around an LLM reasoning step
(hard to measure accurately mid-procedure, unlike a script's own fetch
loop), or cap by page priority (which bounds cost but is blind to which
candidates are actually worth judging), the fix caps **per skill, by
severity**: `select_judgement_items.py` gathers every candidate a skill
produced this run, ranks them by each capability's rubric-declared severity,
and keeps the top 5. Each of the five agent-judged skills is capped
independently, so the worst case is a flat **5 skills × 5 items = 25
items**, constant regardless of site size — a 5-page site and a 500-page
site cost the same judgement-resolution budget. Ties within a skill (same
severity) break by input order: the orchestrator passes `--input` files in
`sample_urls`' own priority order, so the same discovery order used for the
fetch budget also decides which of several equal-severity candidates
survives the cap.

A candidate beyond the cap is not silently dropped: `compose_report.py
--judgement-items-resolved`/`--judgement-items-total` records exactly how
many candidates were resolved versus produced, summed across the five
skills, in the report's own `coverage.stages` — the same "reduced coverage
is reported, never hidden" principle the 90s-fetch-cap and 280s-deadline
stages already follow.

## Why the multi-page skills fetch concurrently instead of one page at a time

The competition's own runtime budget is 5 minutes for a typical site. Early
in this project, every multi-page capability (CQ-13, ENT-07/08, EN-04/08/11,
CIT-08/09, and both of `retrieval-readiness-audit`'s and
`static-extraction-audit`'s entire per-page capability sets) worked by
spawning one sequential subprocess per sampled page. On a realistic 25-page
sample, that meant 25 sequential network round-trips per skill, repeated
across six skills that all consume the same page-sample file — comfortably
enough wall-clock time on a slow or distant host to blow the 5-minute budget
on its own, before any other skill had run at all.

`shared/page_fetch.fetch_pages_concurrently` fixes this by fetching the whole
sample in one process, bounded by a global concurrency cap of 5 and a
**per-host** cap of 3. The per-host cap exists on top of the global one
because every skill's own page sample is, by construction, almost always
pages on the one site being audited — without it, the global cap alone would
let 5 simultaneous requests land on a single slow host, which is a
self-inflicted mini denial-of-service against the exact site this project is
supposed to be auditing politely, not a third party. `shared/budget.
StageBudget` then caps the whole fetch loop at 90 seconds regardless, so a
genuinely unresponsive host degrades the audit's coverage (visibly, via
`coverage.stages` and per-page `unknown_checks` entries) rather than hanging
the whole run.

This is also why `retrieval-readiness-audit` and `static-extraction-audit`
specifically are told to *prefer* `--sample-file` bulk mode over one `--url`
call per page (Procedure step 5): every one of their capabilities is
inherently per-page, so for them the concurrent bulk path is strictly
better, not just an optional convenience the way it is for skills that also
have real per-site capabilities of their own.
