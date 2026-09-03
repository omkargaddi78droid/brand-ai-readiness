"""Unit tests for static-extraction-audit (REN-02/04/05/06/07/08/10/11).

Each detector is tested as a positive/negative pair, per project convention.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_static_extraction", REPO_ROOT / "skills/static-extraction-audit/scripts/check_static_extraction.py"
)
sea = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sea)


class ParsePageTests(unittest.TestCase):
    def test_json_ld_and_hydration_blocks_are_separated(self):
        html = (
            '<script type="application/ld+json">{"@type": "Product"}</script>'
            '<script type="application/json" id="__NEXT_DATA__">{"a": "b"}</script>'
        )
        parsed = sea.parse_page(html)
        self.assertEqual(len(parsed["json_ld_blocks"]), 1)
        self.assertEqual(len(parsed["hydration_blocks"]), 1)
        self.assertEqual(parsed["hydration_blocks"][0][0], "__NEXT_DATA__")

    def test_nuxt_data_id_is_recognized_even_without_json_type(self):
        html = '<script id="__NUXT_DATA__">{"a": "b"}</script>'
        parsed = sea.parse_page(html)
        self.assertEqual(len(parsed["hydration_blocks"]), 1)

    def test_ordinary_script_is_not_treated_as_hydration_or_json_ld(self):
        html = '<script>var x = {"a": "b"};</script>'
        parsed = sea.parse_page(html)
        self.assertEqual(parsed["json_ld_blocks"], [])
        self.assertEqual(parsed["hydration_blocks"], [])
        self.assertIn('{"a": "b"}', parsed["script_text"])

    def test_script_and_style_content_is_excluded_from_visible_text(self):
        html = "<script>var x = 'SECRET';</script><style>.x { color: red; }</style><p>Real text.</p>"
        parsed = sea.parse_page(html)
        self.assertNotIn("SECRET", parsed["visible_text"])
        self.assertIn("Real text.", parsed["visible_text"])

    def test_adjacent_block_tags_stay_separate_words(self):
        html = "<h1>Widgets</h1><p>Our platform.</p>"
        parsed = sea.parse_page(html)
        self.assertIn("Widgets", parsed["visible_text"])
        self.assertNotIn("WidgetsOur", parsed["visible_text"])

    def test_main_article_text_is_scoped_to_the_boundary(self):
        html = "<main><p>Inside.</p></main><nav><p>Outside.</p></nav>"
        parsed = sea.parse_page(html)
        self.assertIn("Inside.", parsed["main_article_text"])
        self.assertNotIn("Outside.", parsed["main_article_text"])

    def test_has_main_or_article_true_for_article_tag(self):
        self.assertTrue(sea.parse_page("<article><p>Text</p></article>")["has_main_or_article"])

    def test_has_main_or_article_false_when_absent(self):
        self.assertFalse(sea.parse_page("<div><p>Text</p></div>")["has_main_or_article"])

    def test_pdf_link_is_collected(self):
        html = '<a href="/spec.pdf">Spec</a><a href="/page.html">Not a PDF</a>'
        self.assertEqual(sea.parse_page(html)["pdf_links"], ["/spec.pdf"])

    def test_pdf_link_with_query_string_is_still_detected(self):
        html = '<a href="/spec.pdf?v=2">Spec</a>'
        self.assertEqual(sea.parse_page(html)["pdf_links"], ["/spec.pdf?v=2"])

    def test_decorative_image_is_flagged_as_decorative(self):
        html = '<img src="a.jpg" role="presentation">'
        images = sea.parse_page(html)["images"]
        self.assertEqual(images, [{"has_alt": False, "decorative": True}])

    def test_image_with_alt_is_not_decorative_by_default(self):
        html = '<img src="a.jpg" alt="A widget">'
        images = sea.parse_page(html)["images"]
        self.assertEqual(images, [{"has_alt": True, "decorative": False}])

    def test_video_with_track_is_recorded(self):
        html = "<video><track kind='captions'></video>"
        self.assertEqual(sea.parse_page(html)["media_results"], [{"tag": "video", "has_track": True}])

    def test_audio_without_track_is_recorded(self):
        html = "<audio></audio>"
        self.assertEqual(sea.parse_page(html)["media_results"], [{"tag": "audio", "has_track": False}])


class HydrationCoverageGapTests(unittest.TestCase):
    def test_a_missing_hydration_fragment_fires(self):
        fragments = sea.extract_hydration_text_fragments(
            [("__NEXT_DATA__", '{"description": "A fragment long enough to matter here."}')]
        )
        findings = sea.find_hydration_coverage_gaps(fragments, "Nothing related to that on the page.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-02-hydration-content-not-in-text")

    def test_a_fragment_present_in_visible_text_does_not_fire(self):
        fragments = sea.extract_hydration_text_fragments(
            [("__NEXT_DATA__", '{"description": "A fragment long enough to matter here."}')]
        )
        text = "This page says: A fragment long enough to matter here. Right there."
        self.assertEqual(sea.find_hydration_coverage_gaps(fragments, text), [])

    def test_short_values_are_not_extracted_as_fragments(self):
        fragments = sea.extract_hydration_text_fragments([("__NEXT_DATA__", '{"id": "abc123"}')])
        self.assertEqual(fragments, [])

    def test_url_like_values_are_excluded(self):
        fragments = sea.extract_hydration_text_fragments(
            [("__NEXT_DATA__", '{"link": "https://example.com/some/long/path/here"}')]
        )
        self.assertEqual(fragments, [])

    def test_no_hydration_blocks_returns_no_fragments(self):
        self.assertEqual(sea.extract_hydration_text_fragments([]), [])

    def test_malformed_hydration_json_is_silently_skipped(self):
        fragments = sea.extract_hydration_text_fragments([("__NEXT_DATA__", "{not valid json")])
        self.assertEqual(fragments, [])


class PriceRenderGapTests(unittest.TestCase):
    def test_a_missing_offer_price_fires(self):
        nodes = [{"@type": "Product", "offers": {"@type": "Offer", "price": "29.99"}}]
        prices = sea.extract_offer_prices(nodes)
        findings = sea.find_price_render_gaps(prices, "No price mentioned here at all.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-04-price-not-in-text")

    def test_a_price_restated_with_currency_symbol_does_not_fire(self):
        nodes = [{"@type": "Product", "offers": {"@type": "Offer", "price": "29.99"}}]
        prices = sea.extract_offer_prices(nodes)
        self.assertEqual(sea.find_price_render_gaps(prices, "The price is $29.99 today."), [])

    def test_a_price_restated_with_comma_thousands_separator_does_not_fire(self):
        nodes = [{"@type": "Product", "offers": {"@type": "Offer", "price": "1299.00"}}]
        prices = sea.extract_offer_prices(nodes)
        self.assertEqual(sea.find_price_render_gaps(prices, "It costs $1,299.00 total."), [])

    def test_price_on_a_product_offers_list_is_extracted(self):
        nodes = [{"@type": "Product", "offers": [{"price": "9.99"}, {"price": "19.99"}]}]
        prices = sea.extract_offer_prices(nodes)
        self.assertEqual({p["price"] for p in prices}, {"9.99", "19.99"})

    def test_price_specification_price_is_extracted(self):
        nodes = [{"@type": "Offer", "priceSpecification": {"price": "15.00"}}]
        prices = sea.extract_offer_prices(nodes)
        self.assertEqual(prices, [{"price": "15.00"}])

    def test_no_offer_nodes_returns_no_prices(self):
        self.assertEqual(sea.extract_offer_prices([{"@type": "Organization"}]), [])

    def test_no_prices_produces_no_findings(self):
        self.assertEqual(sea.find_price_render_gaps([], "Some text with no prices."), [])


class FreshnessSignalTests(unittest.TestCase):
    def test_availability_with_no_freshness_signal_fires(self):
        nodes = [{"@type": "Offer", "availability": "https://schema.org/InStock"}]
        findings = sea.find_missing_freshness_signal(nodes, "It is in stock right now.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-05-no-freshness-signal")

    def test_a_freshness_phrase_in_text_prevents_the_finding(self):
        nodes = [{"@type": "Offer", "availability": "https://schema.org/InStock"}]
        text = "In stock as of this morning."
        self.assertEqual(sea.find_missing_freshness_signal(nodes, text), [])

    def test_a_date_modified_field_prevents_the_finding(self):
        nodes = [{"@type": "Offer", "availability": "https://schema.org/InStock", "dateModified": "2026-09-01"}]
        self.assertEqual(sea.find_missing_freshness_signal(nodes, "In stock."), [])

    def test_no_availability_field_stays_silent(self):
        nodes = [{"@type": "Offer", "price": "10.00"}]
        self.assertEqual(sea.find_missing_freshness_signal(nodes, "No stock info here."), [])


class SemanticBoundaryTests(unittest.TestCase):
    _LONG_TEXT = "word " * 200

    def test_no_boundary_on_a_substantial_page_fires(self):
        findings = sea.find_missing_semantic_boundary(False, self._LONG_TEXT)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-06-no-semantic-boundary")

    def test_a_boundary_present_stays_silent(self):
        self.assertEqual(sea.find_missing_semantic_boundary(True, self._LONG_TEXT), [])

    def test_a_short_page_stays_silent_even_with_no_boundary(self):
        self.assertEqual(sea.find_missing_semantic_boundary(False, "word " * 20), [])


class ContentRatioTests(unittest.TestCase):
    def test_a_low_ratio_fires(self):
        main_text = "content " * 10
        total_text = main_text + ("chrome " * 200)
        findings = sea.find_low_content_ratio(True, main_text, total_text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-07-low-content-ratio")

    def test_a_high_ratio_stays_silent(self):
        main_text = "content " * 150
        total_text = main_text + ("chrome " * 10)
        self.assertEqual(sea.find_low_content_ratio(True, main_text, total_text), [])

    def test_no_boundary_stays_silent_regardless_of_ratio(self):
        self.assertEqual(sea.find_low_content_ratio(False, "", "word " * 300), [])

    def test_below_the_word_floor_stays_silent(self):
        self.assertEqual(sea.find_low_content_ratio(True, "a", "word " * 20), [])


class MultimodalAccessibilityTests(unittest.TestCase):
    def test_missing_alt_on_a_non_decorative_image_fires(self):
        images = [{"has_alt": False, "decorative": False}]
        findings = sea.find_missing_alt_text(images)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-08-missing-alt-text")

    def test_decorative_image_with_no_alt_does_not_fire(self):
        images = [{"has_alt": False, "decorative": True}]
        self.assertEqual(sea.find_missing_alt_text(images), [])

    def test_image_with_alt_does_not_fire(self):
        images = [{"has_alt": True, "decorative": False}]
        self.assertEqual(sea.find_missing_alt_text(images), [])

    def test_no_images_produces_no_findings(self):
        self.assertEqual(sea.find_missing_alt_text([]), [])

    def test_media_without_track_fires(self):
        results = [{"tag": "video", "has_track": False}]
        findings = sea.find_missing_media_tracks(results)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-08-missing-media-track")

    def test_media_with_track_does_not_fire(self):
        results = [{"tag": "video", "has_track": True}]
        self.assertEqual(sea.find_missing_media_tracks(results), [])


class NapScriptOnlyPhoneTests(unittest.TestCase):
    def test_a_phone_only_in_script_fires(self):
        script_text = "var p = '555-123-4567';"
        findings = sea.find_nap_script_only_phone(script_text, "No phone here.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-10-phone-only-in-script")

    def test_a_phone_present_in_both_does_not_fire(self):
        script_text = "var p = '555-123-4567';"
        self.assertEqual(sea.find_nap_script_only_phone(script_text, "Call 555-123-4567 now."), [])

    def test_no_phone_in_script_stays_silent(self):
        self.assertEqual(sea.find_nap_script_only_phone("var x = 1;", "No phone here."), [])


class PdfRestatementSuggestionTests(unittest.TestCase):
    def test_a_pdf_link_produces_a_proactive_suggestion(self):
        findings = sea.find_pdf_restatement_suggestion(["/spec.pdf"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "REN-11-pdf-content-unverified")
        self.assertEqual(findings[0].track, "proactive")

    def test_no_pdf_links_produces_no_findings(self):
        self.assertEqual(sea.find_pdf_restatement_suggestion([]), [])

    def test_duplicate_links_are_deduplicated(self):
        findings = sea.find_pdf_restatement_suggestion(["/a.pdf", "/a.pdf", "/b.pdf"])
        self.assertEqual(findings[0].structured_evidence["pdf_link_count"], 2)


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        html = (
            '<script type="application/ld+json">{"@type": "Product", "offers": {"price": "29.99"}}</script>'
            "<h1>Widget</h1><p>No price stated here at all.</p>"
        )
        output = sea.audit_html("example.com", html)
        self.assertGreaterEqual(len(output["findings"]), 1)
        for finding_dict in output["findings"]:
            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "static-extraction-audit")
            self.assertEqual(restored.gate, 2)
            self.assertEqual(restored.category, "discoverability")

    def test_evaluation_is_deterministic(self):
        html = "<main><h1>Widget</h1><p>" + "word " * 200 + "</p></main>"
        first = sea.audit_html("example.com", html)
        second = sea.audit_html("example.com", html)
        self.assertEqual(first, second)

    def test_a_clean_page_produces_no_findings(self):
        html = "<main><h1>Widget</h1><p>" + "word " * 200 + "</p></main>"
        output = sea.audit_html("example.com", html)
        self.assertEqual(output["findings"], [])

    def test_agent_judgement_required_is_always_empty(self):
        html = "<main><h1>Widget</h1><p>Some text.</p></main>"
        output = sea.audit_html("example.com", html)
        self.assertEqual(output["agent_judgement_required"], [])


class PageAttributionTests(unittest.TestCase):
    def test_page_url_is_stamped_into_evidence_and_structured_evidence(self):
        html = '<a href="/spec.pdf">Spec</a>'
        output = sea.audit_html("example.com", html, page_url="https://example.com/page")
        finding = output["findings"][0]
        self.assertTrue(finding["evidence"].startswith("On https://example.com/page:"))
        self.assertEqual(finding["structured_evidence"]["page_url"], "https://example.com/page")

    def test_no_page_url_leaves_evidence_unstamped(self):
        html = '<a href="/spec.pdf">Spec</a>'
        output = sea.audit_html("example.com", html)
        self.assertFalse(output["findings"][0]["evidence"].startswith("On "))


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(sea.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(sea.is_public_host("10.0.0.5"))

    def test_an_unresolvable_host_is_refused(self):
        self.assertFalse(sea.is_public_host("this-host-does-not-exist.invalid"))


if __name__ == "__main__":
    unittest.main()
