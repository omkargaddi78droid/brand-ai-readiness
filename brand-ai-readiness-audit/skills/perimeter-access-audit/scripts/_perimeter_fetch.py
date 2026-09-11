"""The one fetch primitive shared by every split perimeter-access-audit module (`fetch_text`) — PER-03's edge probe, PER-11's content parity, and PER-09's tdmrep.json check each need to fetch a well-known text file independently of check_perimeter.py's own robots.txt/llms.txt fetches in `main()`.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from _perimeter_constants import USER_AGENT, FETCH_TIMEOUT_SECONDS  # noqa: E402
from _perimeter_encoding import decode_content_encoding, _best_effort_decode_content_encoding  # noqa: E402


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
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
            content_encoding = response.headers.get("Content-Encoding", "")
        raw = decode_content_encoding(raw, content_encoding)
        return raw.decode("utf-8", errors="replace"), "present"
    except urllib.error.HTTPError as error:
        code = error.code
        if code in (404, 410):
            error.close()
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
            return (
                f"{url} returned HTTP {code}, classified as a CDN/edge {classification}{server_note}: "
                f"the edge answered with {how} rather than a generic error, so this is not confirmation "
                "the file is absent — see PER-03 for the same classification applied to root access",
                "unavailable",
            )
        return f"{url} returned HTTP {code}", "unavailable"
    except Exception as error:  # timeout, DNS, TLS, redirect loop
        return f"{url} could not be fetched: {type(error).__name__}: {error}", "unavailable"
