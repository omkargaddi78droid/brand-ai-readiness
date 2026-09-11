"""PER-03 — CDN/edge access probing for perimeter-access-audit — split out of check_perimeter.py.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from _perimeter_constants import (  # noqa: E402
    OWNER_SKILL,
    FETCH_TIMEOUT_SECONDS,
    EDGE_PROBE_DELAY_SECONDS,
    TIER_SEVERITY,
    TIER_LABELS,
    TIER_MECHANISM,
    CONTROL_USER_AGENT,
    AUDIT_PURPOSE_HEADER,
    REPRESENTATIVE_AGENTS,
)
from _perimeter_encoding import _best_effort_decode_content_encoding  # noqa: E402
from _perimeter_fetch import (  # noqa: E402
    fetch_text,
    classify_response,
    CHALLENGE_MARKERS,
    EDGE_BLOCK_STATUS_CODES,
)
from _perimeter_access_rules import can_fetch_root, parse_groups  # noqa: E402

# `EDGE_BLOCK_STATUS_CODES`/`CHALLENGE_MARKERS`/`classify_response` now live in
# `_perimeter_fetch` (single source of truth shared with `fetch_text`, so a
# 429/403 hit on /llms.txt or similar well-known file is classified the same
# way this module's own root-`/` probes are) and are re-imported here so
# every existing `from _perimeter_edge_probe import classify_response`
# (check_perimeter.py, tests/test_edge_access.py) keeps working unchanged.


def plan_edge_probes(groups: list[tuple[set[str], list[str]]]) -> dict:
    """Decide what PER-03 may compliantly probe, from parsed robots.txt groups
    alone. Pure and deterministic — no network I/O — so this is directly unit
    testable, and it is the one place the "never probe what robots already
    disallows" rule is enforced.
    """
    if not can_fetch_root(groups, "*"):
        return {"probe_baseline": False, "tiers_to_probe": {}, "tiers_skipped_by_robots": []}

    tiers_to_probe: dict[str, str] = {}
    tiers_skipped: list[str] = []
    for tier, agent in REPRESENTATIVE_AGENTS.items():
        if can_fetch_root(groups, agent):
            tiers_to_probe[tier] = agent
        else:
            tiers_skipped.append(tier)
    return {"probe_baseline": True, "tiers_to_probe": tiers_to_probe, "tiers_skipped_by_robots": tiers_skipped}


def interpret_edge_results(
    plan: dict,
    baseline_classification: str | None,
    agent_results: dict[str, tuple[str, int | None]],
) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-03 from already-classified probe results. Pure — no network I/O —
    so the interpretation logic is unit tested without a live site; only the
    actual HTTP fetch in `fetch_and_evaluate_edge_access` is not.
    """
    if not plan["probe_baseline"]:
        return [], [
            UnknownCheck(
                "PER-03",
                OWNER_SKILL,
                "robots.txt disallows / for the wildcard group; no compliant baseline "
                "request could be made to distinguish an edge block from a site-wide block",
            )
        ]

    if baseline_classification != "ok":
        return [], [
            UnknownCheck(
                "PER-03",
                OWNER_SKILL,
                f"the reachability control request returned {baseline_classification!r} rather "
                "than a normal response, so an AI-bot-specific block cannot be distinguished "
                "from the origin being generally unreachable",
            )
        ]

    findings: list[Finding] = []
    unknowns: list[UnknownCheck] = []
    for tier, agent in plan["tiers_to_probe"].items():
        result = agent_results.get(tier)
        if result is None:
            unknowns.append(UnknownCheck("PER-03", OWNER_SKILL, f"the probe for {agent} did not complete"))
            continue
        classification, http_status = result
        if classification in ("blocked", "challenge"):
            findings.append(_edge_block_finding(tier, agent, classification, http_status))
        elif classification == "ambiguous":
            unknowns.append(
                UnknownCheck(
                    "PER-03",
                    OWNER_SKILL,
                    f"{agent} received HTTP {http_status}, which is neither a clear allow nor a "
                    "deliberate block, so no conclusion is drawn",
                )
            )
        # "ok": no finding — the representative agent was served normally.
    return findings, unknowns


def _edge_block_finding(tier: str, agent: str, classification: str, http_status: int | None) -> Finding:
    severity, _ = TIER_SEVERITY[tier]
    label = TIER_LABELS[tier]
    if classification == "blocked":
        confidence = "high"
        how = f"the edge returned HTTP {http_status}"
    else:
        confidence = "medium"
        how = (
            f"the edge returned HTTP {http_status} with a bot-management challenge page "
            "(interstitial detected in the response body)"
        )

    return Finding(
        id=f"PER-03-{tier.replace('_', '-')}-edge-blocked",
        title=f"CDN/edge blocks {agent} even though robots.txt allows it",
        severity=severity,
        evidence=(
            f"robots.txt permits {agent} ({label}), but a direct GET / sent with that user "
            f"agent got {how}, while the same request with an ordinary browser user agent "
            "succeeded."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f"Add an allow rule for {agent} in the CDN/WAF's bot-management configuration "
                "(Cloudflare's AI Bots / Verified Bots list, or the equivalent allowlist for the "
                "CDN in front of this site) so the edge decision matches the published robots.txt."
            ),
            priority=severity,
            details=(
                "robots.txt is a request a compliant crawler chooses to honour; an edge rule is "
                "enforced before the request reaches the origin at all, so it overrides robots.txt "
                "in practice regardless of what robots.txt says."
            ),
        ),
        category="discoverability",
        capability_id="PER-03",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "robots.txt is the origin server's published policy; a CDN or WAF sitting in front of "
            "it enforces its own bot-management rules first, and can block a request before the "
            "origin — and its robots.txt — are ever consulted. A site can publish full permission "
            "and still be invisible to the exact agents it claims to welcome, because the block is "
            "happening one layer up from where robots.txt is checked. " + TIER_MECHANISM[tier]
        ),
        gate=1,
        confidence=confidence,
        structured_evidence={
            "tier": tier,
            "agent": agent,
            "classification": classification,
            "http_status": http_status,
        },
    )


def probe_with_user_agent(url: str, user_agent: str, timeout: float = FETCH_TIMEOUT_SECONDS) -> tuple[str, int | None]:
    """Live GET classified by `classify_response`. The only impure function in
    the PER-03 chain; kept this small so everything upstream of it stays
    testable without a network."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "X-Audit-Purpose": AUDIT_PURPOSE_HEADER},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(4096)
            raw = _best_effort_decode_content_encoding(raw, response.headers.get("Content-Encoding", ""))
            body = raw.decode("utf-8", errors="replace")
            return classify_response(response.status, body), response.status
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(4096)
            raw = _best_effort_decode_content_encoding(raw, error.headers.get("Content-Encoding", ""))
            body = raw.decode("utf-8", errors="replace")
        except Exception:
            body = ""
        finally:
            error.close()
        return classify_response(error.code, body), error.code
    except Exception:
        return "unreachable", None


def fetch_and_evaluate_edge_access(base_url_value: str) -> tuple[list[Finding], list[UnknownCheck], list[tuple[set[str], list[str]]]]:
    """PER-03, end to end, for `--url` mode only. Fetches robots.txt itself
    (sharing nothing with the PER-01 fetch that already happened in `main`,
    since the two calls happen independently) to compute the compliance plan,
    then probes only what the plan permits.

    Returns the groups alongside the result so the caller can assert PER-01's
    robots.txt and PER-03's agree without a second fetch.
    """
    robots_text, robots_status = fetch_text(base_url_value + "/robots.txt")
    if robots_status == "unavailable":
        return (
            [],
            [
                UnknownCheck(
                    "PER-03",
                    OWNER_SKILL,
                    "robots.txt could not be established, so it is not known which agents "
                    "may compliantly be probed for edge access",
                )
            ],
            [],
        )

    groups = parse_groups(robots_text or "") if robots_status == "present" else []
    plan = plan_edge_probes(groups)

    if not plan["probe_baseline"]:
        return interpret_edge_results(plan, None, {}) + (groups,)

    baseline_classification, _ = probe_with_user_agent(base_url_value + "/", CONTROL_USER_AGENT)
    agent_results: dict[str, tuple[str, int | None]] = {}
    for tier, agent in plan["tiers_to_probe"].items():
        time.sleep(EDGE_PROBE_DELAY_SECONDS)
        agent_results[tier] = probe_with_user_agent(base_url_value + "/", agent)

    findings, unknowns = interpret_edge_results(plan, baseline_classification, agent_results)
    return findings, unknowns, groups
