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
    cap_list,
    merge_paginated_findings,
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

    def test_build_report_attaches_total_elapsed_seconds_rounded(self):
        report = build_report(
            "example.com", [], audited_at=FIXED_TIMESTAMP, total_elapsed_seconds=142.567
        )
        self.assertEqual(report["total_elapsed_seconds"], 142.6)

    def test_build_report_omits_total_elapsed_seconds_when_not_given(self):
        report = build_report("example.com", [], audited_at=FIXED_TIMESTAMP)
        self.assertNotIn("total_elapsed_seconds", report)


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


class MergeTests(unittest.TestCase):
    def test_a_singleton_id_passes_through_unchanged(self):
        findings = [make_finding(structured_evidence={"page_url": "https://example.com/"})]
        self.assertEqual(merge_paginated_findings(findings), findings)

    def test_two_pages_merge_into_one_finding(self):
        page1 = make_finding(
            evidence="On https://example.com/a: 5 of 6 images unsized.",
            structured_evidence={"page_url": "https://example.com/a", "unsized_count": 5},
        )
        page2 = make_finding(
            evidence="On https://example.com/b: 3 of 3 images unsized.",
            structured_evidence={"page_url": "https://example.com/b", "unsized_count": 3},
        )
        merged = merge_paginated_findings([page1, page2])

        self.assertEqual(len(merged), 1)
        result = merged[0]
        self.assertEqual(
            result.evidence,
            "Found on 2 pages:\n"
            "- On https://example.com/a: 5 of 6 images unsized.\n"
            "- On https://example.com/b: 3 of 3 images unsized.",
        )
        self.assertEqual(result.structured_evidence["affected_page_count"], 2)
        self.assertEqual(
            [p["page_url"] for p in result.structured_evidence["pages"]],
            ["https://example.com/a", "https://example.com/b"],
        )

    def test_identity_field_mismatch_raises(self):
        page1 = make_finding(severity="critical", structured_evidence={"page_url": "https://example.com/a"})
        page2 = make_finding(severity="low", structured_evidence={"page_url": "https://example.com/b"})
        with self.assertRaises(ValueError):
            merge_paginated_findings([page1, page2])

    def test_suggested_action_priority_mismatch_raises(self):
        page1 = make_finding(
            suggested_action=SuggestedAction(summary="Fix it.", priority="critical"),
            structured_evidence={"page_url": "https://example.com/a"},
        )
        page2 = make_finding(
            suggested_action=SuggestedAction(summary="Fix it too.", priority="low"),
            structured_evidence={"page_url": "https://example.com/b"},
        )
        with self.assertRaises(ValueError):
            merge_paginated_findings([page1, page2])

    def test_missing_page_url_raises(self):
        page1 = make_finding(structured_evidence={"page_url": "https://example.com/a"})
        page2 = make_finding(structured_evidence=None)
        with self.assertRaises(ValueError):
            merge_paginated_findings([page1, page2])

    def test_duplicate_page_url_in_group_raises(self):
        page1 = make_finding(structured_evidence={"page_url": "https://example.com/a"})
        page2 = make_finding(structured_evidence={"page_url": "https://example.com/a"})
        with self.assertRaises(ValueError):
            merge_paginated_findings([page1, page2])

    def test_differing_confidence_resolves_to_the_weakest(self):
        page1 = make_finding(confidence="high", structured_evidence={"page_url": "https://example.com/a"})
        page2 = make_finding(confidence="low", structured_evidence={"page_url": "https://example.com/b"})
        merged = merge_paginated_findings([page1, page2])
        self.assertEqual(merged[0].confidence, "low")

    def test_differing_suggested_action_summary_merges_via_lexicographically_first_page(self):
        page_b = make_finding(
            suggested_action=SuggestedAction(summary="Fix field X missing on b.", priority="critical"),
            structured_evidence={"page_url": "https://example.com/b"},
        )
        page_a = make_finding(
            suggested_action=SuggestedAction(summary="Fix field Y missing on a.", priority="critical"),
            structured_evidence={"page_url": "https://example.com/a"},
        )
        merged = merge_paginated_findings([page_b, page_a])
        self.assertEqual(merged[0].suggested_action.summary, "Fix field Y missing on a.")


class CapListTests(unittest.TestCase):
    def test_empty_list(self):
        shown, total = cap_list([], 10)
        self.assertEqual(shown, [])
        self.assertEqual(total, 0)

    def test_under_limit_is_untouched(self):
        shown, total = cap_list([1, 2, 3], 10)
        self.assertEqual(shown, [1, 2, 3])
        self.assertEqual(total, 3)

    def test_at_limit_is_untouched(self):
        shown, total = cap_list([1, 2, 3], 3)
        self.assertEqual(shown, [1, 2, 3])
        self.assertEqual(total, 3)

    def test_over_limit_is_truncated_but_total_is_true_count(self):
        shown, total = cap_list(list(range(15)), 10)
        self.assertEqual(shown, list(range(10)))
        self.assertEqual(total, 15)


class MergeCappingTests(unittest.TestCase):
    def _make_group(self, count: int) -> list[Finding]:
        return [
            make_finding(
                evidence=f"On https://example.com/p{i}: unsized.",
                structured_evidence={"page_url": f"https://example.com/p{i}", "unsized_count": i},
            )
            for i in range(count)
        ]

    def test_structured_evidence_pages_capped_at_ten_but_count_is_true_total(self):
        merged = merge_paginated_findings(self._make_group(15))
        result = merged[0]
        self.assertEqual(len(result.structured_evidence["pages"]), 10)
        self.assertEqual(result.structured_evidence["affected_page_count"], 15)

    def test_evidence_prose_states_true_total_and_notes_the_overflow(self):
        merged = merge_paginated_findings(self._make_group(15))
        result = merged[0]
        self.assertIn("Found on 15 pages:", result.evidence)
        self.assertIn("(+5 more)", result.evidence)

    def test_exactly_ten_pages_is_not_marked_as_truncated(self):
        merged = merge_paginated_findings(self._make_group(10))
        result = merged[0]
        self.assertEqual(len(result.structured_evidence["pages"]), 10)
        self.assertEqual(result.structured_evidence["affected_page_count"], 10)
        self.assertNotIn("more)", result.evidence)


if __name__ == "__main__":
    unittest.main()
