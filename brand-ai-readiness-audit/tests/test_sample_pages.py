"""Unit tests for skills/audit-orchestrator/scripts/sample_pages.py's
`collect_sitemap_urls` — the sitemap-index recursion fix.

Before this fix, a `<sitemapindex>` root (what WordPress, Shopify, and
Next.js all generate by default) made the whole sampler return zero pages,
silently disabling every multi-page check on most real sites. A follow-up
fix (live-tested against pw.live) then found that a fixed one-level-only
recursion, gated on root tag name alone, still returns zero real pages
against a site whose sitemap nests deeper or wraps further sitemap files in
a `<urlset>` instead of a `<sitemapindex>`. These tests verify the
budget-bounded, tag-and-shape-aware walk that replaced both, entirely
offline via a monkeypatched `fetch_text` (matching this project's
no-network-in-tests guarantee).
"""

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sample_pages_cli = _load("sample_pages", "skills/audit-orchestrator/scripts/sample_pages.py")


def _urlset(*locs: str) -> str:
    body = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


def _sitemapindex(*sub_locs: str) -> str:
    body = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in sub_locs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</sitemapindex>'
    )


class CollectSitemapUrlsTests(unittest.TestCase):
    def setUp(self):
        self._orig_fetch_text = sample_pages_cli.fetch_text
        self.addCleanup(setattr, sample_pages_cli, "fetch_text", self._orig_fetch_text)

    def test_a_plain_urlset_is_returned_unchanged(self):
        xml = _urlset("https://example.com/", "https://example.com/about")
        self.assertEqual(
            sample_pages_cli.collect_sitemap_urls(xml),
            ["https://example.com/", "https://example.com/about"],
        )

    def test_a_sitemapindex_is_recursed_into_its_sub_sitemaps(self):
        index_xml = _sitemapindex(
            "https://example.com/sitemap-products.xml",
            "https://example.com/sitemap-articles.xml",
        )
        sub_sitemaps = {
            "https://example.com/sitemap-products.xml": _urlset(
                "https://example.com/products/a", "https://example.com/products/b"
            ),
            "https://example.com/sitemap-articles.xml": _urlset("https://example.com/blog/post-1"),
        }

        def fake_fetch_text(url):
            return sub_sitemaps[url], "present"

        sample_pages_cli.fetch_text = fake_fetch_text

        urls = sample_pages_cli.collect_sitemap_urls(index_xml)
        self.assertEqual(
            sorted(urls),
            sorted(
                [
                    "https://example.com/products/a",
                    "https://example.com/products/b",
                    "https://example.com/blog/post-1",
                ]
            ),
        )

    def test_a_sub_sitemap_that_fails_to_fetch_is_skipped_not_fatal(self):
        index_xml = _sitemapindex(
            "https://example.com/sitemap-ok.xml", "https://example.com/sitemap-broken.xml"
        )

        def fake_fetch_text(url):
            if url.endswith("sitemap-ok.xml"):
                return _urlset("https://example.com/ok-page"), "present"
            return "site returned HTTP 403", "unavailable"

        sample_pages_cli.fetch_text = fake_fetch_text

        self.assertEqual(
            sample_pages_cli.collect_sitemap_urls(index_xml), ["https://example.com/ok-page"]
        )

    def test_a_multi_level_chain_of_nested_indexes_is_chased_to_real_pages(self):
        # pw.live's live sitemap tree is this shape: sitemapindex ->
        # sitemapindex -> urlset. A one-level-only recursion returns zero
        # pages against it; the fix must not stop until it hits a urlset of
        # real (non-.xml) page URLs.
        index_xml = _sitemapindex("https://example.com/sitemap-nested-index.xml")
        chain = {
            "https://example.com/sitemap-nested-index.xml": _sitemapindex(
                "https://example.com/sitemap-leaf.xml"
            ),
            "https://example.com/sitemap-leaf.xml": _urlset("https://example.com/real-page"),
        }

        def fake_fetch_text(url):
            return chain[url], "present"

        sample_pages_cli.fetch_text = fake_fetch_text

        self.assertEqual(
            sample_pages_cli.collect_sitemap_urls(index_xml), ["https://example.com/real-page"]
        )

    def test_a_urlset_whose_locs_are_further_sitemap_files_is_recursed_into(self):
        # pw.live's own middle sitemap level: tagged <urlset>, but every
        # <loc> inside it is a further per-category sitemap.xml file, not a
        # page. A root-tag-only check misreads these as pages.
        index_xml = _sitemapindex("https://example.com/sitemap-1.xml")
        chain = {
            "https://example.com/sitemap-1.xml": _urlset(
                "https://example.com/category-a/sitemap.xml",
                "https://example.com/category-b/sitemap.xml",
            ),
            "https://example.com/category-a/sitemap.xml": _urlset("https://example.com/a/page-1"),
            "https://example.com/category-b/sitemap.xml": _urlset("https://example.com/b/page-1"),
        }

        def fake_fetch_text(url):
            return chain[url], "present"

        sample_pages_cli.fetch_text = fake_fetch_text

        self.assertEqual(
            sorted(sample_pages_cli.collect_sitemap_urls(index_xml)),
            sorted(["https://example.com/a/page-1", "https://example.com/b/page-1"]),
        )

    def test_a_cyclic_sitemap_graph_terminates_instead_of_looping(self):
        index_xml = _sitemapindex("https://example.com/sitemap-a.xml")
        chain = {
            "https://example.com/sitemap-a.xml": _sitemapindex("https://example.com/sitemap-b.xml"),
            "https://example.com/sitemap-b.xml": _sitemapindex("https://example.com/sitemap-a.xml"),
        }
        calls = []

        def fake_fetch_text(url):
            calls.append(url)
            return chain[url], "present"

        sample_pages_cli.fetch_text = fake_fetch_text

        self.assertEqual(sample_pages_cli.collect_sitemap_urls(index_xml), [])
        # each distinct sub-sitemap URL is fetched at most once, so a cycle
        # terminates on the dedup set long before the fetch budget would
        # have to catch it
        self.assertEqual(calls, ["https://example.com/sitemap-a.xml", "https://example.com/sitemap-b.xml"])

    def test_sub_sitemap_fetch_count_is_bounded(self):
        many_sub_locs = [f"https://example.com/sitemap-{i}.xml" for i in range(50)]
        index_xml = _sitemapindex(*many_sub_locs)

        calls = []

        def fake_fetch_text(url):
            calls.append(url)
            return _urlset(f"https://example.com/page-from-{url}"), "present"

        sample_pages_cli.fetch_text = fake_fetch_text

        sample_pages_cli.collect_sitemap_urls(index_xml)
        self.assertEqual(len(calls), sample_pages_cli._MAX_SUB_SITEMAPS)

    def test_malformed_xml_returns_empty_not_raises(self):
        self.assertEqual(sample_pages_cli.collect_sitemap_urls("not xml at all <<<"), [])

    def test_one_oversized_leaf_sitemap_does_not_starve_its_siblings(self):
        # live-tested against cleartrip.com: a sitemapindex listing separate
        # flight/hotel/train sitemaps, whose /trains/* leaf alone lists 4993
        # pages. The depth-first walk (stack.pop(), so whichever sub-sitemap
        # is listed LAST is visited first) used to resolve that one huge
        # leaf to the global cap and stop, returning zero pages from any
        # sibling vertical — defeating template-stratified sampling entirely.
        huge_leaf_locs = [f"https://example.com/trains/route-{i}" for i in range(4993)]
        small_leaf_locs = ["https://example.com/flights/a", "https://example.com/flights/b"]
        index_xml = _sitemapindex(
            "https://example.com/sitemap/small-flights.xml",
            "https://example.com/sitemap/huge-trains.xml",
        )

        def fake_fetch_text(url):
            if url.endswith("huge-trains.xml"):
                return _urlset(*huge_leaf_locs), "present"
            if url.endswith("small-flights.xml"):
                return _urlset(*small_leaf_locs), "present"
            return "not found", "unavailable"

        sample_pages_cli.fetch_text = fake_fetch_text

        pages = sample_pages_cli.collect_sitemap_urls(index_xml)
        self.assertIn("https://example.com/flights/a", pages)
        self.assertIn("https://example.com/flights/b", pages)
        self.assertTrue(any(p.startswith("https://example.com/trains/") for p in pages))
        self.assertLessEqual(
            sum(1 for p in pages if p.startswith("https://example.com/trains/")),
            sample_pages_cli._MAX_URLS_PER_LEAF_SITEMAP,
        )


class ProbeForcedPagesTests(unittest.TestCase):
    """`sample_pages()`'s own forced-inclusion only fires for a path already
    present in the sitemap's URL list — `probe_forced_pages` covers the
    common real-world case where the homepage (or another process page)
    simply isn't listed there at all, live-tested against cleartrip.com's
    ~4900-URL sitemap, which never mentions "/" itself."""

    def setUp(self):
        self._orig_fetch_page_html = sample_pages_cli.fetch_page_html
        self._orig_fetch_text = sample_pages_cli.fetch_text
        self.addCleanup(setattr, sample_pages_cli, "fetch_page_html", self._orig_fetch_page_html)
        self.addCleanup(setattr, sample_pages_cli, "fetch_text", self._orig_fetch_text)

    def test_homepage_absent_from_sitemap_is_still_probed_and_found(self):
        def fake_fetch_page_html(url):
            if url == "https://example.com":
                return "<html>home</html>", "present"
            return "not found", "unavailable"

        sample_pages_cli.fetch_page_html = fake_fetch_page_html

        found = sample_pages_cli.probe_forced_pages(
            "https://example.com", ["https://example.com/trains/route-1"]
        )
        self.assertEqual(found, ["https://example.com"])

    def test_a_path_already_in_the_sample_is_not_re_probed(self):
        calls = []

        def fake_fetch_page_html(url):
            calls.append(url)
            return "<html>x</html>", "present"

        sample_pages_cli.fetch_page_html = fake_fetch_page_html

        sample_pages_cli.probe_forced_pages(
            "https://example.com", ["https://example.com/pricing"]
        )
        self.assertNotIn("https://example.com/pricing", calls)

    def test_a_forced_page_that_404s_is_not_included(self):
        sample_pages_cli.fetch_page_html = lambda url: ("not found", "unavailable")

        found = sample_pages_cli.probe_forced_pages("https://example.com", [])
        self.assertEqual(found, [])

    def test_end_to_end_through_main_adds_homepage_missing_from_sitemap(self):
        sitemap_xml = _urlset("https://example.com/trains/route-1")

        def fake_fetch_text(url):
            return sitemap_xml, "present"

        def fake_fetch_page_html(url):
            if url == "https://example.com":
                return "<html>home</html>", "present"
            return "not found", "unavailable"

        sample_pages_cli.fetch_text = fake_fetch_text
        sample_pages_cli.fetch_page_html = fake_fetch_page_html

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = sample_pages_cli.main(["--url", "https://example.com"])

        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertIn("https://example.com", result["sample_urls"])
        self.assertIn("https://example.com", result["forced_included"])


class FallbackNavFooterUrlsTests(unittest.TestCase):
    """The zero-sitemap fallback: sample_pages.py's own homepage-fetch +
    nav/footer-link-extraction wiring (extraction itself is tested in
    tests/test_html_extract.py)."""

    def setUp(self):
        self._orig_fetch_page_html = sample_pages_cli.fetch_page_html
        self.addCleanup(setattr, sample_pages_cli, "fetch_page_html", self._orig_fetch_page_html)

    def test_homepage_nav_links_are_returned(self):
        html = '<nav><a href="/about">About</a><a href="/pricing">Pricing</a></nav>'
        sample_pages_cli.fetch_page_html = lambda url: (html, "present")

        self.assertEqual(
            sample_pages_cli.fallback_nav_footer_urls("https://example.com"),
            ["https://example.com/about", "https://example.com/pricing"],
        )

    def test_homepage_fetch_failure_returns_empty_not_fatal(self):
        sample_pages_cli.fetch_page_html = lambda url: ("site returned HTTP 403", "unavailable")

        self.assertEqual(sample_pages_cli.fallback_nav_footer_urls("https://example.com"), [])


class MainCliFallbackIntegrationTests(unittest.TestCase):
    """End-to-end through main(): a 403 on /sitemap.xml no longer means zero
    sampled pages when the homepage's own nav/footer has links."""

    def setUp(self):
        self._orig_fetch_text = sample_pages_cli.fetch_text
        self._orig_fetch_page_html = sample_pages_cli.fetch_page_html
        self.addCleanup(setattr, sample_pages_cli, "fetch_text", self._orig_fetch_text)
        self.addCleanup(setattr, sample_pages_cli, "fetch_page_html", self._orig_fetch_page_html)

    def test_blocked_sitemap_falls_back_to_nav_footer_links(self):
        sample_pages_cli.fetch_text = lambda url: ("site returned HTTP 403", "unavailable")
        sample_pages_cli.fetch_page_html = lambda url: (
            '<nav><a href="/about">About</a><a href="/pricing">Pricing</a></nav>',
            "present",
        )

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = sample_pages_cli.main(["--url", "https://example.com"])

        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["total_urls"], 2)
        self.assertIn("https://example.com/about", result["sample_urls"])
        self.assertIn("https://example.com/pricing", result["sample_urls"])

    def test_blocked_sitemap_and_unreachable_homepage_yields_empty_result(self):
        sample_pages_cli.fetch_text = lambda url: ("site returned HTTP 403", "unavailable")
        sample_pages_cli.fetch_page_html = lambda url: ("connection refused", "unavailable")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = sample_pages_cli.main(["--url", "https://example.com"])

        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["total_urls"], 0)
        self.assertEqual(result["sample_urls"], [])

    def test_output_has_no_judgement_urls_key(self):
        """judgement_urls/--judgement-cap were the old page-based judgement
        cap, replaced by select_judgement_items.py's per-skill,
        severity-ranked cap. Locks in the removal."""
        sample_pages_cli.fetch_text = lambda url: ("site returned HTTP 403", "unavailable")
        links = "".join(f'<a href="/page-{i}">Page {i}</a>' for i in range(25))
        sample_pages_cli.fetch_page_html = lambda url: (f"<nav>{links}</nav>", "present")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = sample_pages_cli.main(["--url", "https://example.com"])

        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertNotIn("judgement_urls", result)

        with self.assertRaises(SystemExit):
            sample_pages_cli.main(["--url", "https://example.com", "--judgement-cap", "5"])


if __name__ == "__main__":
    unittest.main()
