"""Contract tests for shared/jsonld_graph.py."""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from jsonld_graph import (  # noqa: E402
    Reference,
    build_id_index,
    classify_target,
    flatten,
    iter_references,
)


class FlattenTests(unittest.TestCase):
    def test_single_top_level_object(self):
        block = json.dumps({"@type": "Organization", "name": "Acme"})
        nodes = flatten([block])
        self.assertEqual(nodes, [{"@type": "Organization", "name": "Acme"}])

    def test_graph_array(self):
        block = json.dumps(
            {
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "Organization", "name": "Acme"},
                    {"@type": "WebSite", "name": "Acme Site"},
                ],
            }
        )
        nodes = flatten([block])
        self.assertEqual(len(nodes), 2)
        self.assertEqual([n["@type"] for n in nodes], ["Organization", "WebSite"])

    def test_top_level_array_of_objects(self):
        block = json.dumps(
            [
                {"@type": "Organization", "name": "Acme"},
                {"@type": "Product", "name": "Widget"},
            ]
        )
        nodes = flatten([block])
        self.assertEqual(len(nodes), 2)
        self.assertEqual([n["@type"] for n in nodes], ["Organization", "Product"])

    def test_block_that_fails_to_parse_is_skipped_not_raised(self):
        bad_block = "{not valid json"
        good_block = json.dumps({"@type": "Organization", "name": "Acme"})
        nodes = flatten([bad_block, good_block])
        self.assertEqual(nodes, [{"@type": "Organization", "name": "Acme"}])

    def test_blank_block_is_skipped(self):
        nodes = flatten(["   ", "\n\t"])
        self.assertEqual(nodes, [])

    def test_nested_graph_flattens_via_recursion(self):
        # Matches the existing three _flatten_json_ld implementations:
        # recursion happens through both list and dict branches, so a
        # @graph array whose elements are themselves arrays or @graph
        # dicts is fully flattened.
        block = json.dumps(
            {
                "@graph": [
                    {
                        "@graph": [
                            {"@type": "Organization", "name": "Inner Org"},
                        ]
                    },
                    {"@type": "Product", "name": "Widget"},
                ]
            }
        )
        nodes = flatten([block])
        self.assertEqual(len(nodes), 2)
        self.assertEqual(
            sorted(n["@type"] for n in nodes), ["Organization", "Product"]
        )

    def test_no_blocks_returns_empty_list(self):
        self.assertEqual(flatten([]), [])

    def test_scalar_json_value_flattens_to_nothing(self):
        # A block that parses successfully but isn't a list/dict (e.g. a
        # bare JSON string or number) contributes no nodes.
        nodes = flatten([json.dumps("just a string"), json.dumps(42)])
        self.assertEqual(nodes, [])


class BuildIdIndexTests(unittest.TestCase):
    def test_nodes_with_id_are_indexed(self):
        nodes = [{"@id": "https://site.com/#org", "name": "Acme"}]
        index = build_id_index(nodes)
        self.assertEqual(index, {"https://site.com/#org": nodes[0]})

    def test_nodes_without_id_are_not_indexed(self):
        nodes = [{"name": "Acme"}]
        index = build_id_index(nodes)
        self.assertEqual(index, {})

    def test_mixed_nodes_only_id_bearing_ones_indexed(self):
        with_id = {"@id": "#a", "name": "A"}
        without_id = {"name": "B"}
        index = build_id_index([with_id, without_id])
        self.assertEqual(index, {"#a": with_id})

    def test_duplicate_id_last_one_wins(self):
        first = {"@id": "#dup", "name": "First"}
        second = {"@id": "#dup", "name": "Second"}
        index = build_id_index([first, second])
        self.assertEqual(index, {"#dup": second})
        self.assertIs(index["#dup"], second)


class IterReferencesTests(unittest.TestCase):
    def test_id_dict_reference(self):
        node = {"@type": "Product", "@id": "#p1", "brand": {"@id": "#acme"}}
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.source_node_id, "#p1")
        self.assertEqual(ref.property_path, "Product[0].brand.@id")
        self.assertEqual(ref.target_id, "#acme")
        self.assertFalse(ref.is_bare_uri)

    def test_bare_uri_reference_in_entity_valued_property(self):
        node = {"@type": "Product", "@id": "#p1", "brand": "https://acme.example/#org"}
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.property_path, "Product[0].brand")
        self.assertEqual(ref.target_id, "https://acme.example/#org")
        self.assertTrue(ref.is_bare_uri)

    def test_bare_uri_reference_via_fragment_form(self):
        node = {"@type": "Product", "@id": "#p1", "publisher": "#acme"}
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 1)
        ref = refs[0]
        self.assertEqual(ref.property_path, "Product[0].publisher")
        self.assertEqual(ref.target_id, "#acme")
        self.assertTrue(ref.is_bare_uri)

    def test_bare_uri_in_non_entity_valued_property_is_not_a_reference(self):
        node = {"@type": "Product", "@id": "#p1", "sameAs": "https://example.com/other"}
        refs = list(iter_references([node]))
        self.assertEqual(refs, [])

    def test_array_valued_property_yields_one_reference_per_element_with_indices(self):
        node = {
            "@type": "Article",
            "@id": "#a1",
            "author": [{"@id": "#alice"}, {"@id": "#bob"}],
        }
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0].property_path, "Article[0].author[0].@id")
        self.assertEqual(refs[0].target_id, "#alice")
        self.assertEqual(refs[1].property_path, "Article[0].author[1].@id")
        self.assertEqual(refs[1].target_id, "#bob")

    def test_missing_type_produces_unknown_in_path(self):
        node = {"@id": "#x", "brand": {"@id": "#acme"}}
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].property_path, "Unknown[0].brand.@id")

    def test_missing_source_id_yields_reference_with_none_source(self):
        node = {"@type": "Product", "brand": {"@id": "#acme"}}
        refs = list(iter_references([node]))
        self.assertEqual(len(refs), 1)
        self.assertIsNone(refs[0].source_node_id)

    def test_id_dict_with_extra_keys_is_not_a_bare_id_reference(self):
        # {"@id": ..., "name": ...} has more than just "@id", so it does not
        # qualify under case (a); it's an embedded node, not a reference.
        node = {"@type": "Product", "@id": "#p1", "brand": {"@id": "#acme", "name": "Acme"}}
        refs = list(iter_references([node]))
        self.assertEqual(refs, [])

    def test_non_reference_scalar_values_are_ignored(self):
        node = {"@type": "Product", "@id": "#p1", "name": "Widget", "price": 9.99}
        refs = list(iter_references([node]))
        self.assertEqual(refs, [])

    def test_multiple_nodes_index_by_position_in_nodes_list(self):
        nodes = [
            {"@type": "Organization", "@id": "#org"},
            {"@type": "Product", "@id": "#p1", "brand": {"@id": "#org"}},
        ]
        refs = list(iter_references(nodes))
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].property_path, "Product[1].brand.@id")

    def test_reference_is_a_dataclass_instance(self):
        node = {"@type": "Product", "@id": "#p1", "brand": {"@id": "#acme"}}
        ref = next(iter_references([node]))
        self.assertIsInstance(ref, Reference)


class ClassifyTargetTests(unittest.TestCase):
    PAGE_URL = "https://example.com/products/widget"

    def test_resolved_fragment(self):
        index = {"#org": {"@id": "#org"}}
        self.assertEqual(classify_target("#org", index, self.PAGE_URL), "resolved")

    def test_resolved_fragment_matches_index_key_ending_in_same_fragment(self):
        index = {"https://example.com/products/widget#org": {"@id": "..."}}
        self.assertEqual(classify_target("#org", index, self.PAGE_URL), "resolved")

    def test_dangling_fragment(self):
        index = {"#other": {"@id": "#other"}}
        self.assertEqual(classify_target("#org", index, self.PAGE_URL), "dangling_fragment")

    def test_dangling_fragment_with_empty_index(self):
        self.assertEqual(classify_target("#missing", {}, self.PAGE_URL), "dangling_fragment")

    def test_same_origin_dangling_absolute_url(self):
        index = {}
        target = "https://example.com/other-page#thing"
        self.assertEqual(classify_target(target, index, self.PAGE_URL), "dangling_same_origin")

    def test_same_origin_resolved_absolute_url(self):
        target = "https://example.com/other-page#thing"
        index = {target: {"@id": target}}
        self.assertEqual(classify_target(target, index, self.PAGE_URL), "resolved")

    def test_external_url(self):
        target = "https://other-domain.com/page"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "external")

    def test_schema_org_vocabulary_uri(self):
        target = "https://schema.org/Organization"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "vocabulary")

    def test_schema_org_vocabulary_uri_http_scheme(self):
        target = "http://schema.org/Product"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "vocabulary")

    def test_wikidata_vocabulary_uri(self):
        target = "https://www.wikidata.org/wiki/Q312"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "vocabulary")

    def test_w3_org_vocabulary_uri(self):
        target = "https://www.w3.org/ns/prov"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "vocabulary")

    def test_purl_org_vocabulary_uri(self):
        target = "http://purl.org/dc/terms/creator"
        self.assertEqual(classify_target(target, {}, self.PAGE_URL), "vocabulary")

    def test_vocabulary_takes_precedence_when_also_indexed(self):
        # Even if a vocabulary URI happens to be in the index (unusual, but
        # the first branch checks exact match first), resolved wins per the
        # documented branch order.
        target = "https://schema.org/Organization"
        index = {target: {"@id": target}}
        self.assertEqual(classify_target(target, index, self.PAGE_URL), "resolved")


if __name__ == "__main__":
    unittest.main()
