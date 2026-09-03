"""Unit tests for retrieval-readiness-audit (RET-01, RET-04, RET-08).

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
    "check_retrieval_readiness", REPO_ROOT / "skills/retrieval-readiness-audit/scripts/check_retrieval_readiness.py"
)
ret = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ret)


class ExtractHeadingsTests(unittest.TestCase):
    def test_headings_are_collected_in_document_order(self):
        html = "<h1>Title</h1><p>Intro.</p><h2>Section</h2><h3>Subsection</h3>"
        headings = ret.extract_headings(html)
        self.assertEqual([h["level"] for h in headings], [1, 2, 3])
        self.assertEqual([h["text"] for h in headings], ["Title", "Section", "Subsection"])

    def test_nested_markup_inside_a_heading_is_flattened(self):
        html = "<h2>Shipping <span>Policy</span></h2>"
        headings = ret.extract_headings(html)
        self.assertEqual(headings, [{"level": 2, "text": "Shipping Policy"}])

    def test_a_heading_with_no_text_is_recorded_as_empty(self):
        html = "<h2></h2>"
        headings = ret.extract_headings(html)
        self.assertEqual(headings, [{"level": 2, "text": ""}])

    def test_whitespace_only_heading_is_recorded_as_empty(self):
        html = "<h2>   \n  </h2>"
        headings = ret.extract_headings(html)
        self.assertEqual(headings[0]["text"], "")

    def test_no_headings_returns_an_empty_list(self):
        self.assertEqual(ret.extract_headings("<p>No headings here.</p>"), [])


class EmptyHeadingTests(unittest.TestCase):
    def test_an_empty_heading_fires(self):
        headings = ret.extract_headings("<h1>Title</h1><h2></h2><p>Body.</p>")
        findings = ret.find_empty_headings(headings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "RET-08")

    def test_no_empty_headings_stays_silent(self):
        headings = ret.extract_headings("<h1>Title</h1><h2>Section</h2>")
        self.assertEqual(ret.find_empty_headings(headings), [])

    def test_multiple_empty_headings_aggregate_into_one_finding(self):
        headings = ret.extract_headings("<h1>Title</h1><h2></h2><h3></h3>")
        findings = ret.find_empty_headings(headings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["count"], 2)


class SkippedHeadingLevelTests(unittest.TestCase):
    def test_a_skipped_level_fires(self):
        headings = ret.extract_headings("<h1>Title</h1><h3>Subsection</h3>")
        findings = ret.find_skipped_heading_levels(headings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "RET-08")

    def test_a_two_level_skip_still_fires_once_for_the_pair(self):
        headings = ret.extract_headings("<h1>Title</h1><h4>Deep</h4>")
        findings = ret.find_skipped_heading_levels(headings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["skips"][0]["to_level"], 4)

    def test_consecutive_levels_do_not_fire(self):
        headings = ret.extract_headings("<h1>Title</h1><h2>Section</h2><h3>Subsection</h3>")
        self.assertEqual(ret.find_skipped_heading_levels(headings), [])

    def test_going_back_up_to_a_shallower_level_does_not_fire(self):
        """h3 -> h2 is closing a subsection and starting a new section at a
        higher level — normal document structure, not a skip."""
        headings = ret.extract_headings("<h1>Title</h1><h2>A</h2><h3>A.1</h3><h2>B</h2>")
        self.assertEqual(ret.find_skipped_heading_levels(headings), [])

    def test_same_level_repeated_does_not_fire(self):
        headings = ret.extract_headings("<h2>A</h2><h2>B</h2><h2>C</h2>")
        self.assertEqual(ret.find_skipped_heading_levels(headings), [])

    def test_starting_at_h2_with_no_h1_does_not_fire(self):
        """Deliberately not checked: whether the page starts at h1 — a
        disputed rule, and firing on it would raise the false-positive rate
        on legitimate component-based layouts. Only a skip *between* two
        present headings is checked."""
        headings = ret.extract_headings("<h2>Section</h2><h3>Subsection</h3>")
        self.assertEqual(ret.find_skipped_heading_levels(headings), [])

    def test_multiple_independent_skips_are_aggregated_into_one_finding(self):
        headings = ret.extract_headings("<h1>Title</h1><h3>A</h3><h2>B</h2><h4>C</h4>")
        findings = ret.find_skipped_heading_levels(headings)
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0].structured_evidence["skips"]), 2)

    def test_no_headings_at_all_does_not_crash(self):
        self.assertEqual(ret.find_skipped_heading_levels([]), [])

    def test_a_single_heading_does_not_crash(self):
        headings = ret.extract_headings("<h3>Only heading</h3>")
        self.assertEqual(ret.find_skipped_heading_levels(headings), [])


class BlockBoundaryTests(unittest.TestCase):
    """Adjacent block-level elements with no whitespace between them in the
    raw HTML must not have their text run together into one corrupted word
    — found live on gymshark.com (438 run-together artifacts before this
    fix). Covers both extract_json_ld_and_text's visible_text and
    extract_prose_text's prose_text, since both parsers needed the fix."""

    def test_adjacent_headings_and_paragraphs_stay_separate_words_in_visible_text(self):
        html = "<h1>Widgets</h1><p>Our platform.</p>"
        _, text = ret.extract_json_ld_and_text(html)
        words = ret._tokenize_words(text)
        self.assertIn("widgets", words)
        self.assertNotIn("widgetsour", words)

    def test_adjacent_headings_and_paragraphs_stay_separate_words_in_prose_text(self):
        html = "<h1>Widgets</h1><p>Our platform.</p>"
        text = ret.extract_prose_text(html)
        words = ret._tokenize_words(text)
        self.assertIn("widgets", words)
        self.assertNotIn("widgetsour", words)

    def test_inline_elements_with_no_surrounding_whitespace_are_not_required_to_separate(self):
        # This is a known, accepted, project-wide limitation shared with
        # content-quality-audit and entity-audit's own extractors: only
        # block-level tags insert a boundary, not inline ones (span/a/
        # strong/em), so "the<strong>quick</strong>fox" can still merge.
        # This test documents the boundary of the fix, not a requirement.
        html = "<p>the<strong>quick</strong>fox</p>"
        text = ret.extract_prose_text(html)
        self.assertIn("thequickfox", text)

    def test_div_boundaries_also_separate(self):
        html = "<div>First</div><div>Second</div>"
        words = ret._tokenize_words(ret.extract_prose_text(html))
        self.assertIn("first", words)
        self.assertIn("second", words)
        self.assertNotIn("firstsecond", words)


class ExtractJsonLdAndTextTests(unittest.TestCase):
    def test_a_valid_product_node_is_extracted(self):
        html = (
            '<script type="application/ld+json">'
            '{"@type": "Product", "name": "Widget", "sku": "WID-123"}'
            "</script><p>Body text.</p>"
        )
        nodes, text = ret.extract_json_ld_and_text(html)
        self.assertEqual(nodes, [{"@type": "Product", "name": "Widget", "sku": "WID-123"}])
        self.assertIn("Body text.", text)

    def test_json_ld_content_is_excluded_from_visible_text(self):
        html = (
            '<script type="application/ld+json">{"@type": "Product", "sku": "WID-123"}</script>'
            "<p>Visible only.</p>"
        )
        _, text = ret.extract_json_ld_and_text(html)
        self.assertNotIn("WID-123", text)
        self.assertIn("Visible only.", text)

    def test_script_and_style_content_is_excluded_from_visible_text(self):
        html = "<script>var x = 'SECRET';</script><style>.x { color: red; }</style><p>Real text.</p>"
        _, text = ret.extract_json_ld_and_text(html)
        self.assertNotIn("SECRET", text)
        self.assertIn("Real text.", text)

    def test_a_graph_wrapper_is_flattened(self):
        html = (
            '<script type="application/ld+json">'
            '{"@graph": [{"@type": "Product", "sku": "A1"}, {"@type": "Organization"}]}'
            "</script>"
        )
        nodes, _ = ret.extract_json_ld_and_text(html)
        self.assertEqual(len(nodes), 2)

    def test_malformed_json_ld_is_silently_skipped(self):
        html = '<script type="application/ld+json">{not valid json</script><p>Text.</p>'
        nodes, text = ret.extract_json_ld_and_text(html)
        self.assertEqual(nodes, [])
        self.assertIn("Text.", text)

    def test_no_json_ld_returns_empty_nodes(self):
        nodes, text = ret.extract_json_ld_and_text("<p>Just text.</p>")
        self.assertEqual(nodes, [])
        self.assertIn("Just text.", text)


class ExtractTechnicalTokensTests(unittest.TestCase):
    def test_a_product_sku_is_extracted(self):
        nodes = [{"@type": "Product", "sku": "WID-123"}]
        self.assertEqual(ret.extract_technical_tokens(nodes), [{"field": "sku", "token": "WID-123"}])

    def test_multiple_identifier_fields_are_all_extracted(self):
        nodes = [{"@type": "Product", "sku": "WID-123", "mpn": "MPN-9"}]
        tokens = ret.extract_technical_tokens(nodes)
        self.assertEqual({t["field"] for t in tokens}, {"sku", "mpn"})

    def test_a_non_product_node_is_ignored(self):
        nodes = [{"@type": "Organization", "sku": "WID-123"}]
        self.assertEqual(ret.extract_technical_tokens(nodes), [])

    def test_a_product_type_within_a_type_list_is_recognized(self):
        nodes = [{"@type": ["Thing", "Product"], "sku": "WID-123"}]
        self.assertEqual(len(ret.extract_technical_tokens(nodes)), 1)

    def test_an_empty_identifier_value_is_skipped(self):
        nodes = [{"@type": "Product", "sku": "  "}]
        self.assertEqual(ret.extract_technical_tokens(nodes), [])

    def test_a_non_string_identifier_value_is_skipped(self):
        nodes = [{"@type": "Product", "sku": 123}]
        self.assertEqual(ret.extract_technical_tokens(nodes), [])

    def test_no_product_nodes_returns_empty(self):
        self.assertEqual(ret.extract_technical_tokens([]), [])

    def test_duplicate_identifier_across_nodes_is_deduplicated(self):
        nodes = [{"@type": "Product", "sku": "WID-123"}, {"@type": "Product", "sku": "WID-123"}]
        self.assertEqual(len(ret.extract_technical_tokens(nodes)), 1)


class TokenSurvivalTests(unittest.TestCase):
    def test_a_token_present_in_visible_text_does_not_fire(self):
        tokens = [{"field": "sku", "token": "WID-123"}]
        self.assertEqual(ret.find_token_survival_gaps(tokens, "Buy the WID-123 today."), [])

    def test_a_token_absent_from_visible_text_fires(self):
        tokens = [{"field": "sku", "token": "WID-123"}]
        findings = ret.find_token_survival_gaps(tokens, "Buy the Widget today.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "RET-01-token-not-in-text")

    def test_case_insensitive_match_still_counts_as_surviving(self):
        tokens = [{"field": "sku", "token": "WID-123"}]
        self.assertEqual(ret.find_token_survival_gaps(tokens, "buy the wid-123 today."), [])

    def test_a_token_that_is_a_substring_of_a_longer_alnum_run_does_not_count_as_surviving(self):
        # "WID-123" inside "WID-1234" must not be treated as a match — the
        # word-boundary guard around each end of the token exists for this.
        tokens = [{"field": "sku", "token": "WID-123"}]
        findings = ret.find_token_survival_gaps(tokens, "See model WID-1234 for details.")
        self.assertEqual(len(findings), 1)

    def test_no_tokens_produces_no_findings(self):
        self.assertEqual(ret.find_token_survival_gaps([], "Some text with no identifiers."), [])

    def test_multiple_missing_tokens_aggregate_into_one_finding(self):
        tokens = [{"field": "sku", "token": "A1"}, {"field": "mpn", "token": "B2"}]
        findings = ret.find_token_survival_gaps(tokens, "No identifiers here.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["count"], 2)


class ExtractProseTextTests(unittest.TestCase):
    def test_table_content_is_excluded(self):
        html = "<table><tr><td>Model Weight</td></tr></table><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("Model Weight", text)
        self.assertIn("Real prose here.", text)

    def test_list_content_is_excluded(self):
        html = "<ul><li>Item one</li><li>Item two</li></ul><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("Item one", text)
        self.assertIn("Real prose here.", text)

    def test_definition_list_content_is_excluded(self):
        html = "<dl><dt>Term</dt><dd>Definition</dd></dl><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("Term", text)
        self.assertIn("Real prose here.", text)

    def test_select_content_is_excluded(self):
        html = "<select><option>Choice</option></select><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("Choice", text)

    def test_script_and_style_are_still_excluded(self):
        html = "<script>var x = 'SECRET';</script><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("SECRET", text)

    def test_nested_table_inside_a_list_is_still_excluded(self):
        html = "<ul><li><table><tr><td>Nested</td></tr></table></li></ul><p>Real prose here.</p>"
        text = ret.extract_prose_text(html)
        self.assertNotIn("Nested", text)
        self.assertIn("Real prose here.", text)

    def test_plain_prose_with_no_structured_regions_is_kept_whole(self):
        text = ret.extract_prose_text("<p>Just ordinary prose.</p>")
        self.assertIn("Just ordinary prose.", text)


class KeywordStuffingTests(unittest.TestCase):
    _STUFFED_PROSE = (
        "We sell cheap flights to paris every single day for busy travelers everywhere around the world. "
        "Our cheap flights to paris are widely considered the best value anywhere in the current travel market today. "
        "Book cheap flights to paris right now through our website and save big money on your upcoming trip. "
        "Everyone who has flown with us truly loves our cheap flights to paris deals during this busy travel season. "
        "Try booking cheap flights to paris today for a truly wonderful and memorable vacation experience with family. "
        "Many repeat customers keep coming back because our cheap flights to paris beat every competitor on price."
    )

    _VARIED_PROSE = (
        "Our warehouse ships orders within two business days across the country for every customer. "
        "Customer service representatives are available around the clock to help you with any issue. "
        "Every product undergoes rigorous quality testing before it ever leaves the factory floor. "
        "We stand behind every item we sell with a generous one year manufacturer warranty policy. "
        "Returns are accepted within thirty days provided the original packaging remains intact and clean. "
        "Delivery tracking numbers are emailed automatically as soon as your order ships from our facility."
    )

    def test_a_repeated_phrase_at_high_density_fires(self):
        findings = ret.find_keyword_stuffing(self._STUFFED_PROSE)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "RET-04-keyword-stuffing")
        self.assertIn("cheap flights to paris", findings[0].evidence)

    def test_varied_natural_prose_stays_silent(self):
        self.assertEqual(ret.find_keyword_stuffing(self._VARIED_PROSE), [])

    def test_below_the_minimum_word_count_stays_silent_even_if_repeated(self):
        short = "cheap flights to paris. " * 6
        self.assertEqual(ret.find_keyword_stuffing(short), [])

    def test_a_phrase_made_entirely_of_stopwords_never_counts(self):
        # "of the in the" etc. repeated is degenerate but not a keyword-stuffing signal.
        padding = "genuine content word here filling out the page length nicely today. " * 3
        text = ("in the of the on the at the " * 10) + padding
        findings = ret.find_keyword_stuffing(text)
        for finding in findings:
            phrases = [p["phrase"] for p in finding.structured_evidence["repeated_phrases"]]
            for phrase in phrases:
                self.assertFalse(all(w in ret._STOPWORDS for w in phrase.split()))

    def test_occurrences_below_the_minimum_count_do_not_fire(self):
        # The phrase appears only twice — below _KEYWORD_STUFFING_MIN_OCCURRENCES.
        # The rest of the padding must itself be varied, not a repeated
        # sentence, or it becomes its own (unintended) stuffing signal.
        text = (
            "cheap flights to paris are lovely this time of year for everyone traveling abroad. "
            "cheap flights to paris also make a fine gift for someone you love dearly this winter. "
            + KeywordStuffingTests._VARIED_PROSE
        )
        findings = ret.find_keyword_stuffing(text)
        self.assertEqual(findings, [])

    def test_table_only_repetition_never_reaches_find_keyword_stuffing(self):
        # Structured-region exclusion happens in extract_prose_text, upstream
        # of this function — this test documents that find_keyword_stuffing
        # itself has no awareness of HTML structure, by construction.
        rows_text = "model number weight class " * 10
        self.assertNotEqual(ret.find_keyword_stuffing(rows_text + self._VARIED_PROSE), [])

    def test_evaluation_is_deterministic(self):
        first = ret.find_keyword_stuffing(self._STUFFED_PROSE)
        second = ret.find_keyword_stuffing(self._STUFFED_PROSE)
        self.assertEqual([f.to_dict() for f in first], [f.to_dict() for f in second])


class KeywordStuffingStructuredRegionExclusionTests(unittest.TestCase):
    def test_a_phrase_repeated_only_inside_a_spec_table_does_not_fire(self):
        rows = "".join(f"<tr><td>Model Number Weight Class {i}</td><td>Value {i}</td></tr>" for i in range(10))
        html = f"<html><body><table>{rows}</table><p>{KeywordStuffingTests._VARIED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertNotIn("RET-04-keyword-stuffing", ids)

    def test_a_phrase_repeated_in_real_prose_still_fires_with_a_table_present(self):
        rows = "".join(f"<tr><td>Model Number Weight Class {i}</td><td>Value {i}</td></tr>" for i in range(10))
        html = f"<html><body><table>{rows}</table><p>{KeywordStuffingTests._STUFFED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertIn("RET-04-keyword-stuffing", ids)


class DefinitionBlockTests(unittest.TestCase):
    def test_a_dt_dd_pair_is_detected(self):
        html = "<dl><dt>Term</dt><dd>Definition</dd></dl>"
        self.assertTrue(ret.has_definition_block(html))

    def test_dt_and_dd_do_not_need_to_share_a_dl(self):
        html = "<div><dt>Term</dt></div><div><dd>Definition</dd></div>"
        self.assertTrue(ret.has_definition_block(html))

    def test_only_dt_with_no_dd_is_not_a_definition_block(self):
        self.assertFalse(ret.has_definition_block("<dl><dt>Term</dt></dl>"))

    def test_only_dd_with_no_dt_is_not_a_definition_block(self):
        self.assertFalse(ret.has_definition_block("<dl><dd>Definition</dd></dl>"))

    def test_no_definition_markup_at_all(self):
        self.assertFalse(ret.has_definition_block("<p>Plain prose.</p>"))


class QaFramingTests(unittest.TestCase):
    def test_a_heading_ending_in_a_question_mark_is_qa_framing(self):
        headings = [{"level": 2, "text": "How does shipping work?"}]
        self.assertTrue(ret.has_qa_heading_framing(headings))

    def test_a_declarative_heading_is_not_qa_framing(self):
        headings = [{"level": 2, "text": "Shipping information"}]
        self.assertFalse(ret.has_qa_heading_framing(headings))

    def test_no_headings_is_not_qa_framing(self):
        self.assertFalse(ret.has_qa_heading_framing([]))

    def test_an_faqpage_node_is_qa_schema(self):
        nodes = [{"@type": "FAQPage"}]
        self.assertTrue(ret.has_qa_schema(nodes))

    def test_a_qapage_node_is_qa_schema(self):
        nodes = [{"@type": "QAPage"}]
        self.assertTrue(ret.has_qa_schema(nodes))

    def test_an_unrelated_node_type_is_not_qa_schema(self):
        nodes = [{"@type": "Organization"}]
        self.assertFalse(ret.has_qa_schema(nodes))

    def test_no_nodes_is_not_qa_schema(self):
        self.assertFalse(ret.has_qa_schema([]))


class MissingRetrievalStructureTests(unittest.TestCase):
    # 300+ genuinely varied words, no repeated 4-word phrase, so RET-04
    # never fires alongside RET-07 in these fixtures.
    _LONG_VARIED_PROSE = (
        "Our warehouse ships every order within two business days across the entire country. "
        "A dedicated customer service team is available around the clock to answer questions. "
        "Each product line undergoes rigorous independent testing before it ever reaches a customer. "
        "We back every item sold with a generous twelve month manufacturer warranty at no cost. "
        "Returns are welcomed within thirty days as long as the original packaging stays intact. "
        "Tracking numbers arrive by email automatically the moment your package leaves our facility. "
        "Our design team sources sustainable materials from certified suppliers around the globe. "
        "Employees receive ongoing training so they can answer detailed technical questions confidently. "
        "The company was founded two decades ago by a small group of passionate engineers. "
        "Community outreach programs fund local schools and support small business development nearby. "
        "Every shipment includes recyclable packaging designed to minimize environmental impact overall. "
        "Seasonal promotions are announced through email newsletters sent to subscribed customers monthly. "
        "Product photography is done in house to keep listings accurate and genuinely representative. "
        "A quality assurance checklist accompanies every batch leaving the assembly line each week. "
        "International shipping options now cover more than forty countries across several continents. "
        "Customer feedback directly shapes upcoming product revisions through a structured review process. "
        "The engineering team publishes detailed changelogs whenever a hardware revision ships publicly. "
        "Financing options let customers spread larger purchases across several manageable monthly installments. "
        "A mobile application lets shoppers track orders and manage returns from anywhere conveniently. "
        "Partnerships with regional distributors help reduce delivery times in remote areas significantly. "
        "Annual sustainability reports are published publicly detailing energy and material usage trends. "
        "The founders remain actively involved in day to day product strategy and direction. "
        "Charitable donations are matched dollar for dollar during designated giving campaigns each year. "
        "Volunteer days let staff spend paid time supporting causes they personally care about deeply. "
        "A dedicated repair program extends product lifespan well beyond the standard warranty period."
    )

    def test_no_structure_at_all_fires(self):
        findings = ret.find_missing_retrieval_structure(
            [], [], False, len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, "RET-07-no-retrieval-structure")

    def test_any_heading_present_stays_silent(self):
        headings = [{"level": 1, "text": "About us"}]
        findings = ret.find_missing_retrieval_structure(
            headings, [], False, len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        )
        self.assertEqual(findings, [])

    def test_qa_heading_alone_stays_silent(self):
        headings = [{"level": 2, "text": "How does shipping work?"}]
        findings = ret.find_missing_retrieval_structure(
            headings, [], False, len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        )
        self.assertEqual(findings, [])

    def test_qa_schema_alone_stays_silent(self):
        findings = ret.find_missing_retrieval_structure(
            [], [{"@type": "FAQPage"}], False, len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        )
        self.assertEqual(findings, [])

    def test_definition_block_alone_stays_silent(self):
        findings = ret.find_missing_retrieval_structure(
            [], [], True, len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        )
        self.assertEqual(findings, [])

    def test_below_the_word_floor_stays_silent_even_with_no_structure(self):
        findings = ret.find_missing_retrieval_structure([], [], False, 50)
        self.assertEqual(findings, [])

    def test_evaluation_is_deterministic(self):
        word_count = len(ret._tokenize_words(self._LONG_VARIED_PROSE))
        first = ret.find_missing_retrieval_structure([], [], False, word_count)
        second = ret.find_missing_retrieval_structure([], [], False, word_count)
        self.assertEqual([f.to_dict() for f in first], [f.to_dict() for f in second])

    def test_full_page_with_no_structure_fires_via_audit_html(self):
        html = f"<html><body><p>{self._LONG_VARIED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertIn("RET-07-no-retrieval-structure", ids)

    def test_full_page_with_a_heading_does_not_fire_via_audit_html(self):
        html = f"<html><body><h1>About us</h1><p>{self._LONG_VARIED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertNotIn("RET-07-no-retrieval-structure", ids)


class ExtractParagraphsTests(unittest.TestCase):
    def test_each_paragraph_is_its_own_entry(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        self.assertEqual(ret.extract_paragraphs(html), ["First paragraph.", "Second paragraph."])

    def test_nested_markup_inside_a_paragraph_is_flattened(self):
        html = "<p>Some <strong>bold</strong> text.</p>"
        self.assertEqual(ret.extract_paragraphs(html), ["Some bold text."])

    def test_an_empty_paragraph_is_not_recorded(self):
        html = "<p></p><p>Real content.</p>"
        self.assertEqual(ret.extract_paragraphs(html), ["Real content."])

    def test_no_paragraphs_returns_empty_list(self):
        self.assertEqual(ret.extract_paragraphs("<div>No p tags here.</div>"), [])

    def test_text_outside_any_paragraph_is_not_collected(self):
        html = "<div>Not in a p.</div><p>In a p.</p>"
        self.assertEqual(ret.extract_paragraphs(html), ["In a p."])


class SemanticCoverageCandidateTests(unittest.TestCase):
    def test_a_repeated_phrase_is_identified_with_example_sentences(self):
        text = (
            "The pricing model is simple and clear for everyone. "
            "Our pricing model is simple and easy to understand. "
            "You will find our pricing model is simple across every plan we offer."
        )
        result = ret.find_semantic_coverage_candidates(text)
        self.assertEqual(result["dominant_phrase"], "model is simple")
        self.assertEqual(result["occurrences"], 3)
        self.assertEqual(len(result["example_sentences"]), 3)

    def test_no_repeated_phrase_returns_null_dominant_phrase(self):
        text = "Every sentence here discusses something completely different from the last one entirely."
        result = ret.find_semantic_coverage_candidates(text)
        self.assertIsNone(result["dominant_phrase"])
        self.assertEqual(result["occurrences"], 0)
        self.assertEqual(result["example_sentences"], [])


class QueryIntentCandidateTests(unittest.TestCase):
    def test_extracts_primary_heading_and_opening_excerpt(self):
        headings = [{"level": 1, "text": "Pricing"}]
        result = ret.find_query_intent_candidates(headings, [], "This page explains pricing. It covers plans.")
        self.assertEqual(result["primary_heading"], "Pricing")
        self.assertIn("pricing", result["opening_excerpt"].lower())

    def test_existing_qa_headings_are_listed(self):
        headings = [{"level": 1, "text": "Pricing"}, {"level": 2, "text": "How does billing work?"}]
        result = ret.find_query_intent_candidates(headings, [], "")
        self.assertEqual(result["existing_qa_headings"], ["How does billing work?"])

    def test_qa_schema_flag_is_carried_through(self):
        result = ret.find_query_intent_candidates([], [{"@type": "FAQPage"}], "")
        self.assertTrue(result["has_qa_schema"])

    def test_no_headings_gives_null_primary_heading(self):
        result = ret.find_query_intent_candidates([], [], "Some text.")
        self.assertIsNone(result["primary_heading"])


class TerminologyBalanceCandidateTests(unittest.TestCase):
    def test_acronym_and_long_word_signals_are_counted(self):
        text = "The API uses sophisticated cryptographic authentication mechanisms for every transaction."
        result = ret.find_terminology_balance_candidates(text)
        self.assertGreaterEqual(result["acronym_count"], 1)
        self.assertGreater(result["long_word_ratio"], 0.0)

    def test_sample_sentences_span_opening_middle_and_closing(self):
        text = "Sentence one is here. Sentence two is here. Sentence three is here. Sentence four is here."
        result = ret.find_terminology_balance_candidates(text)
        self.assertGreaterEqual(len(result["sample_sentences"]), 2)
        self.assertIn("Sentence one is here.", result["sample_sentences"])

    def test_empty_text_does_not_crash(self):
        result = ret.find_terminology_balance_candidates("")
        self.assertEqual(result["total_words"], 0)
        self.assertEqual(result["long_word_ratio"], 0.0)

    def test_a_verbatim_repeated_nav_block_does_not_inflate_acronym_count(self):
        """Small templated sites repeat an entire nav/menu block verbatim
        2-3 times (desktop state, expanded state, mobile 'Folder:' state),
        each as its own block-boundary-newline-split entry. A live
        yogaoffeast.com page hit acronym_count: 14 this way, almost
        entirely from 'BOOK A CLASS' (a button label, not an acronym)
        repeated across duplicated menu states."""
        text = "\n".join(
            [
                "BOOK A CLASS",
                "BOOK A CLASS",
                "BOOK A CLASS",
                "We teach vinyasa flow yoga classes for every level of experience in our warm downtown studio.",
            ]
        )
        result = ret.find_terminology_balance_candidates(text)
        self.assertEqual(result["acronym_count"], 0)

    def test_short_all_caps_menu_headings_are_not_counted_as_acronyms(self):
        """Distinct (non-duplicated) short all-caps headings are a second
        real root cause hit live on creswellbakery.com/menu:
        acronym_count: 39 from product-name headings like 'CHIPOTLE HAM
        BRIOCHE SANDWICH' and 'CIABATTA BACON SANDWICH' — each unique, so
        de-duplication alone doesn't touch them."""
        text = "\n".join(
            [
                "CHIPOTLE HAM BRIOCHE SANDWICH",
                "CIABATTA BACON SANDWICH",
                "Made to order breakfast and lunch is served every day from our fresh-baked artisan breads.",
            ]
        )
        result = ret.find_terminology_balance_candidates(text)
        self.assertEqual(result["acronym_count"], 0)

    def test_a_real_acronym_in_ordinary_mixed_case_prose_still_counts(self):
        text = "The API leverages OAuth2 PKCE flows with JWT-based RBAC enforcement across multi-tenant namespace isolation boundaries."
        result = ret.find_terminology_balance_candidates(text)
        self.assertGreaterEqual(result["acronym_count"], 3)

    def test_duplicated_short_chrome_lines_do_not_crowd_out_a_real_prose_sample(self):
        text = "\n".join(
            [
                "MENU",
                "BOOK A CLASS",
                "BOOK A CLASS",
                "BOOK A CLASS",
                "Our studio offers vinyasa flow yoga classes every day of the week for all skill levels.",
            ]
        )
        result = ret.find_terminology_balance_candidates(text)
        self.assertEqual(
            result["sample_sentences"],
            ["Our studio offers vinyasa flow yoga classes every day of the week for all skill levels."],
        )


class ChunkQualityCandidateTests(unittest.TestCase):
    _LONG_PARAGRAPH = (
        "This paragraph discusses shipping timelines in significant detail for the first few sentences here. "
        "It then pivots entirely to describe warranty terms and coverage limitations without any transition. "
        "Midway through it also brings up an unrelated return policy exception for international customers. "
        "Finally it closes with a completely separate note about customer support contact hours and channels. "
        "Each of these four distinct ideas really belongs in its own separate paragraph rather than being "
        "blended together the way it has been written here, which is exactly the kind of chunk-quality "
        "problem this capability exists to flag for a page's author to go fix properly."
    )

    def test_a_long_multi_sentence_paragraph_is_flagged_as_a_candidate(self):
        candidates = ret.find_chunk_quality_candidates([self._LONG_PARAGRAPH])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["paragraph"], self._LONG_PARAGRAPH)

    def test_a_short_paragraph_is_not_a_candidate(self):
        candidates = ret.find_chunk_quality_candidates(["A short paragraph about one thing."])
        self.assertEqual(candidates, [])

    def test_candidates_are_capped(self):
        candidates = ret.find_chunk_quality_candidates([self._LONG_PARAGRAPH] * 15)
        self.assertEqual(len(candidates), 10)

    def test_no_paragraphs_returns_empty(self):
        self.assertEqual(ret.find_chunk_quality_candidates([]), [])


class BuildAgentJudgementRequestsTests(unittest.TestCase):
    def test_returns_one_entry_per_capability(self):
        requests = ret.build_agent_judgement_requests([], [], "Some prose text here for testing purposes.", [])
        ids = [r["capability_id"] for r in requests]
        self.assertEqual(ids, ["RET-02", "RET-03", "RET-05", "RET-06"])

    def test_every_entry_has_instructions_and_observations(self):
        requests = ret.build_agent_judgement_requests([], [], "Some prose text here.", [])
        for request in requests:
            self.assertIn("instructions", request)
            self.assertIn("observations", request)
            self.assertIn("references/retrieval-judgement-rubric.md", request["instructions"])

    def test_wired_into_audit_html_output(self):
        html = "<html><body><h1>Widgets</h1><p>Some ordinary text here about widgets.</p></body></html>"
        output = ret.audit_html("example.com", html, page_url="https://example.com/widgets")
        self.assertIn("agent_judgement_required", output)
        self.assertEqual(len(output["agent_judgement_required"]), 4)
        for request in output["agent_judgement_required"]:
            self.assertEqual(request["observations"]["page_url"], "https://example.com/widgets")


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        html = "<h1>Title</h1><h3>Skips h2</h3><h4></h4>"
        output = ret.audit_html("example.com", html)
        self.assertEqual(len(output["findings"]), 2)
        for finding_dict in output["findings"]:
            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "retrieval-readiness-audit")
            self.assertEqual(restored.gate, 3)
            self.assertEqual(restored.category, "discoverability")

    def test_ret01_finding_satisfies_the_contract(self):
        html = (
            '<script type="application/ld+json">{"@type": "Product", "sku": "WID-123"}</script>'
            "<h1>Widget</h1><p>No identifier here.</p>"
        )
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertIn("RET-01-token-not-in-text", ids)
        for finding_dict in output["findings"]:
            self.assertEqual(Finding.from_dict(finding_dict).validate(), [])

    def test_ret04_finding_satisfies_the_contract(self):
        html = f"<html><body><p>{KeywordStuffingTests._STUFFED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertIn("RET-04-keyword-stuffing", ids)
        for finding_dict in output["findings"]:
            self.assertEqual(Finding.from_dict(finding_dict).validate(), [])

    def test_ret07_finding_satisfies_the_contract(self):
        html = f"<html><body><p>{MissingRetrievalStructureTests._LONG_VARIED_PROSE}</p></body></html>"
        output = ret.audit_html("example.com", html)
        ids = [f["id"] for f in output["findings"]]
        self.assertIn("RET-07-no-retrieval-structure", ids)
        for finding_dict in output["findings"]:
            self.assertEqual(Finding.from_dict(finding_dict).validate(), [])

    def test_evaluation_is_deterministic(self):
        html = "<h1>Title</h1><h3>Skips h2</h3>"
        first = ret.audit_html("example.com", html)
        second = ret.audit_html("example.com", html)
        self.assertEqual(first, second)

    def test_a_clean_page_produces_no_findings(self):
        html = "<h1>Title</h1><h2>Section</h2><h3>Subsection</h3><h2>Another section</h2>"
        output = ret.audit_html("example.com", html)
        self.assertEqual(output["findings"], [])


class PageAttributionTests(unittest.TestCase):
    def test_page_url_is_stamped_into_evidence_and_structured_evidence(self):
        output = ret.audit_html("example.com", "<h1>Title</h1><h3>Skip</h3>", page_url="https://example.com/page")
        finding = output["findings"][0]
        self.assertTrue(finding["evidence"].startswith("On https://example.com/page:"))
        self.assertEqual(finding["structured_evidence"]["page_url"], "https://example.com/page")

    def test_no_page_url_leaves_evidence_unstamped(self):
        output = ret.audit_html("example.com", "<h1>Title</h1><h3>Skip</h3>")
        self.assertFalse(output["findings"][0]["evidence"].startswith("On "))


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(ret.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(ret.is_public_host("10.0.0.5"))

    def test_an_unresolvable_host_is_refused(self):
        self.assertFalse(ret.is_public_host("this-host-does-not-exist.invalid"))


if __name__ == "__main__":
    unittest.main()
