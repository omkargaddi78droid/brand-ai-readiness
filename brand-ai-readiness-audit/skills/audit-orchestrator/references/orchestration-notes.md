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
