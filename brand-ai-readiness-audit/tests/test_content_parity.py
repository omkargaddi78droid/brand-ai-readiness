"""PER-11 (AI-crawler content-parity diff / cloaking) tests, cycle 23 Phase 2.

Everything here is pure: `evaluate_content_parity`, `_visible_text_length`,
`_json_ld_node_count`. Only `fetch_full_body_with_user_agent` and
`fetch_and_evaluate_content_parity` touch the network — same split as
PER-03's own test_edge_access.py, and for the same reason: those two are
exercised live, not in this suite.

Distinct from PER-03 throughout: every case below uses HTTP 200 for both
the browser and the crawler fetch. A blocked/challenged crawler request is
PER-03's finding, not this one's — evaluate_content_parity must stay silent
whenever either status isn't a plain 200.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

_spec = importlib.util.spec_from_file_location(
    "check_perimeter", REPO_ROOT / "skills/perimeter-access-audit/scripts/check_perimeter.py"
)
perimeter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perimeter)

_FULL_PAGE = (
    "<html><body><h1>Welcome</h1>"
    "<p>" + ("Real product content that a visitor or search crawler should see. " * 10) + "</p>"
    '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>'
    "</body></html>"
)


class VisibleTextLengthTests(unittest.TestCase):
    def test_counts_visible_text_only(self):
        html = "<p>Hello world</p><script>ignored();</script>"
        self.assertEqual(perimeter._visible_text_length(html), len("Hello world"))

    def test_empty_page_is_zero(self):
        self.assertEqual(perimeter._visible_text_length(""), 0)


class JsonLdNodeCountTests(unittest.TestCase):
    def test_counts_one_node_per_block(self):
        html = '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>'
        self.assertEqual(perimeter._json_ld_node_count(html), 1)

    def test_no_json_ld_is_zero(self):
        self.assertEqual(perimeter._json_ld_node_count("<html><body>Hi</body></html>"), 0)

    def test_malformed_json_ld_is_silently_zero(self):
        html = '<script type="application/ld+json">not json</script>'
        self.assertEqual(perimeter._json_ld_node_count(html), 0)


class EvaluateContentParityTests(unittest.TestCase):
    def test_identical_content_is_silent(self):
        finding = perimeter.evaluate_content_parity(
            "ai_search", "OAI-SearchBot", 200, _FULL_PAGE, 200, _FULL_PAGE
        )
        self.assertIsNone(finding)

    def test_a_thin_crawler_response_fires(self):
        thin_html = "<html><body><h1>Welcome</h1></body></html>"
        finding = perimeter.evaluate_content_parity(
            "ai_search", "OAI-SearchBot", 200, _FULL_PAGE, 200, thin_html
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-11-ai-search-content-parity")
        self.assertEqual(finding.severity, "critical")
        self.assertEqual(finding.confidence, "medium")

    def test_missing_json_ld_alone_fires(self):
        """Same visible text length, but the crawler's copy carries no
        structured data the browser's copy has — a distinct signal from
        thin text, and either one alone must be sufficient to fire."""
        no_jsonld_html = _FULL_PAGE.replace(
            '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>', ""
        )
        finding = perimeter.evaluate_content_parity(
            "training", "GPTBot", 200, _FULL_PAGE, 200, no_jsonld_html
        )
        self.assertIsNotNone(finding)
        self.assertIn("JSON-LD", finding.evidence)

    def test_a_non_200_browser_status_is_silent_not_a_finding(self):
        """PER-11 needs a genuine browser baseline; a browser-side failure
        means there is nothing trustworthy to compare against, not evidence
        of anything about the crawler's response."""
        finding = perimeter.evaluate_content_parity("ai_search", "OAI-SearchBot", 503, None, 200, _FULL_PAGE)
        self.assertIsNone(finding)

    def test_a_blocked_crawler_status_is_silent_this_is_pers_03_job(self):
        finding = perimeter.evaluate_content_parity("ai_search", "OAI-SearchBot", 200, _FULL_PAGE, 403, None)
        self.assertIsNone(finding)

    def test_an_empty_browser_page_is_silent_nothing_to_compare_against(self):
        finding = perimeter.evaluate_content_parity("ai_search", "OAI-SearchBot", 200, "", 200, "")
        self.assertIsNone(finding)

    def test_finding_validates_against_the_shared_contract(self):
        thin_html = "<html><body><h1>Welcome</h1></body></html>"
        finding = perimeter.evaluate_content_parity(
            "ai_search", "OAI-SearchBot", 200, _FULL_PAGE, 200, thin_html
        )
        self.assertEqual(finding.validate(), [])

    def test_severity_follows_the_same_tier_severity_table_as_per_03(self):
        thin_html = "<html><body><h1>Welcome</h1></body></html>"
        training_finding = perimeter.evaluate_content_parity(
            "training", "GPTBot", 200, _FULL_PAGE, 200, thin_html
        )
        self.assertEqual(training_finding.severity, perimeter.TIER_SEVERITY["training"][0])


if __name__ == "__main__":
    unittest.main()
