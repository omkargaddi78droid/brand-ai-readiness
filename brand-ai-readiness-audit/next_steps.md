# Fix: agent/off-loop time not counted in audit's total time

## Context

Explore confirmed the gap: `skills/audit-orchestrator/SKILL.md`'s only
wall-clock control is a file-backed epoch (`/tmp/audit/start_epoch`, written
step 1, read step 5) gating **just the per-URL loop** of 4 skills against a
280s deadline. Everything else consumes real time but is never measured or
enforced:

- The 6 `--sample-file` bulk invocations are **explicitly excluded** from the
  280s check (SKILL.md:104-106) and only self-cap at 90s each internally via
  `StageBudget` — worst case ~540s of extra, invisible time.
- All `agent_judgement_required` resolution (pure LLM reasoning, no
  subprocess) between calls — SKILL.md:128, 152-155, 213-220, 233-235,
  259-261, 298-304 — and off-site candidate discovery (SKILL.md:184-196,
  246-257) run with zero time accounting.
- `compose_report.py` (step 6) never receives or reports a total-duration
  figure. The report's only timing field is `audited_at`, a single instant,
  not a duration. `coverage.stages` shows only each script's internal 90s-cap
  manifest, not the run's real total.

Net effect: actual run time regularly exceeds the "280s" figure and nothing
in the report tells the user (or the next debugging session) by how much or
why. This plan makes total elapsed time honest and visible, and closes the
biggest unbounded gap (bulk invocations).

## Approach

Don't try to preempt or interrupt agent reasoning turns (not measurable from
inside a script). Instead:

1. **Gate the bulk invocations too**, so the worst-case unbounded 540s
   disappears.
2. **Report the true total elapsed time** in the composed report, computed
   from the same `start_epoch` file, so any remaining agent-reasoning
   overrun is at least visible rather than silently absorbed.

## Changes

### 1. `shared/budget.py` — add a run-level elapsed helper
Add `run_elapsed_seconds(epoch_file: str) -> float | None` next to
`StageBudget`: reads the integer epoch written by SKILL.md step 1, returns
`time.time() - epoch`, or `None` if the file is missing/unreadable (never
raises — this is observability, not a gate). Centralizes the `date +%s`
arithmetic currently duplicated ad hoc in SKILL.md bash snippets.

### 2. `shared/finding_contract.py` — accept the total in `build_report`
Add optional `total_elapsed_seconds: float | None = None` param to
`build_report` (same additive pattern as existing `coverage` param, line
352/392-393). When given, attach `report["total_elapsed_seconds"] = round(...)`.
Update the schema/validator section (around line 432-441) only if it
enumerates optional fields explicitly — otherwise no validator change needed
since this mirrors `coverage`'s already-optional handling.

### 3. `skills/audit-orchestrator/scripts/compose_report.py` — wire it through
Add `--start-epoch-file` CLI arg (default `/tmp/audit/start_epoch`). Before
calling `compose(...)`, call `shared.budget.run_elapsed_seconds(args.start_epoch_file)`
and pass the result into `build_report`'s new param (via `compose`'s existing
`audited_at`-style passthrough).

### 4. `skills/audit-orchestrator/SKILL.md` — two edits
- **Step 5**: extend the existing deadline-check paragraph so it also covers
  the 6 bulk `--sample-file` invocations, not just per-URL calls: check
  elapsed before each; if already ≥280s, skip that invocation entirely
  (no output file — same "compose_report treats it like a smaller sample"
  handling already documented at line 111-112, no new code path needed).
  Remove the current line 104-106 clause that explicitly carves bulk mode
  out of the check.
- **Step 6**: add `--start-epoch-file /tmp/audit/start_epoch` to the
  `compose_report.py` example invocation so the real total is captured.

### 5. `skills/audit-orchestrator/references/orchestration-notes.md`
Add a short note under the existing "Why the sample is priority-ordered..."
section explaining: bulk invocations are now deadline-gated like per-page
ones (closing the ~540s unbounded worst case), and `total_elapsed_seconds`
in the report makes any remaining agent-reasoning-turn overrun visible
instead of silently unmeasured.

### 6. Tests
- `tests/test_budget.py`: unit tests for `run_elapsed_seconds` (valid file,
  missing file → `None`, malformed content → `None`).
- `tests/test_finding_contract.py`: `build_report` with/without
  `total_elapsed_seconds` — field present/absent as expected, rounding.
- `tests/test_orchestrator.py` (wherever `compose_report.py`'s CLI is
  exercised): `--start-epoch-file` pointing at a temp file with a known past
  epoch produces the expected `total_elapsed_seconds` in output; missing file
  → field omitted, no crash.

## Verification
- `python3 -m pytest tests/test_budget.py tests/test_finding_contract.py tests/test_orchestrator.py -q`
- Manual: `date +%s > /tmp/audit/start_epoch`, sleep a few seconds, run
  `compose_report.py --start-epoch-file /tmp/audit/start_epoch ...` on
  existing sample skill outputs, confirm `total_elapsed_seconds` appears and
  is roughly correct.
- Full suite: `python3 -m pytest -q` to confirm no regressions.

## Status: IMPLEMENTED — all 6 changes done, full test suite green (1371 passed), manual verification confirmed `total_elapsed_seconds` computed correctly. Not yet committed.
