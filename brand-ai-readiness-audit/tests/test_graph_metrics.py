"""Unit tests for shared/graph_metrics.py (replaces networkx — see the
module docstring for why)."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from graph_metrics import connected_components, degree, pagerank  # noqa: E402


class ConnectedComponentsTests(unittest.TestCase):
    def test_a_single_edge_joins_two_nodes_into_one_component(self):
        components = connected_components(["a", "b"], [("a", "b")])
        self.assertEqual(components, [{"a", "b"}])

    def test_disconnected_nodes_are_separate_singleton_components(self):
        components = connected_components(["a", "b", "c"], [])
        self.assertEqual(sorted(map(sorted, components)), [["a"], ["b"], ["c"]])

    def test_a_chain_transitively_joins_into_one_component(self):
        components = connected_components(["a", "b", "c"], [("a", "b"), ("b", "c")])
        self.assertEqual(components, [{"a", "b", "c"}])

    def test_two_separate_clusters_stay_separate(self):
        components = connected_components(
            ["a", "b", "c", "d"], [("a", "b"), ("c", "d")]
        )
        self.assertEqual(sorted(map(sorted, components)), [["a", "b"], ["c", "d"]])

    def test_an_edge_to_an_id_outside_node_ids_is_ignored_not_an_error(self):
        components = connected_components(["a", "b"], [("a", "outside-the-graph")])
        self.assertEqual(sorted(map(sorted, components)), [["a"], ["b"]])

    def test_every_node_id_appears_in_exactly_one_component(self):
        node_ids = ["a", "b", "c", "d", "e"]
        components = connected_components(node_ids, [("a", "b"), ("c", "d")])
        seen = [node for component in components for node in component]
        self.assertEqual(sorted(seen), sorted(node_ids))

    def test_empty_graph_returns_no_components(self):
        self.assertEqual(connected_components([], []), [])


class DegreeTests(unittest.TestCase):
    def test_an_isolated_node_has_degree_zero(self):
        self.assertEqual(degree(["a"], []), {"a": 0})

    def test_one_edge_gives_both_endpoints_degree_one(self):
        self.assertEqual(degree(["a", "b"], [("a", "b")]), {"a": 1, "b": 1})

    def test_a_hub_node_accumulates_degree_across_multiple_edges(self):
        result = degree(["hub", "a", "b", "c"], [("hub", "a"), ("hub", "b"), ("hub", "c")])
        self.assertEqual(result["hub"], 3)
        self.assertEqual(result["a"], 1)

    def test_an_edge_to_an_id_outside_node_ids_does_not_count_toward_degree(self):
        result = degree(["a"], [("a", "outside")])
        self.assertEqual(result, {"a": 1})


class PagerankTests(unittest.TestCase):
    def test_empty_graph_returns_empty(self):
        self.assertEqual(pagerank([], []), {})

    def test_ranks_sum_to_approximately_one(self):
        node_ids = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        ranks = pagerank(node_ids, edges)
        self.assertAlmostEqual(sum(ranks.values()), 1.0, places=6)

    def test_a_node_receiving_many_links_outranks_one_receiving_none(self):
        node_ids = ["hub", "a", "b", "c", "isolated"]
        edges = [("a", "hub"), ("b", "hub"), ("c", "hub")]
        ranks = pagerank(node_ids, edges)
        self.assertGreater(ranks["hub"], ranks["isolated"])

    def test_a_symmetric_cycle_ranks_every_node_equally(self):
        node_ids = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c"), ("c", "a")]
        ranks = pagerank(node_ids, edges)
        self.assertAlmostEqual(ranks["a"], ranks["b"], places=6)
        self.assertAlmostEqual(ranks["b"], ranks["c"], places=6)

    def test_a_dangling_node_does_not_leak_rank_out_of_the_system(self):
        """A node with no outgoing edges must redistribute its rank rather
        than letting total rank drain away over iterations."""
        node_ids = ["a", "b"]
        edges = [("a", "b")]  # b is dangling: nothing to link onward to
        ranks = pagerank(node_ids, edges, iterations=50)
        self.assertAlmostEqual(sum(ranks.values()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
