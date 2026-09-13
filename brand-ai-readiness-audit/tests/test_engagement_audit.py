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

from finding_contract import Finding, merge_paginated_findings  # noqa: E402

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

    def test_bug_003_a_css_class_hidden_text_field_is_excluded(self):
        # type="hidden" is not the only way markup takes a field out of a
        # person's or an agent's path — class="... hidden" is the common
        # JS-widget convention for the same thing on a type="text" field.
        parser = eng.parse_page('<input type="text" class="lead-service-id hidden" value="2">')
        self.assertEqual(parser.fields, [])

    def test_bug_003_the_hidden_boolean_attribute_is_excluded(self):
        parser = eng.parse_page('<input type="text" hidden value="x">')
        self.assertEqual(parser.fields, [])

    def test_bug_003_aria_hidden_true_is_excluded(self):
        parser = eng.parse_page('<input type="text" aria-hidden="true">')
        self.assertEqual(parser.fields, [])

    def test_bug_003_inline_display_none_is_excluded(self):
        parser = eng.parse_page('<input type="text" style="display: none;">')
        self.assertEqual(parser.fields, [])

    def test_bug_003_visually_hidden_class_is_not_excluded(self):
        # "visually-hidden"/"sr-only" means hidden from sighted users but
        # still exposed to assistive tech — it still needs a real name.
        parser = eng.parse_page('<input type="text" class="visually-hidden">')
        self.assertEqual(len(parser.fields), 1)

    def test_bug_003_a_class_token_that_merely_contains_hidden_is_not_excluded(self):
        # "hidden" must match as a whole class token, not a substring —
        # a class like "overhidden-field" is not this convention.
        parser = eng.parse_page('<input type="text" class="overhidden-field">')
        self.assertEqual(len(parser.fields), 1)

    def test_select_and_textarea_are_checked_too(self):
        parser = eng.parse_page("<select><option>A</option></select><textarea></textarea>")
        self.assertEqual(len(parser.fields), 2)
        self.assertFalse(any(f["labeled"] for f in parser.fields))

    def test_a_disabled_field_is_excluded(self):
        parser = eng.parse_page('<input type="text" disabled>')
        self.assertEqual(parser.fields, [])

    def test_a_readonly_range_is_excluded(self):
        """paytm live-testing false positive: a readonly range input is a
        decorative gauge/progress display, never a real interactive
        slider — a native range input cannot be dragged when readonly."""
        parser = eng.parse_page('<input type="range" readonly value="70">')
        self.assertEqual(parser.fields, [])

    def test_a_real_interactive_range_is_still_checked(self):
        """Real interactive range sliders (price filters, volume controls)
        must still be caught — only readonly/disabled ranges are exempt."""
        parser = eng.parse_page('<input type="range" min="0" max="100">')
        self.assertEqual(len(parser.fields), 1)
        self.assertFalse(parser.fields[0]["labeled"])

    def test_a_readonly_text_field_is_not_excluded(self):
        """readonly is exempted only for type="range" — a readonly
        text/number field can still carry information (e.g. a computed
        total) that needs a name."""
        parser = eng.parse_page('<input type="text" readonly value="42">')
        self.assertEqual(len(parser.fields), 1)


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


class MachineReadableActionTests(unittest.TestCase):
    """EN-09 extension (cycle 23 Phase 2): schema.org potentialAction /
    WebMCP detection. Every case below wraps its fields in a real <form>,
    unlike the label-only fixtures above — form_count is part of the gate."""

    _TWO_FIELD_FORM = '<form><input type="text" id="a"><input type="text" id="b"></form>'

    def test_a_non_trivial_form_with_no_signal_at_all_fires(self):
        parser = eng.parse_page(self._TWO_FIELD_FORM)
        findings = eng.find_missing_machine_readable_action(parser)
        self.assertEqual([f.id for f in findings], ["EN-09-no-machine-readable-action"])
        self.assertEqual(findings[0].track, "proactive")
        self.assertEqual(findings[0].severity, "low")

    def test_a_single_field_form_is_too_trivial_to_evaluate(self):
        html = '<form><input type="text" id="q" placeholder="Search"></form>'
        parser = eng.parse_page(html)
        self.assertEqual(eng.find_missing_machine_readable_action(parser), [])

    def test_no_forms_at_all_is_silent(self):
        parser = eng.parse_page("<p>No forms on this page.</p>")
        self.assertEqual(eng.find_missing_machine_readable_action(parser), [])

    def test_a_potential_action_in_json_ld_suppresses_the_finding(self):
        html = self._TWO_FIELD_FORM + (
            '<script type="application/ld+json">'
            '{"@type":"WebSite","potentialAction":{"@type":"SearchAction","target":"https://example.com/?q={q}"}}'
            "</script>"
        )
        parser = eng.parse_page(html)
        self.assertEqual(eng.find_missing_machine_readable_action(parser), [])

    def test_a_webmcp_inline_script_signature_suppresses_the_finding(self):
        html = self._TWO_FIELD_FORM + "<script>navigator.modelContext.registerTool({});</script>"
        parser = eng.parse_page(html)
        self.assertEqual(eng.find_missing_machine_readable_action(parser), [])

    def test_a_webmcp_declarative_form_attribute_suppresses_the_finding(self):
        html = '<form toolname="book-appointment"><input type="text" id="a"><input type="text" id="b"></form>'
        parser = eng.parse_page(html)
        self.assertEqual(eng.find_missing_machine_readable_action(parser), [])

    def test_an_external_script_with_no_src_fetch_never_sees_its_content(self):
        """This skill never fetches linked JS (same EN-07 narrowing) — a
        <script src="..."> tag's own attributes/URL are not scanned for
        WebMCP text, only a truly inline script's body is."""
        html = self._TWO_FIELD_FORM + '<script src="https://example.com/registerTool-modelContext.js"></script>'
        parser = eng.parse_page(html)
        findings = eng.find_missing_machine_readable_action(parser)
        self.assertEqual([f.id for f in findings], ["EN-09-no-machine-readable-action"])

    def test_finding_validates_against_the_shared_contract(self):
        parser = eng.parse_page(self._TWO_FIELD_FORM)
        finding = eng.find_missing_machine_readable_action(parser)[0]
        self.assertEqual(finding.validate(), [])


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

    def test_bug_001_a_leading_cookie_banner_is_skipped_from_first_150_words(self):
        html = (
            "<p>We use cookies to improve your experience. Accept all cookies to continue.</p>"
            "<h1>Example Corp</h1><p>We help small teams ship faster.</p>"
        )
        parser = eng.parse_page(html)
        signals = eng.extract_orientation_signals(parser, parser.visible_text())
        self.assertIn("ship faster", signals["first_150_words"])
        self.assertNotIn("cookies", signals["first_150_words"].lower())

    def test_bug_001_a_generic_intro_line_before_the_banner_sentence_is_also_skipped(self):
        # Real consent banners often render a generic intro/heading line
        # ("Help us improve your experience") before the sentence that
        # actually names a cookie action, and use a curly apostrophe
        # ("we’d like...") rather than a straight one. Both must not
        # defeat the skip.
        html = (
            "<p>Help us improve your experience</p>"
            "<p>In addition to Cookies necessary for this site, we’d like your "
            "permission to set some additional Cookies.</p>"
            "<p>Accept All Additional Cookies Reject All Additional Cookies</p>"
            "<h1>Example Corp</h1><p>We help small teams ship faster.</p>"
        )
        parser = eng.parse_page(html)
        signals = eng.extract_orientation_signals(parser, parser.visible_text())
        self.assertIn("ship faster", signals["first_150_words"])
        self.assertNotIn("cookies", signals["first_150_words"].lower())

    def test_bug_001_total_word_count_still_counts_the_banner(self):
        # The 150-word opening window skips the banner; the page's overall
        # word count must not silently shrink because of that.
        html = "<p>We use cookies to improve your experience.</p><h1>Example Corp</h1>"
        parser = eng.parse_page(html)
        full_text = parser.visible_text()
        signals = eng.extract_orientation_signals(parser, full_text)
        self.assertEqual(signals["total_word_count"], len(full_text.split()))

    def test_bug_001_cookie_banner_buttons_are_excluded_from_candidate_ctas(self):
        html = (
            "<button>Accept All Additional Cookies</button>"
            "<button>Reject All Additional Cookies</button>"
            '<a href="/start">Get started</a>'
        )
        parser = eng.parse_page(html)
        signals = eng.extract_orientation_signals(parser, parser.visible_text())
        self.assertEqual(signals["candidate_cta_texts"], ["Get started"])

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


class PrimaryCtaTests(unittest.TestCase):
    def test_returns_the_first_cta_text_in_document_order(self):
        parser = eng.parse_page('<a href="/a">Start free trial</a><a href="/b">Learn more</a>')
        self.assertEqual(eng._primary_cta(parser), "Start free trial")

    def test_no_cta_at_all_returns_none(self):
        parser = eng.parse_page("<p>No buttons or links here.</p>")
        self.assertIsNone(eng._primary_cta(parser))

    def test_bug_001_a_leading_cookie_banner_button_is_skipped(self):
        html = (
            "<button>Accept All Additional Cookies</button>"
            "<button>Reject All Additional Cookies</button>"
            '<a href="/start">Start free trial</a>'
        )
        parser = eng.parse_page(html)
        self.assertEqual(eng._primary_cta(parser), "Start free trial")

    def test_bug_001_only_cookie_banner_ctas_returns_none(self):
        parser = eng.parse_page("<button>Accept All Cookies</button><button>Cookie settings</button>")
        self.assertIsNone(eng._primary_cta(parser))

    def test_a_nav_link_before_the_real_cta_is_skipped(self):
        """paytm live-testing false positive: a global header/nav utility
        link ("Mobile Recharge") preceded the page's real hero CTA in
        document order and was picked as the "primary CTA" instead."""
        html = (
            '<header><a href="/recharge">Mobile Recharge</a></header>'
            '<main><h1>Pay Loan EMI</h1><a href="/pay">Pay Loan EMI</a></main>'
        )
        parser = eng.parse_page(html)
        self.assertEqual(eng._primary_cta(parser), "Pay Loan EMI")

    def test_a_link_inside_nav_is_skipped(self):
        html = '<nav><a href="/home">Home</a></nav><a href="/start">Start free trial</a>'
        parser = eng.parse_page(html)
        self.assertEqual(eng._primary_cta(parser), "Start free trial")

    def test_a_link_inside_role_navigation_is_skipped(self):
        html = (
            '<div role="navigation"><a href="/home">Home</a></div>'
            '<a href="/start">Start free trial</a>'
        )
        parser = eng.parse_page(html)
        self.assertEqual(eng._primary_cta(parser), "Start free trial")

    def test_only_chrome_ctas_returns_none(self):
        parser = eng.parse_page('<header><a href="/recharge">Mobile Recharge</a></header>')
        self.assertIsNone(eng._primary_cta(parser))

    def test_a_cta_in_the_main_content_is_still_picked_when_no_chrome_precedes_it(self):
        html = '<main><a href="/start">Start free trial</a></main><footer><a href="/about">About</a></footer>'
        parser = eng.parse_page(html)
        self.assertEqual(eng._primary_cta(parser), "Start free trial")


class CtaCoherenceCandidateTests(unittest.TestCase):
    def test_a_cta_sharing_no_vocabulary_with_the_h1_is_a_candidate(self):
        candidate = eng._cta_coherence_candidate(
            "https://acme.com/refund-policy", "Refund Policy", "Subscribe to our newsletter"
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["page_url"], "https://acme.com/refund-policy")
        self.assertLess(candidate["lexical_overlap_score"], eng._INFO_SCENT_LOW_OVERLAP_THRESHOLD)

    def test_a_cta_that_echoes_the_h1_is_not_a_candidate(self):
        candidate = eng._cta_coherence_candidate(
            "https://acme.com/pricing", "Pricing Plans", "See pricing plans"
        )
        self.assertIsNone(candidate)


class LinkScentCandidateTests(unittest.TestCase):
    def test_anchor_text_unrelated_to_target_h1_is_a_candidate(self):
        page_h1 = {"https://acme.com/returns": "Return & Refund Policy"}
        internal_links = {
            "https://acme.com/home": [
                eng.LinkRef(url="https://acme.com/returns", anchor_text="Check this out")
            ]
        }
        candidates = eng._link_scent_candidates(page_h1, internal_links)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["target_page_url"], "https://acme.com/returns")

    def test_anchor_text_matching_target_h1_is_not_a_candidate(self):
        page_h1 = {"https://acme.com/returns": "Return & Refund Policy"}
        internal_links = {
            "https://acme.com/home": [
                eng.LinkRef(url="https://acme.com/returns", anchor_text="Refund Policy")
            ]
        }
        self.assertEqual(eng._link_scent_candidates(page_h1, internal_links), [])

    def test_link_to_a_page_outside_the_sample_is_not_a_candidate(self):
        """A target with no known H1 (not itself in the sample) cannot be
        scored — silently skipped, not flagged."""
        internal_links = {
            "https://acme.com/home": [
                eng.LinkRef(url="https://acme.com/unsampled", anchor_text="Random text")
            ]
        }
        self.assertEqual(eng._link_scent_candidates({}, internal_links), [])

    def test_empty_anchor_text_is_not_a_candidate(self):
        page_h1 = {"https://acme.com/returns": "Return & Refund Policy"}
        internal_links = {
            "https://acme.com/home": [eng.LinkRef(url="https://acme.com/returns", anchor_text="")]
        }
        self.assertEqual(eng._link_scent_candidates(page_h1, internal_links), [])

    def test_candidates_are_capped_and_sorted_lowest_score_first(self):
        page_h1 = {f"https://acme.com/page{i}": f"Topic {i} specifics" for i in range(20)}
        internal_links = {
            "https://acme.com/home": [
                eng.LinkRef(url=f"https://acme.com/page{i}", anchor_text="Click here now")
                for i in range(20)
            ]
        }
        candidates = eng._link_scent_candidates(page_h1, internal_links)
        self.assertLessEqual(len(candidates), eng._INFO_SCENT_MAX_CANDIDATES)
        scores = [c["lexical_overlap_score"] for c in candidates]
        self.assertEqual(scores, sorted(scores))


class AuditSampledPagesTests(unittest.TestCase):
    def test_an_unreachable_page_becomes_one_unknown_check(self):
        out = eng.audit_sampled_pages("acme.com", ["https://this-host-does-not-exist.invalid/page"])
        self.assertEqual(out["agent_judgement_required"], [])
        self.assertEqual(len(out["unknown_checks"]), 1)
        self.assertIn("this-host-does-not-exist.invalid", out["unknown_checks"][0]["reason"])

    def test_no_page_urls_produces_an_empty_clean_report_not_a_crash(self):
        out = eng.audit_sampled_pages("acme.com", [])
        self.assertEqual(out["agent_judgement_required"], [])
        self.assertEqual(out["unknown_checks"], [])

    def test_output_always_carries_the_capability_ids(self):
        out = eng.audit_sampled_pages("acme.com", [])
        self.assertEqual(out["capability_ids"], eng.CAPABILITY_IDS)
        self.assertIn("EN-11", out["capability_ids"])
        self.assertIn("EN-08", out["capability_ids"])

    def test_coverage_manifest_is_always_attached_and_not_expired_by_default(self):
        out = eng.audit_sampled_pages("acme.com", [])
        self.assertEqual(len(out["coverage"]["stages"]), 1)
        self.assertFalse(out["coverage"]["stages"][0]["expired"])

    def test_pages_beyond_the_fetch_budget_get_an_unknown_check_not_a_hang(self):
        calls = {"n": 0}

        def fake_clock():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 1000.0

        page_urls = ["https://this-host-does-not-exist.invalid/a", "https://this-host-does-not-exist.invalid/b"]
        out = eng.audit_sampled_pages("acme.com", page_urls, clock=fake_clock)
        self.assertEqual(len(out["unknown_checks"]), 2)
        for unknown in out["unknown_checks"]:
            self.assertEqual(unknown["capability_id"], "*")
            self.assertIn("budget", unknown["reason"])
        self.assertTrue(out["coverage"]["stages"][0]["expired"])

    def test_navigational_chrome_anchor_text_is_excluded_before_scoring(self):
        """Dominant false positive: a plain 'Home' link to a welcome-copy H1
        would otherwise score low and wrongly look like weak scent — this is
        why `audit_sampled_pages` drops nav-chrome anchor text from
        `internal_links` before `_link_scent_candidates` ever sees it."""
        self.assertIn("home", eng._NAV_CHROME_ANCHOR_TEXTS)
        self.assertIn("contact", eng._NAV_CHROME_ANCHOR_TEXTS)
        # Sanity: without the filter this pair WOULD score low, confirming
        # the filter (not a coincidentally high score) is what protects it.
        page_h1 = {"https://acme.com/": "Welcome to Acme Widgets"}
        internal_links = {
            "https://acme.com/about": [eng.LinkRef(url="https://acme.com/", anchor_text="Home")]
        }
        self.assertEqual(len(eng._link_scent_candidates(page_h1, internal_links)), 1)


class DeadEndPageTests(unittest.TestCase):
    def test_zero_internal_links_and_no_cta_is_a_dead_end(self):
        raw_internal_links = {"https://acme.com/thanks": []}
        findings = eng.find_dead_end_pages(raw_internal_links, page_cta={})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "EN-04")
        self.assertIn("https://acme.com/thanks", findings[0].evidence)

    def test_zero_internal_links_but_has_a_cta_is_not_a_dead_end(self):
        """Dominant false positive: a page whose only actions are external
        (e.g. an off-site payment redirect button) still has a next step."""
        raw_internal_links = {"https://acme.com/checkout": []}
        page_cta = {"https://acme.com/checkout": "Pay with Stripe"}
        self.assertEqual(eng.find_dead_end_pages(raw_internal_links, page_cta), [])

    def test_has_internal_links_but_no_cta_is_not_a_dead_end(self):
        """A nav-only page (e.g. a category hub) with real internal links
        but no CTA text still gives a visitor somewhere to go."""
        raw_internal_links = {
            "https://acme.com/category": [eng.LinkRef(url="https://acme.com/item1", anchor_text="Item 1")]
        }
        self.assertEqual(eng.find_dead_end_pages(raw_internal_links, page_cta={}), [])

    def test_finding_validates_against_the_shared_contract(self):
        raw_internal_links = {"https://acme.com/thanks": []}
        finding = eng.find_dead_end_pages(raw_internal_links, page_cta={})[0]
        self.assertEqual(finding.validate(), [])

    def test_id_is_shared_across_pages_so_findings_can_be_merged(self):
        """Regression: a per-URL id defeats merge_paginated_findings, which
        groups by exact id — every dead-end finding must share one id."""
        raw_internal_links = {"https://acme.com/thanks": [], "https://acme.com/other": []}
        findings = eng.find_dead_end_pages(raw_internal_links, page_cta={})
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].id, findings[1].id)


def _filler_links(count: int) -> list["eng.LinkRef"]:
    """Outbound links (add to the homepage's own link list) pointing at
    `_filler_pages(count)` so those pages aren't themselves orphans."""
    return [eng.LinkRef(url=f"https://acme.com/filler-{i}", anchor_text=f"Filler {i}") for i in range(count)]


def _filler_pages(count: int) -> dict[str, list["eng.LinkRef"]]:
    """Non-orphan padding pages so a test sample can reach
    `_EN04_MIN_SAMPLE_SIZE_FOR_ORPHAN` without introducing unrelated
    orphan/inbound-link noise into the case under test. Must be paired with
    `_filler_links(count)` added to some other page's outbound links, or
    these pages will themselves register as orphans."""
    return {f"https://acme.com/filler-{i}": [] for i in range(count)}


class OrphanPageTests(unittest.TestCase):
    def test_a_page_with_no_inbound_internal_link_is_flagged(self):
        raw_internal_links = {
            "https://acme.com/": [eng.LinkRef(url="https://acme.com/about", anchor_text="About")]
            + _filler_links(2),
            "https://acme.com/about": [],
            "https://acme.com/orphan": [],
            **_filler_pages(2),
        }
        findings = eng.find_orphan_pages(raw_internal_links)
        self.assertEqual(len(findings), 1)
        self.assertIn("orphan", findings[0].id)
        self.assertEqual(findings[0].severity, "medium")

    def test_the_homepage_is_never_flagged_as_an_orphan(self):
        """Dominant false positive: a site's homepage is expected to have
        few or no inbound *internal* links — visitors arrive at it from
        outside the site, not by following an internal link. Padded to
        clear the minimum-sample-size gate so the homepage's own 0
        in-degree is the only thing under test — without the exemption
        this would be flagged."""
        raw_internal_links = {"https://acme.com/": _filler_links(4), **_filler_pages(4)}
        self.assertEqual(eng.find_orphan_pages(raw_internal_links), [])

    def test_a_page_linked_from_another_sampled_page_is_not_an_orphan(self):
        raw_internal_links = {
            "https://acme.com/": [eng.LinkRef(url="https://acme.com/pricing", anchor_text="Pricing")]
            + _filler_links(3),
            "https://acme.com/pricing": [],
            **_filler_pages(3),
        }
        self.assertEqual(eng.find_orphan_pages(raw_internal_links), [])

    def test_below_minimum_sample_size_emits_nothing(self):
        """Scribd live-testing false positive: a thin sample (e.g. 9 pages
        against a 170M-document platform) should not produce a
        site-scale-blind orphan claim at all when the sample is even
        thinner than this floor."""
        raw_internal_links = {"https://acme.com/": [], "https://acme.com/orphan": []}
        self.assertEqual(eng.find_orphan_pages(raw_internal_links), [])

    def test_confidence_is_low_below_the_low_confidence_sample_size(self):
        raw_internal_links = {
            "https://acme.com/": _filler_links(3),
            "https://acme.com/orphan": [],
            **_filler_pages(3),
        }
        finding = eng.find_orphan_pages(raw_internal_links)[0]
        self.assertEqual(finding.confidence, "low")
        self.assertIn("weak signal", finding.evidence)

    def test_confidence_is_medium_at_or_above_the_low_confidence_sample_size(self):
        raw_internal_links = {
            "https://acme.com/": _filler_links(18),
            "https://acme.com/orphan": [],
            **_filler_pages(18),
        }
        finding = eng.find_orphan_pages(raw_internal_links)[0]
        self.assertEqual(finding.confidence, "medium")
        self.assertNotIn("weak signal", finding.evidence)

    def test_evidence_states_its_own_sample_size_never_site_wide_scope(self):
        raw_internal_links = {
            "https://acme.com/": _filler_links(3),
            "https://acme.com/orphan": [],
            **_filler_pages(3),
        }
        finding = eng.find_orphan_pages(raw_internal_links)[0]
        self.assertIn("5 pages sampled", finding.evidence)
        self.assertIn("does not prove site-wide orphan status", finding.evidence)

    def test_finding_validates_against_the_shared_contract(self):
        raw_internal_links = {
            "https://acme.com/": _filler_links(3),
            "https://acme.com/orphan": [],
            **_filler_pages(3),
        }
        finding = eng.find_orphan_pages(raw_internal_links)[0]
        self.assertEqual(finding.validate(), [])

    def test_id_is_shared_across_pages_so_findings_can_be_merged(self):
        """Regression: a per-URL id defeats merge_paginated_findings, which
        groups by exact id — every orphan finding must share one id."""
        raw_internal_links = {
            "https://acme.com/": _filler_links(2),
            "https://acme.com/orphan-a": [],
            "https://acme.com/orphan-b": [],
            **_filler_pages(2),
        }
        findings = eng.find_orphan_pages(raw_internal_links)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].id, findings[1].id)


class IsHomepageTests(unittest.TestCase):
    def test_root_path_is_the_homepage(self):
        self.assertTrue(eng._is_homepage("https://acme.com/"))

    def test_empty_path_is_the_homepage(self):
        self.assertTrue(eng._is_homepage("https://acme.com"))

    def test_a_subpage_is_not_the_homepage(self):
        self.assertFalse(eng._is_homepage("https://acme.com/about"))


class OrphanAndDeadEndMergeIntegrationTests(unittest.TestCase):
    """Regression for the bug where per-URL ids defeated
    merge_paginated_findings: many single-page orphan/dead-end findings
    should collapse into one finding per check, not stay separate."""

    def test_orphan_findings_across_pages_merge_into_one(self):
        raw_internal_links = {
            "https://acme.com/": _filler_links(1),
            "https://acme.com/orphan-a": [],
            "https://acme.com/orphan-b": [],
            "https://acme.com/orphan-c": [],
            **_filler_pages(1),
        }
        findings = eng.find_orphan_pages(raw_internal_links)
        self.assertEqual(len(findings), 3)
        merged = merge_paginated_findings(findings)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].structured_evidence["affected_page_count"], 3)

    def test_dead_end_findings_across_pages_merge_into_one(self):
        raw_internal_links = {
            "https://acme.com/dead-a": [],
            "https://acme.com/dead-b": [],
        }
        findings = eng.find_dead_end_pages(raw_internal_links, page_cta={})
        self.assertEqual(len(findings), 2)
        merged = merge_paginated_findings(findings)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].structured_evidence["affected_page_count"], 2)


if __name__ == "__main__":
    unittest.main()
