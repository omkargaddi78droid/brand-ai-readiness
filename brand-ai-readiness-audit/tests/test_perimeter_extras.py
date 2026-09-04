"""Unit tests for PER-05/06/07/08 — the second half of perimeter-access-audit's
Cluster A, added after PER-01/02/03/04 were already frozen. Each detector is
tested as a positive/negative pair, same convention as every prior detector
in this project.

Field validation (docs/phase-4-completion-6.md) confirmed the happy path
against a real, 857-line sitemap.xml (apple.com) using the standard default
namespace, and confirmed the "genuinely blocked, not missing" distinction
against two sites that 403/406 rather than 404 on /sitemap.xml.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "corpus" / "perimeter_extras"
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_perimeter", REPO_ROOT / "skills/perimeter-access-audit/scripts/check_perimeter.py"
)
per = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(per)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class LlmsFullTxtTests(unittest.TestCase):
    def test_a_substantial_file_produces_nothing(self):
        findings, unknowns = per.evaluate_llms_full_txt(fixture("llms_full_substantial.txt"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_absence_alone_is_not_a_finding(self):
        """Unlike llms.txt itself, llms-full.txt is a secondary, optional
        companion — its own absence is not worth a proactive note."""
        findings, unknowns = per.evaluate_llms_full_txt(None, "absent")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_thin_stub_file_is_flagged(self):
        findings, _ = per.evaluate_llms_full_txt(fixture("llms_full_thin.txt"), "present")
        self.assertEqual([f.id for f in findings], ["PER-05-llms-full-txt-thin"])
        self.assertEqual(findings[0].track, "proactive")
        self.assertEqual(findings[0].severity, "low")

    def test_unreachable_is_unknown_not_a_verdict(self):
        findings, unknowns = per.evaluate_llms_full_txt("timeout", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-05"])


class SitemapTests(unittest.TestCase):
    def test_a_valid_urlset_produces_nothing(self):
        findings, unknowns = per.evaluate_sitemap(fixture("sitemap_valid_urlset.xml"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_valid_sitemap_index_produces_nothing(self):
        findings, _ = per.evaluate_sitemap(fixture("sitemap_valid_index.xml"), "present")
        self.assertEqual(findings, [])

    def test_missing_sitemap_is_flagged(self):
        findings, _ = per.evaluate_sitemap(None, "absent")
        self.assertEqual([f.id for f in findings], ["PER-06-sitemap-missing"])
        self.assertEqual(findings[0].severity, "medium")

    def test_an_html_error_page_at_the_sitemap_url_is_flagged_as_malformed_not_crashed_on(self):
        findings, _ = per.evaluate_sitemap(fixture("sitemap_html_error.txt"), "present")
        self.assertEqual([f.id for f in findings], ["PER-06-sitemap-malformed"])

    def test_an_empty_urlset_is_flagged(self):
        findings, _ = per.evaluate_sitemap(fixture("sitemap_empty.xml"), "present")
        self.assertEqual([f.id for f in findings], ["PER-06-sitemap-empty"])

    def test_unreachable_is_unknown_not_a_verdict(self):
        findings, unknowns = per.evaluate_sitemap("HTTP 403", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-06"])

    def test_a_namespace_prefixed_root_is_still_recognised(self):
        """Real sitemaps overwhelmingly use the default (unprefixed)
        namespace — confirmed live against apple.com's 857-entry sitemap —
        but a prefixed root (<s:urlset xmlns:s="...">) is legal XML and
        should not be misclassified as malformed."""
        xml = '<?xml version="1.0"?><s:urlset xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></s:urlset>'
        findings, _ = per.evaluate_sitemap(xml, "present")
        self.assertEqual(findings, [])


class MdNegotiationTests(unittest.TestCase):
    def test_a_real_markdown_variant_produces_nothing(self):
        findings, unknowns = per.evaluate_md_negotiation(fixture("md_variant_real.md"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_absent_md_variant_is_a_low_severity_proactive_suggestion(self):
        findings, _ = per.evaluate_md_negotiation(None, "absent")
        self.assertEqual([f.id for f in findings], ["PER-07-no-md-negotiation"])
        self.assertEqual(findings[0].track, "proactive")
        self.assertEqual(findings[0].severity, "low")

    def test_a_soft_404_html_page_is_treated_the_same_as_absent(self):
        findings, _ = per.evaluate_md_negotiation(fixture("md_variant_soft404.html"), "present")
        self.assertEqual([f.id for f in findings], ["PER-07-no-md-negotiation"])

    def test_unreachable_is_unknown_not_a_verdict(self):
        findings, unknowns = per.evaluate_md_negotiation("timeout", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-07"])


class MdVariantUrlTests(unittest.TestCase):
    def test_a_path_gets_a_suffixed_md(self):
        self.assertEqual(per.md_variant_url("https://example.com/blog/post"), "https://example.com/blog/post.md")

    def test_a_bare_domain_falls_back_to_index_md(self):
        self.assertEqual(per.md_variant_url("https://example.com"), "https://example.com/index.md")

    def test_a_root_path_falls_back_to_index_md(self):
        self.assertEqual(per.md_variant_url("https://example.com/"), "https://example.com/index.md")

    def test_query_and_fragment_are_dropped(self):
        result = per.md_variant_url("https://example.com/page?x=1#section")
        self.assertEqual(result, "https://example.com/page.md")


class SitemapDiscoverabilityTests(unittest.TestCase):
    def test_sitemap_referenced_in_robots_produces_nothing(self):
        robots = "User-agent: *\nDisallow:\nSitemap: https://example.com/sitemap.xml\n"
        findings, _ = per.evaluate_sitemap_discoverability(robots, "present", "present")
        self.assertEqual(findings, [])

    def test_sitemap_not_referenced_in_robots_is_flagged(self):
        robots = "User-agent: *\nDisallow:\n"
        findings, _ = per.evaluate_sitemap_discoverability(robots, "present", "present")
        self.assertEqual([f.id for f in findings], ["PER-08-sitemap-not-in-robots"])
        self.assertEqual(findings[0].track, "proactive")

    def test_no_sitemap_at_all_is_not_this_checks_problem(self):
        """PER-06 already covers a *confirmed-absent* sitemap; PER-08 only
        asks whether an existing sitemap is discoverable from robots.txt."""
        robots = "User-agent: *\nDisallow:\n"
        findings, unknowns = per.evaluate_sitemap_discoverability(robots, "present", "absent")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_robots_unavailable_is_unknown_not_a_verdict(self):
        findings, unknowns = per.evaluate_sitemap_discoverability(None, "unavailable", "present")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-08"])

    def test_sitemap_status_itself_unknown_is_also_reported_not_silently_dropped(self):
        """Regression: sitemap_status='unavailable' (we don't know whether a
        sitemap exists at all) was originally collapsed into the same
        'nothing to check' bucket as 'confirmed absent', silently losing a
        genuine unknown. The two are different states and must be reported
        differently."""
        robots = "User-agent: *\nDisallow:\n"
        findings, unknowns = per.evaluate_sitemap_discoverability(robots, "present", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-08"])

    def test_sitemap_directive_matching_is_case_insensitive_and_at_line_start(self):
        robots = "User-agent: *\nDisallow:\nSITEMAP: https://example.com/sitemap.xml\n"
        findings, _ = per.evaluate_sitemap_discoverability(robots, "present", "present")
        self.assertEqual(findings, [])


class LlmsSitemapAgreementTests(unittest.TestCase):
    """PER-08's second half: llms.txt is a curated subset (PER-04's own
    mechanism note), so the sitemap having URLs llms.txt omits is expected —
    only a llms.txt link the sitemap doesn't know about at all is a real
    inconsistency."""

    _SITEMAP = (
        "<urlset><url><loc>https://example.com/pricing</loc></url>"
        "<url><loc>https://example.com/docs</loc></url></urlset>"
    )

    def test_llms_txt_absent_is_not_this_checks_problem(self):
        findings, unknowns = per.evaluate_llms_sitemap_agreement(None, "absent", self._SITEMAP, "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_sitemap_absent_is_not_this_checks_problem(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs): the docs\n"
        findings, unknowns = per.evaluate_llms_sitemap_agreement(llms, "present", None, "absent")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_llms_txt_status_unavailable_is_reported_as_unknown(self):
        findings, unknowns = per.evaluate_llms_sitemap_agreement(None, "unavailable", self._SITEMAP, "present")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-08"])

    def test_sitemap_status_unavailable_is_reported_as_unknown(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs): the docs\n"
        findings, unknowns = per.evaluate_llms_sitemap_agreement(llms, "present", None, "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-08"])

    def test_llms_txt_links_all_present_in_sitemap_is_clean(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs): the docs\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_sitemap_having_extra_urls_llms_txt_omits_is_not_a_defect(self):
        """llms.txt curating a small subset of the sitemap is the documented,
        intended pattern, not a disagreement."""
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs): the docs\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_llms_txt_link_missing_from_sitemap_is_flagged(self):
        llms = (
            "# Brand\n> Summary\n## Docs\n"
            "- [Docs](https://example.com/docs): the docs\n"
            "- [Old Guide](https://example.com/old-guide): a stale link\n"
        )
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual([f.id for f in findings], ["PER-08-llms-sitemap-disagreement"])
        self.assertIn("old-guide", findings[0].evidence)
        self.assertEqual(findings[0].structured_evidence["orphaned_urls"], ["https://example.com/old-guide"])

    def test_trailing_slash_and_www_prefix_do_not_count_as_a_disagreement(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://www.example.com/docs/): the docs\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_md_variant_of_a_sitemap_page_is_not_a_disagreement(self):
        """Live-caught on vercel.com/supabase.com: llms.txt conventionally
        links a `.md` content-negotiation variant of a real page (PER-07's
        own concept) — the sitemap correctly lists the page without the
        suffix, and that is not a missing page."""
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs.md): the docs\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_a_companion_llms_full_txt_link_is_not_a_disagreement(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Full text](https://example.com/llms-full.txt): everything\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_a_different_host_link_is_not_this_sites_sitemaps_concern(self):
        """Live-caught on vercel.com: llms.txt linked a separate API-spec
        host (openapi.vercel.sh) that was never going to be in vercel.com's
        own sitemap, and shouldn't be treated as a missing page."""
        llms = "# Brand\n> Summary\n## API\n- [API spec](https://api-spec.example.org/openapi.json): the spec\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual(findings, [])

    def test_a_genuinely_missing_same_host_html_page_still_fires(self):
        llms = "# Brand\n> Summary\n## Docs\n- [Old Guide](https://example.com/old-guide): a stale link\n"
        findings, _ = per.evaluate_llms_sitemap_agreement(llms, "present", self._SITEMAP, "present")
        self.assertEqual([f.id for f in findings], ["PER-08-llms-sitemap-disagreement"])

    def test_a_sitemap_index_is_not_flattened_into_a_false_comparison(self):
        """Live-caught on vercel.com and supabase.com: sitemap.xml there is
        a <sitemapindex> of sub-sitemap URLs, not a flat <urlset> of real
        pages. Comparing llms.txt links against the index's own pointer
        URLs flagged nearly everything as 'missing' — a false positive from
        comparing against the wrong URL set, not a real disagreement. This
        project doesn't recurse into sitemap indexes (same class of gap as
        PER-06's own documented completeness limitation), so the honest
        result is 'cannot compare', not a fabricated finding."""
        sitemap_index = (
            "<sitemapindex><sitemap><loc>https://example.com/sitemap_www.xml</loc></sitemap>"
            "<sitemap><loc>https://example.com/docs/sitemap.xml</loc></sitemap></sitemapindex>"
        )
        llms = "# Brand\n> Summary\n## Docs\n- [Docs](https://example.com/docs): the docs\n"
        findings, unknowns = per.evaluate_llms_sitemap_agreement(llms, "present", sitemap_index, "present")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-08"])


class ContractComplianceTests(unittest.TestCase):
    def test_every_new_finding_satisfies_the_contract(self):
        findings = (
            per.evaluate_llms_full_txt(fixture("llms_full_thin.txt"), "present")[0]
            + per.evaluate_sitemap(None, "absent")[0]
            + per.evaluate_md_negotiation(None, "absent")[0]
            # sitemap_status="present" here (independent of the sitemap
            # check above) so PER-08 has something to evaluate discoverability for
            + per.evaluate_sitemap_discoverability("User-agent: *\nDisallow:\n", "present", "present")[0]
        )
        self.assertEqual(len(findings), 4)  # PER-05, PER-06, PER-07, PER-08 — one finding each
        for finding in findings:
            restored = Finding.from_dict(finding.to_dict())
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "perimeter-access-audit")
            self.assertEqual(restored.gate, 1)

    def test_capability_ids_include_all_nine(self):
        self.assertEqual(
            per.CAPABILITY_IDS,
            ["PER-01", "PER-02", "PER-03", "PER-04", "PER-05", "PER-06", "PER-07", "PER-08", "PER-09"],
        )

    def test_audit_defaults_the_new_capabilities_to_an_honest_unknown(self):
        """A caller that predates PER-05/06/07/08 (every test written before
        this cycle) must not have those capabilities silently fabricated as
        a pass — they should surface as unknown."""
        output = per.audit("example.com", "User-agent: *\nDisallow:\n", "present", None, "absent")
        unknown_ids = {u["capability_id"] for u in output["unknown_checks"]}
        self.assertEqual(unknown_ids, {"PER-05", "PER-06", "PER-07", "PER-08"})

    def test_audit_wires_all_four_new_capabilities_when_given_inputs(self):
        output = per.audit(
            "example.com",
            "User-agent: *\nDisallow:\n",
            "present",
            None,
            "absent",
            llms_full_text=fixture("llms_full_thin.txt"),
            llms_full_status="present",
            sitemap_text=None,
            sitemap_status="absent",
            md_text=None,
            md_status="absent",
        )
        ids = {f["id"] for f in output["findings"]}
        self.assertIn("PER-05-llms-full-txt-thin", ids)
        self.assertIn("PER-06-sitemap-missing", ids)
        self.assertIn("PER-07-no-md-negotiation", ids)


if __name__ == "__main__":
    unittest.main()
