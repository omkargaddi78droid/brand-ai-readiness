"""Shared page-fetching (shared infrastructure, INF-02/INF-04).

Six skill scripts (content-quality-audit, citability-audit, entity-audit,
engagement-audit, static-extraction-audit, retrieval-readiness-audit) each
carried a byte-for-byte identical `fetch_page_html`/`decode_content_encoding`
pair, independently reimplemented per this project's now-superseded
"independently runnable skill" convention. shared/ is already a hard runtime
dependency of every script via `sys.path.insert`, so the duplication bought
nothing but six places for the same bug (see tests/test_gzip_decoding.py) to
be reintroduced independently.

check_perimeter.py deliberately keeps its own fetch path (`fetch_text`): it
varies User-Agent per AI-crawler identity and must not share a cache keyed
on URL alone.

Pure stdlib: `urllib.request` only, no third-party HTTP client. No write
methods are ever used (GET only) — this module fetches from audited sites,
it never mutates them.
"""

from __future__ import annotations

import dataclasses
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
import zlib

USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5_000_000
_MAX_DECOMPRESSED_BYTES = 20_000_000


def is_public_host(hostname: str) -> bool:
    """SSRF guard: refuse to fetch a hostname that resolves to a private,
    loopback, link-local, reserved, or multicast address."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _bounded_decompress(decompressor, raw: bytes) -> bytes:
    output = decompressor.decompress(raw, _MAX_DECOMPRESSED_BYTES)
    if decompressor.unconsumed_tail:
        raise ValueError(f"decompressed body exceeds {_MAX_DECOMPRESSED_BYTES} bytes")
    return output + decompressor.flush()


def decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Undo Content-Encoding before the body is treated as text.

    `urllib.request` never auto-decompresses (unlike `requests`), and some
    CDNs gzip responses regardless of whether the client's Accept-Encoding
    advertised support for it — observed live against python.org, whose
    `Content-Encoding: gzip` raw bytes were then decoded as UTF-8 text,
    producing binary garbage in every extracted-text field silently.

    Bounded to guard against a decompression-bomb response: this reads from
    the audited site, which is trusted to be a legitimate target but not to
    be well-behaved.
    """
    tokens = [t.strip().lower() for t in (content_encoding or "").split(",") if t.strip()]
    for token in reversed(tokens):
        if token in ("gzip", "x-gzip"):
            raw = _bounded_decompress(zlib.decompressobj(zlib.MAX_WBITS | 16), raw)
        elif token == "deflate":
            raw = _bounded_decompress(zlib.decompressobj(), raw)
        elif token in ("identity", ""):
            continue
        else:
            raise ValueError(f"unsupported Content-Encoding {token!r}; refusing to guess")
    return raw


def fetch_page_html(url: str) -> tuple[str | None, str]:
    """Fetch `url` and return (html_or_error_message, status).

    status is one of "present", "not_html", "unavailable". On any failure
    the first element is a human-readable message, never None — the None
    case in the type signature exists only for callers that intend to treat
    a non-"present" status as "no HTML content", not as a promise the first
    element is ever actually None.
    """
    hostname = urllib.parse.urlparse(url).hostname
    if not hostname or not is_public_host(hostname):
        return f"{url} does not resolve to a public address", "unavailable"

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            if content_type and "html" not in content_type.lower() and "text" not in content_type.lower():
                return f"{url} returned Content-Type {content_type!r}, not HTML/text", "not_html"
            raw = response.read(MAX_PAGE_BYTES)
            content_encoding = response.headers.get("Content-Encoding", "")
        raw = decode_content_encoding(raw, content_encoding)
        return raw.decode("utf-8", errors="replace"), "present"
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        return f"{url} returned HTTP {code}", "unavailable"
    except Exception as error:
        return f"{url} could not be fetched: {type(error).__name__}: {error}", "unavailable"


@dataclasses.dataclass(frozen=True)
class PageBundle:
    """Everything a check script needs from one fetched page, computed once.

    `html` is None exactly when `status != "present"`; callers that only
    care about text should check `status` first. Immutable so a cached
    instance shared across checks within one orchestrator run can't be
    mutated by one check in a way that corrupts another's view of it.
    """

    url: str
    status: str
    html: str | None
    error: str | None
    final_url: str
    headers: dict[str, str]


_page_cache: dict[str, PageBundle] = {}


def fetch_page(url: str, *, use_cache: bool = True) -> PageBundle:
    """Fetch `url` once per process, cached by URL for the lifetime of the
    interpreter. Every check script run within the same orchestrator process
    against the same URL gets the same bundle instead of refetching.

    Only successful ("present") fetches are cached — a transient failure
    (a timeout, a 503) is retried on the next call rather than pinned.
    """
    if use_cache and url in _page_cache:
        return _page_cache[url]

    hostname = urllib.parse.urlparse(url).hostname
    if not hostname or not is_public_host(hostname):
        return PageBundle(
            url=url,
            status="unavailable",
            html=None,
            error=f"{url} does not resolve to a public address",
            final_url=url,
            headers={},
        )

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            headers = dict(response.headers.items())
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            if content_type and "html" not in content_type.lower() and "text" not in content_type.lower():
                return PageBundle(
                    url=url,
                    status="not_html",
                    html=None,
                    error=f"{url} returned Content-Type {content_type!r}, not HTML/text",
                    final_url=final_url,
                    headers=headers,
                )
            raw = response.read(MAX_PAGE_BYTES)
            content_encoding = response.headers.get("Content-Encoding", "")
        raw = decode_content_encoding(raw, content_encoding)
        bundle = PageBundle(
            url=url,
            status="present",
            html=raw.decode("utf-8", errors="replace"),
            error=None,
            final_url=final_url,
            headers=headers,
        )
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        return PageBundle(
            url=url, status="unavailable", html=None,
            error=f"{url} returned HTTP {code}", final_url=url, headers={},
        )
    except Exception as error:
        return PageBundle(
            url=url, status="unavailable", html=None,
            error=f"{url} could not be fetched: {type(error).__name__}: {error}",
            final_url=url, headers={},
        )

    if use_cache:
        _page_cache[url] = bundle
    return bundle


def clear_cache() -> None:
    """Reset the in-process page cache. Tests call this between cases so one
    test's fetch can't leak into another's assertions."""
    _page_cache.clear()
