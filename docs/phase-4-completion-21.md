# Phase 4 completion — cycle 21

## What changed

The user drew a hard line on the capability set: stop expanding anything
already built, select exactly 3 more `NOT_STARTED` capabilities against
five criteria (core-problem impact, differentiation, feasibility within
this project's non-negotiable constraints, complementary/no-overlap,
concrete findings not scores), and discard every other remaining candidate
with no further scope growth. See `docs/capability-matrix.md`'s "Capability
freeze — cycle 21" section for the full selection reasoning and the
discard list (15 capabilities, each with a one-line reason).

Selected: EN-07 (perceived-performance friction), EN-05 (mobile usability,
narrowed), CQ-10 (temporal freshness, narrowed). The user then narrowed
execution further: **only EN-07 and EN-05 were built. CQ-10 was explicitly
dropped — discarded like every other candidate, not deferred.**

## `engagement-audit` — EN-05, EN-07

Both script-decided, both land in the existing `engagement-audit` skill
(no new skill file) alongside EN-01/03/06/09. `CAPABILITY_IDS` now
`["EN-01", "EN-03", "EN-05", "EN-06", "EN-07", "EN-09"]`.

**EN-05 (mobile usability), narrowed to two static markup facts:**
- `find_missing_viewport()` — no `<meta name="viewport">` at all
  (`EN-05-missing-viewport`, medium), or one present without
  `width=device-width` (`EN-05-viewport-not-responsive`, low).
- `find_fixed_width_overflow()` — an inline `style="width:NNNpx"` above
  480px with no `max-width:100%`/`width:100%` override in the same style
  attribute (`EN-05-fixed-width-overflow`, medium).
- Tap-target sizing and font legibility (the matrix's other two named
  signals) are NOT built — both need resolved CSS layout (computed pixel
  geometry), which needs either rendering (banned) or a full CSS cascade
  resolver (out of scope, no proven low-FP path). Stated exclusion, not a
  silent gap.

**EN-07 (perceived-performance friction), three static proxies, all
computed from the fetched HTML document alone (no linked CSS/JS/image
assets are fetched):**
- `find_render_blocking_resources()` — synchronous (no async/defer)
  `<script src>` plus `<link rel="stylesheet">` inside `<head>`, ≥5 total
  (`EN-07-render-blocking-resources`, medium).
- `find_unsized_images()` — `<img>` with neither width/height nor
  aspect-ratio, ≥3 (`EN-07-unsized-images`, low).
- `find_payload_weight()` — the HTML document's own UTF-8 byte size, ≥300KB
  (`EN-07-heavy-html-payload`, low). Named "HTML payload" deliberately, not
  "page weight" — a stated narrowing, since this skill never fetches the
  assets a real page-weight measurement would need to include.

## Verification

- 27 new unit tests (`ViewportTests`, `FixedWidthOverflowTests`,
  `RenderBlockingResourceTests`, `UnsizedImageTests`, `PayloadWeightTests`
  in `tests/test_engagement_audit.py`), each function tested as a
  positive/negative pair.
- Existing `test_engagement_audit.py` tests whose fixtures had no viewport
  tag (`ContractComplianceTests`, `UnresolvedJudgementCompositionTests`)
  updated to include a valid viewport tag, isolating them from EN-05 noise
  they were never testing for.
- Corpus: all 6 pre-existing `tests/corpus/engagement/*.html` fixtures
  gained a valid `<meta name="viewport">` in a newly-added `<head>` (none
  had a `<head>` element before), so EN-05 stays correctly silent on
  fixtures that were never about mobile usability. Two new corpus cases
  added: `defect-missing-viewport-and-overflow` (both EN-05 findings) and
  `defect-heavy-page` (all three EN-07 findings, ~328KB HTML). `tests/measure_engagement.py`:
  precision/recall 1.000 across 8 cases (up from 6).
- Full suite: 597/597 passing (up from 574).
- Live-validated: `info.cern.ch` (no viewport tag — confirmed
  `EN-05-missing-viewport`); `vercel.com`/`docs.python.org`/`chewy.com`
  (render-blocking head-resource counts of 5/14/24 respectively, all
  genuinely high, not threshold-noise; `docs.python.org` also fired
  `EN-07-unsized-images`). No false crashes across any of the 4 live
  fetches, and the 5-resource threshold did not fire on any of them at a
  trivially-low count — the real signal separates cleanly from normal
  pages with just one or two stylesheets.

## Wiring

- `skills/engagement-audit/SKILL.md`: description, capabilities note,
  Procedure steps 2/5, "What it checks" table, Excludes (EN-05/EN-07's own
  narrowing stated explicitly, plus the discard list moved out of this
  skill's Excludes and into the capability matrix's own freeze section),
  Output's `capability_ids` example, Failure-modes rows.
- `skills/engagement-audit/scripts/check_engagement.py`: module docstring
  rewritten (six capabilities, not four); new functions inserted between
  the existing EN-09 and EN-06 sections (script-decided capabilities kept
  together); wired into `audit_html()`.
- No `references/engagement-judgement-rubric.md` change — both new
  capabilities are script-decided, no agent judgement, no new rubric
  section needed.
- `marketplace.json` needed no change (no new skill); version bumped to
  0.22.0 for consistency with prior cycles' practice.
- `README.md`: `engagement-audit`'s one-line description, test count
  (574 → 597), engagement corpus case count (6 → 8).
- `docs/capability-matrix.md`: EN-05/EN-07 flipped to `IMPLEMENTED`; new
  "Capability freeze — cycle 21" section; all 15 discarded rows tagged
  in their own status text with a one-line reason each, per the user's
  "do not propose alternatives" instruction — nothing added in their
  place.

## Next

The capability freeze is explicit and final for this phase: no further
capability additions without a new, explicit unfreeze decision from the
user. Remaining open items from prior cycles, untouched by this one: the
`measure_perimeter_extras.py` regression flagged in
`docs/phase-4-completion-20.md` (3 false positives, PER-06/08, still
unfixed); a live orchestrator end-to-end validation pass exercising
EN-05/07 alongside ENT-05/06/CIT-13 together has not been run.
