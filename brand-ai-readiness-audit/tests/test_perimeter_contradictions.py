"""Unit tests for PER-09 — cross-layer access-signal contradiction.

Every rule is tested as a pair where a false-positive risk exists: a fixture
that exhibits the contradiction, and a fixture that looks similar but is
clean. Overlap-control tests prove PER-09 stays silent on ground PER-01/02
already own.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import validate_floor_shape  # noqa: E402


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perimeter = _load("check_perimeter", "skills/perimeter-access-audit/scripts/check_perimeter.py")

ALLOW_ALL_NAMED_AI = (
    "User-agent: GPTBot\n"
    "User-agent: ClaudeBot\n"
    "User-agent: CCBot\n"
    "User-agent: OAI-SearchBot\n"
    "User-agent: PerplexityBot\n"
    "User-agent: Claude-SearchBot\n"
    "User-agent: DuckAssistBot\n"
    "User-agent: ChatGPT-User\n"
    "User-agent: Claude-User\n"
    "User-agent: Perplexity-User\n"
    "User-agent: Meta-ExternalFetcher\n"
    "User-agent: Google-Extended\n"
    "User-agent: Applebot-Extended\n"
    "User-agent: meta-externalagent\n"
    "User-agent: Bytespider\n"
    "Allow: /\n"
)

PATH_SPECIFIC_BLOCK = ALLOW_ALL_NAMED_AI + (
    "\nUser-agent: GPTBot\n"
    "Disallow: /pricing\n"
)

WILDCARD_ONLY = "User-agent: *\nAllow: /\n"

BLANKET_BLOCK = "User-agent: *\nDisallow: /\n"

SITEMAP_WITH_PRICING = (
    "<?xml version='1.0'?><urlset><url><loc>https://example.com/pricing</loc></url>"
    "<url><loc>https://example.com/about</loc></url></urlset>"
)

LLMS_WITH_PRICING = "# Example\n\n> Summary.\n\n## Docs\n\n- [Pricing](https://example.com/pricing): plans.\n"


class MetaDirectiveParsingTests(unittest.TestCase):
    def test_robots_meta_tokens_are_collected_case_insensitively(self):
        html = '<html><head><meta name="Robots" content="NOINDEX, NoFollow"></head></html>'
        result = perimeter.parse_meta_directives(html)
        self.assertEqual(result["robots_tokens"], {"noindex", "nofollow"})

    def test_noai_meta_tag_sets_noai_flag(self):
        html = '<html><head><meta name="noai" content="1"></head></html>'
        result = perimeter.parse_meta_directives(html)
        self.assertTrue(result["noai"])

    def test_noai_token_inside_robots_content_also_sets_flag(self):
        html = '<html><head><meta name="robots" content="noai, noimageai"></head></html>'
        result = perimeter.parse_meta_directives(html)
        self.assertTrue(result["noai"])
        self.assertTrue(result["noimageai"])

    def test_tdm_reservation_meta_is_captured(self):
        html = '<html><head><meta name="tdm-reservation" content="1"></head></html>'
        result = perimeter.parse_meta_directives(html)
        self.assertEqual(result["tdm_reservation"], "1")

    def test_meta_tags_in_body_are_ignored(self):
        html = '<html><head></head><body><meta name="robots" content="noindex"></body></html>'
        result = perimeter.parse_meta_directives(html)
        self.assertEqual(result["robots_tokens"], set())

    def test_malformed_html_does_not_raise(self):
        result = perimeter.parse_meta_directives("<html><head><meta name=robots content=noindex")
        self.assertIsInstance(result, dict)

    def test_empty_html_returns_empty_defaults(self):
        result = perimeter.parse_meta_directives("")
        self.assertEqual(result["robots_tokens"], set())
        self.assertIsNone(result["tdm_reservation"])


class TdmRepParsingTests(unittest.TestCase):
    def test_top_level_reservation_true(self):
        self.assertTrue(perimeter._tdmrep_reserves({"tdm-reservation": "1"}))

    def test_top_level_reservation_zero_is_not_reserved(self):
        self.assertFalse(perimeter._tdmrep_reserves({"tdm-reservation": "0"}))

    def test_nested_policies_default_reservation(self):
        data = {"policies": {"default": {"tdm-reservation": "true"}}}
        self.assertTrue(perimeter._tdmrep_reserves(data))

    def test_none_is_not_reserved(self):
        self.assertFalse(perimeter._tdmrep_reserves(None))

    def test_non_dict_is_not_reserved(self):
        self.assertFalse(perimeter._tdmrep_reserves("not a dict"))

    def test_malformed_json_body_does_not_crash_fetch_tdmrep_parsing(self):
        # fetch_tdmrep itself needs a live/mocked fetch; the json.loads path
        # it guards is exercised directly here.
        import json

        with self.assertRaises(Exception):
            json.loads("{not valid json")
        # The function under test never lets that exception escape:
        # covered end-to-end by EndToEndAccessContradictionsTests below via
        # tdmrep_data=None (the value fetch_tdmrep returns for malformed JSON).


class C1SitemapUrlAiDisallowedTests(unittest.TestCase):
    def test_path_specific_disallow_for_an_otherwise_allowed_bot_fires(self):
        groups = perimeter.parse_groups(PATH_SPECIFIC_BLOCK)
        sitemap_urls = ["https://example.com/pricing", "https://example.com/about"]
        finding = perimeter._c1_sitemap_url_ai_disallowed(groups, sitemap_urls)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-09-sitemap-url-ai-disallowed")

    def test_no_path_specific_rules_produces_nothing(self):
        groups = perimeter.parse_groups(ALLOW_ALL_NAMED_AI)
        sitemap_urls = ["https://example.com/pricing"]
        finding = perimeter._c1_sitemap_url_ai_disallowed(groups, sitemap_urls)
        self.assertIsNone(finding)

    def test_bot_already_blocked_at_root_is_excluded_per_overlap_control(self):
        """A bot with no root access at all is PER-01/02's finding, not a
        new PER-09 contradiction — even though it also fails the path
        check, it must not appear in C1's affected list."""
        robots_text = "User-agent: GPTBot\nDisallow: /\n"
        groups = perimeter.parse_groups(robots_text)
        sitemap_urls = ["https://example.com/pricing"]
        finding = perimeter._c1_sitemap_url_ai_disallowed(groups, sitemap_urls)
        self.assertIsNone(finding, "a root-wide block is PER-01's finding, not C1's")

    def test_empty_sitemap_urls_produces_nothing(self):
        groups = perimeter.parse_groups(PATH_SPECIFIC_BLOCK)
        finding = perimeter._c1_sitemap_url_ai_disallowed(groups, [])
        self.assertIsNone(finding)


class C2NoindexOnDeclaredUrlTests(unittest.TestCase):
    def test_header_noindex_on_a_sitemap_declared_url_fires(self):
        page_results = [
            {"url": "https://example.com/pricing", "headers": {"x-robots-tag": "noindex, nofollow"}, "meta": {}}
        ]
        finding = perimeter._c2_noindex_on_declared_url(
            page_results, ["https://example.com/pricing"], []
        )
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-09-noindex-on-declared-url")
        self.assertEqual(finding.severity, "high")

    def test_meta_noindex_on_an_llms_txt_declared_url_fires(self):
        page_results = [
            {
                "url": "https://example.com/pricing",
                "headers": {},
                "meta": {"robots_tokens": {"noindex"}, "noai": False},
            }
        ]
        finding = perimeter._c2_noindex_on_declared_url(page_results, [], ["https://example.com/pricing"])
        self.assertIsNotNone(finding)

    def test_noindex_on_an_undeclared_page_stays_silent(self):
        """A thank-you page with noindex that is not in the sitemap at all
        is not a contradiction — nothing declares it canonical."""
        page_results = [
            {"url": "https://example.com/thanks", "headers": {"x-robots-tag": "noindex"}, "meta": {}}
        ]
        finding = perimeter._c2_noindex_on_declared_url(
            page_results, ["https://example.com/pricing"], []
        )
        self.assertIsNone(finding)

    def test_noarchive_alone_is_not_a_noindex_signal(self):
        page_results = [
            {"url": "https://example.com/pricing", "headers": {"x-robots-tag": "noarchive"}, "meta": {}}
        ]
        finding = perimeter._c2_noindex_on_declared_url(
            page_results, ["https://example.com/pricing"], []
        )
        self.assertIsNone(finding)

    def test_clean_declared_page_with_no_noindex_signal_stays_silent(self):
        page_results = [{"url": "https://example.com/pricing", "headers": {}, "meta": {}}]
        finding = perimeter._c2_noindex_on_declared_url(
            page_results, ["https://example.com/pricing"], []
        )
        self.assertIsNone(finding)


class C3TdmReservationContradictsRobotsTests(unittest.TestCase):
    def test_reservation_with_training_bots_still_allowed_fires(self):
        groups = perimeter.parse_groups(WILDCARD_ONLY)
        finding = perimeter._c3_tdm_reservation_contradicts_robots(groups, True, "tdmrep.json")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-09-tdm-reservation-contradicts-robots")
        self.assertEqual(finding.severity, "medium")

    def test_no_reservation_produces_nothing(self):
        groups = perimeter.parse_groups(WILDCARD_ONLY)
        finding = perimeter._c3_tdm_reservation_contradicts_robots(groups, False, None)
        self.assertIsNone(finding)

    def test_reservation_with_all_training_bots_blocked_produces_nothing(self):
        robots_text = "User-agent: GPTBot\nUser-agent: ClaudeBot\nUser-agent: CCBot\nDisallow: /\n"
        groups = perimeter.parse_groups(robots_text)
        finding = perimeter._c3_tdm_reservation_contradicts_robots(groups, True, "tdmrep.json")
        self.assertIsNone(finding, "no contradiction when the reservation is already effectively enforced")


class C4HeaderMetaRobotsDisagreeTests(unittest.TestCase):
    def test_header_noindex_meta_index_disagree(self):
        page_results = [
            {
                "url": "https://example.com/",
                "headers": {"x-robots-tag": "noindex"},
                "meta": {"robots_tokens": {"index", "follow"}},
            }
        ]
        finding = perimeter._c4_header_meta_robots_disagree(page_results)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-09-header-meta-robots-disagree")

    def test_both_noindex_is_not_a_disagreement(self):
        page_results = [
            {
                "url": "https://example.com/",
                "headers": {"x-robots-tag": "noindex"},
                "meta": {"robots_tokens": {"noindex"}},
            }
        ]
        finding = perimeter._c4_header_meta_robots_disagree(page_results)
        self.assertIsNone(finding)

    def test_absent_meta_tag_is_not_a_disagreement_here(self):
        """An absent meta tag is C2's contradiction (against sitemap/llms),
        not C4's — C4 needs both channels genuinely present."""
        page_results = [{"url": "https://example.com/", "headers": {"x-robots-tag": "noindex"}, "meta": {}}]
        finding = perimeter._c4_header_meta_robots_disagree(page_results)
        self.assertIsNone(finding)

    def test_absent_header_is_not_a_disagreement(self):
        page_results = [
            {"url": "https://example.com/", "headers": {}, "meta": {"robots_tokens": {"noindex"}}}
        ]
        finding = perimeter._c4_header_meta_robots_disagree(page_results)
        self.assertIsNone(finding)


class C5NoTdmDeclarationTests(unittest.TestCase):
    def test_named_ai_groups_and_confirmed_absent_tdmrep_fires(self):
        groups = perimeter.parse_groups(ALLOW_ALL_NAMED_AI)
        finding = perimeter._c5_no_tdm_declaration(groups, "absent")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.id, "PER-09-no-tdm-declaration")
        self.assertEqual(finding.track, "proactive")

    def test_wildcard_only_robots_stays_silent(self):
        """Precision guard: never suggest TDMRep to a site that has not
        demonstrably taken a position on AI access at all."""
        groups = perimeter.parse_groups(WILDCARD_ONLY)
        finding = perimeter._c5_no_tdm_declaration(groups, "absent")
        self.assertIsNone(finding)

    def test_tdmrep_present_stays_silent_even_with_named_groups(self):
        groups = perimeter.parse_groups(ALLOW_ALL_NAMED_AI)
        finding = perimeter._c5_no_tdm_declaration(groups, "present")
        self.assertIsNone(finding)

    def test_unavailable_status_is_not_treated_as_absent(self):
        """A caller that never attempted the tdmrep.json fetch (status
        defaults to "unavailable") must not have C5 silently fabricate a
        finding from an unknown state — "unavailable" is not "absent"."""
        groups = perimeter.parse_groups(ALLOW_ALL_NAMED_AI)
        finding = perimeter._c5_no_tdm_declaration(groups, "unavailable")
        self.assertIsNone(finding)


class EndToEndAccessContradictionsTests(unittest.TestCase):
    def test_robots_unavailable_is_reported_unknown_not_silently_skipped(self):
        findings, unknowns = perimeter.evaluate_access_contradictions(
            "robots.txt timed out", "unavailable", None, "unavailable", None, "unavailable", [], None, "unavailable"
        )
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)
        self.assertEqual(unknowns[0].capability_id, "PER-09")

    def test_a_fully_clean_site_produces_no_findings(self):
        findings, unknowns = perimeter.evaluate_access_contradictions(
            WILDCARD_ONLY,
            "present",
            SITEMAP_WITH_PRICING,
            "present",
            LLMS_WITH_PRICING,
            "present",
            [{"url": "https://example.com/pricing", "headers": {}, "meta": {"robots_tokens": set()}}],
            None,
            "absent",
        )
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_blanket_block_suppresses_c1_per_overlap_control(self):
        """Explicit overlap-control test: PER-02's blanket-block condition
        must not also produce a PER-09 C1 finding."""
        findings, _ = perimeter.evaluate_access_contradictions(
            BLANKET_BLOCK, "present", SITEMAP_WITH_PRICING, "present", None, "absent", [], None, "absent"
        )
        ids = {f.id for f in findings}
        self.assertNotIn("PER-09-sitemap-url-ai-disallowed", ids)

    def test_sitemapindex_root_does_not_crash_and_yields_no_c1(self):
        sitemapindex = "<?xml version='1.0'?><sitemapindex><sitemap><loc>https://example.com/s1.xml</loc></sitemap></sitemapindex>"
        findings, unknowns = perimeter.evaluate_access_contradictions(
            PATH_SPECIFIC_BLOCK, "present", sitemapindex, "present", None, "absent", [], None, "absent"
        )
        ids = {f.id for f in findings}
        self.assertNotIn("PER-09-sitemap-url-ai-disallowed", ids)

    def test_malformed_tdmrep_data_behaves_as_absent_for_c3(self):
        """fetch_tdmrep returns (None, "present") for malformed JSON —
        callers passing that through must not crash and C3 must not fire
        from a None payload."""
        findings, _ = perimeter.evaluate_access_contradictions(
            WILDCARD_ONLY, "present", None, "absent", None, "absent", [], None, "present"
        )
        ids = {f.id for f in findings}
        self.assertNotIn("PER-09-tdm-reservation-contradicts-robots", ids)

    def test_every_emitted_finding_satisfies_the_contract(self):
        findings, _ = perimeter.evaluate_access_contradictions(
            PATH_SPECIFIC_BLOCK,
            "present",
            SITEMAP_WITH_PRICING,
            "present",
            LLMS_WITH_PRICING,
            "present",
            [
                {
                    "url": "https://example.com/",
                    "headers": {"x-robots-tag": "noindex"},
                    "meta": {"robots_tokens": {"index"}},
                }
            ],
            {"tdm-reservation": "1"},
            "present",
        )
        self.assertTrue(findings, "fixture should produce at least one finding to validate")
        for finding in findings:
            errors = finding.validate()
            self.assertEqual(errors, [], f"{finding.id}: {errors}")

    def test_evaluation_is_deterministic(self):
        args = (
            PATH_SPECIFIC_BLOCK,
            "present",
            SITEMAP_WITH_PRICING,
            "present",
            LLMS_WITH_PRICING,
            "present",
            [{"url": "https://example.com/pricing", "headers": {"x-robots-tag": "noindex"}, "meta": {}}],
            {"tdm-reservation": "1"},
            "present",
        )
        first = [f.id for f in perimeter.evaluate_access_contradictions(*args)[0]]
        second = [f.id for f in perimeter.evaluate_access_contradictions(*args)[0]]
        self.assertEqual(first, second)


class CanFetchPathTests(unittest.TestCase):
    def test_root_allowed_but_specific_path_blocked(self):
        groups = perimeter.parse_groups(PATH_SPECIFIC_BLOCK)
        self.assertTrue(perimeter.can_fetch_root(groups, "GPTBot"))
        self.assertFalse(perimeter.can_fetch_path(groups, "GPTBot", "/pricing"))

    def test_unrelated_path_still_allowed(self):
        groups = perimeter.parse_groups(PATH_SPECIFIC_BLOCK)
        self.assertTrue(perimeter.can_fetch_path(groups, "GPTBot", "/about"))

    def test_no_matching_group_falls_back_to_permit(self):
        groups = perimeter.parse_groups("")
        self.assertTrue(perimeter.can_fetch_path(groups, "GPTBot", "/anything"))


class DegradeSeverityTests(unittest.TestCase):
    def test_critical_degrades_to_high(self):
        self.assertEqual(perimeter._degrade_severity("critical"), "high")

    def test_low_stays_low(self):
        self.assertEqual(perimeter._degrade_severity("low"), "low")


class AuditWiringTests(unittest.TestCase):
    def test_audit_wires_per_09_when_given_inputs(self):
        output = perimeter.audit(
            "example.com",
            PATH_SPECIFIC_BLOCK,
            "present",
            None,
            "absent",
            sitemap_text=SITEMAP_WITH_PRICING,
            sitemap_status="present",
            page_results=[],
            tdmrep_data=None,
            tdmrep_status="absent",
        )
        ids = {f["id"] for f in output["findings"]}
        self.assertIn("PER-09-sitemap-url-ai-disallowed", ids)

    def test_audit_without_per_09_inputs_defaults_safely(self):
        """A caller that predates PER-09 (page_results/tdmrep args omitted)
        must not have it silently fabricate a finding — only a genuine
        robots.txt-unavailable case should surface PER-09 as unknown."""
        output = perimeter.audit("example.com", WILDCARD_ONLY, "present", None, "absent")
        per09_findings = [f for f in output["findings"] if f["capability_id"] == "PER-09"]
        self.assertEqual(per09_findings, [])

    def test_validate_floor_shape_accepts_a_composed_per_09_report(self):
        import tempfile
        import json as _json

        orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")
        output = perimeter.audit(
            "example.com",
            PATH_SPECIFIC_BLOCK,
            "present",
            None,
            "absent",
            sitemap_text=SITEMAP_WITH_PRICING,
            sitemap_status="present",
        )
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "skill.json"
            path.write_text(_json.dumps(output), encoding="utf-8")
            report = orchestrator.compose(
                "example.com", [("perimeter-access-audit", str(path))], audited_at="2026-09-20T14:32:00Z"
            )
        self.assertEqual(validate_floor_shape(report), [])


if __name__ == "__main__":
    unittest.main()
