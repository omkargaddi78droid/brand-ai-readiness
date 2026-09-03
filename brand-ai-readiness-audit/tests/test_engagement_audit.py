"""Unit tests for engagement-audit.

EN-06 and EN-09 are deterministic and tested as positive/negative pairs like
every other detector in this project. EN-01 and EN-03 are agent-judged: there
is no verdict function to test, only the extraction functions that build the
`agent_judgement_required` payload — those are tested for what they hand the
agent, not for a pass/fail they don't produce.

The label-ordering test documents a real bug: `<label for="pw">` appearing
*after* its `<input>` (legal, common) was not recognised, because the
labeled-or-not decision was made at input-open time using an as-yet-
incomplete set of seen labels.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_engagement", REPO_ROOT / "skills/engagement-audit/scripts/check_engagement.py"
)
eng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eng)


class FormLabelingTests(unittest.TestCase):
    def test_a_field_with_an_explicit_label_before_it_is_labeled(self):
        parser = eng.parse_page('<label for="n">Name</label><input id="n">')
        self.assertTrue(parser.fields[0]["labeled"])

    def test_a_field_with_an_explicit_label_after_it_is_labeled(self):
        """Regression: forward-referenced <label for=...> was not recognised
        because the check ran before the later label had been seen."""
        parser = eng.parse_page('<input id="pw" type="password"><label for="pw">Password</label>')
        self.assertTrue(parser.fields[0]["labeled"])

    def test_an_implicitly_wrapped_field_is_labeled(self):
        parser = eng.parse_page("<label>Phone<input type=\"tel\"></label>")
        self.assertTrue(parser.fields[0]["labeled"])

    def test_aria_label_counts_as_labeled(self):
        parser = eng.parse_page('<input aria-label="Search" type="text">')
        self.assertTrue(parser.fields[0]["labeled"])

    def test_empty_aria_label_does_not_count(self):
        parser = eng.parse_page('<input aria-label="" type="text">')
        self.assertFalse(parser.fields[0]["labeled"])

    def test_aria_labelledby_referencing_a_later_element_is_labeled(self):
        parser = eng.parse_page('<input aria-labelledby="lbl1"><span id="lbl1">Search term</span>')
        self.assertTrue(parser.fields[0]["labeled"])

    def test_a_placeholder_only_field_is_not_labeled(self):
        parser = eng.parse_page('<input type="email" placeholder="Email">')
        self.assertFalse(parser.fields[0]["labeled"])

    def test_hidden_submit_button_and_reset_fields_are_excluded(self):
        html = (
            '<input type="hidden" name="csrf" value="x">'
            '<input type="submit" value="Go">'
            '<input type="reset">'
            '<button type="button">Not counted, not an input</button>'
        )
        parser = eng.parse_page(html)
        self.assertEqual(parser.fields, [])

    def test_select_and_textarea_are_checked_too(self):
        parser = eng.parse_page("<select><option>A</option></select><textarea></textarea>")
        self.assertEqual(len(parser.fields), 2)
        self.assertFalse(any(f["labeled"] for f in parser.fields))


class UnlabelledFieldFindingTests(unittest.TestCase):
    def test_all_labeled_produces_nothing(self):
        parser = eng.parse_page('<label for="n">Name</label><input id="n">')
        self.assertEqual(eng.find_unlabelled_fields(parser), [])

    def test_unlabelled_fields_produce_one_aggregated_finding(self):
        html = '<input type="email" placeholder="Email"><input type="tel" placeholder="Phone">'
        parser = eng.parse_page(html)
        findings = eng.find_unlabelled_fields(parser)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["unlabelled_count"], 2)
        self.assertEqual(findings[0].category, "engagement")
        self.assertIsNone(findings[0].gate)


class InterstitialWallTests(unittest.TestCase):
    def test_a_dismissible_cookie_banner_is_not_flagged(self):
        html = (
            '<div role="dialog" class="cookie-modal">'
            "<p>We use cookies. Accept all cookies, or reject.</p>"
            "<button>Accept</button><button>Reject</button></div>"
        )
        self.assertEqual(eng.find_interstitial_walls(html), [])

    def test_a_modal_with_no_wall_language_is_not_flagged(self):
        html = '<div class="modal"><p>New feature launched!</p><button>Close</button></div>'
        self.assertEqual(eng.find_interstitial_walls(html), [])

    def test_wall_language_with_no_element_signal_is_not_flagged(self):
        """A plain paragraph mentioning cookies, with no dialog/modal/overlay
        marker at all, is not a content wall — it might just be a privacy
        policy page talking about cookies."""
        html = "<p>This site uses cookies. Accept cookies to personalise your experience.</p>"
        self.assertEqual(eng.find_interstitial_walls(html), [])

    def test_a_subscribe_wall_with_no_dismiss_is_flagged(self):
        html = (
            '<div role="dialog" aria-modal="true"><p>Subscribe to continue reading.</p>'
            "<button>Subscribe</button></div>"
        )
        findings = eng.find_interstitial_walls(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "high")
        self.assertEqual(findings[0].category, "engagement")

    def test_overlapping_signals_in_the_same_block_produce_one_finding_not_several(self):
        html = (
            '<div role="dialog" aria-modal="true" class="subscribe-modal" id="wall">'
            "<p>Subscribe to continue reading.</p><button>Subscribe</button></div>"
        )
        self.assertEqual(len(eng.find_interstitial_walls(html)), 1)

    def test_finding_id_is_stable_across_repeated_runs(self):
        """The id must not depend on Python's per-process hash randomisation."""
        html = '<div role="dialog"><p>Log in to continue.</p><button>Log in</button></div>'
        first = [f.id for f in eng.find_interstitial_walls(html)]
        second = [f.id for f in eng.find_interstitial_walls(html)]
        self.assertEqual(first, second)


class ViewportTests(unittest.TestCase):
    def test_no_viewport_tag_fires(self):
        findings = eng.find_missing_viewport("<html><head></head><body></body></html>")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-05-missing-viewport")

    def test_a_proper_viewport_tag_stays_silent(self):
        html = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        self.assertEqual(eng.find_missing_viewport(html), [])

    def test_a_viewport_tag_with_no_device_width_fires_the_lesser_finding(self):
        html = '<meta name="viewport" content="width=600">'
        findings = eng.find_missing_viewport(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-05-viewport-not-responsive")

    def test_device_width_with_extra_directives_still_counts_as_responsive(self):
        html = '<meta name="viewport" content="initial-scale=1, width=device-width, shrink-to-fit=no">'
        self.assertEqual(eng.find_missing_viewport(html), [])


class FixedWidthOverflowTests(unittest.TestCase):
    def test_a_wide_fixed_width_element_fires(self):
        html = '<div style="width:900px">wide</div>'
        findings = eng.find_fixed_width_overflow(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-05-fixed-width-overflow")

    def test_a_narrow_fixed_width_element_does_not_fire(self):
        html = '<div style="width:200px">narrow, fits any mobile viewport</div>'
        self.assertEqual(eng.find_fixed_width_overflow(html), [])

    def test_a_responsive_override_in_the_same_style_suppresses_it(self):
        html = '<div style="width:900px; max-width:100%">wide but responsive</div>'
        self.assertEqual(eng.find_fixed_width_overflow(html), [])

    def test_no_inline_styles_at_all_does_not_crash(self):
        self.assertEqual(eng.find_fixed_width_overflow("<p>Plain text only.</p>"), [])

    def test_multiple_offenders_aggregate_into_one_finding(self):
        html = '<div style="width:900px">a</div><div style="width:1000px">b</div>'
        findings = eng.find_fixed_width_overflow(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["count"], 2)


class RenderBlockingResourceTests(unittest.TestCase):
    def test_enough_blocking_resources_fires(self):
        head = "<head>" + '<script src="a.js"></script>' * 3 + '<link rel="stylesheet" href="a.css">' * 3 + "</head>"
        findings = eng.find_render_blocking_resources(head)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-07-render-blocking-resources")

    def test_deferred_scripts_are_not_counted_as_blocking(self):
        head = "<head>" + '<script src="a.js" defer></script>' * 5 + "</head>"
        self.assertEqual(eng.find_render_blocking_resources(head), [])

    def test_async_scripts_are_not_counted_as_blocking(self):
        head = "<head>" + '<script src="a.js" async></script>' * 5 + "</head>"
        self.assertEqual(eng.find_render_blocking_resources(head), [])

    def test_inline_scripts_with_no_src_are_not_counted(self):
        head = "<head>" + "<script>var x = 1;</script>" * 5 + "</head>"
        self.assertEqual(eng.find_render_blocking_resources(head), [])

    def test_below_the_threshold_stays_silent(self):
        head = "<head>" + '<script src="a.js"></script>' + '<link rel="stylesheet" href="a.css">' + "</head>"
        self.assertEqual(eng.find_render_blocking_resources(head), [])

    def test_a_script_outside_head_is_not_counted(self):
        html = "<head></head><body>" + '<script src="a.js"></script>' * 10 + "</body>"
        self.assertEqual(eng.find_render_blocking_resources(html), [])

    def test_no_head_element_at_all_stays_silent(self):
        self.assertEqual(eng.find_render_blocking_resources("<div>no head here</div>"), [])


class UnsizedImageTests(unittest.TestCase):
    def test_enough_unsized_images_fires(self):
        html = '<img src="a.jpg">' * 4
        findings = eng.find_unsized_images(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-07-unsized-images")

    def test_images_with_width_and_height_do_not_count(self):
        html = '<img src="a.jpg" width="100" height="100">' * 4
        self.assertEqual(eng.find_unsized_images(html), [])

    def test_an_inline_aspect_ratio_counts_as_sized(self):
        html = '<img src="a.jpg" style="aspect-ratio: 16/9">' * 4
        self.assertEqual(eng.find_unsized_images(html), [])

    def test_below_the_threshold_stays_silent(self):
        html = '<img src="a.jpg">' * 2
        self.assertEqual(eng.find_unsized_images(html), [])

    def test_no_images_at_all_stays_silent(self):
        self.assertEqual(eng.find_unsized_images("<p>No images here.</p>"), [])


class PayloadWeightTests(unittest.TestCase):
    def test_a_large_document_fires(self):
        html = "<html>" + ("x" * 310_000) + "</html>"
        findings = eng.find_payload_weight(html)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "EN-07-heavy-html-payload")

    def test_a_small_document_stays_silent(self):
        self.assertEqual(eng.find_payload_weight("<html>small</html>"), [])


class ExtractionForAgentJudgementTests(unittest.TestCase):
    """These functions produce evidence for the agent, not a verdict. Tested
    for what they hand over, not for a pass/fail they deliberately don't
    compute."""

    def test_orientation_signals_carry_the_h1_and_leading_text(self):
        html = "<h1>Example Corp</h1><p>We help small teams ship faster.</p>"
        parser = eng.parse_page(html)
        signals = eng.extract_orientation_signals(parser, parser.visible_text())
        self.assertEqual(signals["h1_text"], "Example Corp")
        self.assertIn("ship faster", signals["first_150_words"])

    def test_orientation_signals_collect_candidate_ctas(self):
        html = '<a href="/start">Get started</a><button>Book a demo</button>'
        parser = eng.parse_page(html)
        signals = eng.extract_orientation_signals(parser, parser.visible_text())
        self.assertIn("Get started", signals["candidate_cta_texts"])
        self.assertIn("Book a demo", signals["candidate_cta_texts"])

    def test_conversion_signals_detect_a_password_field_without_guest_language(self):
        html = '<form><input type="password"></form><p>Checkout now.</p>'
        parser = eng.parse_page(html)
        signals = eng.extract_conversion_path_signals(parser, parser.visible_text())
        self.assertEqual(signals["forms_with_password_field"], 1)
        self.assertFalse(signals["guest_checkout_language_present"])

    def test_conversion_signals_recognise_guest_checkout_language(self):
        html = "<p>You can continue as a guest, no account required.</p>"
        parser = eng.parse_page(html)
        signals = eng.extract_conversion_path_signals(parser, parser.visible_text())
        self.assertTrue(signals["guest_checkout_language_present"])

    def test_conversion_signals_capture_fee_disclosure_snippets(self):
        html = "<p>Price shown excludes shipping and applicable taxes.</p>"
        parser = eng.parse_page(html)
        signals = eng.extract_conversion_path_signals(parser, parser.visible_text())
        self.assertTrue(signals["fee_or_tax_disclosure_snippets"])

    def test_agent_judgement_requests_name_both_capabilities(self):
        parser = eng.parse_page("<h1>Hi</h1>")
        requests = eng.build_agent_judgement_requests(parser, parser.visible_text())
        self.assertEqual({r["capability_id"] for r in requests}, {"EN-01", "EN-03"})
        for request in requests:
            self.assertIn("references/engagement-judgement-rubric.md", request["instructions"])


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        html = (
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<input type="email" placeholder="Email">'
            '<div role="dialog" aria-modal="true"><p>Subscribe to continue reading.</p>'
            "<button>Subscribe</button></div>"
        )
        out = eng.audit_html("example.com", html, page_url="https://example.com/page")
        self.assertEqual(len(out["findings"]), 2)
        for finding_dict in out["findings"]:
            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "engagement-audit")
            self.assertIsNone(restored.gate)
            self.assertEqual(restored.category, "engagement")

    def test_agent_judgement_required_is_present_and_is_not_a_finding(self):
        out = eng.audit_html("example.com", "<h1>Hi</h1>")
        self.assertIn("agent_judgement_required", out)
        self.assertEqual(len(out["agent_judgement_required"]), 2)

    def test_evaluation_is_deterministic(self):
        html = '<input type="email" placeholder="Email">'
        first = eng.audit_html("example.com", html)
        second = eng.audit_html("example.com", html)
        self.assertEqual(first, second)


class UnresolvedJudgementCompositionTests(unittest.TestCase):
    """If the calling procedure forgets to resolve `agent_judgement_required`
    before handing the file to compose_report.py, that must become a visible
    `unknown_checks` entry — never a silent drop, and never a crash."""

    def _orchestrator(self):
        spec = importlib.util.spec_from_file_location(
            "compose_report", REPO_ROOT / "skills/audit-orchestrator/scripts/compose_report.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_an_unresolved_entry_becomes_an_unknown_check_not_a_silent_drop(self):
        import tempfile

        orchestrator = self._orchestrator()
        html = '<meta name="viewport" content="width=device-width, initial-scale=1"><h1>Hi</h1>'
        skill_output = eng.audit_html("example.com", html, page_url="https://example.com/")
        self.assertEqual(skill_output["agent_judgement_required"][0]["capability_id"], "EN-01")

        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "engagement.json"
            path.write_text(json.dumps(skill_output), encoding="utf-8")
            report = orchestrator.compose("example.com", [("engagement-audit", str(path))], audited_at="2026-09-20T14:32:00Z")

        unresolved = {u["capability_id"] for u in report["unknown_checks"]}
        self.assertEqual(unresolved, {"EN-01", "EN-03"})
        self.assertEqual(report["findings"], [])


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(eng.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(eng.is_public_host("10.0.0.5"))


if __name__ == "__main__":
    unittest.main()
