"""Regression coverage for the gzip Content-Encoding bug, found live against
python.org during engagement-audit's field validation and confirmed present
in all four page/file-fetching scripts in this marketplace.

`urllib.request` never auto-decompresses a response body (unlike `requests`).
python.org's CDN sends `Content-Encoding: gzip` regardless of whether the
client's Accept-Encoding advertised support for it — a real server observed
doing this, not a hypothetical. Every script that read a response body and
decoded it straight to UTF-8 text was silently treating raw gzip bytes as
text, producing binary garbage that every downstream detector then ran
against without any error — because nothing checked for it. A wrong result
this severe, from every page-reading skill at once, and no test caught it
until a live run did.

Every page-fetching script but perimeter-access-audit now delegates to
shared/page_fetch.py (cycle 23 consolidation) rather than carrying its own
copy, so `module.decode_content_encoding`/`module.fetch_page_html` are the
same function object as `page_fetch`'s for all of them; the SSRF guard they
each import (`is_public_host`) is patched on `page_fetch` itself, not on the
individual skill module, since that's where the imported name is actually
looked up at call time. `check_perimeter.py` deliberately keeps its own
`fetch_text`/`decode_content_encoding` — it varies User-Agent per AI-crawler
identity and must not share a cache keyed on URL alone. This file tests all
six via a real local HTTP server serving genuinely gzip-compressed content —
not a mock — so a regression in any one of them fails a real end-to-end
round trip, not just an isolated unit call.
"""

import gzip
import http.server
import importlib.util
import sys
import threading
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import page_fetch  # noqa: E402

perimeter = _load("check_perimeter", "skills/perimeter-access-audit/scripts/check_perimeter.py")
content_quality = _load("check_content_quality", "skills/content-quality-audit/scripts/check_content_quality.py")
entity_audit = _load("check_entity", "skills/entity-audit/scripts/check_entity.py")
engagement_audit = _load("check_engagement", "skills/engagement-audit/scripts/check_engagement.py")
citability_audit = _load("check_citability", "skills/citability-audit/scripts/check_citability.py")
static_extraction_audit = _load(
    "check_static_extraction", "skills/static-extraction-audit/scripts/check_static_extraction.py"
)
retrieval_readiness_audit = _load(
    "check_retrieval_readiness", "skills/retrieval-readiness-audit/scripts/check_retrieval_readiness.py"
)

MODULES_WITH_DECODE = [
    perimeter, content_quality, entity_audit, engagement_audit, citability_audit,
    static_extraction_audit, retrieval_readiness_audit,
]

SAMPLE_HTML = "<html><body><h1>Example Corp</h1><p>Hello, world.</p></body></html>"


class DecodeContentEncodingUnitTests(unittest.TestCase):
    """Every module's own copy of the decoder, tested identically."""

    def test_gzip_round_trips_in_every_module(self):
        compressed = gzip.compress(SAMPLE_HTML.encode("utf-8"))
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                result = module.decode_content_encoding(compressed, "gzip")
                self.assertEqual(result.decode("utf-8"), SAMPLE_HTML)

    def test_deflate_round_trips_in_every_module(self):
        compressed = zlib.compress(SAMPLE_HTML.encode("utf-8"))
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                result = module.decode_content_encoding(compressed, "deflate")
                self.assertEqual(result.decode("utf-8"), SAMPLE_HTML)

    def test_no_content_encoding_passes_through_unchanged(self):
        raw = SAMPLE_HTML.encode("utf-8")
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                self.assertEqual(module.decode_content_encoding(raw, ""), raw)

    def test_identity_encoding_passes_through_unchanged(self):
        raw = SAMPLE_HTML.encode("utf-8")
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                self.assertEqual(module.decode_content_encoding(raw, "identity"), raw)

    def test_an_unsupported_encoding_raises_rather_than_guessing(self):
        """Brotli ("br") has no stdlib decompressor. Silently returning the
        raw bytes would reintroduce the exact bug this file exists to catch,
        just for a different encoding — refuse instead."""
        raw = b"not actually brotli, doesn't matter"
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                with self.assertRaises(ValueError):
                    module.decode_content_encoding(raw, "br")

    def test_gzip_bomb_is_rejected_not_silently_truncated(self):
        """A pathological input (highly compressible, deliberately oversized)
        must fail loudly, not silently hand back a truncated or enormous
        result."""
        bomb = gzip.compress(b"0" * 50_000_000)
        for module in MODULES_WITH_DECODE:
            with self.subTest(module=module.__name__):
                with self.assertRaises(ValueError):
                    module.decode_content_encoding(bomb, "gzip")


class _GzipHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = gzip.compress(SAMPLE_HTML.encode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _GzipServer:
    def __init__(self):
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), _GzipHandler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class EndToEndGzipFetchTests(unittest.TestCase):
    """A real local HTTP server, genuinely gzip-compressed — not a mock —
    so a regression in the actual fetch function (not just the decoder it
    calls) fails this test.

    `content_quality`/`entity_audit`/`engagement_audit`/`citability_audit`/
    `static_extraction_audit`/`retrieval_readiness_audit` all import
    `fetch_page_html` from shared `page_fetch` now, so it's the same function
    object refusing a loopback address in every one of them (see
    page_fetch's own SsrfGuardTests) — patched on `page_fetch` itself, since
    that's the module whose global namespace `fetch_page_html` actually
    looks `is_public_host` up in, only for the duration of this narrow
    decompression check, which is orthogonal to the guard.
    `perimeter.fetch_text` has no such guard (it only ever fetches a fixed
    well-known path, never an arbitrary caller-supplied URL), so nothing
    needs patching for it.
    """

    def test_perimeter_fetch_text_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server:
            text, status = perimeter.fetch_text(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", text)

    def test_content_quality_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = content_quality.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)

    def test_entity_audit_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = entity_audit.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)

    def test_engagement_audit_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = engagement_audit.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)

    def test_citability_audit_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = citability_audit.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)

    def test_static_extraction_audit_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = static_extraction_audit.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)

    def test_retrieval_readiness_audit_fetch_page_html_decompresses_a_real_gzip_response(self):
        with _GzipServer() as server, patch.object(page_fetch, "is_public_host", return_value=True):
            html, status = retrieval_readiness_audit.fetch_page_html(server.url)
        self.assertEqual(status, "present")
        self.assertIn("Example Corp", html)


if __name__ == "__main__":
    unittest.main()
