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
import time as time_module
import unittest
import urllib.error
import urllib.parse
from email.message import Message
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

    def test_text_xml_content_type_is_rejected_as_not_html(self):
        # Regression: text/xml (pw.live's own sitemap.xml Content-Type,
        # live-confirmed) contains the substring "text" and was previously
        # accepted as page content by a naive substring check, producing a
        # false-positive engagement finding against a raw XML document.
        with _LocalServer(_TextXmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "not_html")
        self.assertIn("not HTML/text", html)

    def test_a_non_ascii_url_path_does_not_raise_unicode_encode_error(self):
        # Regression: a raw non-ASCII character in the URL path (e.g.
        # pw.live's Devanagari course-page slugs) previously made
        # urllib.request.Request's request-line encoding raise
        # UnicodeEncodeError before any socket was even opened.
        with _LocalServer(_UnicodePathHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url + "हिंदी-माध्यम-2027")
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)


class EncodeUrlForRequestTests(unittest.TestCase):
    def test_an_ascii_only_url_round_trips_unchanged(self):
        url = "https://example.com/a/b?x=1&y=2#frag"
        self.assertEqual(page_fetch._encode_url_for_request(url), url)

    def test_non_ascii_path_characters_are_percent_encoded(self):
        encoded = page_fetch._encode_url_for_request("https://example.com/हिंदी-माध्यम")
        self.assertTrue(encoded.isascii())
        self.assertTrue(encoded.startswith("https://example.com/%"))

    def test_already_percent_encoded_sequences_are_preserved(self):
        url = "https://example.com/a%20b"
        self.assertEqual(page_fetch._encode_url_for_request(url), url)

    def test_non_ascii_query_characters_are_percent_encoded(self):
        encoded = page_fetch._encode_url_for_request("https://example.com/search?q=हिंदी")
        self.assertTrue(encoded.isascii())
        self.assertIn("q=%", encoded)


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


class _TextXmlHandler(http.server.BaseHTTPRequestHandler):
    """Serves Content-Type: text/xml — the exact header pw.live's own
    sitemap.xml files use live. Regression coverage for the false-positive
    bug where `"text" in content_type` let this straight through
    `fetch_page_html`/`fetch_page` as if it were an HTML page."""

    def do_GET(self):  # noqa: N802
        body = b"<?xml version='1.0'?><urlset><url><loc>https://example.com/a</loc></url></urlset>"
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _UnicodePathHandler(http.server.BaseHTTPRequestHandler):
    """Returns the same page regardless of path — used to prove a request
    whose URL path contains non-ASCII characters reaches this server at all
    (no UnicodeEncodeError raised before the socket is even opened)."""

    def do_GET(self):  # noqa: N802
        body = SAMPLE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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


def _headers_with_content_type(content_type: str | None) -> Message:
    msg = Message()
    if content_type is not None:
        msg["Content-Type"] = content_type
    return msg


class DecodeBodyTests(unittest.TestCase):
    """shared/page_fetch.py's own charset-aware decode fallback (Defect 5):
    a declared charset is honoured, an undeclared or garbage one falls back
    safely, and a genuinely non-UTF-8 body with no declared charset lands on
    windows-1252 instead of being silently mojibake'd."""

    def test_a_declared_charset_is_honoured(self):
        raw = "café".encode("iso-8859-1")
        headers = _headers_with_content_type("text/html; charset=iso-8859-1")
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_no_content_type_header_falls_back_to_utf8(self):
        raw = "café".encode("utf-8")
        headers = _headers_with_content_type(None)
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_an_empty_charset_declaration_falls_back_to_utf8(self):
        raw = "café".encode("utf-8")
        headers = _headers_with_content_type('text/html; charset=""')
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_an_unknown_codec_name_falls_back_to_utf8(self):
        raw = "café".encode("utf-8")
        headers = _headers_with_content_type("text/html; charset=bogus-not-a-real-codec")
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_a_declared_charset_that_cannot_actually_decode_the_body_falls_through(self):
        # Declares utf-8 but the body is actually windows-1252 — a real-world
        # mislabeled-page case, not just a malformed header.
        raw = "café".encode("windows-1252")
        headers = _headers_with_content_type("text/html; charset=utf-8")
        # utf-8 raises on this byte sequence, so it falls through to the
        # final windows-1252 fallback and decodes correctly anyway.
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_non_utf8_body_with_no_declared_charset_falls_back_to_windows_1252(self):
        raw = "café".encode("windows-1252")
        headers = _headers_with_content_type("text/html")
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_duplicate_content_type_headers_use_the_first(self):
        headers = Message()
        headers.add_header("Content-Type", "text/html; charset=iso-8859-1")
        headers.add_header("Content-Type", "text/html; charset=utf-8")
        raw = "café".encode("iso-8859-1")
        self.assertEqual(page_fetch._decode_body(raw, headers), "café")

    def test_plain_ascii_with_no_charset_round_trips(self):
        raw = b"Hello, world."
        headers = _headers_with_content_type(None)
        self.assertEqual(page_fetch._decode_body(raw, headers), "Hello, world.")


class RequestHeadersTests(unittest.TestCase):
    """Defect 5: standard Accept/Accept-Language headers are sent alongside
    User-Agent; Sec-CH-UA (a browser-identifying Client Hint that would be
    inconsistent with this project's own honest User-Agent string) is
    deliberately not."""

    def test_accept_and_accept_language_are_present(self):
        self.assertIn("Accept", page_fetch._REQUEST_HEADERS)
        self.assertIn("Accept-Language", page_fetch._REQUEST_HEADERS)
        self.assertEqual(page_fetch._REQUEST_HEADERS["User-Agent"], page_fetch.USER_AGENT)

    def test_no_browser_identifying_client_hints_are_sent(self):
        self.assertNotIn("Sec-CH-UA", page_fetch._REQUEST_HEADERS)


class _Windows1252Handler(http.server.BaseHTTPRequestHandler):
    """Serves a body only valid as windows-1252, with the charset correctly
    declared in Content-Type — a legacy-encoding page that should decode
    correctly rather than mojibake into replacement characters."""

    def do_GET(self):  # noqa: N802
        body = "Café — déjà vu".encode("windows-1252")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=windows-1252")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _UndeclaredLegacyEncodingHandler(http.server.BaseHTTPRequestHandler):
    """Serves a windows-1252-only body with NO charset declared at all —
    exercises the final fallback, not the declared-charset path."""

    def do_GET(self):  # noqa: N802
        body = "Café".encode("windows-1252")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FetchPageHtmlEncodingEndToEndTests(unittest.TestCase):
    def test_a_declared_windows_1252_page_decodes_correctly(self):
        with _LocalServer(_Windows1252Handler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertEqual(html, "Café — déjà vu")

    def test_an_undeclared_legacy_encoding_falls_back_correctly_not_mojibake(self):
        with _LocalServer(_UndeclaredLegacyEncodingHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            html, status = page_fetch.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertEqual(html, "Café")
        self.assertNotIn("�", html)


class FetchPagesConcurrentlyTests(unittest.TestCase):
    """shared/page_fetch.py's concurrent-fetch helper (Defect 2): the fix
    for a 5-minute audit budget colliding with fully sequential HTTP
    requests. Determinism (order-stable results despite concurrent
    completion) and the global/per-host politeness caps are the two
    properties the fix explicitly promises, so they're tested directly
    rather than just trusted."""

    def test_empty_list_returns_empty_without_calling_fetch(self):
        with patch.object(page_fetch, "fetch_page_html") as fetch_mock:
            result = page_fetch.fetch_pages_concurrently([])
        self.assertEqual(result, [])
        fetch_mock.assert_not_called()

    def test_results_are_returned_in_input_order_regardless_of_completion_order(self):
        urls = [f"https://example.com/page-{i}" for i in range(5)]
        # Later URLs finish FIRST (decreasing sleep) to prove gather doesn't
        # reorder by completion time.
        delays = {url: 0.05 * (len(urls) - i) for i, url in enumerate(urls)}

        def fake_fetch(url):
            time_module.sleep(delays[url])
            return (f"content-for-{url}", "present")

        with patch.object(page_fetch, "fetch_page_html", side_effect=fake_fetch):
            results = page_fetch.fetch_pages_concurrently(urls, max_concurrency=5)

        self.assertEqual([r[0] for r in results], urls)
        for url, content, status in results:
            self.assertEqual(content, f"content-for-{url}")
            self.assertEqual(status, "present")

    def test_global_concurrency_bound_is_respected(self):
        # Distinct hosts so only the global cap (not the per-host cap) binds.
        urls = [f"https://host{i}.example.com/" for i in range(10)]
        lock = threading.Lock()
        state = {"current": 0, "max_seen": 0}

        def fake_fetch(url):
            with lock:
                state["current"] += 1
                state["max_seen"] = max(state["max_seen"], state["current"])
            time_module.sleep(0.03)
            with lock:
                state["current"] -= 1
            return ("x", "present")

        with patch.object(page_fetch, "fetch_page_html", side_effect=fake_fetch):
            page_fetch.fetch_pages_concurrently(urls, max_concurrency=3)

        self.assertLessEqual(state["max_seen"], 3)
        self.assertGreater(state["max_seen"], 1, "fetches ran fully serialized, not concurrently")

    def test_per_host_concurrency_bound_is_respected_even_with_a_generous_global_cap(self):
        # All URLs share one host; the global cap is generous enough that
        # only the per-host cap should actually bind.
        urls = [f"https://example.com/page-{i}" for i in range(8)]
        lock = threading.Lock()
        state = {"current": 0, "max_seen": 0}

        def fake_fetch(url):
            with lock:
                state["current"] += 1
                state["max_seen"] = max(state["max_seen"], state["current"])
            time_module.sleep(0.03)
            with lock:
                state["current"] -= 1
            return ("x", "present")

        with patch.object(page_fetch, "fetch_page_html", side_effect=fake_fetch):
            page_fetch.fetch_pages_concurrently(urls, max_concurrency=8)

        self.assertLessEqual(state["max_seen"], page_fetch._MAX_CONCURRENT_FETCHES_PER_HOST)
        self.assertGreater(state["max_seen"], 1, "fetches ran fully serialized, not concurrently")

    def test_a_failure_for_one_url_does_not_affect_others(self):
        urls = ["https://example.com/ok", "https://example.com/broken"]

        def fake_fetch(url):
            if "broken" in url:
                return ("boom: something went wrong", "unavailable")
            return ("fine", "present")

        with patch.object(page_fetch, "fetch_page_html", side_effect=fake_fetch):
            results = page_fetch.fetch_pages_concurrently(urls)

        by_url = {r[0]: r for r in results}
        self.assertEqual(by_url["https://example.com/ok"][2], "present")
        self.assertEqual(by_url["https://example.com/broken"][2], "unavailable")

    def test_the_real_fetch_page_html_is_used_end_to_end(self):
        with _LocalServer(_HtmlHandler) as server, \
                patch.object(page_fetch, "is_public_host", return_value=True), \
                patch.object(page_fetch, "robots_allows_fetch", return_value=True):
            results = page_fetch.fetch_pages_concurrently([server.url, server.url])
        self.assertEqual(len(results), 2)
        for url, content, status in results:
            self.assertEqual(status, "present")
            self.assertIn("Example Corp", content)


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
