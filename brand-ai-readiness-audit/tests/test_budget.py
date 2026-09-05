"""Unit tests for shared/budget.py (INF-10: stage budget + coverage ledger,
cycle 23 Phase 1).

A fake clock is injected everywhere instead of sleeping real time — these
tests must stay fast and deterministic.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from budget import StageBudget, coverage_manifest, unreached_capability_unknowns  # noqa: E402


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class StageBudgetTests(unittest.TestCase):
    def test_elapsed_is_zero_at_construction(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        self.assertEqual(budget.elapsed(), 0.0)

    def test_elapsed_tracks_the_injected_clock(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(4)
        self.assertEqual(budget.elapsed(), 4.0)

    def test_remaining_counts_down_and_floors_at_zero(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(7)
        self.assertEqual(budget.remaining(), 3.0)
        clock.advance(10)
        self.assertEqual(budget.remaining(), 0.0)

    def test_expired_is_false_before_the_cap(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(9.9)
        self.assertFalse(budget.expired())

    def test_expired_is_true_at_and_past_the_cap(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(10)
        self.assertTrue(budget.expired())

    def test_manifest_reports_stage_cap_elapsed_and_expired(self):
        clock = _FakeClock()
        budget = StageBudget("near-duplicate-detection", cap_seconds=60, clock=clock)
        clock.advance(15)
        manifest = budget.manifest()
        self.assertEqual(manifest["stage"], "near-duplicate-detection")
        self.assertEqual(manifest["cap_seconds"], 60)
        self.assertEqual(manifest["elapsed_seconds"], 15.0)
        self.assertFalse(manifest["expired"])


class UnreachedCapabilityUnknownsTests(unittest.TestCase):
    def test_returns_nothing_when_the_budget_has_not_expired(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(1)
        unknowns = unreached_capability_unknowns(
            "some-skill", budget, ["CAP-01", "CAP-02"], reached_capability_ids=set()
        )
        self.assertEqual(unknowns, [])

    def test_only_unreached_capabilities_become_unknowns(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=10, clock=clock)
        clock.advance(10)
        unknowns = unreached_capability_unknowns(
            "some-skill", budget, ["CAP-01", "CAP-02", "CAP-03"], reached_capability_ids={"CAP-01"}
        )
        self.assertEqual({u.capability_id for u in unknowns}, {"CAP-02", "CAP-03"})

    def test_unknown_reason_names_the_stage_and_cap(self):
        clock = _FakeClock()
        budget = StageBudget("near-duplicate-detection", cap_seconds=30, clock=clock)
        clock.advance(30)
        unknowns = unreached_capability_unknowns(
            "content-quality-audit", budget, ["CAP-01"], reached_capability_ids=set()
        )
        self.assertEqual(len(unknowns), 1)
        self.assertIn("near-duplicate-detection", unknowns[0].reason)
        self.assertIn("30", unknowns[0].reason)

    def test_owner_skill_is_carried_onto_every_unknown(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=5, clock=clock)
        clock.advance(5)
        unknowns = unreached_capability_unknowns(
            "content-quality-audit", budget, ["CAP-01"], reached_capability_ids=set()
        )
        self.assertEqual(unknowns[0].owner_skill, "content-quality-audit")

    def test_all_capabilities_already_reached_yields_nothing_even_when_expired(self):
        clock = _FakeClock()
        budget = StageBudget("test-stage", cap_seconds=5, clock=clock)
        clock.advance(5)
        unknowns = unreached_capability_unknowns(
            "some-skill", budget, ["CAP-01"], reached_capability_ids={"CAP-01"}
        )
        self.assertEqual(unknowns, [])


class CoverageManifestTests(unittest.TestCase):
    def test_summarises_every_stage_budget_given(self):
        clock = _FakeClock()
        budget_a = StageBudget("stage-a", cap_seconds=10, clock=clock)
        clock.advance(3)
        budget_b = StageBudget("stage-b", cap_seconds=5, clock=clock)
        clock.advance(5)
        manifest = coverage_manifest([budget_a, budget_b])
        self.assertEqual(len(manifest["stages"]), 2)
        self.assertEqual(manifest["stages"][0]["stage"], "stage-a")
        self.assertEqual(manifest["stages"][1]["stage"], "stage-b")
        self.assertTrue(manifest["stages"][1]["expired"])

    def test_an_empty_budget_list_yields_an_empty_stages_list(self):
        self.assertEqual(coverage_manifest([]), {"stages": []})


if __name__ == "__main__":
    unittest.main()
