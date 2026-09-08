"""Unit tests for skills/audit-orchestrator/scripts/sample_pages.py's
`collect_sitemap_urls` — the sitemap-index recursion fix.

Before this fix, a `<sitemapindex>` root (what WordPress, Shopify, and
Next.js all generate by default) made the whole sampler return zero pages,
silently disabling every multi-page check on most real sites. These tests
verify the fetch-and-recurse-one-level replacement, entirely offline via a
monkeypatched `fetch_text` (matching this project's no-network-in-tests
guarantee).
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

    def test_a_sub_sitemap_that_is_itself_an_index_is_not_chased_further(self):
        index_xml = _sitemapindex("https://example.com/sitemap-nested-index.xml")

        def fake_fetch_text(url):
            return _sitemapindex("https://example.com/sitemap-should-not-be-fetched.xml"), "present"

        calls = []
        real_fake = fake_fetch_text

        def counting_fetch_text(url):
            calls.append(url)
            return real_fake(url)

        sample_pages_cli.fetch_text = counting_fetch_text

        self.assertEqual(sample_pages_cli.collect_sitemap_urls(index_xml), [])
        self.assertEqual(calls, ["https://example.com/sitemap-nested-index.xml"])

    def test_sub_sitemap_fetch_count_is_bounded(self):
        many_sub_locs = [f"https://example.com/sitemap-{i}.xml" for i in range(20)]
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


if __name__ == "__main__":
    unittest.main()
