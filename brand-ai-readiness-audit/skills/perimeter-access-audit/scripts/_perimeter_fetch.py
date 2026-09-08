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
from _perimeter_encoding import decode_content_encoding  # noqa: E402


def fetch_text(url: str) -> tuple[str | None, str]:
    """GET a well-known text file. Returns (text_or_error, status).

    status is "present", "absent" (404/410) or "unavailable" (anything else).
    A fetch failure is never allowed to become "the file is not there".
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
        error.close()
        if code in (404, 410):
            return None, "absent"
        return f"{url} returned HTTP {code}", "unavailable"
    except Exception as error:  # timeout, DNS, TLS, redirect loop
        return f"{url} could not be fetched: {type(error).__name__}: {error}", "unavailable"
