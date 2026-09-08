"""Coverage for shared/judgement_merge.py (cycle 24 item 9): the optional
merge helper that validates agent-authored Finding-shaped judgements before
appending them to a report's `findings` and removing
`agent_judgement_required`."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "shared"))

from judgement_merge import JudgementMergeError, merge_judgements


def _valid_finding(finding_id: str = "CQ-01-example") -> dict:
    return {
        "id": finding_id,
        "title": "Example finding",
        "severity": "medium",
        "evidence": "The opening block never answers the implied question.",
        "suggested_action": {"summary": "Answer the question in the first 150 words.", "priority": "medium"},
        "category": "discoverability",
        "capability_id": "CQ-01",
        "owner_skill": "content-quality-audit",
        "mechanism": "An assistant windows only the opening text when deciding whether to quote a page.",
        "gate": 2,
        "confidence": "high",
    }


class MergeHappyPathTests(unittest.TestCase):
    def test_a_valid_judgement_is_appended_and_the_stub_key_removed(self):
        report = {"findings": [], "agent_judgement_required": [{"capability_id": "CQ-01"}]}
        merged = merge_judgements(report, [_valid_finding()])
        self.assertEqual(len(merged["findings"]), 1)
        self.assertEqual(merged["findings"][0]["id"], "CQ-01-example")
        self.assertNotIn("agent_judgement_required", merged)

    def test_an_empty_judgement_list_still_removes_the_stub_key(self):
        report = {"findings": [], "agent_judgement_required": []}
        merged = merge_judgements(report, [])
        self.assertEqual(merged["findings"], [])
        self.assertNotIn("agent_judgement_required", merged)

    def test_existing_findings_are_preserved_alongside_the_new_one(self):
        existing = _valid_finding("CQ-02-existing")
        report = {"findings": [existing], "agent_judgement_required": []}
        merged = merge_judgements(report, [_valid_finding("CQ-01-new")])
        ids = {f["id"] for f in merged["findings"]}
        self.assertEqual(ids, {"CQ-02-existing", "CQ-01-new"})

    def test_the_input_report_and_judgements_are_not_mutated(self):
        report = {"findings": [], "agent_judgement_required": [{"capability_id": "CQ-01"}]}
        judgements = [_valid_finding()]
        merge_judgements(report, judgements)
        self.assertIn("agent_judgement_required", report)
        self.assertEqual(report["findings"], [])
        self.assertEqual(judgements, [_valid_finding()])

    def test_multiple_valid_judgements_are_all_appended(self):
        report = {"findings": [], "agent_judgement_required": []}
        merged = merge_judgements(report, [_valid_finding("CQ-01-a"), _valid_finding("CQ-01-b")])
        ids = {f["id"] for f in merged["findings"]}
        self.assertEqual(ids, {"CQ-01-a", "CQ-01-b"})


class MergeRejectionTests(unittest.TestCase):
    def test_a_malformed_judgement_is_rejected_and_nothing_is_merged(self):
        bad = _valid_finding()
        del bad["evidence"]
        report = {"findings": [], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError) as ctx:
            merge_judgements(report, [bad])
        self.assertIn("evidence is empty", str(ctx.exception))

    def test_the_error_names_the_offending_judgements_id(self):
        bad = _valid_finding("CQ-01-bad-severity")
        bad["severity"] = "not-a-real-severity"
        report = {"findings": [], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError) as ctx:
            merge_judgements(report, [bad])
        self.assertIn("CQ-01-bad-severity", str(ctx.exception))

    def test_a_duplicate_id_against_an_existing_finding_is_rejected(self):
        existing = _valid_finding("CQ-01-dup")
        report = {"findings": [existing], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError) as ctx:
            merge_judgements(report, [_valid_finding("CQ-01-dup")])
        self.assertIn("id already present", str(ctx.exception))

    def test_one_bad_judgement_blocks_the_good_ones_in_the_same_call(self):
        """Nothing is partially applied: a batch with one bad judgement
        merges none of them, good or bad."""
        bad = _valid_finding("CQ-01-bad")
        del bad["title"]
        report = {"findings": [], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError):
            merge_judgements(report, [_valid_finding("CQ-01-good"), bad])
        # Confirm the original report truly was never touched.
        self.assertEqual(report["findings"], [])

    def test_multiple_bad_judgements_are_all_named_in_one_error(self):
        bad_one = _valid_finding("CQ-01-bad-one")
        del bad_one["evidence"]
        bad_two = _valid_finding("CQ-01-bad-two")
        bad_two["severity"] = "nonsense"
        report = {"findings": [], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError) as ctx:
            merge_judgements(report, [bad_one, bad_two])
        message = str(ctx.exception)
        self.assertIn("CQ-01-bad-one", message)
        self.assertIn("CQ-01-bad-two", message)

    def test_a_judgement_missing_an_id_is_still_named_by_its_index(self):
        bad = _valid_finding()
        bad["id"] = ""
        report = {"findings": [], "agent_judgement_required": []}
        with self.assertRaises(JudgementMergeError) as ctx:
            merge_judgements(report, [bad])
        self.assertIn("judgement[0]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
