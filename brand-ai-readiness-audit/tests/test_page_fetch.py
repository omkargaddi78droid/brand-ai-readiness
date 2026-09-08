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
import urllib.error
import urllib.parse
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
        with _LocalServer(_NotHtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "not_html")
        self.assertIn("not HTML/text", html)

    def test_a_normal_html_response_is_returned_present(self):
        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)


class _XmlHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b"<?xml version='1.0'?><urlset></urlset>"
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchTextTests(unittest.TestCase):
    def test_a_loopback_url_is_refused_without_a_network_call(self):
        text, status = page_fetch.fetch_text("http://127.0.0.1:9/")
        self.assertEqual(status, "unavailable")
        self.assertIn("does not resolve to a public address", text)

    def test_application_xml_content_type_is_accepted_unlike_fetch_page_html(self):
        with _LocalServer(_XmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            text, status = page_fetch.fetch_text(server.url)
        self.assertEqual(status, "present")
        self.assertIn("<urlset>", text)

    def test_a_normal_html_response_is_still_returned_present(self):
        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            text, status = page_fetch.fetch_text(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", text)


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
                patch.object(page_fetch, "robots_allows_fetch", return_value=True), \
                patch.object(page_fetch.urllib.request, "urlopen", side_effect=counting_urlopen):
            first = page_fetch.fetch_page(server.url)
            calls_after_first = len(calls)
            second = page_fetch.fetch_page(server.url)

        self.assertEqual(len(calls), calls_after_first, "the second fetch must not make any new HTTP calls")
        self.assertEqual(first.status, "present")
        self.assertEqual(first, second)

    def test_use_cache_false_bypasses_the_cache(self):
        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            page_fetch.fetch_page(server.url)
            bundle = page_fetch.fetch_page(server.url, use_cache=False)
        self.assertEqual(bundle.status, "present")

    def test_a_failed_fetch_is_not_cached(self):
        bundle = page_fetch.fetch_page("http://127.0.0.1:1/")
        self.assertEqual(bundle.status, "unavailable")
        self.assertNotIn("http://127.0.0.1:1/", page_fetch._page_cache)

    def test_bundle_carries_the_final_url_and_headers(self):
        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            bundle = page_fetch.fetch_page(server.url)
        self.assertEqual(bundle.final_url, server.url)
        self.assertIn("Content-Type", bundle.headers)


class _RobotsHandler(http.server.BaseHTTPRequestHandler):
    """Serves a fixed robots.txt body at /robots.txt and HTML everywhere
    else, so the disallow test proves the gate actually reads the response
    rather than assuming the shape of the URL."""

    body = b"User-agent: *\nDisallow: /blocked\n"

    def do_GET(self):  # noqa: N802
        if self.path == "/robots.txt":
            body = self.body
            content_type = "text/plain"
        else:
            body = SAMPLE_HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class RobotsGateTests(unittest.TestCase):
    def setUp(self):
        page_fetch.clear_cache()

    def tearDown(self):
        page_fetch.clear_cache()

    def test_robots_txt_unreachable_defaults_to_allow(self):
        # No server is listening on this port at all, so the robots.txt
        # lookup itself fails — RFC 9309's convention is allow-all here.
        self.assertTrue(page_fetch.robots_allows_fetch("http://127.0.0.1:1/somewhere"))

    def test_a_disallowed_path_is_refused_by_fetch_page_html(self):
        with _LocalServer(_RobotsHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            blocked_url = server.url.rstrip("/") + "/blocked/page"
            html, status = page_fetch.fetch_page_html(blocked_url)
        self.assertEqual(status, "unavailable")
        self.assertIn("robots.txt", html)

    def test_an_allowed_path_still_fetches_normally(self):
        with _LocalServer(_RobotsHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            allowed_url = server.url.rstrip("/") + "/allowed/page"
            html, status = page_fetch.fetch_page_html(allowed_url)
        self.assertEqual(status, "present")

    def test_the_robots_decision_is_cached_per_host(self):
        with _LocalServer(_RobotsHandler) as server, patch.object(page_fetch, "is_public_host", return_value=True):
            netloc = urllib.parse.urlparse(server.url).netloc
            page_fetch.robots_allows_fetch(server.url + "blocked/one")
            self.assertIn(netloc, page_fetch._robots_cache)
            with patch.object(page_fetch, "_raw_get") as raw_get:
                page_fetch.robots_allows_fetch(server.url + "blocked/two")
                raw_get.assert_not_called()


class RetryTests(unittest.TestCase):
    def setUp(self):
        page_fetch.clear_cache()

    def tearDown(self):
        page_fetch.clear_cache()

    def test_a_transient_503_is_retried_and_can_still_succeed(self):
        attempts = {"count": 0}
        real_urlopen = page_fetch.urllib.request.urlopen

        def flaky_urlopen(request, *args, **kwargs):
            if "robots.txt" in request.full_url:
                raise urllib.error.URLError("no robots server")
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)
            return real_urlopen(request, *args, **kwargs)

        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch.time, "sleep"), \
                patch.object(page_fetch.urllib.request, "urlopen", side_effect=flaky_urlopen):
            html, status = page_fetch.fetch_page_html(server.url)

        self.assertEqual(status, "present")
        self.assertEqual(attempts["count"], 3)

    def test_a_permanent_404_is_not_retried(self):
        attempts = {"count": 0}

        def always_404(request, *args, **kwargs):
            if "robots.txt" in request.full_url:
                raise urllib.error.URLError("no robots server")
            attempts["count"] += 1
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

        with patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch.time, "sleep"), \
                patch.object(page_fetch.urllib.request, "urlopen", side_effect=always_404):
            html, status = page_fetch.fetch_page_html("http://example.invalid/")

        self.assertEqual(status, "unavailable")
        self.assertEqual(attempts["count"], 1)


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
