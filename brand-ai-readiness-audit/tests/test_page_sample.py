"""Unit tests for shared/page_sample.py (INF-01/D1: template-stratified
sitemap sampling, cycle 23 Phase 1).

Pure functions throughout — no network. See the module's own docstring for
why template-stratified sampling replaces the orchestrator's former
interest-biased prose instruction.
"""

import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from page_sample import (  # noqa: E402
    parse_sitemap_index_locs,
    parse_sitemap_urls,
    sample_pages,
    sitemap_root_kind,
    template_key,
)


def _urlset(*locs: str) -> str:
    body = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


class ParseSitemapUrlsTests(unittest.TestCase):
    def test_extracts_every_loc(self):
        xml = _urlset("https://example.com/", "https://example.com/about")
        self.assertEqual(
            parse_sitemap_urls(xml), ["https://example.com/", "https://example.com/about"]
        )

    def test_a_sitemapindex_returns_empty_not_recursed(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        self.assertEqual(parse_sitemap_urls(xml), [])

    def test_malformed_xml_returns_empty_not_raises(self):
        self.assertEqual(parse_sitemap_urls("not xml at all <<<"), [])

    def test_empty_string_returns_empty(self):
        self.assertEqual(parse_sitemap_urls(""), [])

    def test_a_loc_with_no_text_is_skipped(self):
        xml = (
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc></loc></url><url><loc>https://example.com/real</loc></url></urlset>"
        )
        self.assertEqual(parse_sitemap_urls(xml), ["https://example.com/real"])


class SitemapRootKindTests(unittest.TestCase):
    def test_urlset_root(self):
        self.assertEqual(sitemap_root_kind(_urlset("https://example.com/")), "urlset")

    def test_sitemapindex_root(self):
        xml = (
            '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap></sitemapindex>"
        )
        self.assertEqual(sitemap_root_kind(xml), "sitemapindex")

    def test_malformed_xml_is_unknown(self):
        self.assertEqual(sitemap_root_kind("not xml at all <<<"), "unknown")

    def test_empty_string_is_unknown(self):
        self.assertEqual(sitemap_root_kind(""), "unknown")


class ParseSitemapIndexLocsTests(unittest.TestCase):
    def test_extracts_every_sub_sitemap_loc(self):
        xml = (
            '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap-products.xml</loc></sitemap>"
            "<sitemap><loc>https://example.com/sitemap-articles.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        self.assertEqual(
            parse_sitemap_index_locs(xml),
            ["https://example.com/sitemap-products.xml", "https://example.com/sitemap-articles.xml"],
        )

    def test_a_plain_urlset_returns_empty(self):
        self.assertEqual(parse_sitemap_index_locs(_urlset("https://example.com/")), [])

    def test_malformed_xml_returns_empty_not_raises(self):
        self.assertEqual(parse_sitemap_index_locs("not xml at all <<<"), [])


class TemplateKeyTests(unittest.TestCase):
    def test_two_blog_posts_with_numeric_slugs_share_a_template(self):
        self.assertEqual(
            template_key("/blog/2024/10-b2b-seo-tips"), template_key("/blog/2023/5-marketing-lessons")
        )

    def test_two_purely_alphabetic_slugs_stay_distinct_a_known_limitation(self):
        """No digit, no UUID, under the long-slug threshold: string shape
        alone cannot distinguish a real page-type segment ("get-started")
        from a per-instance slug ("my-post-title") without the positional
        context (e.g. "follows a year segment") this function does not use.
        A documented limitation, not a silently wrong claim of clustering —
        see the module's own docstring."""
        self.assertNotEqual(template_key("/blog/my-post-title"), template_key("/blog/another-post"))

    def test_short_structural_segments_stay_distinct(self):
        self.assertNotEqual(template_key("/pricing"), template_key("/about"))

    def test_a_numeric_id_segment_becomes_a_wildcard(self):
        self.assertEqual(template_key("/product/12345"), "/product/*")

    def test_a_uuid_segment_becomes_a_wildcard(self):
        self.assertEqual(template_key("/orders/550e8400-e29b-41d4-a716-446655440000"), "/orders/*")

    def test_case_is_normalized(self):
        self.assertEqual(template_key("/Products"), template_key("/products"))

    def test_root_path_is_its_own_template(self):
        self.assertEqual(template_key("/"), "/")

    def test_a_long_opaque_slug_becomes_a_wildcard(self):
        self.assertEqual(
            template_key("/docs/" + "a" * 30),
            "/docs/*",
        )


class SamplePagesTests(unittest.TestCase):
    def test_empty_input_returns_an_empty_sample(self):
        result = sample_pages([])
        self.assertEqual(result["total_urls"], 0)
        self.assertEqual(result["sample_urls"], [])

    def test_duplicate_urls_are_deduplicated(self):
        urls = ["https://example.com/", "https://example.com/"]
        result = sample_pages(urls, budget=10)
        self.assertEqual(result["total_urls"], 1)

    def test_every_cluster_gets_at_least_one_slot_when_budget_allows(self):
        urls = (
            [f"https://example.com/blog/post-{i}" for i in range(20)]
            + [f"https://example.com/product/{i}" for i in range(20)]
            + ["https://example.com/about"]
        )
        result = sample_pages(urls, budget=10)
        template_keys_sampled = {template_key(urlsplit(u).path) for u in result["sample_urls"]}
        self.assertEqual(len(template_keys_sampled), 3)

    def test_larger_clusters_get_proportionally_more_slots(self):
        urls = [f"https://example.com/blog/post-{i}" for i in range(90)] + [
            f"https://example.com/product/{i}" for i in range(10)
        ]
        result = sample_pages(urls, budget=20)
        by_key = {s["template_key"]: s["allocated"] for s in result["strata"]}
        self.assertGreater(by_key["/blog/*"], by_key["/product/*"])

    def test_the_sample_never_exceeds_cluster_size(self):
        urls = ["https://example.com/about", "https://example.com/contact"] + [
            f"https://example.com/blog/post-{i}" for i in range(3)
        ]
        result = sample_pages(urls, budget=25)
        for stratum in result["strata"]:
            self.assertLessEqual(stratum["allocated"], stratum["cluster_size"])

    def test_more_clusters_than_budget_still_returns_a_sample_for_the_largest_ones(self):
        urls = [f"https://example.com/page-{i}" for i in range(50)]  # 50 distinct single-node templates
        result = sample_pages(urls, budget=10)
        self.assertEqual(len(result["sample_urls"]), 10)

    def test_homepage_is_force_included(self):
        urls = ["https://example.com/"] + [f"https://example.com/blog/post-{i}" for i in range(30)]
        result = sample_pages(urls, budget=5)
        self.assertIn("https://example.com/", result["sample_urls"])

    def test_a_process_page_is_force_included_even_outside_the_proportional_pick(self):
        # 20 alphabetically-earlier singleton templates outrank "/checkout"'s
        # own singleton cluster once clusters outnumber budget, per
        # _allocate()'s tie-break (size desc, then key asc) — checkout only
        # survives via forced inclusion.
        urls = [f"https://example.com/aaa{i:02d}" for i in range(20)] + ["https://example.com/checkout"]
        result = sample_pages(urls, budget=10)
        self.assertIn("https://example.com/checkout", result["sample_urls"])
        self.assertIn("https://example.com/checkout", result["forced_included"])

    def test_a_process_page_already_in_the_proportional_pick_is_not_double_counted(self):
        urls = ["https://example.com/pricing"]
        result = sample_pages(urls, budget=25)
        self.assertEqual(result["sample_urls"].count("https://example.com/pricing"), 1)
        self.assertEqual(result["forced_included"], [])

    def test_sampling_is_deterministic_across_repeated_calls(self):
        urls = [f"https://example.com/blog/post-{i}" for i in range(17)]
        first = sample_pages(urls, budget=5)
        second = sample_pages(urls, budget=5)
        self.assertEqual(first, second)

    def test_budget_larger_than_total_urls_returns_everything(self):
        urls = ["https://example.com/a", "https://example.com/b"]
        result = sample_pages(urls, budget=25)
        self.assertEqual(set(result["sample_urls"]), set(urls))


if __name__ == "__main__":
    unittest.main()
