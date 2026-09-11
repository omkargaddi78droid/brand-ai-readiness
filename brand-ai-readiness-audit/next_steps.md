# Next: priority-ordered, deadline-gated page audit (100-page sample)

Status: IMPLEMENTED (2026-09-12), full test suite green (1363 passed).
See `shared/page_sample.py` (`page_priority`/`rank_sample_urls`),
`skills/audit-orchestrator/SKILL.md` (steps 1/4/5), and
`skills/audit-orchestrator/references/orchestration-notes.md` for the
shipped version of this design. Not yet committed — not yet live-site
smoke-tested (Verification items 3-4 below still open). Picks up after the merge_paginated_findings work
(shipped in commit `bea6cef`, see `bugs.md`/`README.md` for that). This
supersedes an earlier two-wave (`--exclude-file` top-up) design that was
prototyped and then deliberately reverted in the same session as overcomplicated
for what the problem actually needs — this document is the simpler replacement,
to be implemented next session.

## Context

`audit-orchestrator`'s page sample is currently a fixed page count:
`sample_pages.py --budget 25` (`shared/page_sample.py:207`,
`_DEFAULT_BUDGET = 25` at `page_sample.py:32`). SKILL.md documents an
unenforced "5-minute budget" (`SKILL.md:78-79` as of `bea6cef`,
`references/orchestration-notes.md:36-44`), but nothing tracks wall-clock time,
and nothing ranks which of the 25 sampled pages matter most — they're audited
in whatever order the template-clustering allocation happens to emit them.
`shared/budget.StageBudget` (`budget.py:32-68`) only caps the *internal*
concurrent-fetch loop inside the six `--sample-file` skill scripts
(`_SAMPLE_FETCH_BUDGET_SECONDS = 90.0`, e.g. `check_engagement.py:1271`) — it
has no idea how much of the overall run's time has already been spent, and no
script knows about any other script's elapsed time either.

Net effect: a slow/large site can blow well past 5 minutes running all 25
pages through 4 separate per-page skills each; a fast/small site finishes with
time to spare and gets a shallower audit (fewer pages) than it could have
afforded; and even within a fixed 25-page run, if something does force an
early stop, the pages that got skipped are arbitrary rather than the
least-important ones.

## Decision (this session, superseding the prior two-wave design)

Rather than sampling twice (wave 1 fixed-size + wave 2 top-up from leftover
URLs, gated by an exclude-list), do this instead — simpler, one sample, one
pass:

1. **Raise the sample size to 100 pages** (`sample_pages.py --budget 100`
   instead of `--budget 25`). The template-stratified clustering/allocation
   algorithm in `shared/page_sample.py` already generalizes to any budget
   number — no code change needed for this part, just the number used in
   `SKILL.md`'s invocation.

2. **Rank the 100 sampled URLs by priority** before auditing, so the pages
   worth getting right are audited first regardless of what order the sample
   happened to emit them in.

3. **Audit in that priority order**, checking wall-clock time before each
   page, and **stop** as soon as either all 100 pages have been audited or the
   time budget (280s / 4m40s, see below) is hit — whichever comes first. No
   second sample, no exclude-list, no wave-2 budget arithmetic.

This directly satisfies "stop at ~5 minutes instead of committing to a fixed
page count up front" while staying simple: one sampling call, one ordered
list, one deadline check, no merging-across-waves concerns for
`compose_report.py` to worry about (it already handles a shorter-than-full
list the same way it handles today's 25-page runs — nothing new needed there).

## Design

### 1. Priority ranking — new function in `shared/page_sample.py`

Add a `page_priority(url: str) -> int` function (or `rank_sample_urls(urls:
list[str]) -> list[str]`, returning a reordered copy) using a tiered,
path-based heuristic — deterministic and pure, consistent with every other
function in this module (no network, no fetching, so ranking can happen
before any page is actually audited):

- **Tier 3 (always first):** the homepage and any `_FORCE_INCLUDE_PATHS`
  member already defined at `page_sample.py:38` (`/`, `/contact`,
  `/checkout`, `/search`, `/pricing`) — these are already special-cased as
  "audit no matter what"; priority ranking should put them first, not just
  guarantee their presence.
- **Tier 2 (claim-bearing keyword match):** a path segment matching a
  keyword list grounded in `SKILL.md`'s own existing prioritization prose
  (`SKILL.md:103-107` as of `bea6cef`: "pricing, specs, policies, dated
  announcements, how-to guides") — e.g. `pricing`, `plans`, `product`,
  `spec`, `docs`, `guide`, `how-to`, `policy`, `terms`, `review`, `compare`.
  Case-insensitive substring match against each path segment.
- **Tier 1 (dated/announcement-shaped):** a path containing a 4-digit-year
  segment or a `blog`/`news`/`press`/`announcement` segment — reuse the
  numeric-detection idea already in `_segment_is_variable`
  (`page_sample.py:110-123`) rather than inventing a second regex from
  scratch.
- **Tier 0 (default):** everything else.

Sort by `(tier desc, original index asc)` — stable on ties — so ranking
never breaks `SamplePagesTests.test_sampling_is_deterministic_across_repeated_calls`
(`tests/test_page_sample.py:199`)-style determinism.

Decide during implementation whether this reorders `sample_pages()`'s
existing `"sample_urls"` key in place, or adds a new `"priority_order"` key
alongside it — check what `skills/audit-orchestrator/scripts/sample_pages.py`
and any other consumer of `sample_urls`'s current (clustering) order actually
depend on before choosing (grep for `sample_urls` across `skills/*/scripts/`
and `tests/` first).

### 2. Orchestrator changes — `skills/audit-orchestrator/SKILL.md`

No new numbered step needed (unlike the reverted two-wave design, which
needed a whole extra "wave 2" step) — everything fits inside the existing
Procedure:

- **Step 1 addition:** start the run's wall-clock budget in a **file**, not a
  shell variable — `mkdir -p /tmp/audit && date +%s > /tmp/audit/start_epoch`.
  This part of the reverted design was correct and should carry over
  unchanged: `SKILL.md`'s Procedure is prose any `agentskills.io`-compliant
  agent can execute (`marketplace.json`), potentially in a harness that does
  not persist a shell session across separate `bash` tool calls (confirmed
  true of this session's own tool), so a plain shell variable would silently
  not exist by the time a later step tries to read it. A file is correct
  regardless of which kind of harness runs this Skill. Later steps read
  elapsed time via `$(( $(date +%s) - $(cat /tmp/audit/start_epoch) ))`.
- **Step 4 change:** `sample_pages.py --budget 100` instead of `--budget 25`;
  note that `sample_urls` in its output is now priority-ordered (highest
  first), and that order is what step 5 should iterate in.
- **Step 5 change:** before each per-page invocation
  (`content-quality-audit`, `entity-audit`, `engagement-audit`,
  `citability-audit`, each via `--url`), check elapsed time against
  `/tmp/audit/start_epoch`. Once elapsed reaches 280s, stop issuing further
  per-page invocations for all four of these skills — they share the same
  priority-ordered list and the same budget, so a lower-priority page never
  reached by one of them shouldn't be reached by another either. A page
  never reached simply produces no output file, composing exactly like a
  smaller sample would today — no new `unknown_checks` bookkeeping needed.
- No step 6, no wave-2, no `--exclude-file` — delete these from
  consideration entirely (they belonged to the reverted design).

The six `--sample-file` skills (`static-extraction-audit`,
`retrieval-readiness-audit`, and the multi-page modes of
`content-quality-audit`/`entity-audit`/`engagement-audit`/`citability-audit`)
already self-cap at 90s via `StageBudget` regardless of how many pages are in
the sample file (`SKILL.md:343-353` as of `bea6cef`) — raising the sample to
100 pages doesn't need a code change there; a slower host just degrades
coverage the same way it already does today, visible via `coverage.stages`.

### 3. `compose_report.py` — no changes needed

Already handles a partial/short findings list the same way regardless of why
it's short (a slow host, a small site, or now: a priority-ordered list cut
short by the deadline). Nothing wave-aware to add.

### 4. Tests

- `tests/test_page_sample.py` — new test class for the priority function:
  homepage/force-include paths always rank first; a `pricing`/`docs`-style
  keyword path outranks a plain path; a dated `/blog/2024/...`-style path
  outranks an undated one but ranks below a keyword match; ties preserve
  original order (determinism); reordering doesn't drop or duplicate any URL
  (same set in, same set out, just reordered).
- `tests/test_sample_pages.py` — if the CLI's `--budget` default or output
  shape changes, update accordingly; otherwise likely untouched (the CLI
  already just forwards `budget` through).
- No new tests needed in `test_orchestrator.py`/`test_finding_contract.py` —
  nothing about merging changes.

## Verification

1. `python -m pytest brand-ai-readiness-audit/tests/ -q` — full suite stays
   green, including new priority-ranking cases.
2. Unit-level: rank a synthetic mixed list (homepage, a `/pricing` page, a
   dated `/blog/2024/...` page, several plain pages) and confirm the output
   order matches the tier rules above.
3. Live-site smoke test (reuse this session's pw.live/eff.org run pattern):
   run the orchestrator by hand against a real site with `--budget 100`,
   confirm the priority-ordered list puts pricing/docs/dated pages ahead of
   generic ones, and — on a deliberately slow run or an artificially short
   budget for testing — confirm the per-page loop actually stops mid-list
   once the deadline check fires, rather than running to completion anyway.
4. Confirm the file-backed elapsed-check idiom survives across genuinely
   separate Bash tool calls (not just one shell session) — this is the one
   part of the design that fixes a real correctness bug versus the naive
   "shell variable" version, so exercise it as literally separate tool calls
   during verification, not just by reading the code.

## Explicitly out of scope (reverted from this session's earlier attempt)

- Two-wave sampling (`--exclude-file`, wave-2 budget-from-observed-pace
  arithmetic, a separate "wave 2" Procedure step). Dropped as unnecessary
  complexity once a single priority-ordered 100-page list with a deadline
  check covers the same goal (spend available time well) more simply.
- Any change to `shared/budget.StageBudget` or the six `--sample-file`
  skills' internal 90s cap — orthogonal, already works, not touched by this
  plan.
