"""Unit tests for shared/shingles.py (k-shingle Jaccard near-duplicate
detection, cycle 23 Part 1/2)."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from shingles import jaccard_similarity, near_duplicate_groups, shingle_set  # noqa: E402


class ShingleSetTests(unittest.TestCase):
    def test_produces_overlapping_k_word_windows(self):
        shingles = shingle_set("the quick brown fox jumps over", k=3)
        self.assertIn(("the", "quick", "brown"), shingles)
        self.assertIn(("quick", "brown", "fox"), shingles)
        self.assertIn(("fox", "jumps", "over"), shingles)

    def test_shorter_than_k_words_yields_one_shingle_not_empty(self):
        shingles = shingle_set("hello world", k=5)
        self.assertEqual(shingles, frozenset({("hello", "world")}))

    def test_empty_text_yields_an_empty_set(self):
        self.assertEqual(shingle_set(""), frozenset())

    def test_is_case_insensitive(self):
        self.assertEqual(shingle_set("Hello World", k=2), shingle_set("hello world", k=2))

    def test_punctuation_does_not_change_the_word_tokens(self):
        self.assertEqual(shingle_set("hello, world!", k=2), shingle_set("hello world", k=2))


class JaccardSimilarityTests(unittest.TestCase):
    def test_identical_sets_score_1(self):
        s = shingle_set("the quick brown fox", k=2)
        self.assertEqual(jaccard_similarity(s, s), 1.0)

    def test_disjoint_sets_score_0(self):
        a = frozenset({("a", "b")})
        b = frozenset({("c", "d")})
        self.assertEqual(jaccard_similarity(a, b), 0.0)

    def test_both_empty_scores_1(self):
        self.assertEqual(jaccard_similarity(frozenset(), frozenset()), 1.0)

    def test_one_empty_scores_0(self):
        self.assertEqual(jaccard_similarity(frozenset({("a",)}), frozenset()), 0.0)

    def test_partial_overlap_is_between_0_and_1(self):
        a = shingle_set("the quick brown fox jumps", k=2)
        b = shingle_set("the quick brown dog jumps", k=2)
        score = jaccard_similarity(a, b)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class NearDuplicateGroupsTests(unittest.TestCase):
    def test_near_identical_pages_cluster_together(self):
        texts = [
            "Our premium widget comes with a thirty day money back guarantee and free shipping worldwide",
            "Our premium widget comes with a thirty day money back guarantee and free shipping globally",
            "Completely unrelated content about quarterly financial reporting standards for enterprises",
        ]
        groups = near_duplicate_groups(texts, k=4, threshold=0.6)
        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [1, 2])

    def test_legitimate_sku_variants_with_real_differences_stay_distinct(self):
        # Same template/boilerplate but different product-specific content
        # throughout — a realistic "not a true duplicate" case.
        texts = [
            "The Widget Pro features a titanium frame, ten hour battery, and ships in blue or black",
            "The Widget Mini features a plastic frame, three hour battery, and ships in red or white",
        ]
        groups = near_duplicate_groups(texts, k=4, threshold=0.85)
        self.assertEqual(sorted(len(g) for g in groups), [1, 1])

    def test_blank_pages_never_join_a_cluster_with_each_other(self):
        texts = ["", "", "some actual page content here that is reasonably long"]
        groups = near_duplicate_groups(texts, k=4, threshold=0.7)
        self.assertEqual(sorted(len(g) for g in groups), [1, 1, 1])

    def test_every_index_appears_exactly_once(self):
        texts = ["alpha beta gamma delta", "alpha beta gamma delta epsilon", "zeta eta theta iota"]
        groups = near_duplicate_groups(texts, k=3, threshold=0.5)
        flattened = sorted(i for g in groups for i in g)
        self.assertEqual(flattened, list(range(len(texts))))

    def test_no_texts_returns_no_groups(self):
        self.assertEqual(near_duplicate_groups([]), [])


if __name__ == "__main__":
    unittest.main()
