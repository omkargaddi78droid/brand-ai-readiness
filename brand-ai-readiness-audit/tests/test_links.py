import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "shared"))

from links import LinkRef, extract_links, extract_outbound_links, is_internal_link


class ExtractLinksTests(unittest.TestCase):
    def test_resolves_relative_href_to_absolute(self):
        html = '<a href="/pricing">Pricing</a>'
        links = extract_links(html, "https://example.com/home")
        self.assertEqual(links, [LinkRef(url="https://example.com/pricing", anchor_text="Pricing")])

    def test_keeps_absolute_href_unchanged(self):
        html = '<a href="https://other.com/page">Other</a>'
        links = extract_links(html, "https://example.com/home")
        self.assertEqual(links[0].url, "https://other.com/page")

    def test_collapses_interior_whitespace_in_anchor_text(self):
        html = "<a href=\"/x\">  Learn\n   more  </a>"
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links[0].anchor_text, "Learn more")

    def test_image_only_link_has_empty_anchor_text(self):
        html = '<a href="/x"><img src="icon.png"></a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links[0].anchor_text, "")

    def test_drops_fragment_only_href(self):
        html = '<a href="#section-2">Jump</a>'
        links = extract_links(html, "https://example.com/page")
        self.assertEqual(links, [])

    def test_drops_mailto_href(self):
        html = '<a href="mailto:info@example.com">Email us</a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [])

    def test_drops_tel_href(self):
        html = '<a href="tel:+15551234567">Call</a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [])

    def test_drops_javascript_href(self):
        html = '<a href="javascript:void(0)">Click</a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [])

    def test_ignores_a_tag_with_no_href(self):
        html = '<a name="anchor-target">Target</a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [])

    def test_self_closing_a_tag_yields_empty_anchor_text(self):
        html = '<a href="/x" />'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [LinkRef(url="https://example.com/x", anchor_text="")])

    def test_unclosed_a_tag_at_end_of_document_still_captured(self):
        html = '<a href="/x">Trailing'
        links = extract_links(html, "https://example.com/")
        self.assertEqual(links, [LinkRef(url="https://example.com/x", anchor_text="Trailing")])

    def test_multiple_links_preserve_document_order(self):
        html = '<a href="/a">First</a><a href="/b">Second</a>'
        links = extract_links(html, "https://example.com/")
        self.assertEqual([link.url for link in links], ["https://example.com/a", "https://example.com/b"])

    def test_relative_href_with_query_string_resolved(self):
        html = '<a href="/search?q=widgets">Search</a>'
        links = extract_links(html, "https://example.com/home")
        self.assertEqual(links[0].url, "https://example.com/search?q=widgets")

    def test_no_links_on_page_returns_empty_list(self):
        html = "<html><body><p>No links here.</p></body></html>"
        self.assertEqual(extract_links(html, "https://example.com/"), [])


class ExtractOutboundLinksCompatTests(unittest.TestCase):
    def test_returns_urls_only(self):
        html = '<a href="/pricing">Pricing</a><a href="/about">About</a>'
        urls = extract_outbound_links(html, "https://example.com/")
        self.assertEqual(urls, ["https://example.com/pricing", "https://example.com/about"])

    def test_empty_html_returns_empty_list(self):
        self.assertEqual(extract_outbound_links("", "https://example.com/"), [])


class IsInternalLinkTests(unittest.TestCase):
    def test_same_registrable_domain_is_internal(self):
        self.assertTrue(is_internal_link("https://www.example.com/page", "example.com"))

    def test_different_domain_is_external(self):
        self.assertFalse(is_internal_link("https://other.com/page", "example.com"))

    def test_link_with_no_hostname_is_not_internal(self):
        self.assertFalse(is_internal_link("mailto:info@example.com", "example.com"))

    def test_subdomain_of_site_is_internal(self):
        self.assertTrue(is_internal_link("https://blog.example.com/post", "www.example.com"))


if __name__ == "__main__":
    unittest.main()
