"""Contract tests for shared/finding_contract.py (INF-05)."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import (  # noqa: E402
    Finding,
    SuggestedAction,
    UnknownCheck,
    assign_sequential_ids,
    build_report,
    to_floor_schema,
    validate_findings,
    validate_floor_shape,
)

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"


def make_finding(**overrides) -> Finding:
    defaults = dict(
        id="PER-01-ai-search-blocked",
        title="robots.txt blocks real-time AI search crawlers",
        severity="critical",
        evidence="robots.txt disallows / for 4/4 real-time AI search crawlers.",
        suggested_action=SuggestedAction(summary="Remove the disallow.", priority="critical"),
        category="discoverability",
        capability_id="PER-01",
        owner_skill="perimeter-access-audit",
        mechanism="A page that is never fetched cannot be cited.",
        gate=1,
    )
    defaults.update(overrides)
    return Finding(**defaults)


class ValidationTests(unittest.TestCase):
    def test_a_well_formed_finding_validates(self):
        self.assertEqual(make_finding().validate(), [])

    def test_empty_evidence_is_rejected(self):
        errors = make_finding(evidence="   ").validate()
        self.assertIn("evidence is empty", errors)

    def test_missing_mechanism_is_rejected(self):
        errors = make_finding(mechanism="").validate()
        self.assertTrue(any("mechanism is empty" in error for error in errors))

    def test_unknown_severity_is_rejected(self):
        errors = make_finding(severity="catastrophic").validate()
        self.assertTrue(any("severity not in" in error for error in errors))

    def test_duplicate_ids_are_reported(self):
        errors = validate_findings([make_finding(), make_finding()])
        self.assertTrue(any("duplicate finding id" in error for error in errors))

    def test_build_report_refuses_invalid_findings(self):
        with self.assertRaises(ValueError):
            build_report("example.com", [make_finding(evidence="")], audited_at=FIXED_TIMESTAMP)

    def test_build_report_attaches_a_given_coverage_manifest_verbatim(self):
        coverage = {"stages": [{"stage": "near-duplicate-detection", "expired": True}]}
        report = build_report("example.com", [], audited_at=FIXED_TIMESTAMP, coverage=coverage)
        self.assertEqual(report["coverage"], coverage)

    def test_build_report_omits_coverage_when_not_given(self):
        report = build_report("example.com", [], audited_at=FIXED_TIMESTAMP)
        self.assertNotIn("coverage", report)


class ReportShapeTests(unittest.TestCase):
    def setUp(self):
        self.findings = assign_sequential_ids(
            [
                make_finding(id="PER-04-llms-txt-missing", severity="low", track="proactive"),
                make_finding(id="PER-01-ai-search-blocked", severity="critical"),
                make_finding(id="PER-01-training-blocked", severity="medium"),
            ]
        )
        self.report = build_report(
            "example.com",
            self.findings,
            [UnknownCheck("PER-02", "perimeter-access-audit", "robots.txt could not be fetched")],
            audited_at=FIXED_TIMESTAMP,
        )

    def test_report_satisfies_the_required_schema(self):
        self.assertEqual(validate_floor_shape(self.report), [])

    def test_summary_counts_match_the_findings(self):
        self.assertEqual(self.report["summary"]["total_findings"], 3)
        self.assertEqual(self.report["summary"]["critical"], 1)
        self.assertEqual(self.report["summary"]["medium"], 1)
        self.assertEqual(self.report["summary"]["low"], 1)
        self.assertEqual(self.report["summary"]["defects"], 2)
        self.assertEqual(self.report["summary"]["proactive_suggestions"], 1)
        self.assertEqual(self.report["summary"]["checks_unknown"], 1)

    def test_unknown_checks_are_reported_not_dropped(self):
        self.assertEqual(len(self.report["unknown_checks"]), 1)
        self.assertEqual(self.report["unknown_checks"][0]["capability_id"], "PER-02")

    def test_defects_precede_proactive_suggestions_and_sort_by_severity(self):
        order = [(f["severity"], f["track"]) for f in self.report["findings"]]
        self.assertEqual(order, [("critical", "defect"), ("medium", "defect"), ("low", "proactive")])

    def test_ids_are_sequential_and_preserve_the_semantic_id(self):
        self.assertEqual([f["id"] for f in self.report["findings"]], ["F-001", "F-002", "F-003"])
        self.assertEqual(self.report["findings"][0]["check_id"], "PER-01-ai-search-blocked")

    def test_floor_projection_carries_exactly_the_required_fields(self):
        floor = to_floor_schema(self.report)
        self.assertEqual(set(floor), {"site", "audited_at", "summary", "findings"})
        self.assertEqual(set(floor["summary"]), {"total_findings", "critical", "high", "medium"})
        self.assertEqual(
            set(floor["findings"][0]),
            {"id", "title", "severity", "evidence", "suggested_action"},
        )
        self.assertEqual(set(floor["findings"][0]["suggested_action"]), {"summary", "priority"})
        self.assertEqual(validate_floor_shape(floor), [])

    def test_report_is_deterministic(self):
        again = build_report(
            "example.com",
            assign_sequential_ids(
                [
                    make_finding(id="PER-01-training-blocked", severity="medium"),
                    make_finding(id="PER-04-llms-txt-missing", severity="low", track="proactive"),
                    make_finding(id="PER-01-ai-search-blocked", severity="critical"),
                ]
            ),
            [UnknownCheck("PER-02", "perimeter-access-audit", "robots.txt could not be fetched")],
            audited_at=FIXED_TIMESTAMP,
        )
        self.assertEqual(again, self.report)


class RoundTripTests(unittest.TestCase):
    def test_finding_survives_serialisation(self):
        original = make_finding(structured_evidence={"blocked": ["GPTBot"]}, confidence="medium")
        self.assertEqual(Finding.from_dict(original.to_dict()), original)

    def test_unknown_check_survives_serialisation(self):
        original = UnknownCheck("PER-01", "perimeter-access-audit", "timeout after 10s")
        self.assertEqual(UnknownCheck.from_dict(original.to_dict()), original)


class FloorShapeGuardTests(unittest.TestCase):
    def test_count_disagreement_is_caught(self):
        report = build_report("example.com", [make_finding()], audited_at=FIXED_TIMESTAMP)
        report["summary"]["critical"] = 0
        self.assertTrue(any("disagrees with the findings" in e for e in validate_floor_shape(report)))

    def test_bad_timestamp_is_caught(self):
        report = build_report("example.com", [make_finding()], audited_at=FIXED_TIMESTAMP)
        report["audited_at"] = "20 September 2026"
        self.assertTrue(any("audited_at" in e for e in validate_floor_shape(report)))

    def test_missing_suggested_action_is_caught(self):
        report = build_report("example.com", [make_finding()], audited_at=FIXED_TIMESTAMP)
        del report["findings"][0]["suggested_action"]
        self.assertTrue(any("suggested_action" in e for e in validate_floor_shape(report)))


if __name__ == "__main__":
    unittest.main()
