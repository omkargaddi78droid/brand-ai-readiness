"""Unit tests for content-quality-audit (CQ-03/05/07/08).

Each detector is tested as a positive/negative pair, per project convention.
Three of the negative cases here are regression fixtures for real bugs found
while building this skill — not hypothetical edge cases:

- "this weekend" containing the literal substring "this week"
- "period" containing the literal substring "per" (a qualifier word)
- "ratings" vs "rating" needing a stem match, not exact-string equality
- a parenthesised label ("Delivery times (days)") the label regex first
  failed to parse at all

All four were caught by running the detectors against realistic fixtures
before writing a single formal test — see docs/phase-4-completion-2.md.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import validate_floor_shape  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_content_quality", REPO_ROOT / "skills/content-quality-audit/scripts/check_content_quality.py"
)
cq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cq)


class ExtractVisibleTextTests(unittest.TestCase):
    def test_script_and_style_are_stripped(self):
        html = "<html><head><style>.x{color:red}</style></head><body><script>alert(1)</script><p>Hello.</p></body></html>"
        self.assertEqual(cq.extract_visible_text(html), "Hello.")

    def test_code_and_pre_are_stripped(self):
        html = "<p>Before.</p><pre><code>{{ leaked }}</code></pre><p>After.</p>"
        text = cq.extract_visible_text(html)
        self.assertNotIn("leaked", text)
        self.assertIn("Before.", text)
        self.assertIn("After.", text)

    def test_entities_are_decoded(self):
        self.assertEqual(cq.extract_visible_text("<p>Tom &amp; Jerry</p>"), "Tom & Jerry")

    def test_block_tags_produce_separate_lines(self):
        text = cq.extract_visible_text("<div>One</div><div>Two</div>")
        self.assertEqual(text, "One\nTwo")

    def test_whitespace_within_a_line_is_collapsed(self):
        text = cq.extract_visible_text("<p>Too    much   \n  space</p>")
        self.assertEqual(text, "Too much space")


class ExtractH1Tests(unittest.TestCase):
    def test_the_first_h1_text_is_extracted(self):
        html = "<html><body><h1>Shipping Policy</h1><p>Details.</p></body></html>"
        self.assertEqual(cq.extract_h1(html), "Shipping Policy")

    def test_nested_markup_inside_h1_is_flattened(self):
        html = "<h1>Shipping <span>Policy</span></h1>"
        self.assertEqual(cq.extract_h1(html), "Shipping Policy")

    def test_only_the_first_h1_is_kept(self):
        html = "<h1>First</h1><h1>Second</h1>"
        self.assertEqual(cq.extract_h1(html), "First")

    def test_no_h1_returns_none(self):
        html = "<p>No heading here.</p>"
        self.assertIsNone(cq.extract_h1(html))


class TemplateLeakageTests(unittest.TestCase):
    def test_mustache_token_is_detected(self):
        findings = cq.find_template_leakage("Welcome, {{first_name}}!")
        self.assertEqual(len(findings), 1)
        self.assertIn("{{first_name}}", findings[0].structured_evidence["tokens"])
        self.assertEqual(findings[0].severity, "high")

    def test_liquid_tag_is_detected(self):
        findings = cq.find_template_leakage("{% if user.premium %}Welcome{% endif %}")
        self.assertEqual(len(findings), 1)

    def test_erb_tag_is_detected(self):
        findings = cq.find_template_leakage("Hello <%= user.name %>, welcome back.")
        self.assertEqual(len(findings), 1)

    def test_ordinary_prose_with_braces_does_not_fire(self):
        """A single brace, or braces around a full sentence, are not
        templating syntax."""
        findings = cq.find_template_leakage("The set is defined as {1, 2, 3} in the textbook.")
        self.assertEqual(findings, [])

    def test_multiple_distinct_tokens_are_deduplicated_and_counted(self):
        text = "{{first_name}} ordered {{order_id}}. {{first_name}} will love it."
        findings = cq.find_template_leakage(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["total_matches"], 3)
        self.assertEqual(len(findings[0].structured_evidence["tokens"]), 2)

    def test_code_block_examples_are_excluded_via_extraction(self):
        html = "<p>Use the double-brace syntax to insert a variable.</p><pre><code>{{ product.title }}</code></pre>"
        self.assertEqual(cq.find_template_leakage(cq.extract_visible_text(html)), [])


class RelativeDateAnchorTests(unittest.TestCase):
    def test_a_claim_verb_plus_relative_phrase_with_no_date_fires(self):
        findings = cq.find_relative_date_anchors("We updated our return policy last month.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")

    def test_an_absolute_date_in_the_same_sentence_suppresses_it(self):
        findings = cq.find_relative_date_anchors("We updated our return policy in March 2026.")
        self.assertEqual(findings, [])

    def test_a_bare_year_counts_as_an_absolute_anchor(self):
        findings = cq.find_relative_date_anchors("Prices increased recently, following the 2025 review.")
        self.assertEqual(findings, [])

    def test_a_relative_phrase_with_no_claim_verb_does_not_fire(self):
        findings = cq.find_relative_date_anchors("This week's newsletter covers three topics.")
        self.assertEqual(findings, [])

    def test_this_weekend_is_not_matched_as_this_week(self):
        """Regression: 'this weekend' contains the literal substring 'this
        week'. Word-boundary matching must not treat it as the phrase."""
        findings = cq.find_relative_date_anchors("We updated the schedule this weekend for everyone.")
        self.assertEqual(findings, [])

    def test_multiple_matches_are_aggregated_into_one_finding(self):
        text = "We updated pricing last month. Support hours changed recently too."
        findings = cq.find_relative_date_anchors(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0].structured_evidence["matches"]), 2)


class ScopeAmbiguousNumberTests(unittest.TestCase):
    def test_two_different_values_same_label_no_qualifier_fires(self):
        text = "Battery life: 10 hours\nBattery life: 14 hours\n"
        findings = cq.find_scope_ambiguous_numbers(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["label"], "battery life")

    def test_a_qualifier_on_either_line_suppresses_the_finding(self):
        text = "Battery life: 10 hours\nBattery life: up to 14 hours\n"
        self.assertEqual(cq.find_scope_ambiguous_numbers(text), [])

    def test_the_same_value_repeated_is_not_ambiguous(self):
        text = "Storage: 128 GB\nStorage: 128 GB\n"
        self.assertEqual(cq.find_scope_ambiguous_numbers(text), [])

    def test_a_single_word_label_is_too_generic_to_compare_on(self):
        text = "Price: 10\nPrice: 20\n"
        self.assertEqual(cq.find_scope_ambiguous_numbers(text), [])

    def test_plural_and_singular_units_are_grouped_together(self):
        text = "Warranty period: 1 year\nWarranty period: 2 years\n"
        findings = cq.find_scope_ambiguous_numbers(text)
        self.assertEqual(len(findings), 1)

    def test_period_is_not_matched_as_the_qualifier_word_per(self):
        """Regression: a naive substring check on the qualifier 'per' also
        matches inside 'period', wrongly suppressing this finding."""
        text = "Warranty period: 1 year\nWarranty period: 2 years\n"
        findings = cq.find_scope_ambiguous_numbers(text)
        self.assertEqual(len(findings), 1, "the qualifier substring bug would incorrectly suppress this")

    def test_two_independent_ambiguous_metrics_both_fire(self):
        text = "Battery life: 10 hours\nBattery life: 14 hours\nWarranty period: 1 year\nWarranty period: 2 years\n"
        findings = cq.find_scope_ambiguous_numbers(text)
        self.assertEqual(len(findings), 2)


class ComputedStatIntegrityTests(unittest.TestCase):
    def test_a_wrong_stated_average_fires_with_the_arithmetic_shown(self):
        text = "Customer ratings: 5, 4, 3, 5, 2\nAverage rating: 4.8 out of 5.\n"
        findings = cq.find_computed_stat_mismatches(text)
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].structured_evidence["computed_mean"], 3.8)
        self.assertEqual(findings[0].structured_evidence["claimed"], 4.8)

    def test_a_correct_stated_average_does_not_fire(self):
        text = "Customer ratings: 5, 4, 3, 5, 2\nAverage rating: 3.8 out of 5.\n"
        self.assertEqual(cq.find_computed_stat_mismatches(text), [])

    def test_a_weighted_average_is_not_compared(self):
        text = "Customer ratings: 5, 4, 3, 5, 2\nWeighted average rating: 4.8 out of 5.\n"
        self.assertEqual(cq.find_computed_stat_mismatches(text), [])

    def test_an_unrelated_list_and_claim_are_not_compared(self):
        text = "Page views: 100, 200, 300\nAverage price: $45.\n"
        self.assertEqual(cq.find_computed_stat_mismatches(text), [])

    def test_singular_plural_keyword_mismatch_still_matches(self):
        """Regression: 'ratings' (list label) vs 'rating' (claim sentence)
        must be recognised as the same metric."""
        text = "Customer ratings: 5, 4, 3, 5, 2\nAverage rating: 4.8.\n"
        self.assertEqual(len(cq.find_computed_stat_mismatches(text)), 1)

    def test_a_parenthesised_label_is_parsed(self):
        """Regression: the label regex originally excluded '(' and ')', so
        'Delivery times (days):' failed to match as a labeled list at all."""
        text = "Delivery times (days): 2, 3, 2, 4, 3\nMean delivery time: 5 days.\n"
        findings = cq.find_computed_stat_mismatches(text)
        self.assertEqual(len(findings), 1)
        self.assertAlmostEqual(findings[0].structured_evidence["computed_mean"], 2.8)

    def test_rounding_within_tolerance_does_not_fire(self):
        text = "Customer ratings: 5, 4, 3, 5, 2\nAverage rating: 3.85.\n"
        self.assertEqual(cq.find_computed_stat_mismatches(text), [])


class NonAnswerCandidateTests(unittest.TestCase):
    """CQ-02. No script verdict — only extraction is tested, for what it
    hands the agent, per this project's established agent-judged pattern."""

    def test_a_hedge_with_no_preceding_question_still_carries_context(self):
        candidates = cq.find_non_answer_candidates("It depends on your fitness level and goals.")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["preceding_sentence"], "")

    def test_a_hedge_captures_the_preceding_sentence_as_the_implied_question(self):
        text = "How much should I run each week? It depends on your fitness level and goals."
        candidates = cq.find_non_answer_candidates(text)
        self.assertEqual(candidates[0]["sentence"], "It depends on your fitness level and goals.")
        self.assertEqual(candidates[0]["preceding_sentence"], "How much should I run each week?")

    def test_results_may_vary_is_recognised(self):
        candidates = cq.find_non_answer_candidates("Our supplement boosts energy. Results may vary from person to person.")
        self.assertEqual(len(candidates), 1)

    def test_ordinary_prose_with_no_hedge_produces_no_candidates(self):
        text = "Runners typically improve by increasing weekly mileage by 10 percent."
        self.assertEqual(cq.find_non_answer_candidates(text), [])

    def test_candidates_are_capped(self):
        text = " ".join(f"Question {i}? It depends on your situation." for i in range(30))
        self.assertLessEqual(len(cq.find_non_answer_candidates(text)), 15)


class GranularityCandidateTests(unittest.TestCase):
    """CQ-04. Extraction only."""

    def test_a_vague_spec_with_no_number_is_a_candidate(self):
        candidates = cq.find_granularity_candidates("The laptop weighs a substantial amount and has a large screen.")
        self.assertEqual(len(candidates), 1)

    def test_a_precise_spec_is_not_a_candidate(self):
        self.assertEqual(cq.find_granularity_candidates("The laptop weighs 1.4 kg."), [])

    def test_a_vague_word_with_no_spec_context_is_not_a_candidate(self):
        """'large' alone, describing something that isn't a spec field, is a
        legitimate qualitative description, not a granularity mismatch."""
        self.assertEqual(cq.find_granularity_candidates("We have a large community of happy customers."), [])

    def test_a_verb_form_spec_context_word_is_recognised(self):
        """Regression, found while smoke-testing before formal tests: the
        context word list originally had only noun forms ('weight'), missing
        the verb form ('weighs') that real product copy actually uses."""
        candidates = cq.find_granularity_candidates("The device weighs a substantial amount.")
        self.assertEqual(len(candidates), 1)


class ProcedureMarketingCandidateTests(unittest.TestCase):
    """CQ-09. Extraction only."""

    def test_a_step_line_with_marketing_language_is_a_candidate(self):
        candidates = cq.find_procedure_marketing_candidates(
            "Step 2: Don't miss our award-winning premium plan, sign up today!"
        )
        self.assertEqual(len(candidates), 1)

    def test_a_step_line_with_no_marketing_language_is_not_a_candidate(self):
        self.assertEqual(
            cq.find_procedure_marketing_candidates("Step 1: Enter your email address and click continue."), []
        )

    def test_marketing_language_outside_a_step_line_is_not_a_candidate(self):
        """The pattern is scoped to numbered-step lines on purpose — the
        same promotional sentence on an ordinary marketing page is not a
        procedure-interleaving defect at all."""
        self.assertEqual(
            cq.find_procedure_marketing_candidates("Don't miss our award-winning premium plan, sign up today!"), []
        )

    def test_a_numeral_dot_style_step_is_also_recognised(self):
        candidates = cq.find_procedure_marketing_candidates("3. Act now and confirm your order.")
        self.assertEqual(len(candidates), 1)


class FillerDensityTests(unittest.TestCase):
    """CQ-12. A page-level measurement, not per-sentence candidates."""

    def test_no_filler_produces_a_zero_count(self):
        result = cq.measure_filler_density("The battery lasts 10 hours and charges in 30 minutes via USB-C.")
        self.assertEqual(result["filler_phrase_count"], 0)

    def test_filler_phrases_are_counted_and_quoted(self):
        text = "In today's fast-paced world, it goes without saying that speed matters. Needless to say, we deliver."
        result = cq.measure_filler_density(text)
        self.assertEqual(result["filler_phrase_count"], 3)
        self.assertEqual(len(result["filler_phrases_found"]), 3)

    def test_word_count_is_reported_alongside_the_filler_count(self):
        result = cq.measure_filler_density("Short text with it goes without saying one filler phrase.")
        self.assertIn("total_word_count", result)
        self.assertGreater(result["total_word_count"], 0)


class AnswerExtractabilitySignalTests(unittest.TestCase):
    """CQ-01. Extraction only — a page-level signal, same design as CQ-12."""

    def test_h1_text_is_carried_through(self):
        signal = cq.find_answer_extractability_signal("Some opening text.", "Shipping Policy")
        self.assertEqual(signal["h1_text"], "Shipping Policy")

    def test_no_h1_is_reported_as_none(self):
        signal = cq.find_answer_extractability_signal("Some opening text.", None)
        self.assertIsNone(signal["h1_text"])

    def test_marketing_phrases_in_the_opening_are_counted(self):
        text = "Don't miss our award-winning premium plan, sign up today!"
        signal = cq.find_answer_extractability_signal(text, None)
        self.assertEqual(len(signal["marketing_phrase_hits_in_opening"]), 3)

    def test_a_plain_factual_opening_has_no_marketing_hits(self):
        text = "Shipping takes 3 to 5 business days within the continental US."
        signal = cq.find_answer_extractability_signal(text, None)
        self.assertEqual(signal["marketing_phrase_hits_in_opening"], [])

    def test_opening_block_is_truncated_at_the_word_limit(self):
        text = " ".join(f"word{i}" for i in range(300))
        signal = cq.find_answer_extractability_signal(text, None)
        self.assertEqual(len(signal["opening_block"].split()), 150)
        self.assertTrue(signal["opening_block_truncated"])

    def test_a_short_page_is_not_marked_truncated(self):
        signal = cq.find_answer_extractability_signal("A short page.", None)
        self.assertFalse(signal["opening_block_truncated"])

    def test_the_window_is_document_start_not_h1_anchored(self):
        """Deliberate design choice, reverted from an H1-anchored version
        after live validation found the anchor itself unreliable (see
        find_answer_extractability_signal's docstring) — nav/header text
        ahead of the H1 is a known, documented limitation the agent's
        instructions account for, not something this function hides."""
        text = "Skip to content\nMain menu\nShipping Policy\nOrders ship within 2 business days."
        signal = cq.find_answer_extractability_signal(text, "Shipping Policy")
        self.assertTrue(signal["opening_block"].startswith("Skip to content"))


class ReadabilityTests(unittest.TestCase):
    """CQ-11. Deterministic: the script decides, same as CQ-03/05/07/08."""

    def test_short_text_is_not_scored_at_all(self):
        """Guard: below the minimum word count, the formula is noise, not
        signal — this is the false-positive guard for this capability."""
        text = "Utilize the aforementioned methodology to optimize outcomes. " * 5
        self.assertIsNone(cq.measure_readability(text))

    def test_a_long_dense_passage_fires(self):
        sentence = (
            "The comprehensive multidisciplinary methodological framework "
            "necessitates an extraordinarily sophisticated reconceptualization "
            "of interdependent organizational infrastructural considerations "
            "notwithstanding the aforementioned characterization difficulties "
            "encountered throughout the preceding investigative undertaking. "
        )
        text = sentence * 20
        finding = cq.measure_readability(text)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.capability_id, "CQ-11")
        self.assertLess(finding.structured_evidence["flesch_reading_ease"], 30.0)

    def test_plain_short_sentences_do_not_fire_even_at_length(self):
        """False-positive guard: a page built from many short, simple
        sentences must not fire just because it is long — the formula's
        known failure mode is jargon density, not sentence count."""
        sentence = "The dog ran fast. The cat sat down. We ate lunch at noon. "
        text = sentence * 40
        self.assertIsNone(cq.measure_readability(text))

    def test_evidence_quotes_the_longest_sentences(self):
        sentence = (
            "The comprehensive multidisciplinary methodological framework "
            "necessitates an extraordinarily sophisticated reconceptualization "
            "of interdependent organizational infrastructural considerations "
            "notwithstanding the aforementioned characterization difficulties "
            "encountered throughout the preceding investigative undertaking. "
        )
        text = sentence * 20
        finding = cq.measure_readability(text)
        self.assertIn("multidisciplinary", finding.evidence)


class AgentJudgementRequestTests(unittest.TestCase):
    def test_all_five_agent_judged_capabilities_are_requested(self):
        requests = cq.build_agent_judgement_requests("Some ordinary text.")
        ids = {r["capability_id"] for r in requests}
        self.assertEqual(ids, {"CQ-01", "CQ-02", "CQ-04", "CQ-09", "CQ-12"})

    def test_every_request_points_at_the_rubric(self):
        requests = cq.build_agent_judgement_requests("Some ordinary text.")
        for request in requests:
            self.assertIn("references/content-judgement-rubric.md", request["instructions"])

    def test_audit_text_carries_agent_judgement_required(self):
        out = cq.audit_text("example.com", "It depends on your situation.")
        self.assertIn("agent_judgement_required", out)
        self.assertEqual(len(out["agent_judgement_required"]), 5)

    def test_h1_text_flows_from_audit_text_into_the_cq01_request(self):
        out = cq.audit_text("example.com", "Some page text.", h1_text="Returns Policy")
        cq01 = next(r for r in out["agent_judgement_required"] if r["capability_id"] == "CQ-01")
        self.assertEqual(cq01["observations"]["h1_text"], "Returns Policy")


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        text = (
            "Welcome, {{first_name}}!\n"
            "We updated our policy last month.\n"
            "Battery life: 10 hours\nBattery life: 14 hours\n"
            "Customer ratings: 5, 4, 3, 5, 2\nAverage rating: 4.8.\n"
        )
        output = cq.audit_text("example.com", text)
        self.assertEqual(len(output["findings"]), 4)
        for finding_dict in output["findings"]:
            from finding_contract import Finding

            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "content-quality-audit")
            self.assertEqual(restored.gate, 3)
            self.assertEqual(restored.category, "discoverability")

    def test_evaluation_is_deterministic(self):
        text = "Battery life: 10 hours\nBattery life: 14 hours\n"
        first = cq.audit_text("example.com", text)
        second = cq.audit_text("example.com", text)
        self.assertEqual(first, second)


class PageAttributionTests(unittest.TestCase):
    """This skill runs once per page. Two findings of the same class from two
    different pages must stay distinguishable in the composed report, or a
    multi-page audit becomes unreadable — which page has the leaked token?"""

    def test_page_url_is_stamped_into_evidence_and_structured_evidence(self):
        output = cq.audit_text("example.com", "Welcome, {{first_name}}!", page_url="https://example.com/home")
        finding = output["findings"][0]
        self.assertTrue(finding["evidence"].startswith("On https://example.com/home:"))
        self.assertEqual(finding["structured_evidence"]["page_url"], "https://example.com/home")

    def test_no_page_url_leaves_evidence_unstamped(self):
        output = cq.audit_text("example.com", "Welcome, {{first_name}}!")
        self.assertFalse(output["findings"][0]["evidence"].startswith("On "))

    def test_two_pages_with_the_same_defect_stay_distinguishable_after_composition(self):
        page1 = cq.audit_text("example.com", "Welcome, {{first_name}}!", page_url="https://example.com/home")
        page2 = cq.audit_text("example.com", "Hi {{name}}, shipped.", page_url="https://example.com/checkout")

        orchestrator_spec = importlib.util.spec_from_file_location(
            "compose_report", REPO_ROOT / "skills/audit-orchestrator/scripts/compose_report.py"
        )
        orchestrator = importlib.util.module_from_spec(orchestrator_spec)
        orchestrator_spec.loader.exec_module(orchestrator)

        with tempfile.TemporaryDirectory() as workdir:
            p1, p2 = Path(workdir) / "p1.json", Path(workdir) / "p2.json"
            p1.write_text(json.dumps(page1))
            p2.write_text(json.dumps(page2))
            report = orchestrator.compose(
                "example.com",
                [("content-quality-audit", str(p1)), ("content-quality-audit", str(p2))],
                audited_at="2026-09-20T14:32:00Z",
            )

        self.assertEqual(len(report["findings"]), 2)
        self.assertEqual({f["check_id"] for f in report["findings"]}, {"CQ-03-template-leakage"})
        pages_mentioned = {f["structured_evidence"]["page_url"] for f in report["findings"]}
        self.assertEqual(pages_mentioned, {"https://example.com/home", "https://example.com/checkout"})
        self.assertEqual({f["id"] for f in report["findings"]}, {"F-001", "F-002"})


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(cq.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(cq.is_public_host("10.0.0.5"))

    def test_an_unresolvable_host_is_refused(self):
        self.assertFalse(cq.is_public_host("this-host-does-not-exist.invalid"))


if __name__ == "__main__":
    unittest.main()
