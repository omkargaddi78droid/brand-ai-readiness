"""Unit tests for shared/fuzzy_match.py (difflib-backed rapidfuzz
replacement, cycle 23 Part 1/2)."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from fuzzy_match import partial_ratio, single_linkage_clusters, token_sort_ratio  # noqa: E402


class TokenSortRatioTests(unittest.TestCase):
    def test_identical_strings_score_100(self):
        self.assertEqual(token_sort_ratio("Acme Widgets", "Acme Widgets"), 100.0)

    def test_word_order_does_not_matter(self):
        self.assertEqual(token_sort_ratio("Acme Widgets Inc", "Inc Acme Widgets"), 100.0)

    def test_is_case_insensitive(self):
        self.assertEqual(token_sort_ratio("ACME WIDGETS", "acme widgets"), 100.0)

    def test_unrelated_strings_score_low(self):
        self.assertLess(token_sort_ratio("Acme Widgets", "Totally Different Corp"), 40.0)

    def test_near_miss_scores_high_but_not_perfect(self):
        score = token_sort_ratio("Acme Widgets Inc", "Acme Widget Inc")
        self.assertGreater(score, 80.0)
        self.assertLess(score, 100.0)

    def test_empty_strings_score_100(self):
        self.assertEqual(token_sort_ratio("", ""), 100.0)


class PartialRatioTests(unittest.TestCase):
    def test_a_short_string_fully_contained_in_a_longer_one_scores_100(self):
        self.assertEqual(partial_ratio("123 Main St", "123 Main St, Suite 400, Springfield"), 100.0)

    def test_unrelated_strings_score_low(self):
        self.assertLess(partial_ratio("123 Main St", "999 Totally Different Ave"), 60.0)

    def test_one_empty_string_scores_zero(self):
        self.assertEqual(partial_ratio("", "123 Main St"), 0.0)

    def test_both_empty_scores_100(self):
        self.assertEqual(partial_ratio("", ""), 100.0)

    def test_is_symmetric_in_which_argument_is_longer(self):
        a, b = "123 Main St", "123 Main St, Suite 400, Springfield"
        self.assertEqual(partial_ratio(a, b), partial_ratio(b, a))


class SingleLinkageClustersTests(unittest.TestCase):
    def test_near_identical_items_cluster_together(self):
        items = ["Acme Widgets Inc", "Acme Widget Inc", "Totally Different Corp"]
        clusters = single_linkage_clusters(items, threshold=85)
        cluster_sizes = sorted(len(c) for c in clusters)
        self.assertEqual(cluster_sizes, [1, 2])

    def test_every_item_appears_exactly_once_across_all_clusters(self):
        items = ["Acme Widgets Inc", "Acme Widget Inc", "Totally Different Corp", "Yet Another Co"]
        clusters = single_linkage_clusters(items, threshold=85)
        flattened = sorted(index for cluster in clusters for index in cluster)
        self.assertEqual(flattened, list(range(len(items))))

    def test_a_chain_of_near_matches_forms_one_cluster_even_without_direct_pairwise_match(self):
        # "A" matches "B" and "B" matches "C" above threshold, but "A" vs "C"
        # alone might not — single-linkage still merges all three via "B".
        items = ["aaaaa bbbbb", "bbbbb ccccc", "ccccc ddddd"]
        clusters = single_linkage_clusters(items, threshold=45)
        self.assertEqual(len(clusters), 1)

    def test_no_items_returns_no_clusters(self):
        self.assertEqual(single_linkage_clusters([], threshold=85), [])

    def test_a_single_item_is_its_own_cluster(self):
        self.assertEqual(single_linkage_clusters(["solo"], threshold=85), [[0]])

    def test_clusters_are_returned_in_order_of_lowest_member_index(self):
        items = ["Acme Widgets Inc", "Totally Different Corp", "Acme Widget Inc"]
        clusters = single_linkage_clusters(items, threshold=85)
        self.assertIn(0, clusters[0])


if __name__ == "__main__":
    unittest.main()
