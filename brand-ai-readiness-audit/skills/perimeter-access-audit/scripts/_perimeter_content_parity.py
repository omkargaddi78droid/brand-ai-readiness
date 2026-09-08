"""PER-11 — AI-crawler content-parity diff (cloaking detection) for perimeter-access-audit — split out of check_perimeter.py.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from text_spans import extract_blocks  # noqa: E402
from jsonld_graph import flatten  # noqa: E402
from _perimeter_constants import (  # noqa: E402
    OWNER_SKILL,
    FETCH_TIMEOUT_SECONDS,
    EDGE_PROBE_DELAY_SECONDS,
    TIER_SEVERITY,
    TIER_LABELS,
    TIER_MECHANISM,
    CONTROL_USER_AGENT,
    AUDIT_PURPOSE_HEADER,
)
from _perimeter_encoding import decode_content_encoding  # noqa: E402
from _perimeter_fetch import fetch_text  # noqa: E402
from _perimeter_access_rules import parse_groups  # noqa: E402
from _perimeter_edge_probe import plan_edge_probes  # noqa: E402


# ---------------------------------------------------------------------------
# PER-11 — AI-crawler content-parity diff (cloaking), cycle 23 Phase 2 (A3)
#
# Distinct from PER-03: PER-03 catches an edge that refuses an AI agent
# outright (a 403/429/challenge while a browser gets through). This catches
# the opposite deception — the edge or origin answers the AI agent's exact
# identity with HTTP 200, the same success status a browser gets, but a
# meaningfully thinner payload: less visible text, or structured data a
# browser-fetched copy of the same URL actually carries. Same permission,
# different content — genuinely invisible to any check that only looks at
# status codes.
# ---------------------------------------------------------------------------

_A3_MAX_BODY_BYTES = 2_000_000
_A3_MIN_TEXT_RETENTION_RATIO = 0.5
_JSON_LD_SCRIPT_PATTERN = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _visible_text_length(html: str) -> int:
    return sum(len(block.text) for block in extract_blocks(html))


def _json_ld_node_count(html: str) -> int:
    return len(flatten(_JSON_LD_SCRIPT_PATTERN.findall(html)))


def evaluate_content_parity(
    tier: str,
    agent: str,
    browser_status: int | None,
    browser_html: str | None,
    crawler_status: int | None,
    crawler_html: str | None,
) -> Finding | None:
    """Pure comparison — no network I/O — given two already-fetched bodies
    for the same URL. Only evaluates when both requests actually succeeded
    (HTTP 200): an outright block is PER-03's finding, not this one's, and
    comparing content across two different failure statuses would not mean
    anything."""
    if browser_status != 200 or crawler_status != 200 or not browser_html or not crawler_html:
        return None

    browser_text_len = _visible_text_length(browser_html)
    if browser_text_len == 0:
        return None  # nothing in the browser copy to compare against either

    crawler_text_len = _visible_text_length(crawler_html)
    text_ratio = crawler_text_len / browser_text_len
    thin_text = text_ratio < _A3_MIN_TEXT_RETENTION_RATIO

    browser_jsonld = _json_ld_node_count(browser_html)
    crawler_jsonld = _json_ld_node_count(crawler_html)
    missing_jsonld = browser_jsonld > 0 and crawler_jsonld == 0

    if not thin_text and not missing_jsonld:
        return None

    severity, _ = TIER_SEVERITY[tier]
    label = TIER_LABELS[tier]
    clauses = []
    if thin_text:
        clauses.append(
            f"{crawler_text_len} of {browser_text_len} visible-text characters "
            f"({text_ratio:.0%})"
        )
    if missing_jsonld:
        clauses.append(f"{browser_jsonld} JSON-LD node(s) present for the browser, 0 for {agent}")

    return Finding(
        id=f"PER-11-{tier.replace('_', '-')}-content-parity",
        title=f"{agent} receives a thinner page than an ordinary browser at the same URL",
        severity=severity,
        evidence=(
            f"Both an ordinary browser and {agent} ({label}) got HTTP 200 at the same URL, but "
            f"{agent}'s response carries {'; '.join(clauses)} — the same URL, the same success "
            "status, materially less content."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f"Confirm the origin or CDN is not serving {agent} a reduced/cached/stale variant "
                "of this page. If this is intentional (e.g. a lightweight bot-facing template), "
                "it still costs this agent the content a browser-driven visitor would see."
            ),
            priority=severity,
        ),
        category="discoverability",
        capability_id="PER-11",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A blocked request is an honest denial; a 200 response with materially less content "
            "is not — the agent believes it successfully fetched the page and has no signal that "
            "anything is missing. " + TIER_MECHANISM[tier]
        ),
        gate=1,
        confidence="medium",
        structured_evidence={
            "tier": tier,
            "agent": agent,
            "browser_text_len": browser_text_len,
            "crawler_text_len": crawler_text_len,
            "text_ratio": round(text_ratio, 3),
            "browser_json_ld_nodes": browser_jsonld,
            "crawler_json_ld_nodes": crawler_jsonld,
        },
    )


def fetch_full_body_with_user_agent(
    url: str, user_agent: str, timeout: float = FETCH_TIMEOUT_SECONDS
) -> tuple[str | None, int | None]:
    """Like `probe_with_user_agent`, but reads the full body (bounded at
    `_A3_MAX_BODY_BYTES`) rather than a 4096-byte classification snippet —
    PER-11 needs enough of the page to compare visible-text length and
    JSON-LD presence, which a truncated read cannot support."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "X-Audit-Purpose": AUDIT_PURPOSE_HEADER},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(_A3_MAX_BODY_BYTES)
            raw = decode_content_encoding(raw, response.headers.get("Content-Encoding", ""))
            return raw.decode("utf-8", errors="replace"), response.status
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        return None, code
    except Exception:
        return None, None


def fetch_and_evaluate_content_parity(base_url_value: str) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-11, end to end, for `--url` mode only. Fetches robots.txt itself
    (sharing nothing with the PER-01 or PER-03 fetches, matching
    `fetch_and_evaluate_edge_access`'s own documented reasoning: the calls
    happen independently, so a caller cannot pass in stale or skipped-probe
    groups and have this silently treat "never checked" as "no rules
    apply") to compute PER-03's own compliance plan — never probe an agent
    robots.txt already disallows — then issues its own full-body fetches,
    since PER-03's probe only reads a small classification snippet."""
    robots_text, robots_status = fetch_text(base_url_value + "/robots.txt")
    if robots_status == "unavailable":
        return [], [
            UnknownCheck(
                "PER-11",
                OWNER_SKILL,
                "robots.txt could not be established, so it is not known which agents "
                "may compliantly be probed for content parity",
            )
        ]

    groups = parse_groups(robots_text or "") if robots_status == "present" else []
    plan = plan_edge_probes(groups)
    if not plan["probe_baseline"]:
        return [], [
            UnknownCheck(
                "PER-11",
                OWNER_SKILL,
                "robots.txt disallows / for the wildcard group; no compliant baseline "
                "request could be made to establish a browser-fetched copy to compare against",
            )
        ]

    browser_html, browser_status = fetch_full_body_with_user_agent(base_url_value + "/", CONTROL_USER_AGENT)
    if browser_status != 200:
        return [], [
            UnknownCheck(
                "PER-11",
                OWNER_SKILL,
                "the reachability control request did not return HTTP 200, so there is no "
                "browser-fetched baseline to compare an AI agent's response against",
            )
        ]

    findings: list[Finding] = []
    for tier, agent in plan["tiers_to_probe"].items():
        time.sleep(EDGE_PROBE_DELAY_SECONDS)
        crawler_html, crawler_status = fetch_full_body_with_user_agent(base_url_value + "/", agent)
        finding = evaluate_content_parity(tier, agent, browser_status, browser_html, crawler_status, crawler_html)
        if finding:
            findings.append(finding)
    return findings, []
