"""Unit tests for shared/page_fetch.py (INF-02/INF-04 consolidation).

tests/test_gzip_decoding.py already covers decode_content_encoding and
fetch_page_html end-to-end against a real gzip-serving HTTP server, across
every skill module that now imports this module's functions. This file
covers page_fetch's own surface directly: the SSRF guard, the not_html/
unavailable status paths, and the PageBundle cache.
"""

import gzip
import http.server
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

import page_fetch  # noqa: E402

SAMPLE_HTML = "<html><body><h1>Example Corp</h1><p>Hello, world.</p></body></html>"


class IsPublicHostTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(page_fetch.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(page_fetch.is_public_host("10.0.0.5"))

    def test_an_unresolvable_host_is_refused(self):
        self.assertFalse(page_fetch.is_public_host("this-host-does-not-exist.invalid"))


class FetchPageHtmlSsrfTests(unittest.TestCase):
    def test_a_loopback_url_is_refused_without_a_network_call(self):
        html, status = page_fetch.fetch_page_html("http://127.0.0.1:9/")
        self.assertEqual(status, "unavailable")
        self.assertIn("does not resolve to a public address", html)

    def test_a_url_with_no_hostname_is_refused(self):
        html, status = page_fetch.fetch_page_html("not-a-url")
        self.assertEqual(status, "unavailable")


class _HtmlHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = SAMPLE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _NotHtmlHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _LocalServer:
    def __init__(self, handler):
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class FetchPageHtmlEndToEndTests(unittest.TestCase):
    def test_a_non_html_content_type_is_reported_as_not_html(self):
        with _LocalServer(_NotHtmlHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "not_html")
        self.assertIn("not HTML/text", html)

    def test_a_normal_html_response_is_returned_present(self):
        with _LocalServer(_HtmlHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)


class PageBundleCacheTests(unittest.TestCase):
    def setUp(self):
        page_fetch.clear_cache()

    def tearDown(self):
        page_fetch.clear_cache()

    def test_a_second_fetch_of_the_same_url_is_served_from_cache(self):
        calls = []
        real_urlopen = page_fetch.urllib.request.urlopen

        def counting_urlopen(*args, **kwargs):
            calls.append(1)
            return real_urlopen(*args, **kwargs)

        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch.urllib.request, "urlopen", side_effect=counting_urlopen):
            first = page_fetch.fetch_page(server.url)
            second = page_fetch.fetch_page(server.url)

        self.assertEqual(len(calls), 1)
        self.assertEqual(first.status, "present")
        self.assertEqual(first, second)

    def test_use_cache_false_bypasses_the_cache(self):
        with _LocalServer(_HtmlHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            page_fetch.fetch_page(server.url)
            bundle = page_fetch.fetch_page(server.url, use_cache=False)
        self.assertEqual(bundle.status, "present")

    def test_a_failed_fetch_is_not_cached(self):
        bundle = page_fetch.fetch_page("http://127.0.0.1:1/")
        self.assertEqual(bundle.status, "unavailable")
        self.assertNotIn("http://127.0.0.1:1/", page_fetch._page_cache)

    def test_bundle_carries_the_final_url_and_headers(self):
        with _LocalServer(_HtmlHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            bundle = page_fetch.fetch_page(server.url)
        self.assertEqual(bundle.final_url, server.url)
        self.assertIn("Content-Type", bundle.headers)


class DecodeContentEncodingTests(unittest.TestCase):
    def test_gzip_round_trips(self):
        compressed = gzip.compress(SAMPLE_HTML.encode("utf-8"))
        result = page_fetch.decode_content_encoding(compressed, "gzip")
        self.assertEqual(result.decode("utf-8"), SAMPLE_HTML)

    def test_an_unsupported_encoding_raises(self):
        with self.assertRaises(ValueError):
            page_fetch.decode_content_encoding(b"whatever", "br")


if __name__ == "__main__":
    unittest.main()
