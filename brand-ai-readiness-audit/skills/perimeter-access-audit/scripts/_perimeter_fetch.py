"""The one fetch primitive shared by every split perimeter-access-audit module (`fetch_text`) — PER-03's edge probe, PER-11's content parity, and PER-09's tdmrep.json check each need to fetch a well-known text file independently of check_perimeter.py's own robots.txt/llms.txt fetches in `main()`.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from _perimeter_constants import USER_AGENT, FETCH_TIMEOUT_SECONDS  # noqa: E402
from _perimeter_encoding import decode_content_encoding, _best_effort_decode_content_encoding  # noqa: E402
from page_fetch import _disk_cache_read, _disk_cache_write  # noqa: E402


# ---------------------------------------------------------------------------
# Fail-fast circuit breaker (R5/S2): a fully-blocked or unreachable host
# (TLS handshake completes, then every request silently times out — observed
# live against goindigo.in, fronted by Akamai) used to pay this module's full
# FETCH_TIMEOUT_SECONDS on EVERY well-known-file fetch and EVERY PER-03
# bot-agent probe in sequence: robots.txt, llms.txt, llms-full.txt,
# sitemap.xml (+ its robots.txt-named fallback), the .md variant, PER-03's
# own robots.txt refetch, then one probe per bot-tier group plus a baseline
# — 10+ sequential 10s timeouts, consuming over half of the orchestrator's
# entire 280s run budget just to discover "unreachable" before any
# downstream skill got a chance to run at all.
#
# This trips per-host, process-lifetime (matching `_robots_cache`'s own
# scope in shared/page_fetch.py) after `_CIRCUIT_FAILURE_THRESHOLD`
# CONSECUTIVE raw connection-level failures (timeout, DNS, TLS, connection
# reset — the `except Exception` branch below) to that host. A classified
# HTTP outcome (2xx, 404/410, or an edge 403/429/challenge) is a real
# response from a reachable host, not an outage, and resets the counter —
# only genuine connection-level failure counts, so a WAF that legitimately
# blocks with 403 never trips this. Once open, every further fetch or probe
# to that host returns immediately without touching the network, at
# whatever the module's already-paid cost was to detect the outage
# (2 x 10s here, not 10+ x 10s).
_CIRCUIT_FAILURE_THRESHOLD = 2
_circuit_failures: dict[str, int] = {}
_circuit_open: dict[str, str] = {}


def _host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


def circuit_is_open(url: str) -> str | None:
    """The error message that tripped this host's circuit, or `None` if it
    is still closed (no fetch attempted yet, or every attempt so far got a
    real — even if blocked — HTTP response)."""
    return _circuit_open.get(_host_of(url))


def record_connection_result(url: str, *, failed: bool, error_text: str = "") -> None:
    """Call after every raw network attempt (not a circuit-skip, not a disk
    cache hit) to this module's own primitives. `failed=True` only for a
    connection-level failure — never for a classified HTTP outcome, which
    proves the host IS reachable regardless of what it answered."""
    host = _host_of(url)
    if not failed:
        _circuit_failures.pop(host, None)
        return
    count = _circuit_failures.get(host, 0) + 1
    _circuit_failures[host] = count
    if count >= _CIRCUIT_FAILURE_THRESHOLD and host not in _circuit_open:
        _circuit_open[host] = error_text


def reset_circuit_breaker() -> None:
    """Test isolation, mirrors `shared/page_fetch.py`'s own `clear_cache`."""
    _circuit_failures.clear()
    _circuit_open.clear()


# Status codes that name a deliberate access decision. 5xx and other errors are
# excluded on purpose: a 500 is at least as likely to be an origin fault as a
# bot-specific block, and asserting a block from an ambiguous status would be
# exactly the false-positive-of-severity failure this project tests against.
#
# Single source of truth for both PER-03's own live edge probe (which sends
# bot user agents at root `/`) and every other well-known-file fetch in this
# module (`fetch_text`) — a CDN/WAF can rule-match on *path*, not just be a
# blanket allow/block at root, so a 429/403 hit on /llms.txt or similar must
# be classified the same way PER-03 already classifies its own probes,
# instead of collapsing into a generic "unavailable" that looks identical to
# a transient network blip.
EDGE_BLOCK_STATUS_CODES = (403, 429)

# A CDN challenge page often returns 200 with a JS/CAPTCHA interstitial rather
# than a 4xx. These are the markers of the major bot-management vendors' stock
# challenge pages. A body match is a weaker signal than a status code, so it is
# reported at reduced confidence by callers that score it (see PER-03's
# `_edge_block_finding`).
CHALLENGE_MARKERS = (
    "checking your browser",
    "just a moment",
    "cf-browser-verification",
    "attention required! | cloudflare",
    "please verify you are a human",
    "captcha-delivery.com",
    "distil_r_captcha",
    "perimeterx",
    "access denied",
    "request blocked",
    "you have been blocked",
    "vercel security checkpoint",
)


def classify_response(status: int | None, body: str) -> str:
    """Pure classifier: HTTP status + body -> "ok" | "blocked" | "challenge" |
    "ambiguous". No network I/O, so this is unit tested directly with fixed
    inputs."""
    lowered = body.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        return "challenge"
    if status in EDGE_BLOCK_STATUS_CODES:
        return "blocked"
    if status is not None and 200 <= status < 300:
        return "ok"
    return "ambiguous"


def fetch_text(url: str) -> tuple[str | None, str]:
    """GET a well-known text file. Returns (text_or_error, status).

    status is "present", "absent" (404/410) or "unavailable" (anything else).
    A fetch failure is never allowed to become "the file is not there".

    On a non-404/410 HTTPError, the response body and headers are still
    inspected (bounded to 4KB, same budget as PER-03's own probes) and run
    through the same `classify_response` PER-03 uses for its live bot-agent
    probes. When that names a "blocked" or "challenge" edge decision — a
    429/403 status, or a 200 with a bot-management interstitial in the body —
    the returned error text says so explicitly, so a caller's `unknown_checks`
    reason reads "edge challenge, not absence" instead of a bare HTTP code
    that looks identical to a transient failure.

    Gated by the module's fail-fast circuit breaker (see its own comment
    above): once `_CIRCUIT_FAILURE_THRESHOLD` consecutive raw connection
    failures have been seen for this host this process, every further call
    here returns immediately without a network attempt.
    """
    disk_hit = _disk_cache_read("text", url)
    if disk_hit is not None:
        return disk_hit.get("text"), disk_hit.get("status", "unavailable")

    tripped_by = circuit_is_open(url)
    if tripped_by is not None:
        return (
            f"{url} skipped: {_host_of(url)} has been unreachable ({tripped_by}) on every recent "
            "attempt this run, so no further fetches to this host are attempted",
            "unavailable",
        )

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
            content_encoding = response.headers.get("Content-Encoding", "")
        raw = decode_content_encoding(raw, content_encoding)
        text, status = raw.decode("utf-8", errors="replace"), "present"
        _disk_cache_write("text", url, {"text": text, "status": status})
        record_connection_result(url, failed=False)
        return text, status
    except urllib.error.HTTPError as error:
        record_connection_result(url, failed=False)
        code = error.code
        if code in (404, 410):
            error.close()
            _disk_cache_write("text", url, {"text": None, "status": "absent"})
            return None, "absent"
        try:
            raw = error.read(4096)
            raw = _best_effort_decode_content_encoding(raw, error.headers.get("Content-Encoding", "") if error.headers else "")
            body = raw.decode("utf-8", errors="replace")
            server = error.headers.get("Server", "") if error.headers else ""
        except Exception:
            body = ""
            server = ""
        finally:
            error.close()
        classification = classify_response(code, body)
        if classification in ("blocked", "challenge"):
            how = "a bot-management challenge page" if classification == "challenge" else "a deliberate edge decision"
            server_note = f" (server: {server})" if server else ""
            text, status = (
                f"{url} returned HTTP {code}, classified as a CDN/edge {classification}{server_note}: "
                f"the edge answered with {how} rather than a generic error, so this is not confirmation "
                "the file is absent — see PER-03 for the same classification applied to root access",
                "unavailable",
            )
            _disk_cache_write("text", url, {"text": text, "status": status})
            return text, status
        text, status = f"{url} returned HTTP {code}", "unavailable"
        _disk_cache_write("text", url, {"text": text, "status": status})
        return text, status
    except Exception as error:  # timeout, DNS, TLS, redirect loop
        text, status = f"{url} could not be fetched: {type(error).__name__}: {error}", "unavailable"
        _disk_cache_write("text", url, {"text": text, "status": status})
        record_connection_result(url, failed=True, error_text=text)
        return text, status
