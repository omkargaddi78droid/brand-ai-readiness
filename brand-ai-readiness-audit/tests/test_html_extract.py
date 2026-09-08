"""Coverage for shared/html_extract.py (cycle 24 item 9): the vendored-bs4
wrapper used by content-quality-audit's CQ-07/CQ-08 (table/dl labeled-pair
extraction) and CQ-01 (main-content boundary extraction)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "shared"))

from html_extract import extract_labeled_pairs, extract_main_content_text


class ExtractLabeledPairsTableTests(unittest.TestCase):
    def test_a_th_td_row_produces_a_labeled_line(self):
        html = "<table><tr><th>Revenue</th><td>$4.2M</td></tr></table>"
        self.assertEqual(extract_labeled_pairs(html), ["Revenue: $4.2M"])

    def test_multiple_rows_each_produce_their_own_line(self):
        html = (
            "<table>"
            "<tr><th>Revenue</th><td>$4.2M</td></tr>"
            "<tr><th>Headcount</th><td>230</td></tr>"
            "</table>"
        )
        self.assertEqual(
            extract_labeled_pairs(html), ["Revenue: $4.2M", "Headcount: 230"]
        )

    def test_a_row_with_only_one_cell_produces_nothing(self):
        html = "<table><tr><th>Revenue</th></tr></table>"
        self.assertEqual(extract_labeled_pairs(html), [])

    def test_an_empty_cell_is_not_paired(self):
        html = "<table><tr><th></th><td>$4.2M</td></tr></table>"
        self.assertEqual(extract_labeled_pairs(html), [])

    def test_a_td_td_row_still_pairs_the_first_two_cells(self):
        """No <th> required — some real pages use two <td>s for a label/value
        row; the pairing is positional, not header-semantics-based."""
        html = "<table><tr><td>Revenue</td><td>$4.2M</td></tr></table>"
        self.assertEqual(extract_labeled_pairs(html), ["Revenue: $4.2M"])


class ExtractLabeledPairsDlTests(unittest.TestCase):
    def test_a_dt_dd_pair_produces_a_labeled_line(self):
        html = "<dl><dt>Founded</dt><dd>2014</dd></dl>"
        self.assertEqual(extract_labeled_pairs(html), ["Founded: 2014"])

    def test_a_dt_with_no_following_dd_produces_nothing(self):
        html = "<dl><dt>Founded</dt></dl>"
        self.assertEqual(extract_labeled_pairs(html), [])

    def test_a_dd_with_no_preceding_dt_produces_nothing(self):
        html = "<dl><dd>2014</dd></dl>"
        self.assertEqual(extract_labeled_pairs(html), [])

    def test_multiple_dt_dd_pairs_each_produce_their_own_line(self):
        html = "<dl><dt>Founded</dt><dd>2014</dd><dt>HQ</dt><dd>Austin</dd></dl>"
        self.assertEqual(extract_labeled_pairs(html), ["Founded: 2014", "HQ: Austin"])


class ExtractLabeledPairsEmptyAndMalformedTests(unittest.TestCase):
    def test_empty_html_produces_nothing(self):
        self.assertEqual(extract_labeled_pairs(""), [])

    def test_html_with_no_table_or_dl_produces_nothing(self):
        self.assertEqual(extract_labeled_pairs("<p>Just a paragraph.</p>"), [])

    def test_malformed_markup_does_not_crash(self):
        html = "<table><tr><th>Revenue<td>$4.2M</tr></table>"
        # No assertion on the exact result — bs4's stdlib-backend error
        # recovery is not this project's contract — only that a real,
        # commonly-malformed (unclosed tags) fragment never raises.
        extract_labeled_pairs(html)


class ExtractMainContentTextTests(unittest.TestCase):
    def test_a_main_tag_is_used(self):
        html = "<body><nav>Home About</nav><main>The actual answer is 42.</main></body>"
        text = extract_main_content_text(html)
        self.assertIn("The actual answer is 42.", text)
        self.assertNotIn("Home About", text)

    def test_an_article_tag_is_used_when_no_main_exists(self):
        html = "<body><header>Brand</header><article>The actual answer is 42.</article></body>"
        text = extract_main_content_text(html)
        self.assertIn("The actual answer is 42.", text)
        self.assertNotIn("Brand", text)

    def test_main_is_preferred_over_article_when_both_exist(self):
        html = (
            "<body><article>Wrong region.</article>"
            "<main>Right region.</main></body>"
        )
        text = extract_main_content_text(html)
        self.assertIn("Right region.", text)
        self.assertNotIn("Wrong region.", text)

    def test_neither_tag_present_returns_none(self):
        html = "<body><div>Only a div, no semantic sectioning tag.</div></body>"
        self.assertIsNone(extract_main_content_text(html))

    def test_nav_header_footer_aside_nested_inside_main_are_stripped(self):
        html = (
            "<main>"
            "<nav>Skip nav text</nav>"
            "<header>Skip header text</header>"
            "Keep this content."
            "<aside>Skip aside text</aside>"
            "<footer>Skip footer text</footer>"
            "</main>"
        )
        text = extract_main_content_text(html)
        self.assertIn("Keep this content.", text)
        for excluded in ("Skip nav text", "Skip header text", "Skip aside text", "Skip footer text"):
            self.assertNotIn(excluded, text)

    def test_an_empty_main_tag_returns_none_not_an_empty_string(self):
        html = "<main><nav>Only nav, nothing else.</nav></main>"
        self.assertIsNone(extract_main_content_text(html))

    def test_empty_html_returns_none(self):
        self.assertIsNone(extract_main_content_text(""))


if __name__ == "__main__":
    unittest.main()
