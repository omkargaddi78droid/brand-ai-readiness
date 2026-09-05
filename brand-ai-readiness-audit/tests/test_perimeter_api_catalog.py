"""Unit tests for PER-10 — RFC 9727 API catalog discovery (cycle 23, Phase 2).

Same positive/negative-pair convention as PER-05/06/07/08
(tests/test_perimeter_extras.py). The dominant false positive this project's
calibration discipline requires a fixture for: an SPA's client-side-routing
catch-all answering *every* unmatched path — including
/.well-known/api-catalog — with its index.html at HTTP 200. Since this is a
brand-new (2024) RFC with essentially no adoption yet, treating that as "the
wrong Content-Type" would flag nearly every site that has not implemented
it, rather than only the sites that tried and got it wrong.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "corpus" / "perimeter_api_catalog"
sys.path.insert(0, str(REPO_ROOT / "shared"))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "check_perimeter", REPO_ROOT / "skills/perimeter-access-audit/scripts/check_perimeter.py"
)
per = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(per)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


LINKSET_HEADERS = {"content-type": "application/linkset+json"}


class ApiCatalogAbsentOrUnknownTests(unittest.TestCase):
    def test_a_confirmed_404_is_not_a_finding(self):
        """Zero adoption pressure yet for a 2024 RFC — unlike llms.txt,
        absence alone is not worth a proactive suggestion."""
        findings, unknowns = per.evaluate_api_catalog(None, {}, "absent")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_unreachable_is_unknown_not_a_verdict(self):
        findings, unknowns = per.evaluate_api_catalog("timeout", {}, "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-10"])


class ApiCatalogSoftFalsePositiveTests(unittest.TestCase):
    def test_an_spa_catch_all_html_response_is_not_flagged(self):
        """The dominant false positive: an SPA serving its index.html for
        every unmatched route, including this one, at HTTP 200."""
        html = "<!doctype html><html><head></head><body><div id='root'></div></body></html>"
        findings, unknowns = per.evaluate_api_catalog(html, {"content-type": "text/html"}, "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])


class ApiCatalogWrongContentTypeTests(unittest.TestCase):
    def test_a_json_body_served_as_plain_json_is_flagged(self):
        findings, _ = per.evaluate_api_catalog(
            fixture("api_catalog_valid.json"), {"content-type": "application/json"}, "present"
        )
        self.assertEqual([f.id for f in findings], ["PER-10-api-catalog-wrong-content-type"])
        self.assertEqual(findings[0].track, "defect")
        self.assertEqual(findings[0].severity, "low")


class ApiCatalogMalformedTests(unittest.TestCase):
    def test_a_valid_linkset_produces_nothing(self):
        findings, unknowns = per.evaluate_api_catalog(fixture("api_catalog_valid.json"), LINKSET_HEADERS, "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_linkset_entry_missing_service_desc_is_flagged(self):
        findings, _ = per.evaluate_api_catalog(
            fixture("api_catalog_missing_service_desc.json"), LINKSET_HEADERS, "present"
        )
        self.assertEqual([f.id for f in findings], ["PER-10-api-catalog-malformed"])
        self.assertIn("service-desc", findings[0].evidence)

    def test_invalid_json_is_flagged_malformed(self):
        findings, _ = per.evaluate_api_catalog("not json at all {{{", LINKSET_HEADERS, "present")
        self.assertEqual([f.id for f in findings], ["PER-10-api-catalog-malformed"])

    def test_missing_linkset_key_is_flagged_malformed(self):
        findings, _ = per.evaluate_api_catalog('{"other": []}', LINKSET_HEADERS, "present")
        self.assertEqual([f.id for f in findings], ["PER-10-api-catalog-malformed"])


class ContractComplianceTests(unittest.TestCase):
    def test_every_finding_validates(self):
        for fetch_args in [
            (fixture("api_catalog_missing_service_desc.json"), LINKSET_HEADERS, "present"),
            (fixture("api_catalog_valid.json"), {"content-type": "application/json"}, "present"),
        ]:
            findings, _ = per.evaluate_api_catalog(*fetch_args)
            for finding in findings:
                self.assertEqual(finding.validate(), [])


if __name__ == "__main__":
    unittest.main()
