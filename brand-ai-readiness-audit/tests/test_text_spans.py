"""Contract tests for shared/text_spans.py."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from text_spans import (  # noqa: E402
    extract_blocks,
    normalized_position,
    proper_noun_tokens,
    split_sentences,
)


class ExtractBlocksTests(unittest.TestCase):
    def test_empty_page_returns_empty_list_without_raising(self):
        self.assertEqual(extract_blocks(""), [])
        self.assertEqual(extract_blocks("<html><body></body></html>"), [])

    def test_simple_multi_paragraph_page(self):
        html = "<html><body><p>First paragraph.</p><p>Second paragraph.</p></body></html>"
        blocks = extract_blocks(html)
        self.assertEqual([b.text for b in blocks], ["First paragraph.", "Second paragraph."])
        self.assertEqual([b.tag for b in blocks], ["p", "p"])
        self.assertEqual([b.word_count for b in blocks], [2, 2])

    def test_offsets_are_into_the_concatenated_visible_text_stream(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        blocks = extract_blocks(html)
        first, second = blocks
        self.assertEqual(first.start_char, 0)
        self.assertEqual(first.end_char, len("First paragraph."))
        # blocks are joined by exactly one space in the coordinate system
        self.assertEqual(second.start_char, first.end_char + 1)
        self.assertEqual(second.end_char, second.start_char + len("Second paragraph."))

    def test_nearest_heading_tracks_across_multiple_headings(self):
        html = (
            "<h1>Intro</h1>"
            "<p>Under intro.</p>"
            "<h2>Details</h2>"
            "<p>Under details.</p>"
            "<p>Also under details.</p>"
        )
        blocks = extract_blocks(html)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0].text, "Under intro.")
        self.assertEqual(blocks[0].nearest_heading, "Intro")
        self.assertEqual(blocks[1].text, "Under details.")
        self.assertEqual(blocks[1].nearest_heading, "Details")
        self.assertEqual(blocks[2].text, "Also under details.")
        self.assertEqual(blocks[2].nearest_heading, "Details")

    def test_block_before_any_heading_has_no_nearest_heading(self):
        html = "<p>No heading yet.</p><h1>First heading</h1><p>Now has a heading.</p>"
        blocks = extract_blocks(html)
        self.assertIsNone(blocks[0].nearest_heading)
        self.assertEqual(blocks[1].nearest_heading, "First heading")

    def test_script_style_pre_content_is_excluded_and_does_not_shift_offsets(self):
        html_with_junk = (
            "<p>Before.</p>"
            "<script>var x = 'this must never appear, it is quite long';</script>"
            "<style>.cls { color: red; /* also long */ }</style>"
            "<pre>some\npreformatted\ncode\nblock</pre>"
            "<p>After.</p>"
        )
        html_without_junk = "<p>Before.</p><p>After.</p>"

        blocks_with_junk = extract_blocks(html_with_junk)
        blocks_without_junk = extract_blocks(html_without_junk)

        texts = [b.text for b in blocks_with_junk]
        self.assertEqual(texts, ["Before.", "After."])
        for text in texts:
            self.assertNotIn("must never appear", text)
            self.assertNotIn("preformatted", text)

        # Offsets for "After." must be identical whether or not the skipped
        # content was ever there.
        self.assertEqual(
            [b.start_char for b in blocks_with_junk],
            [b.start_char for b in blocks_without_junk],
        )
        self.assertEqual(
            [b.end_char for b in blocks_with_junk],
            [b.end_char for b in blocks_without_junk],
        )

    def test_blockquote_and_list_items(self):
        html = (
            "<blockquote>A quoted line.</blockquote>"
            "<ul><li>First item.</li><li>Second item.</li></ul>"
        )
        blocks = extract_blocks(html)
        self.assertEqual(
            [(b.tag, b.text) for b in blocks],
            [
                ("blockquote", "A quoted line."),
                ("li", "First item."),
                ("li", "Second item."),
            ],
        )

    def test_nested_block_tags_stay_in_document_order(self):
        # blockquote > p is common real-world markup; a naive implementation
        # can emit the nested block before the outer's leading text because
        # the nested tag closes first.
        html = "<li>Outer start <p>Nested para</p> outer end</li>"
        blocks = extract_blocks(html)
        self.assertEqual(
            [(b.tag, b.text) for b in blocks],
            [
                ("li", "Outer start"),
                ("p", "Nested para"),
                ("li", "outer end"),
            ],
        )
        # offsets must also be strictly increasing, matching document order
        for earlier, later in zip(blocks, blocks[1:]):
            self.assertLess(earlier.start_char, later.start_char)

    def test_bare_text_outside_block_tags_becomes_a_block(self):
        html = "<section><h2>Section heading</h2>Bare text node under section.</section>"
        blocks = extract_blocks(html)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].text, "Bare text node under section.")
        self.assertEqual(blocks[0].nearest_heading, "Section heading")
        self.assertEqual(blocks[0].tag, "section")


class SplitSentencesTests(unittest.TestCase):
    def test_multi_sentence_paragraph(self):
        text = "The cat sat. The dog ran. Birds flew away."
        sentences = split_sentences(text)
        self.assertEqual(
            [s.text for s in sentences],
            ["The cat sat.", "The dog ran.", "Birds flew away."],
        )
        for sentence in sentences:
            self.assertEqual(text[sentence.start_char : sentence.end_char], sentence.text)

    def test_abbreviation_guard_does_not_split_on_dr(self):
        text = "Dr. Smith went home. He was tired."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0].text, "Dr. Smith went home.")
        self.assertEqual(sentences[1].text, "He was tired.")

    def test_decimal_number_does_not_split(self):
        text = "The price rose 3.5 percent."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, text)

    def test_other_abbreviations_do_not_split(self):
        text = "We support cats, dogs, etc. All pets are welcome."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, text)

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(split_sentences(""), [])

    def test_offsets_always_reproduce_the_span_text(self):
        text = "Mr. Lee said 3.14 is close to pi. It really is!"
        for sentence in split_sentences(text):
            self.assertEqual(text[sentence.start_char : sentence.end_char], sentence.text)


class NormalizedPositionTests(unittest.TestCase):
    def test_mid_range_value(self):
        self.assertAlmostEqual(normalized_position(25, 100), 0.25)

    def test_offset_equals_total_returns_one(self):
        self.assertEqual(normalized_position(100, 100), 1.0)

    def test_total_chars_zero_returns_zero_without_raising(self):
        self.assertEqual(normalized_position(0, 0), 0.0)
        self.assertEqual(normalized_position(5, 0), 0.0)

    def test_offset_beyond_total_is_clamped_to_one(self):
        self.assertEqual(normalized_position(150, 100), 1.0)


class ProperNounTokensTests(unittest.TestCase):
    def test_brand_name_mid_sentence_is_captured(self):
        tokens = proper_noun_tokens("Our new Widget Pro launches next month.")
        self.assertIn("Widget", tokens)
        self.assertIn("Pro", tokens)

    def test_sentence_initial_capitalised_word_is_not_captured(self):
        tokens = proper_noun_tokens("Widgets are great. They help everyone.")
        self.assertNotIn("Widgets", tokens)
        self.assertNotIn("They", tokens)

    def test_month_name_mid_sentence_is_not_captured(self):
        tokens = proper_noun_tokens("The event happens in July every year.")
        self.assertNotIn("July", tokens)

    def test_weekday_name_mid_sentence_is_not_captured(self):
        tokens = proper_noun_tokens("The meeting is on Friday afternoon.")
        self.assertNotIn("Friday", tokens)

    def test_result_is_deduplicated(self):
        tokens = proper_noun_tokens("Acme sells Acme products under the Acme brand.")
        self.assertEqual(sum(1 for t in tokens if t == "Acme"), 1)


if __name__ == "__main__":
    unittest.main()
