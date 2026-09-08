"""Stage budget & coverage ledger (shared infrastructure, INF-10).

Every multi-page capability (Phase 3/4: engagement grounding, near-duplicate
detection, cross-page consistency) runs a bounded but still potentially large
number of comparisons — a worked example is ~30 sampled pages, ~450 pairwise
comparisons for near-duplicate detection. None of
that is safe to ship inside a 5-minute audit budget without a cap: a `for`
loop over every page pair with no time awareness either finishes fast on a
small site or silently blows the budget on a large one.

`StageBudget` is a monotonic-clock cap a long-running stage checks between
units of work (each page pair, each page) and stops starting new units once
expired — it is cooperative, not preemptive: nothing here interrupts a unit of
work already in flight. When a stage is cut off partway through,
`unreached_capability_unknowns` turns "we didn't get to check this" into a
typed `UnknownCheck` naming the cap as the reason, instead of the capability
silently vanishing from the report — the same "reduced coverage is reported,
never hidden" posture already documented in
skills/audit-orchestrator/SKILL.md.

Pure stdlib, no network, no file I/O.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from finding_contract import UnknownCheck


class StageBudget:
    """A monotonic-clock cap on one pipeline stage's wall-clock time.

    Starts timing at construction, not at some later `start()` call — a
    stage's budget begins the moment it is entered, matching how a caller
    actually uses it (`budget = StageBudget(...)` right before the loop it
    bounds).
    """

    def __init__(
        self,
        stage: str,
        cap_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.stage = stage
        self.cap_seconds = cap_seconds
        self._clock = clock
        self._started_at = clock()

    def elapsed(self) -> float:
        return self._clock() - self._started_at

    def remaining(self) -> float:
        return max(0.0, self.cap_seconds - self.elapsed())

    def expired(self) -> bool:
        return self.elapsed() >= self.cap_seconds

    def manifest(self) -> dict:
        return {
            "stage": self.stage,
            "cap_seconds": self.cap_seconds,
            "elapsed_seconds": round(self.elapsed(), 3),
            "expired": self.expired(),
        }


def unreached_capability_unknowns(
    owner_skill: str,
    budget: StageBudget,
    all_capability_ids: list[str],
    reached_capability_ids: set[str],
) -> list[UnknownCheck]:
    """One `UnknownCheck` per capability in `all_capability_ids` not present
    in `reached_capability_ids`, naming `budget`'s cap as the reason.

    Returns `[]` when `budget` has not actually expired: a capability that
    simply hasn't run *yet* in a stage that still has time left is not yet a
    coverage gap, and manufacturing one here would misreport "still working"
    as "gave up."
    """
    if not budget.expired():
        return []
    return [
        UnknownCheck(
            capability_id=capability_id,
            owner_skill=owner_skill,
            reason=(
                f"{budget.stage} stage budget of {budget.cap_seconds}s was exceeded "
                f"({budget.elapsed():.1f}s elapsed) before {capability_id} could run"
            ),
        )
        for capability_id in all_capability_ids
        if capability_id not in reached_capability_ids
    ]


def coverage_manifest(budgets: list[StageBudget]) -> dict:
    """Attachable report section summarising every stage's budget, for
    `finding_contract.build_report`'s optional `coverage` parameter — a
    reviewer reading the report can see which stages ran to completion and
    which were cut off, without cross-referencing `unknown_checks` reasons."""
    return {"stages": [b.manifest() for b in budgets]}
