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
before writing a single formal test.
"""

import email.utils
import importlib.util
import json
import sys
import tempfile
import time as time_module
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

import page_fetch  # noqa: E402
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

    def test_an_unrelated_absolute_date_far_from_the_relative_phrase_still_fires(self):
        """Cycle 24 fix: an absolute date far from the relative claim in the
        same sentence must not suppress it — the two are unrelated. Previously
        any absolute date anywhere in the sentence suppressed the finding."""
        text = (
            "Founded in 2010 by two college roommates who met on the very first "
            "day of orientation, prices increased recently based on market demand."
        )
        findings = cq.find_relative_date_anchors(text)
        self.assertEqual(len(findings), 1)

    def test_an_absolute_date_just_inside_the_proximity_window_still_suppresses(self):
        text = "Support hours changed recently, on March 2026 notice."
        findings = cq.find_relative_date_anchors(text)
        self.assertEqual(findings, [])

    def test_a_short_ui_sort_label_does_not_fire(self):
        """scribd live-testing false positive: "Recently Added" is a UI
        sort/filter label, not a sentence describing a change."""
        self.assertEqual(cq.find_relative_date_anchors("Recently Added"), [])

    def test_a_short_ui_label_with_a_different_claim_verb_does_not_fire(self):
        self.assertEqual(cq.find_relative_date_anchors("Recently Updated"), [])

    def test_a_real_short_prose_claim_above_the_floor_still_fires(self):
        text = "Our support hours changed recently for everyone."
        findings = cq.find_relative_date_anchors(text)
        self.assertEqual(len(findings), 1)


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


class SyllableCounterTests(unittest.TestCase):
    """Cycle 24: silent -ed/-es were being counted as real syllables,
    overcounting and skewing the Flesch score. `changes`/`boxes`/`wanted`
    prove the fix keeps the suffix's syllable exactly where it's real."""

    def test_silent_ed_is_not_counted(self):
        self.assertEqual(cq._count_syllables("walked"), 1)
        self.assertEqual(cq._count_syllables("closed"), 1)

    def test_ed_after_t_or_d_is_its_own_syllable(self):
        self.assertEqual(cq._count_syllables("wanted"), 2)
        self.assertEqual(cq._count_syllables("needed"), 2)

    def test_silent_es_is_not_counted(self):
        self.assertEqual(cq._count_syllables("makes"), 1)
        self.assertEqual(cq._count_syllables("likes"), 1)

    def test_es_after_a_sibilant_is_its_own_syllable(self):
        self.assertEqual(cq._count_syllables("boxes"), 2)
        self.assertEqual(cq._count_syllables("watches"), 2)

    def test_es_after_a_soft_g_or_c_is_its_own_syllable(self):
        self.assertEqual(cq._count_syllables("changes"), 2)
        self.assertEqual(cq._count_syllables("places"), 2)

    def test_silent_trailing_e_is_still_handled(self):
        self.assertEqual(cq._count_syllables("the"), 1)
        self.assertEqual(cq._count_syllables("make"), 1)

    def test_never_returns_zero_for_a_real_word(self):
        self.assertEqual(cq._count_syllables("a"), 1)


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

    def test_a_massive_unbroken_line_does_not_contribute_to_word_or_sentence_counts(self):
        """paytm/scribd live-testing false positive: a punctuation-free run
        of concatenated nav/footer links becomes one giant "sentence" with
        no real sentence boundary — it must not inflate avg_sentence_length
        or otherwise count toward the score at all."""
        sentence = (
            "The comprehensive multidisciplinary methodological framework "
            "necessitates an extraordinarily sophisticated reconceptualization "
            "of interdependent organizational infrastructural considerations "
            "notwithstanding the aforementioned characterization difficulties "
            "encountered throughout the preceding investigative undertaking. "
        )
        base_text = sentence * 20
        baseline = cq.measure_readability(base_text)
        self.assertIsNotNone(baseline)

        nav_dump = " ".join(["Online Movies in Kannada"] * 30)  # 120 words, one line, no punctuation
        finding = cq.measure_readability(base_text + "\n" + nav_dump)
        self.assertIsNotNone(finding)
        self.assertEqual(finding.structured_evidence["word_count"], baseline.structured_evidence["word_count"])
        self.assertEqual(
            finding.structured_evidence["sentence_count"], baseline.structured_evidence["sentence_count"]
        )

    def test_a_single_glued_together_word_does_not_contribute_to_word_count(self):
        """paytm live-testing false positive: a run of concatenated,
        unspaced entity/partner names becomes one giant pseudo-word with an
        inflated vowel-group syllable count — it must not count as a real
        word at all."""
        sentence = (
            "The comprehensive multidisciplinary methodological framework "
            "necessitates an extraordinarily sophisticated reconceptualization "
            "of interdependent organizational infrastructural considerations "
            "notwithstanding the aforementioned characterization difficulties "
            "encountered throughout the preceding investigative undertaking. "
        )
        base_text = sentence * 20
        baseline = cq.measure_readability(base_text)
        self.assertIsNotNone(baseline)

        glued = "Ess" + "Kay" * 15  # 46 letters, no spaces — an unspaced entity-name run
        finding = cq.measure_readability(base_text + f" {glued}.")
        self.assertIsNotNone(finding)
        self.assertEqual(finding.structured_evidence["word_count"], baseline.structured_evidence["word_count"])

    def test_a_page_below_the_minimum_sentence_count_is_not_scored(self):
        """A page satisfying the word-count floor with almost no real
        sentence structure (e.g. dominated by excluded non-prose runs)
        should not produce a score at all, rather than an unstable one from
        a handful of leftover sentences."""
        words = " ".join(["lorem"] * 350)  # one giant unbroken "sentence", well over the word floor
        self.assertIsNone(cq.measure_readability(words))


class StripIntraPageRepeatedLinesTests(unittest.TestCase):
    def test_a_line_repeated_at_or_above_the_minimum_count_is_removed(self):
        text = "\n".join(["This is a repeated navigation line entry."] * 3 + ["Unique prose sentence here."])
        stripped = cq._strip_intra_page_repeated_lines(text)
        self.assertNotIn("This is a repeated navigation line entry.", stripped)
        self.assertIn("Unique prose sentence here.", stripped)

    def test_a_line_appearing_only_twice_is_kept(self):
        text = "\n".join(["This line appears just twice in the document."] * 2 + ["Other line."])
        stripped = cq._strip_intra_page_repeated_lines(text)
        self.assertIn("This line appears just twice in the document.", stripped)

    def test_short_lines_are_never_treated_as_repeated_chrome(self):
        text = "\n".join(["Hi"] * 5)
        self.assertEqual(cq._strip_intra_page_repeated_lines(text), text)


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

    def test_two_pages_with_the_same_defect_merge_into_one_finding_with_both_pages_recoverable(self):
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

        # Same semantic id, same page-count check across two pages: one merged finding.
        self.assertEqual(len(report["findings"]), 1)
        finding = report["findings"][0]
        self.assertEqual(finding["id"], "F-001")
        self.assertEqual(finding["check_id"], "CQ-03-template-leakage")
        pages_mentioned = {p["page_url"] for p in finding["structured_evidence"]["pages"]}
        self.assertEqual(pages_mentioned, {"https://example.com/home", "https://example.com/checkout"})
        self.assertEqual(finding["structured_evidence"]["affected_page_count"], 2)
        self.assertIn("https://example.com/home", finding["evidence"])
        self.assertIn("https://example.com/checkout", finding["evidence"])


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(cq.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(cq.is_public_host("10.0.0.5"))

    def test_an_unresolvable_host_is_refused(self):
        self.assertFalse(cq.is_public_host("this-host-does-not-exist.invalid"))


_CHROME_NAV = "Home About Products Support Contact Sign In Cart"
_CHROME_FOOTER = "Copyright Acme Widgets Inc All rights reserved Privacy Policy Terms of Service"


def _page(*body_lines: str) -> str:
    return "\n".join([_CHROME_NAV, *body_lines, _CHROME_FOOTER])


class StripChromeLinesTests(unittest.TestCase):
    def test_lines_repeated_on_at_least_half_the_pages_are_removed(self):
        pages = {
            "https://acme.com/a": _page("Unique content for page A goes here"),
            "https://acme.com/b": _page("Unique content for page B goes here"),
        }
        stripped = cq._strip_chrome_lines(pages)
        for text in stripped.values():
            self.assertNotIn(_CHROME_NAV, text)
            self.assertNotIn(_CHROME_FOOTER, text)

    def test_unique_content_lines_are_preserved(self):
        pages = {
            "https://acme.com/a": _page("Unique content for page A goes here"),
            "https://acme.com/b": _page("Unique content for page B goes here"),
        }
        stripped = cq._strip_chrome_lines(pages)
        self.assertIn("Unique content for page A goes here", stripped["https://acme.com/a"])
        self.assertIn("Unique content for page B goes here", stripped["https://acme.com/b"])

    def test_short_lines_are_never_treated_as_chrome(self):
        # Below the minimum length guard even if it repeats everywhere —
        # avoids stripping something like a repeated one-word price label.
        pages = {"https://acme.com/a": "Hi\nReal content line one", "https://acme.com/b": "Hi\nReal content line two"}
        stripped = cq._strip_chrome_lines(pages)
        self.assertIn("Hi", stripped["https://acme.com/a"])


class FindNearDuplicateClustersTests(unittest.TestCase):
    def test_near_identical_pages_under_the_same_template_are_flagged(self):
        body = (
            "Our premium widget line offers industry leading durability backed by a "
            "comprehensive five year warranty and free worldwide shipping on every order "
            "placed through our online store this month only while supplies last"
        )
        page_texts = {
            "https://acme.com/blog/post-1": _page(body),
            "https://acme.com/blog/post-2": _page(body.replace("this month", "this week")),
        }
        findings = cq.find_near_duplicate_clusters(page_texts)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "CQ-13")
        self.assertEqual(set(findings[0].structured_evidence["urls"]), set(page_texts))

    def test_legitimately_distinct_pages_under_the_same_template_are_not_flagged(self):
        page_texts = {
            "https://acme.com/blog/post-1": _page(
                "This article explains our new titanium frame manufacturing process in detail "
                "covering material sourcing quality control and the twelve step assembly line"
            ),
            "https://acme.com/blog/post-2": _page(
                "This unrelated article covers our quarterly financial results for shareholders "
                "including revenue growth margin expansion and guidance for the coming fiscal year"
            ),
        }
        self.assertEqual(cq.find_near_duplicate_clusters(page_texts), [])

    def test_different_templates_are_never_compared_to_each_other(self):
        # Dominant false positive: two totally different page kinds that
        # happen to share generic boilerplate phrasing must never be
        # compared just because their content overlaps somewhat — they are
        # not even in the same stratum.
        body = "Identical filler text repeated on purpose to maximize any shingle overlap score"
        page_texts = {"https://acme.com/pricing": _page(body), "https://acme.com/about": _page(body)}
        self.assertEqual(cq.find_near_duplicate_clusters(page_texts), [])

    def test_a_single_page_stratum_is_never_flagged(self):
        page_texts = {"https://acme.com/blog/only-post": _page("Some reasonably long unique article body text here")}
        self.assertEqual(cq.find_near_duplicate_clusters(page_texts), [])

    def test_near_empty_stub_pages_are_excluded_from_comparison(self):
        page_texts = {
            "https://acme.com/blog/stub-1": _page("Coming soon"),
            "https://acme.com/blog/stub-2": _page("Coming soon"),
        }
        self.assertEqual(cq.find_near_duplicate_clusters(page_texts), [])

    def test_findings_pass_the_finding_contract_validation(self):
        body = (
            "Our premium widget line offers industry leading durability backed by a "
            "comprehensive five year warranty and free worldwide shipping on every order "
            "placed through our online store this month only while supplies last"
        )
        page_texts = {
            "https://acme.com/blog/post-1": _page(body),
            "https://acme.com/blog/post-2": _page(body),
        }
        findings = cq.find_near_duplicate_clusters(page_texts)
        for finding in findings:
            self.assertEqual(finding.validate(), [])


class ExtractLabeledFactsTests(unittest.TestCase):
    def test_a_price_labeled_line_is_extracted(self):
        facts = cq.extract_labeled_facts("Price: $49.99\nSome other text.")
        self.assertEqual(facts["price"], "$49.99")

    def test_an_iso_date_labeled_line_is_extracted(self):
        facts = cq.extract_labeled_facts("Founded: 1998-04-12")
        self.assertEqual(facts["founded"], "1998-04-12")

    def test_a_month_name_date_is_extracted(self):
        facts = cq.extract_labeled_facts("Launched: January 5, 2020")
        self.assertEqual(facts["launched"], "January 5, 2020")

    def test_a_thousands_grouped_count_is_extracted(self):
        facts = cq.extract_labeled_facts("Employees: 1,200")
        self.assertEqual(facts["employees"], "1,200")

    def test_an_untyped_value_is_not_extracted(self):
        facts = cq.extract_labeled_facts("Description: A great product for everyone.")
        self.assertEqual(facts, {})

    def test_a_line_with_no_label_colon_shape_is_ignored(self):
        facts = cq.extract_labeled_facts("This costs $49.99 but is not a label line.")
        self.assertEqual(facts, {})


class FindFactCollisionCandidatesTests(unittest.TestCase):
    def test_same_label_different_value_across_three_same_template_pages_is_a_candidate(self):
        # "/store/1", "/store/2", "/store/3" collapse to the same template
        # ("/store/*") since a numeric segment is recognised as variable.
        page_texts = {
            "https://acme.com/store/1": "Founded: 1998",
            "https://acme.com/store/2": "Founded: 2001",
            "https://acme.com/store/3": "Founded: 1998",
        }
        candidates = cq.find_fact_collision_candidates(page_texts)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["label"], "founded")

    def test_per_sku_price_variation_across_product_pages_is_not_flagged_below_the_page_threshold(self):
        # Only 2 pages state a price at all — below the 3-page minimum, so
        # this never becomes a candidate regardless of value agreement.
        page_texts = {
            "https://acme.com/product/1": "Price: $19.99",
            "https://acme.com/product/2": "Price: $29.99",
        }
        self.assertEqual(cq.find_fact_collision_candidates(page_texts), [])

    def test_the_same_value_on_every_page_is_not_a_candidate(self):
        page_texts = {
            "https://acme.com/store/1": "Founded: 1998",
            "https://acme.com/store/2": "Founded: 1998",
            "https://acme.com/store/3": "Founded: 1998",
        }
        self.assertEqual(cq.find_fact_collision_candidates(page_texts), [])

    def test_pages_in_different_template_strata_are_not_compared(self):
        page_texts = {
            "https://acme.com/product/1": "Founded: 1998",
            "https://acme.com/blog/1": "Founded: 2001",
            "https://acme.com/blog/2": "Founded: 2001",
        }
        # "founded" appears on 3 pages total, but split across two distinct
        # template strata (product/* vs blog/*) — neither stratum alone
        # reaches the 3-page minimum, so no candidate is produced.
        self.assertEqual(cq.find_fact_collision_candidates(page_texts), [])

    def test_no_labeled_facts_anywhere_produces_no_candidates(self):
        page_texts = {"https://acme.com/store/1": "Welcome to our site.", "https://acme.com/store/2": "Meet the team."}
        self.assertEqual(cq.find_fact_collision_candidates(page_texts), [])


class AuditNearDuplicatesTests(unittest.TestCase):
    def test_an_unreachable_page_becomes_one_unknown_check(self):
        out = cq.audit_sample("acme.com", ["https://this-host-does-not-exist.invalid/page"])
        self.assertEqual(out["findings"], [])
        self.assertEqual(len(out["unknown_checks"]), 1)
        self.assertIn("this-host-does-not-exist.invalid", out["unknown_checks"][0]["reason"])

    def test_no_page_urls_produces_an_empty_clean_report_not_a_crash(self):
        out = cq.audit_sample("acme.com", [])
        self.assertEqual(out["findings"], [])
        self.assertEqual(out["unknown_checks"], [])

    def test_output_always_carries_the_capability_ids(self):
        out = cq.audit_sample("acme.com", [])
        self.assertEqual(out["capability_ids"], cq.CAPABILITY_IDS)
        self.assertIn("CQ-13", out["capability_ids"])
        self.assertIn("CQ-10", out["capability_ids"])

    def test_cq10_judgement_request_is_always_present_even_with_no_pages(self):
        out = cq.audit_sample("acme.com", [])
        self.assertEqual(len(out["agent_judgement_required"]), 1)
        self.assertEqual(out["agent_judgement_required"][0]["capability_id"], "CQ-10")
        self.assertEqual(out["agent_judgement_required"][0]["observations"]["candidates"], [])

    def test_coverage_manifest_is_always_attached_and_not_expired_by_default(self):
        out = cq.audit_sample("acme.com", [])
        self.assertEqual(len(out["coverage"]["stages"]), 1)
        self.assertFalse(out["coverage"]["stages"][0]["expired"])

    def test_pages_beyond_the_fetch_budget_get_an_unknown_check_not_a_hang(self):
        # A fake clock that reports the cap already blown past on the very
        # first check — this exercises the cutoff deterministically, with no
        # dependency on real fetch timing or network flakiness.
        calls = {"n": 0}

        def fake_clock():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 1000.0

        page_urls = ["https://this-host-does-not-exist.invalid/a", "https://this-host-does-not-exist.invalid/b"]
        out = cq.audit_sample("acme.com", page_urls, clock=fake_clock)
        self.assertEqual(len(out["unknown_checks"]), 2)
        for unknown in out["unknown_checks"]:
            self.assertEqual(unknown["capability_id"], "*")
            self.assertIn("budget", unknown["reason"])
        self.assertTrue(out["coverage"]["stages"][0]["expired"])

    def test_a_duplicate_pair_split_across_two_concurrent_fetch_chunks_is_still_caught(self):
        """Defect 2: the sample loop now fetches concurrently, in chunks of
        cq._SAMPLE_FETCH_CHUNK_SIZE, with LATER urls finishing FIRST
        (reversed delay) so completion order is the opposite of input order.
        Proves two things at once: chunking doesn't drop or mismatch a page
        at the chunk boundary, and out-of-order completion can't scramble
        which content ends up attributed to which URL — a real near-
        duplicate pair (post-0 in chunk 1, post-N in chunk 2) must still be
        correctly paired and flagged."""
        chunk_size = cq._SAMPLE_FETCH_CHUNK_SIZE
        duplicate_body = (
            "Our premium widget line offers industry leading durability backed by a "
            "comprehensive five year warranty and free worldwide shipping on every order "
            "placed through our online store this month only while supplies last"
        )
        page_count = chunk_size + 3
        urls = [f"https://acme.com/blog/post-{i}" for i in range(page_count)]
        # post-0 (chunk 1) and the last url (chunk 2) are near-duplicates;
        # everything else is distinct filler under the same template.
        duplicate_urls = {urls[0], urls[-1]}
        bodies = {
            url: (duplicate_body if url in duplicate_urls else f"Distinct filler content unique to {url} only.")
            for url in urls
        }
        delays = {url: 0.01 * (page_count - i) for i, url in enumerate(urls)}

        def fake_fetch(url):
            time_module.sleep(delays[url])
            return page_fetch.PageBundle(
                url=url, status="present", html=f"<p>{bodies[url]}</p>", error=None,
                final_url=url, headers={},
            )

        with patch.object(page_fetch, "fetch_page", side_effect=fake_fetch), \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            out = cq.audit_sample("acme.com", urls)

        self.assertEqual(out["unknown_checks"], [])
        cq13_findings = [f for f in out["findings"] if f["capability_id"] == "CQ-13"]
        self.assertEqual(len(cq13_findings), 1)
        self.assertEqual(set(cq13_findings[0]["structured_evidence"]["urls"]), duplicate_urls)


class FindFreshnessContradictionTests(unittest.TestCase):
    FETCHED_AT = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)

    def _http_date(self, dt: datetime) -> str:
        return email.utils.format_datetime(dt, usegmt=True)

    def test_claimed_date_much_newer_than_last_modified_fires(self):
        last_modified = self.FETCHED_AT - timedelta(days=250)
        headers = {"Last-Modified": self._http_date(last_modified)}
        text = "Last updated: August 20, 2026\nSome page content."
        findings = cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.capability_id, "CQ-10")
        self.assertEqual(finding.severity, "medium")
        self.assertEqual(finding.confidence, "medium")
        self.assertEqual(finding.validate(), [])
        self.assertGreaterEqual(finding.structured_evidence["gap_days"], 30)

    def test_no_last_modified_header_produces_no_finding(self):
        text = "Last updated: August 20, 2026"
        self.assertEqual(cq.find_freshness_contradiction(text, "", {}, fetched_at=self.FETCHED_AT), [])

    def test_last_modified_close_to_fetch_time_is_treated_as_untrustworthy(self):
        # Dominant false positive: a CDN stamping Last-Modified with serve
        # time, not real edit time, looks identical to a genuine fresh edit
        # from a single fetch — so this window is never trusted either way.
        last_modified = self.FETCHED_AT - timedelta(minutes=10)
        headers = {"Last-Modified": self._http_date(last_modified)}
        text = "Last updated: August 20, 2026"
        self.assertEqual(cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT), [])

    def test_gap_below_threshold_does_not_fire(self):
        last_modified = self.FETCHED_AT - timedelta(days=100)
        claimed = last_modified + timedelta(days=10)
        headers = {"Last-Modified": self._http_date(last_modified)}
        text = f"Last updated: {claimed.strftime('%B %d, %Y')}"
        self.assertEqual(cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT), [])

    def test_claimed_date_older_than_last_modified_does_not_fire(self):
        last_modified = self.FETCHED_AT - timedelta(days=50)
        claimed = self.FETCHED_AT - timedelta(days=300)
        headers = {"Last-Modified": self._http_date(last_modified)}
        text = f"Last updated: {claimed.strftime('%B %d, %Y')}"
        self.assertEqual(cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT), [])

    def test_falls_back_to_jsonld_datemodified_when_no_visible_text_matches(self):
        last_modified = self.FETCHED_AT - timedelta(days=250)
        headers = {"Last-Modified": self._http_date(last_modified)}
        html = '<script type="application/ld+json">{"dateModified": "2026-08-20"}</script>'
        findings = cq.find_freshness_contradiction("Some unrelated visible text.", html, headers, fetched_at=self.FETCHED_AT)
        self.assertEqual(len(findings), 1)

    def test_an_unparseable_claimed_date_produces_no_finding(self):
        last_modified = self.FETCHED_AT - timedelta(days=250)
        headers = {"Last-Modified": self._http_date(last_modified)}
        # Matches the slash-date shape but is not a real calendar date.
        text = "Last updated: 13/45/2026"
        self.assertEqual(cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT), [])

    def test_header_lookup_is_case_insensitive(self):
        last_modified = self.FETCHED_AT - timedelta(days=250)
        headers = {"last-modified": self._http_date(last_modified)}
        text = "Last updated: August 20, 2026"
        findings = cq.find_freshness_contradiction(text, "", headers, fetched_at=self.FETCHED_AT)
        self.assertEqual(len(findings), 1)


class AuditTextFreshnessIntegrationTests(unittest.TestCase):
    def test_audit_text_includes_freshness_finding_when_headers_given(self):
        now = datetime.now(timezone.utc)
        last_modified = now - timedelta(days=250)
        claimed = now - timedelta(days=1)
        headers = {"Last-Modified": email.utils.format_datetime(last_modified, usegmt=True)}
        text = f"Last updated: {claimed.strftime('%B %d, %Y')}\nWelcome to our site."
        out = cq.audit_text("example.com", text, page_url="https://example.com/about", headers=headers)
        ids = [f["id"] for f in out["findings"]]
        self.assertTrue(any(i.startswith("CQ-10-freshness-contradiction-") for i in ids))

    def test_audit_text_without_headers_never_runs_the_freshness_check(self):
        text = "Last updated: August 20, 2026\nWelcome to our site."
        out = cq.audit_text("example.com", text)
        ids = [f["id"] for f in out["findings"]]
        self.assertFalse(any(i.startswith("CQ-10-freshness-contradiction-") for i in ids))


class LabeledPairsWiringTests(unittest.TestCase):
    """Cycle 24 items 2.1/9: `_text_with_labeled_pairs` wiring into
    `audit_text` — a table-shaped page must now produce a CQ-07
    scope-ambiguous-number finding that could never have fired before this
    cycle, since `extract_visible_text()` always puts a `<th>` and its
    `<td>` on separate lines, and the `Label: value` regex only matches
    within a single line."""

    def test_a_table_with_conflicting_values_fires_only_via_html_wiring(self):
        html = (
            "<table><tr><th>Storage capacity</th><td>500 GB</td></tr></table>"
            "<table><tr><th>Storage capacity</th><td>1000 GB</td></tr></table>"
        )
        text = "Storage capacity\n500 GB\nStorage capacity\n1000 GB\n"

        without_html = cq.audit_text("example.com", text)
        ids_without_html = [f["id"] for f in without_html["findings"]]
        self.assertFalse(
            any(i.startswith("CQ-07-scope-ambiguous-") for i in ids_without_html),
            "line-separated table text alone must not satisfy the same-line Label: value regex",
        )

        with_html = cq.audit_text("example.com", text, html=html)
        ids_with_html = [f["id"] for f in with_html["findings"]]
        self.assertTrue(
            any(i.startswith("CQ-07-scope-ambiguous-storage-capacity") for i in ids_with_html),
            "the labeled-pairs line synthesized from real <th>/<td> markup must now trigger CQ-07",
        )

    def test_a_table_with_one_consistent_value_does_not_fire(self):
        html = "<table><tr><th>Storage capacity</th><td>500 GB</td></tr></table>"
        out = cq.audit_text("example.com", "Welcome to our product page.", html=html)
        ids = [f["id"] for f in out["findings"]]
        self.assertFalse(any(i.startswith("CQ-07-scope-ambiguous-") for i in ids))

    def test_every_other_check_still_sees_the_unmodified_text(self):
        """The labeled-pairs text must be additive only for CQ-07/CQ-08 —
        every other check (here, template-leakage) must see `text` exactly
        as passed, unaffected by whatever `html` happens to contain."""
        html = "<table><tr><th>Storage capacity</th><td>500 GB</td></tr></table>"
        text = "Welcome, {{first_name}}!"
        out = cq.audit_text("example.com", text, html=html)
        ids = [f["id"] for f in out["findings"]]
        self.assertTrue(any(i.startswith("CQ-03-template-leakage") for i in ids))


class MainContentTextWiringTests(unittest.TestCase):
    """Cycle 24 items 2.2/9: `extract_main_content_text` wiring into
    `build_agent_judgement_requests` — nav/header text ahead of a `<main>`
    region must no longer poison CQ-01's `opening_block` candidate."""

    def test_nav_text_ahead_of_main_no_longer_poisons_the_opening_block(self):
        html = (
            "<nav>Skip to content Main menu Home About</nav>"
            "<main>Orders ship within 2 business days of purchase.</main>"
        )
        text = "Skip to content Main menu Home About\nOrders ship within 2 business days of purchase."
        requests = cq.build_agent_judgement_requests(text, None, html)
        cq01 = next(r for r in requests if r["capability_id"] == "CQ-01")
        self.assertTrue(cq01["observations"]["opening_block"].startswith("Orders ship within"))
        self.assertEqual(cq01["observations"]["opening_block_source"], "main_content")

    def test_no_main_or_article_tag_falls_back_to_document_start_unchanged(self):
        html = "<div>Skip to content Main menu</div>"
        text = "Skip to content Main menu\nOrders ship within 2 business days."
        requests = cq.build_agent_judgement_requests(text, None, html)
        cq01 = next(r for r in requests if r["capability_id"] == "CQ-01")
        self.assertTrue(cq01["observations"]["opening_block"].startswith("Skip to content"))
        self.assertEqual(cq01["observations"]["opening_block_source"], "document_start")

    def test_no_html_at_all_falls_back_to_document_start_unchanged(self):
        text = "Skip to content Main menu\nOrders ship within 2 business days."
        requests = cq.build_agent_judgement_requests(text, None, None)
        cq01 = next(r for r in requests if r["capability_id"] == "CQ-01")
        self.assertTrue(cq01["observations"]["opening_block"].startswith("Skip to content"))
        self.assertEqual(cq01["observations"]["opening_block_source"], "document_start")

    def test_audit_text_end_to_end_threads_html_into_the_cq01_request(self):
        html = "<main>Orders ship within 2 business days of purchase.</main>"
        text = "Orders ship within 2 business days of purchase."
        out = cq.audit_text("example.com", text, html=html)
        cq01 = next(r for r in out["agent_judgement_required"] if r["capability_id"] == "CQ-01")
        self.assertEqual(cq01["observations"]["opening_block_source"], "main_content")


if __name__ == "__main__":
    unittest.main()
