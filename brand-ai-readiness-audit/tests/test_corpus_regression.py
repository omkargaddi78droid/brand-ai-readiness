"""The labelled corpus as a regression gate.

`measure_detection.py` reports the numbers; this asserts they stay perfect.
Any new false positive, missed detection, wrong severity or invalid report
fails the suite with the offending case named.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "shared"))

_spec = importlib.util.spec_from_file_location("measure_detection", TESTS_DIR / "measure_detection.py")
measure_detection = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure_detection)

perimeter = measure_detection.perimeter


class CorpusRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measurement = measure_detection.measure()

    def test_no_false_positives(self):
        offenders = {
            r["id"]: r["false_positives"] for r in self.measurement["results"] if r["false_positives"]
        }
        self.assertEqual(offenders, {})

    def test_no_missed_detections(self):
        offenders = {
            r["id"]: r["false_negatives"] for r in self.measurement["results"] if r["false_negatives"]
        }
        self.assertEqual(offenders, {})

    def test_severities_match_the_labels(self):
        offenders = {
            r["id"]: r["severity_errors"] for r in self.measurement["results"] if r["severity_errors"]
        }
        self.assertEqual(offenders, {})

    def test_unknown_checks_match_the_labels(self):
        offenders = {
            r["id"]: r["unknown_errors"] for r in self.measurement["results"] if r["unknown_errors"]
        }
        self.assertEqual(offenders, {})

    def test_every_case_composes_into_a_valid_report(self):
        offenders = {r["id"]: r["report_errors"] for r in self.measurement["results"] if r["report_errors"]}
        self.assertEqual(offenders, {})

    def test_the_corpus_still_contains_clean_cases(self):
        """Precision is only measurable against lookalikes that must stay silent."""
        totals = self.measurement["totals"]
        self.assertGreaterEqual(totals["clean_cases"], 8)
        self.assertGreater(totals["defect_cases"], 0)


class UserAgentMatchingTests(unittest.TestCase):
    """Group selection is ours because the standard library's is substring-based.

    Minimised from a live run: a group written for the historical `Fetch` bot
    was applied to `Meta-ExternalFetcher`, producing a confident wrong finding.
    """

    TRAP = "User-agent: *\nDisallow:\n\nUser-agent: Fetch\nDisallow: /\n"

    def test_a_group_token_is_not_matched_as_a_substring(self):
        groups = perimeter.parse_groups(self.TRAP)
        self.assertTrue(perimeter.can_fetch_root(groups, "Meta-ExternalFetcher"))

    def test_the_named_agent_is_still_matched(self):
        groups = perimeter.parse_groups(self.TRAP)
        self.assertFalse(perimeter.can_fetch_root(groups, "Fetch"))

    def test_matching_is_case_insensitive(self):
        groups = perimeter.parse_groups("User-agent: gptbot\nDisallow: /\n")
        self.assertFalse(perimeter.can_fetch_root(groups, "GPTBot"))

    def test_the_wildcard_group_is_the_fallback(self):
        groups = perimeter.parse_groups("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n")
        self.assertTrue(perimeter.can_fetch_root(groups, "GPTBot"))
        self.assertFalse(perimeter.can_fetch_root(groups, "ClaudeBot"))

    def test_no_rules_at_all_permits_everything(self):
        self.assertTrue(perimeter.can_fetch_root(perimeter.parse_groups(""), "GPTBot"))


class LlmsTxtFieldFixTests(unittest.TestCase):
    def test_asterisk_list_markers_are_valid_markdown(self):
        text = "# Brand\n\n> Summary.\n\n## Docs\n\n* [Start](https://example.com/a): how to begin.\n"
        self.assertEqual(perimeter.evaluate_llms_txt(text, "present")[0], [])

    def test_an_html_soft_404_is_reported_as_an_absence_not_a_malformed_file(self):
        html = "<!DOCTYPE html>\n<html><head><title>x</title></head><body>app</body></html>"
        findings, _ = perimeter.evaluate_llms_txt(html, "present")
        self.assertEqual([f.id for f in findings], ["PER-04-llms-txt-missing"])
        self.assertIn("soft 404", findings[0].evidence)


if __name__ == "__main__":
    unittest.main()
