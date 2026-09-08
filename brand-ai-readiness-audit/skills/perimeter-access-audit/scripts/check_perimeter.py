#!/usr/bin/env python3
"""Gate-1 perimeter audit: can AI crawlers reach the site at all?

Owns four capabilities:
  PER-01  AI-crawler access across the three-tier bot taxonomy (robots.txt)
  PER-02  Blanket-block anti-pattern (every AI agent disallowed at the root)
  PER-03  CDN/WAF edge blocking — robots.txt allows, the edge answers 403 or a
          challenge. Live-only: it needs real requests under real bot user
          agents, so it runs from --url and never from --robots-file.
  PER-04  llms.txt presence and spec validity

Deliberately does NOT own: llms-full.txt payload depth, sitemap discovery,
`.md` content negotiation. Those need a crawl and belong to sibling skills.

PER-03's compliance rule, binding and enforced in code (`plan_edge_probes`):
never probe an agent robots.txt already disallows. Two reasons, both hard
requirements rather than politeness — sending that request would itself
violate "respect robots.txt", and it would write a hit from that agent's exact
UA string into the target's own bot-traffic logs under a name it explicitly
excluded. This is why PER-03 needs the same parsed robots.txt groups PER-01
computes: the two checks share the compliance boundary, not just the taxonomy.

Bot-taxonomy accelerator
------------------------
`_baseline_bot_taxonomy()` loads the vendored snapshot at
`vendor/bot_taxonomy.json` (175 bots, MIT, see vendor/VENDORED.md) and
`resolve_bot_tiers()` widens BOT_TIERS with it, case-insensitively
deduplicated so the same bot can never end up double-counted across two
tiers. It degrades to None — falling back to BOT_TIERS alone — if the file is
missing or unparseable, so a corrupted or absent snapshot never breaks an
audit run. The 15 original bot->tier assignments always win over the
snapshot's own classification for the same bot name: the snapshot can only
add bots BOT_TIERS doesn't already name, never override one.

`resolve_bot_tiers()` is deliberately NOT called by PER-01/PER-02/C1 (see
`evaluate_robots`, `_is_blanket_blocked`, `_c1_sitemap_url_ai_disallowed`,
which all use BOT_TIERS directly): widening those checks' bot list to all 175
makes "blocks every AI agent" require blocking every obscure one, so a
robots.txt that blocks the ~15 well-known bots — the realistic real-world
"block all AI" pattern — would silently stop tripping the critical PER-02
finding at all. Explicit user decision, cycle 24: keep PER-01/PER-02/C1's
threshold on the 15 curated bots; `resolve_bot_tiers()` stays available as a
tested, correct seam for a future capability that wants the wider list.

Determinism
-----------
Every evaluation is a pure function of the fetched text. No randomness, no
clock, no ordering by dict iteration. The same robots.txt always yields the
same findings in the same order.

Safety
------
Read-only. Two GETs (`/robots.txt`, `/llms.txt`) plus, in `--url` mode, at most
four more for PER-03 (one reachability control plus one per bot tier, fewer
whenever robots.txt already covers a tier) — six requests total, worst case, to
one path each. No query strings, no credentials, no form submission, no
redirect chasing past the standard urllib limit. A short delay separates the
PER-03 probes so they never burst. The fetched text is parsed as data only; it
is never executed and never forwarded anywhere that interprets instructions.
The PER-03 probes send real bot user-agent strings on purpose — that is the
only way to observe edge-layer behaviour that diverges from robots.txt — plus
an `X-Audit-Purpose` header naming this as a read-only accessibility check, so
the request is honest about what sent it even while it wears a bot's identity
to test how that bot would be treated.

Usage:
    check_perimeter.py --url https://example.com
    check_perimeter.py --site example.com --robots-file R.txt --llms-file L.txt
    check_perimeter.py --site example.com --robots-file R.txt --llms-absent

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...],
     "findings": [...], "unknown_checks": [...]}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.robotparser import RobotFileParser

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SEVERITIES, SuggestedAction, UnknownCheck  # noqa: E402
from text_spans import extract_blocks  # noqa: E402
from jsonld_graph import flatten  # noqa: E402

OWNER_SKILL = "perimeter-access-audit"
CAPABILITY_IDS = [
    "PER-01", "PER-02", "PER-03", "PER-04", "PER-05", "PER-06",
    "PER-07", "PER-08", "PER-09", "PER-10", "PER-11",
]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
EDGE_PROBE_DELAY_SECONDS = 0.3

# Three tiers, because a block on one tier means something different from a
# block on another. Collapsing them into "AI bots" is what produces both false
# alarms and missed critical failures. See references/ai-bot-taxonomy.md.
BOT_TIERS: dict[str, tuple[str, ...]] = {
    "training": (
        "GPTBot",
        "ClaudeBot",
        "Google-Extended",
        "CCBot",
        "Applebot-Extended",
        "meta-externalagent",
        "Bytespider",
    ),
    "ai_search": (
        "OAI-SearchBot",
        "PerplexityBot",
        "Claude-SearchBot",
        "DuckAssistBot",
    ),
    "on_demand": (
        "ChatGPT-User",
        "Claude-User",
        "Perplexity-User",
        "Meta-ExternalFetcher",
    ),
}

TIER_LABELS = {
    "training": "model-training crawlers",
    "ai_search": "real-time AI search crawlers",
    "on_demand": "on-demand user-triggered fetchers",
}

# Severity is derived from the causal chain, not from how alarming the block
# looks. Each entry states the chain it is claiming.
TIER_SEVERITY = {
    # Blocking these removes the site from the live retrieval pass that builds
    # cited answers. Direct, immediate, and the reason gate 1 exists.
    "ai_search": ("critical", "high"),
    # A user asked the assistant to open this specific page. Providers often
    # treat that as user-directed access rather than crawling, so a disallow
    # here is less reliably decisive than it looks.
    "on_demand": ("high", "medium"),
    # Affects what the model absorbs into parametric memory over time, not
    # whether today's answer can cite the page — and it is frequently a
    # deliberate content-licensing decision, not a defect.
    "training": ("medium", "high"),
}

TIER_MECHANISM = {
    "ai_search": (
        "Assistants that answer with citations run a live retrieval pass with these "
        "user agents. A disallow stops the fetch, and a page that is never fetched "
        "cannot be quoted or linked, however good its content is."
    ),
    "on_demand": (
        "These agents fetch one URL because a user asked the assistant to open it. "
        "Providers vary in whether they treat that as user-directed access outside "
        "crawl rules, so a disallow here degrades — rather than reliably prevents — "
        "the brand appearing when a user pastes or names one of its pages."
    ),
    "training": (
        "These crawlers gather text for future model training, so a disallow shapes "
        "what a model knows about the brand without being prompted. It does not stop "
        "today's cited answers. Blocking them can be a deliberate licensing position; "
        "it is only a defect if the brand also expects assistants to know it unprompted."
    ),
}


_DEFAULT_BOT_TAXONOMY_PATH = _REPO_ROOT / "vendor" / "bot_taxonomy.json"


def _baseline_bot_taxonomy(*, path: Path | None = None) -> dict[str, tuple[str, ...]] | None:
    """Load the vendored bot-taxonomy snapshot, or None if unavailable.

    Degrades, never raises: a missing file, unreadable file, or malformed/
    unexpected JSON shape all fall through to None so `resolve_bot_tiers`
    falls back to BOT_TIERS alone — matching `shared/public_suffix.py`'s
    degrade-never-raise pattern for the other vendored data asset.
    """
    try:
        text = (path or _DEFAULT_BOT_TAXONOMY_PATH).read_text(encoding="utf-8")
        data = json.loads(text)
        tiers = data["tiers"]
        return {tier: tuple(bots) for tier, bots in tiers.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def resolve_bot_tiers() -> dict[str, tuple[str, ...]]:
    """BOT_TIERS widened with the vendored snapshot. Case-insensitive
    dedup, global across all tiers, not just within one: the raw snapshot
    lists the same bot in two different tiers under different casing
    (e.g. "meta-externalagent" in training, "Meta-ExternalAgent" in
    on_demand) — a real classification conflict in the upstream data, not a
    project bug, but robots.txt product tokens are matched case-insensitively
    (RFC 9309), so treating those as two different bots would double-count
    one crawler under two tiers. First tier claiming a name (builtin tiers
    always claim first) keeps it; every later duplicate is dropped."""
    accelerated = _baseline_bot_taxonomy()
    if not accelerated:
        return BOT_TIERS
    claimed = {bot.lower() for bots in BOT_TIERS.values() for bot in bots}
    merged: dict[str, tuple[str, ...]] = {}
    for tier, builtin in BOT_TIERS.items():
        extra: list[str] = []
        for bot in sorted(accelerated.get(tier, ())):
            key = bot.lower()
            if key in claimed:
                continue
            claimed.add(key)
            extra.append(bot)
        merged[tier] = builtin + tuple(extra)
    return merged


_MAX_DECOMPRESSED_BYTES = 20_000_000


def decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Undo Content-Encoding before the body is treated as text.

    `urllib.request` never auto-decompresses (unlike `requests`), and some
    CDNs gzip responses regardless of whether the client's Accept-Encoding
    advertised support for it — observed live against python.org: raw gzip
    bytes were decoded as UTF-8 text and treated as robots.txt/llms.txt
    content, producing binary garbage that every downstream check kept
    processing rather than failing loudly on, because nothing checked for
    this. Bounded to guard against a decompression-bomb response.
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


def _bounded_decompress(decompressor, raw: bytes) -> bytes:
    output = decompressor.decompress(raw, _MAX_DECOMPRESSED_BYTES)
    if decompressor.unconsumed_tail:
        raise ValueError(f"decompressed body exceeds {_MAX_DECOMPRESSED_BYTES} bytes")
    return output + decompressor.flush()


def _best_effort_decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Lenient variant for `probe_with_user_agent`, which reads a truncated
    4096-byte prefix for classification purposes only — a truncated gzip
    stream can legitimately fail to decompress even though the response was
    fine. Falls back to the raw bytes (today's behaviour) rather than
    treating a decompression hiccup on a deliberately-truncated read as a
    fetch failure; `classify_response`'s "ambiguous" path already covers text
    that fails to look like anything recognisable."""
    try:
        return decode_content_encoding(raw, content_encoding)
    except Exception:
        return raw


def parse_groups(robots_text: str) -> list[tuple[set[str], list[str]]]:
    """Split robots.txt into (user-agent tokens, rule lines) groups.

    Group *selection* is ours; rule *evaluation* stays with the standard
    library. `urllib.robotparser` selects a group by substring — its
    `applies_to` asks whether a group's token appears anywhere inside the
    crawler name — so a group written for the historical `Fetch` bot captures
    `Meta-ExternalFetcher`, and one written for `Claude` would capture
    `Claude-User`. Measured on a real site, that produced a confident,
    completely wrong "this agent is blocked" finding.

    RFC 9309 matches the product token case-insensitively and exactly, with
    `*` as the fallback group. That is what this does.
    """
    groups: list[tuple[set[str], list[str]]] = []
    agents: set[str] = set()
    rules: list[str] = []
    previous_was_agent = False

    for raw_line in robots_text.splitlines():
        line = raw_line.split("#", 1)[0].strip().lstrip("﻿")
        if not line or ":" not in line:
            continue
        field, value = line.split(":", 1)
        field, value = field.strip().lower(), value.strip()

        if field == "user-agent":
            if rules and previous_was_agent is False and agents:
                groups.append((agents, rules))
                agents, rules = set(), []
            agents.add(value.lower())
            previous_was_agent = True
        elif field in ("allow", "disallow"):
            if agents:
                rules.append(f"{field.capitalize()}: {value}")
            previous_was_agent = False
        else:
            previous_was_agent = False

    if agents:
        groups.append((agents, rules))
    return groups


def can_fetch_root(groups: list[tuple[set[str], list[str]]], agent: str) -> bool:
    """Whether `agent` may fetch `/`, using exact-token group selection.

    Rule evaluation — path matching, Allow/Disallow precedence — is delegated
    to the standard library by handing it only the group that actually applies.
    """
    token = agent.lower()
    applicable = [rules for tokens, rules in groups if token in tokens]
    if not applicable:
        applicable = [rules for tokens, rules in groups if "*" in tokens]
    if not applicable:
        return True

    lines = [f"User-agent: {agent}"]
    for rules in applicable:
        lines.extend(rules)
    parser = RobotFileParser()
    parser.parse(lines)
    return parser.can_fetch(agent, "/")


def can_fetch_path(groups: list[tuple[set[str], list[str]]], agent: str, path: str) -> bool:
    """Same group-selection contract as `can_fetch_root`, generalised to an
    arbitrary path. PER-09's C1 needs to know whether a *specific*
    sitemap-declared URL is blocked, not just the root — a site can allow an
    agent at `/` while disallowing the one path a sitemap actually lists.
    Kept as its own function rather than refactoring `can_fetch_root` to call
    it, so PER-01/02/03 (already frozen, already regression-tested) cannot
    regress from a PER-09 change."""
    token = agent.lower()
    applicable = [rules for tokens, rules in groups if token in tokens]
    if not applicable:
        applicable = [rules for tokens, rules in groups if "*" in tokens]
    if not applicable:
        return True

    lines = [f"User-agent: {agent}"]
    for rules in applicable:
        lines.extend(rules)
    parser = RobotFileParser()
    parser.parse(lines)
    return parser.can_fetch(agent, path or "/")


def evaluate_robots(robots_text: str | None, status: str) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-01 and PER-02 against robots.txt content.

    status:
      "present"     — fetched, body is `robots_text`
      "absent"      — 404/410. Under the exclusion protocol this permits
                      everything, so it is not a finding.
      "unavailable" — timeout, 5xx, DNS failure. Not knowable, so both checks
                      report unknown rather than guessing either way.
    """
    if status == "unavailable":
        reason = robots_text or "robots.txt could not be fetched"
        return [], [
            UnknownCheck("PER-01", OWNER_SKILL, reason),
            UnknownCheck("PER-02", OWNER_SKILL, reason),
        ]
    if status == "absent":
        return [], []

    groups = parse_groups(robots_text or "")

    tiers = BOT_TIERS
    blocked: dict[str, list[str]] = {}
    allowed: dict[str, list[str]] = {}
    for tier, bots in tiers.items():
        blocked[tier] = [bot for bot in bots if not can_fetch_root(groups, bot)]
        allowed[tier] = [bot for bot in bots if can_fetch_root(groups, bot)]

    total_bots = sum(len(bots) for bots in tiers.values())
    total_blocked = sum(len(bots) for bots in blocked.values())
    wildcard_blocks_root = not can_fetch_root(groups, "*")

    if total_blocked == total_bots:
        return [_blanket_block_finding(tiers, wildcard_blocks_root, total_bots)], []

    findings = [
        _tier_finding(tier, blocked[tier], allowed[tier], len(tiers[tier]))
        for tier in ("ai_search", "on_demand", "training")
        if blocked[tier]
    ]
    return findings, []


def _blanket_block_finding(
    tiers: dict[str, tuple[str, ...]],
    wildcard_blocks_root: bool,
    total_bots: int,
) -> Finding:
    """PER-02. One finding, not three — the tier distinction is moot when every
    tier is blocked, and three findings for one root cause is report noise."""
    named = ", ".join(bot for tier in ("ai_search", "on_demand", "training") for bot in tiers[tier])
    if wildcard_blocks_root:
        title = "robots.txt blocks every crawler at the site root"
        evidence = (
            f"robots.txt disallows / for the wildcard user-agent group, so all {total_bots} "
            f"AI user agents checked are blocked: {named}."
        )
        summary = (
            "Replace the site-wide `Disallow: /` with rules that block only the paths that "
            "genuinely must stay private, so public pages stay reachable."
        )
        mechanism = (
            "A root-level disallow for the wildcard group removes the whole site from every "
            "compliant crawler, AI assistants included. This is the correct configuration for "
            "a staging host and a total loss of visibility for a production one."
        )
    else:
        title = "robots.txt blocks every AI assistant while allowing conventional crawlers"
        evidence = (
            f"robots.txt disallows / for all {total_bots} AI user agents checked across the "
            f"training, AI-search and on-demand tiers ({named}), while the wildcard group is "
            "not blocked at the root."
        )
        summary = (
            "Allow the AI-search and on-demand tiers (OAI-SearchBot, PerplexityBot, "
            "Claude-SearchBot, DuckAssistBot, ChatGPT-User, Claude-User, Perplexity-User, "
            "Meta-ExternalFetcher) at the root, and keep training-crawler rules only if "
            "blocking them is a deliberate licensing decision."
        )
        mechanism = (
            "This configuration reads as one decision but has two very different effects. "
            "Blocking training crawlers withholds content from future models. Blocking the "
            "AI-search and on-demand tiers removes the brand from answers being generated "
            "right now, with citations, for users already asking about it — while surrendering "
            "nothing in return, because these crawlers are low-volume and carry no meaningful "
            "bandwidth cost."
        )
    return Finding(
        id="PER-02-all-ai-agents-blocked",
        title=title,
        severity="critical",
        evidence=evidence,
        suggested_action=SuggestedAction(
            summary=summary,
            priority="critical",
            details=(
                "Verify the change with a robots.txt tester for each named user agent before "
                "and after. Blocking is enforced per user-agent group, so a rule under a "
                "wildcard group does not have to be repeated per bot unless it differs."
            ),
        ),
        category="discoverability",
        capability_id="PER-02",
        owner_skill=OWNER_SKILL,
        mechanism=mechanism,
        gate=1,
        confidence="high",
        structured_evidence={
            "blocked_bots": {tier: list(bots) for tier, bots in tiers.items()},
            "wildcard_blocks_root": wildcard_blocks_root,
            "bots_checked": total_bots,
        },
    )


def _tier_finding(tier: str, blocked: list[str], allowed: list[str], tier_size: int) -> Finding:
    """PER-01. One finding per affected tier, listing exactly which agents."""
    severity, confidence = TIER_SEVERITY[tier]
    label = TIER_LABELS[tier]
    evidence = (
        f"robots.txt disallows / for {len(blocked)}/{tier_size} {label}: "
        f"{', '.join(blocked)}."
    )
    if allowed:
        evidence += f" Still allowed in this tier: {', '.join(allowed)}."

    if tier == "training":
        summary = (
            f"Decide explicitly whether blocking {', '.join(blocked)} is intended. If the brand "
            "wants assistants to describe it without being handed a URL, remove the disallow "
            "for these agents; if the block is a licensing position, keep it and make sure the "
            "AI-search tier stays allowed."
        )
    else:
        summary = (
            f"Remove the `Disallow: /` under the {', '.join(blocked)} user-agent group(s) in "
            "robots.txt, keeping any path-level rules that protect genuinely private areas."
        )

    return Finding(
        id=f"PER-01-{tier.replace('_', '-')}-blocked",
        title=f"robots.txt blocks {label} ({len(blocked)} of {tier_size})",
        severity=severity,
        evidence=evidence,
        suggested_action=SuggestedAction(
            summary=summary,
            priority=severity,
            details=(
                "Scope the rule to paths rather than to the whole site where the intent is to "
                "protect a section: `Disallow: /internal/` costs nothing in visibility, "
                "`Disallow: /` costs all of it."
            ),
        ),
        category="discoverability",
        capability_id="PER-01",
        owner_skill=OWNER_SKILL,
        mechanism=TIER_MECHANISM[tier],
        gate=1,
        confidence=confidence,
        structured_evidence={"tier": tier, "blocked": blocked, "allowed": allowed},
    )


# One representative agent per tier. Probing all fifteen would multiply
# request volume for signal CDN rulesets rarely provide — edge bot-management
# products typically block by vendor category ("AI crawlers"), not by
# individually enumerated agent — so one probe per tier is the cheap,
# considerate design, stated here as a chosen tradeoff rather than hidden.
# Chosen because each is the most commonly named agent in published CDN
# AI-bot-blocking rule sets for its tier.
REPRESENTATIVE_AGENTS: dict[str, str] = {
    "ai_search": "OAI-SearchBot",
    "on_demand": "ChatGPT-User",
    "training": "GPTBot",
}

# An ordinary browser UA, used only as a reachability control: is the origin up
# at all, for a request that carries no AI-bot identity? Without this, "the AI
# bot got a 403" and "the whole site is down right now" are indistinguishable,
# and reporting the former when the truth is the latter is a false positive.
CONTROL_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

AUDIT_PURPOSE_HEADER = "read-only accessibility audit; single GET; no data collected; see brand-ai-readiness-audit"

# Status codes that name a deliberate access decision. 5xx and other errors are
# excluded on purpose: a 500 is at least as likely to be an origin fault as a
# bot-specific block, and asserting a block from an ambiguous status would be
# exactly the false-positive-of-severity failure this project tests against.
EDGE_BLOCK_STATUS_CODES = (403, 429)

# A CDN challenge page often returns 200 with a JS/CAPTCHA interstitial rather
# than a 4xx. These are the markers of the major bot-management vendors' stock
# challenge pages. A body match is a weaker signal than a status code, so it is
# reported at reduced confidence (see `_edge_block_finding`).
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
)


def classify_response(status: int | None, body: str) -> str:
    """Pure classifier: HTTP status + body -> "ok" | "blocked" | "challenge" |
    "ambiguous". No network I/O, so this is the part of PER-03 that is unit
    tested directly with fixed inputs."""
    lowered = body.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        return "challenge"
    if status in EDGE_BLOCK_STATUS_CODES:
        return "blocked"
    if status is not None and 200 <= status < 300:
        return "ok"
    return "ambiguous"


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


def evaluate_llms_txt(llms_text: str | None, status: str) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-04. Presence and structural validity of /llms.txt.

    Severity is capped at `low` and the track is `proactive`, deliberately.
    Server-log studies consistently show AI crawlers fetching robots.txt orders
    of magnitude more often than llms.txt, and no major provider has committed
    to consuming it in production. Calling its absence a defect would assert a
    causal claim the evidence does not support. It is recommended as a
    forward-compatibility and agentic-retrieval measure, which is what the
    evidence does support.
    """
    if status == "unavailable":
        reason = llms_text or "llms.txt could not be fetched"
        return [], [UnknownCheck("PER-04", OWNER_SKILL, reason)]

    if status == "absent":
        return [_llms_missing_finding()], []

    if _looks_like_html(llms_text or ""):
        # A soft 404: the host answers an unknown path with its own HTML page.
        # No llms.txt is published, so report the absence. Calling this a
        # malformed llms.txt would diagnose a file the site never wrote.
        return [_llms_missing_finding(soft_404=True)], []

    problems = _llms_structure_problems(llms_text or "")
    if not problems:
        return [], []
    return [_llms_malformed_finding(problems, llms_text or "")], []


def _looks_like_html(text: str) -> bool:
    head = text.lstrip().lstrip("﻿").lower()[:400]
    if head.startswith(("<!doctype html", "<html")):
        return True
    return "<head" in head or "<body" in head


def _llms_structure_problems(text: str) -> list[str]:
    """Structural gaps against the llms.txt convention, in fixed order."""
    lines = [line.strip() for line in text.splitlines()]
    problems: list[str] = []
    if not any(line.startswith("# ") for line in lines):
        problems.append("no H1 title line (`# Name`)")
    if not any(line.startswith("> ") for line in lines):
        problems.append("no blockquote summary line (`> one-sentence description`)")
    if not any(line.startswith("## ") for line in lines):
        problems.append("no `##` section headings grouping the links")
    # `-`, `*` and `+` are the same list marker in Markdown. Accepting only one
    # of them reported a correctly formatted real-world file as malformed.
    link_lines = [
        line
        for line in lines
        if line[:2] in ("- ", "* ", "+ ") and "[" in line and "](" in line
    ]
    if not link_lines:
        problems.append("no markdown link list entries (`- [Title](url): description`)")
    elif not any("):" in line for line in link_lines):
        problems.append("link entries carry no description after the URL")
    return problems


def _llms_missing_finding(soft_404: bool = False) -> Finding:
    evidence = (
        "GET /llms.txt returned an HTML page rather than a text file, so the host is "
        "answering an unknown path with its own markup (a soft 404). No llms.txt is published."
        if soft_404
        else "GET /llms.txt returned no file (404)."
    )
    return Finding(
        id="PER-04-llms-txt-missing",
        title="No llms.txt published",
        severity="low",
        evidence=evidence,
        suggested_action=SuggestedAction(
            summary=(
                "Publish /llms.txt: an H1 with the brand name, a one-sentence blockquote "
                "summary, then `##` sections listing the canonical documentation, product and "
                "contact URLs, each link followed by a short description."
            ),
            priority="low",
            details=(
                "Keep it a curated index of the pages the brand wants quoted, not a mirror of "
                "the sitemap. Its value is highest for documentation and developer-facing "
                "sites, where user-configured agents and IDE tools do fetch it."
            ),
        ),
        category="discoverability",
        capability_id="PER-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "llms.txt is a curated, machine-readable map of a site's most quotable pages. "
            "Measured crawler traffic to it remains a rounding error next to robots.txt, and "
            "no major assistant has committed to consuming it, so this is a low-cost "
            "forward-compatibility measure and an aid to user-configured agents — not a "
            "citation lever. It is reported as a suggestion, not a defect, for that reason."
        ),
        track="proactive",
        gate=1,
        confidence="high",
    )


def _llms_malformed_finding(problems: list[str], text: str) -> Finding:
    return Finding(
        id="PER-04-llms-txt-malformed",
        title="llms.txt is published but does not follow the convention",
        severity="low",
        evidence=(
            f"/llms.txt exists ({len(text.splitlines())} lines) but has "
            f"{len(problems)} structural gap(s): {'; '.join(problems)}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Repair the file to the convention: `# Brand`, a `> summary` blockquote, then "
                "`##` sections whose entries are `- [Title](url): what this page covers`."
            ),
            priority="low",
            details=(
                "A file that parsers cannot read is worth less than no file, because it "
                "signals support the site does not actually provide."
            ),
        ),
        category="discoverability",
        capability_id="PER-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "The convention exists so an agent can pick out titles, URLs and descriptions "
            "without parsing HTML. Missing the H1, the summary blockquote or the annotated "
            "link entries removes the parts that make it machine-readable, leaving a file "
            "that costs maintenance and returns nothing."
        ),
        track="proactive",
        gate=1,
        confidence="high",
        structured_evidence={"problems": problems},
    )


# ---------------------------------------------------------------------------
# PER-05 — llms-full.txt ingestion audit
# ---------------------------------------------------------------------------

MIN_LLMS_FULL_WORDS = 50


def evaluate_llms_full_txt(text: str | None, status: str) -> tuple[list[Finding], list[UnknownCheck]]:
    """llms-full.txt is llms.txt's companion: the concatenated full-text
    payload the curated index points to. Same calibration discipline as
    PER-04 — the evidence for citation impact is even thinner for this
    secondary, optional file than for llms.txt itself, so both outcomes stay
    `low` severity and `proactive` track, never asserted as a defect."""
    if status == "unavailable":
        reason = text or "llms-full.txt could not be fetched"
        return [], [UnknownCheck("PER-05", OWNER_SKILL, reason)]
    if status == "absent":
        return [], []  # optional companion file; absence alone is not worth a proactive note on its own

    word_count = len((text or "").split())
    if word_count < MIN_LLMS_FULL_WORDS:
        return [
            Finding(
                id="PER-05-llms-full-txt-thin",
                title="llms-full.txt exists but carries very little content",
                severity="low",
                evidence=f"/llms-full.txt exists but contains only {word_count} word(s).",
                suggested_action=SuggestedAction(
                    summary="Populate llms-full.txt with the full text of the pages llms.txt indexes, or remove the file if it is a stub.",
                    priority="low",
                ),
                category="discoverability",
                capability_id="PER-05",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "llms-full.txt exists specifically to hand an agent the full page text in one "
                    "fetch. A near-empty file costs the same maintenance as a real one and gives "
                    "an agent that does fetch it nothing usable in return."
                ),
                track="proactive",
                gate=1,
                confidence="medium",
                structured_evidence={"word_count": word_count},
            )
        ], []
    return [], []


# ---------------------------------------------------------------------------
# PER-06 — sitemap.xml discovery audit
# ---------------------------------------------------------------------------

# Regex, not xml.etree: this parses a remote, untrusted response. A regex has
# no entity-expansion surface at all, so "billion laughs" / external-entity
# attacks that a naive XML parser can be vulnerable to are structurally not a
# concern here — the same reasoning that kept JSON-LD parsing on `json.loads`
# (safe by construction) and HTML parsing on a restricted `HTMLParser`
# elsewhere in this marketplace, rather than reaching for a fuller parser.
_SITEMAP_ROOT_PATTERN = re.compile(r"<\s*(?:\w+:)?(urlset|sitemapindex)\b", re.IGNORECASE)
_SITEMAP_LOC_PATTERN = re.compile(r"<loc>\s*([^<\s][^<]*)</loc>", re.IGNORECASE)


def evaluate_sitemap(text: str | None, status: str) -> tuple[list[Finding], list[UnknownCheck]]:
    if status == "unavailable":
        reason = text or "sitemap.xml could not be fetched"
        return [], [UnknownCheck("PER-06", OWNER_SKILL, reason)]

    if status == "absent":
        return [
            Finding(
                id="PER-06-sitemap-missing",
                title="No sitemap.xml found",
                severity="medium",
                evidence="GET /sitemap.xml returned no file (404).",
                suggested_action=SuggestedAction(
                    summary="Publish a sitemap.xml listing the site's canonical URLs, and reference it from robots.txt.",
                    priority="medium",
                ),
                category="discoverability",
                capability_id="PER-06",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "A sitemap is how a crawler finds pages that aren't reachable through a "
                    "short internal-link path. Without one, deep or orphaned pages — exactly the "
                    "fact-dense ones a query might target — may never be discovered at all."
                ),
                gate=1,
                confidence="high",
            )
        ], []

    body = text or ""
    if not _SITEMAP_ROOT_PATTERN.search(body[:2000]):
        return [
            Finding(
                id="PER-06-sitemap-malformed",
                title="sitemap.xml does not look like a valid sitemap",
                severity="medium",
                evidence="GET /sitemap.xml returned content with no recognisable <urlset> or <sitemapindex> root element.",
                suggested_action=SuggestedAction(
                    summary="Serve a sitemap.xml that follows the sitemaps.org XML format, or fix the endpoint if it is returning an error page.",
                    priority="medium",
                ),
                category="discoverability",
                capability_id="PER-06",
                owner_skill=OWNER_SKILL,
                mechanism="A sitemap a crawler cannot recognise as a sitemap is equivalent to having none, at the cost of the maintenance and the misleading URL.",
                gate=1,
                confidence="medium",
            )
        ], []

    urls = _SITEMAP_LOC_PATTERN.findall(body)
    if not urls:
        return [
            Finding(
                id="PER-06-sitemap-empty",
                title="sitemap.xml is valid but lists no URLs",
                severity="medium",
                evidence="GET /sitemap.xml has a valid <urlset>/<sitemapindex> root but contains zero <loc> entries.",
                suggested_action=SuggestedAction(
                    summary="Populate the sitemap with the site's canonical URLs, or remove it if it is a leftover stub.",
                    priority="medium",
                ),
                category="discoverability",
                capability_id="PER-06",
                owner_skill=OWNER_SKILL,
                mechanism="An empty sitemap provides no discovery benefit over having none, while still claiming to be authoritative about the site's URL set.",
                gate=1,
                confidence="high",
            )
        ], []

    return [], []


# ---------------------------------------------------------------------------
# PER-07 — Markdown content negotiation
# ---------------------------------------------------------------------------


def evaluate_md_negotiation(text: str | None, status: str) -> tuple[list[Finding], list[UnknownCheck]]:
    """Whether the site serves a `.md` variant of a page under simple path
    negotiation (`/page` -> `/page.md`). Emerging and speculative — like
    llms.txt, framed as a proactive, low-cost, forward-compatibility measure,
    never as a defect, because most of the web does not do this yet and
    absence carries no established citation cost."""
    if status == "unavailable":
        reason = text or ".md variant could not be checked"
        return [], [UnknownCheck("PER-07", OWNER_SKILL, reason)]

    if status == "present" and not _looks_like_html(text or ""):
        return [], []  # a real markdown/text variant is being served — nothing to suggest

    # "absent" (404), or "present" but the response is a soft-404 HTML page
    return [
        Finding(
            id="PER-07-no-md-negotiation",
            title="No Markdown variant available via simple path negotiation",
            severity="low",
            evidence="Requesting this page's URL with a `.md` suffix did not return a Markdown/plain-text variant.",
            suggested_action=SuggestedAction(
                summary="Consider serving a `.md` (or plain-text) variant of key pages at `<path>.md`, a low-cost way for agents to fetch clean content without HTML stripping.",
                priority="low",
            ),
            category="discoverability",
            capability_id="PER-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A Markdown variant removes the need for an agent to extract text from HTML at "
                "all, eliminating boilerplate and markup noise in one fetch. Few sites do this "
                "yet, so this is a forward-compatibility suggestion, not a defect — most pages "
                "score the same as most of the web here."
            ),
            track="proactive",
            gate=1,
            confidence="medium",
        )
    ], []


# ---------------------------------------------------------------------------
# PER-10 — RFC 9727 API catalog discovery
# ---------------------------------------------------------------------------


def _parse_api_catalog(text: str) -> tuple[list[dict] | None, list[str]]:
    """Parse an api-catalog body against RFC 9727 §3's `linkset` shape.

    Returns (entries, problems). `entries` is None when the document is not
    even a linkset object at all (invalid JSON, or no top-level `linkset`
    array) — there is nothing further to check. A non-None `entries` with a
    non-empty `problems` list means the document parsed but individual
    entries are missing the RFC's two required-in-practice fields.
    """
    try:
        parsed = json.loads(text or "")
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, ["response body is not valid JSON"]

    if not isinstance(parsed, dict):
        return None, ["response body is not a JSON object"]

    linkset = parsed.get("linkset")
    if not isinstance(linkset, list) or not linkset:
        return None, ['no top-level "linkset" array (RFC 9727 §3)']

    entries = [e for e in linkset if isinstance(e, dict)]
    if not entries:
        return None, ['"linkset" array contains no object entries']

    problems: list[str] = []
    missing_anchor = sum(1 for e in entries if not e.get("anchor"))
    missing_service_desc = sum(1 for e in entries if not e.get("service-desc"))
    if missing_anchor:
        problems.append(f'{missing_anchor} linkset entry(ies) missing required "anchor"')
    if missing_service_desc:
        problems.append(f'{missing_service_desc} linkset entry(ies) missing "service-desc"')
    return entries, problems


def evaluate_api_catalog(
    text: str | None, headers: dict[str, str] | None, status: str
) -> tuple[list[Finding], list[UnknownCheck]]:
    """RFC 9727's `/.well-known/api-catalog`: a machine-readable index of a
    site's API surface (OpenAPI specs, Agent-to-Agent cards) via
    `application/linkset+json`. Unlike llms.txt/`.md` negotiation, a
    published-but-wrong response is treated as a defect, not a suggestion —
    the RFC fixes the path and the media type exactly, so there is no
    judgement call in "this Content-Type does not match" the way there is
    in "this llms.txt could be better organized"."""
    if status == "unavailable":
        reason = text or "api-catalog could not be checked"
        return [], [UnknownCheck("PER-10", OWNER_SKILL, reason)]

    if status == "absent":
        return [], []  # a 2024 RFC with no adoption pressure yet; absence is not worth a suggestion

    if status == "present" and _looks_like_html(text or ""):
        # A same-origin soft-404 (an SPA's client-side-routing catch-all
        # answering every unmatched path with its index page, HTTP 200) is
        # not evidence anyone attempted this RFC — the dominant false
        # positive here would otherwise be "every site that hasn't adopted
        # a 2024 RFC yet" flagged as serving the wrong Content-Type.
        return [], []

    content_type = (headers or {}).get("content-type", "")
    if "application/linkset+json" not in content_type.lower():
        return [
            Finding(
                id="PER-10-api-catalog-wrong-content-type",
                title="api-catalog is served with the wrong Content-Type",
                severity="low",
                evidence=(
                    f"GET /.well-known/api-catalog returned Content-Type "
                    f"{content_type!r}, not the RFC 9727-required application/linkset+json."
                ),
                suggested_action=SuggestedAction(
                    summary="Serve /.well-known/api-catalog with Content-Type: application/linkset+json.",
                    priority="low",
                    details="Agent-to-Agent and API-discovery tooling that checks Content-Type strictly will not recognize this as a valid catalog even though the path exists.",
                ),
                category="discoverability",
                capability_id="PER-10",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "RFC 9727 fixes both the well-known path and the media type. A response at "
                    "the right path with the wrong Content-Type is unambiguously non-compliant, "
                    "not a style choice."
                ),
                track="defect",
                gate=1,
                confidence="high",
            )
        ], []

    entries, problems = _parse_api_catalog(text or "")
    if entries is None or problems:
        detail = "; ".join(problems) if problems else "unparseable linkset document"
        return [
            Finding(
                id="PER-10-api-catalog-malformed",
                title="api-catalog does not follow the RFC 9727 linkset structure",
                severity="low",
                evidence=f"/.well-known/api-catalog is served as application/linkset+json but {detail}.",
                suggested_action=SuggestedAction(
                    summary='Structure the body as {"linkset": [{"anchor": "<api base url>", "service-desc": [...]}]} per RFC 9727 §3.',
                    priority="low",
                    details="A present-but-malformed catalog is worse than a missing one — it signals support the site does not actually provide to anything that tries to parse it.",
                ),
                category="discoverability",
                capability_id="PER-10",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "Each linkset entry needs `anchor` (the described API's base URL) and "
                    "`service-desc` (links to its machine-readable description, e.g. an OpenAPI "
                    "document) to be usable by anything that consumes this catalog."
                ),
                track="defect",
                gate=1,
                confidence="high",
            )
        ], []

    return [], []


# ---------------------------------------------------------------------------
# PER-08 — AI-discoverability of the sitemap itself
# ---------------------------------------------------------------------------

_SITEMAP_DIRECTIVE_PATTERN = re.compile(r"(?im)^\s*sitemap\s*:", re.MULTILINE)


def evaluate_sitemap_discoverability(
    robots_text: str | None, robots_status: str, sitemap_status: str
) -> tuple[list[Finding], list[UnknownCheck]]:
    """Only meaningful once a sitemap is known to exist (PER-06 covers its
    absence); this asks whether robots.txt — the first place a crawler looks
    — actually points to it.

    `sitemap_status` distinguishes "confirmed absent" from "unknown" for a
    reason: collapsing both into "nothing to check" would silently drop a
    genuine unknown (the sitemap fetch failed, so applicability itself is
    unknown) into the same bucket as "PER-06 already covers this, correctly
    nothing to say" (the sitemap is confirmed absent). Only the latter is
    silent; the former is reported.
    """
    if sitemap_status == "absent":
        return [], []
    if sitemap_status == "unavailable":
        return [], [
            UnknownCheck(
                "PER-08",
                OWNER_SKILL,
                "sitemap.xml's status could not be determined, so its discoverability from robots.txt cannot be evaluated",
            )
        ]
    if robots_status == "unavailable":
        reason = robots_text or "robots.txt could not be fetched"
        return [], [UnknownCheck("PER-08", OWNER_SKILL, reason)]
    if robots_status == "present" and _SITEMAP_DIRECTIVE_PATTERN.search(robots_text or ""):
        return [], []

    return [
        Finding(
            id="PER-08-sitemap-not-in-robots",
            title="sitemap.xml exists but is not referenced from robots.txt",
            severity="low",
            evidence="A sitemap was found at /sitemap.xml, but robots.txt contains no `Sitemap:` directive pointing to it.",
            suggested_action=SuggestedAction(
                summary="Add `Sitemap: https://<site>/sitemap.xml` to robots.txt so crawlers that check there can find it without guessing the conventional path.",
                priority="low",
            ),
            category="discoverability",
            capability_id="PER-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "robots.txt is the first file a compliant crawler reads, and a `Sitemap:` "
                "directive there is the standard way to announce a sitemap's location. Without "
                "it, discovery depends on a crawler guessing the conventional `/sitemap.xml` "
                "path, which is common but not guaranteed."
            ),
            track="proactive",
            gate=1,
            confidence="high",
        )
    ], []


_LLMS_LINK_URL_PATTERN = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


_NON_PAGE_SUFFIXES = (".txt", ".json", ".xml")


def _normalized_host(url: str) -> str:
    host = urllib.parse.urlparse(url.strip()).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _normalized_url_key(url: str) -> tuple[str, str]:
    """(www.-stripped host, trailing-slash- and `.md`-suffix-stripped path)
    — the same www. equivalence citability-audit's `_strip_www` and
    entity-audit's ENT-04 fix already treat as "not a different URL". The
    `.md` strip was added live: llms.txt conventionally links a `.md`
    content-negotiation variant of a real page (PER-07's own concept), and
    the sitemap correctly lists the page under its real URL — confirmed on
    vercel.com and supabase.com, both of which do exactly this."""
    parsed = urllib.parse.urlparse(url.strip())
    path = parsed.path
    if path.endswith(".md"):
        path = path[: -len(".md")]
    path = path.rstrip("/") or "/"
    return _normalized_host(url), path


def evaluate_llms_sitemap_agreement(
    llms_text: str | None, llms_status: str, sitemap_text: str | None, sitemap_status: str
) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-08's second half. llms.txt is a curated subset of the site, never
    a mirror (PER-04's own mechanism note) — the sitemap having URLs
    llms.txt omits is the intended pattern, not a disagreement. The real
    inconsistency worth flagging runs the other way: a URL llms.txt curates
    that the sitemap doesn't know about at all, which means either a
    stale/wrong link in llms.txt, or a page the brand considers important
    enough to hand-curate that ordinary sitemap-based crawling can't
    discover.
    """
    if llms_status == "unavailable" or sitemap_status == "unavailable":
        return [], [
            UnknownCheck(
                "PER-08",
                OWNER_SKILL,
                "llms.txt or sitemap.xml status could not be determined, so their URL sets cannot be compared",
            )
        ]
    if llms_status != "present" or sitemap_status != "present":
        return [], []  # PER-04/PER-06 already cover either file's confirmed absence

    root_match = _SITEMAP_ROOT_PATTERN.search((sitemap_text or "")[:2000])
    if root_match and root_match.group(1).lower() == "sitemapindex":
        # A <sitemapindex>'s own <loc> entries are sub-sitemap URLs, not
        # pages — comparing against them flags nearly everything in
        # llms.txt as "missing" from a URL set that was never the site's
        # real page list. This project doesn't recurse into sub-sitemaps
        # (the same class of gap PER-06 already documents for
        # completeness), so an honest "cannot compare" beats a fabricated
        # finding built on the wrong data.
        return [], [
            UnknownCheck(
                "PER-08",
                OWNER_SKILL,
                "sitemap.xml is a <sitemapindex> of sub-sitemaps; this project does not recurse "
                "into them, so llms.txt's URL set cannot be compared against the site's real pages",
            )
        ]

    llms_urls = _LLMS_LINK_URL_PATTERN.findall(llms_text or "")
    sitemap_urls = _SITEMAP_LOC_PATTERN.findall(sitemap_text or "")
    if not llms_urls or not sitemap_urls:
        return [], []

    sitemap_host = _normalized_host(sitemap_urls[0])
    sitemap_keys = {_normalized_url_key(u) for u in sitemap_urls}

    def _is_comparable_page_link(url: str) -> bool:
        # llms.txt conventionally also links its own companion machine-
        # readable files (llms-full.txt, JSON/XML schemas) and sometimes a
        # wholly separate API-spec host — none of these are HTML pages a
        # sitemap is expected to list, so they are out of this check's
        # scope entirely rather than compared and found "missing". Caught
        # live on vercel.com (openapi.vercel.sh, taxonomy.json) and
        # supabase.com (per-language llms/*.txt files).
        if url.lower().split("?")[0].endswith(_NON_PAGE_SUFFIXES):
            return False
        return _normalized_host(url) == sitemap_host

    orphaned = [
        u
        for u in dict.fromkeys(llms_urls)
        if _is_comparable_page_link(u) and _normalized_url_key(u) not in sitemap_keys
    ]
    if not orphaned:
        return [], []

    shown = orphaned[:5]
    more = f" (+{len(orphaned) - 5} more)" if len(orphaned) > 5 else ""
    return [
        Finding(
            id="PER-08-llms-sitemap-disagreement",
            title="llms.txt links to URLs the sitemap doesn't list",
            severity="low",
            evidence=(
                f"llms.txt curates {len(orphaned)} URL(s) not present in sitemap.xml: "
                f"{', '.join(shown)}{more}."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Add these URLs to sitemap.xml, or fix/remove the links in llms.txt if the "
                    "pages have moved or no longer exist."
                ),
                priority="low",
            ),
            category="discoverability",
            capability_id="PER-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "llms.txt is a curated subset, so the sitemap having more URLs than it is "
                "expected — but a URL llms.txt curates that the sitemap doesn't know about at "
                "all is a real inconsistency the brand likely hasn't noticed, since the two "
                "files are usually maintained separately."
            ),
            track="defect",
            gate=1,
            confidence="medium",
            structured_evidence={"orphaned_urls": orphaned},
        )
    ], []


# ---------------------------------------------------------------------------
# PER-09 — Cross-layer access-signal contradiction
# ---------------------------------------------------------------------------

# The three crawlers TDMRep's own spec discussion names as the training
# crawlers a `tdm-reservation` signal is meant to reach. Kept separate from
# BOT_TIERS["training"] (which is broader, this project's own taxonomy) so
# C3's claim stays scoped to what TDMRep itself is understood to govern.
_TDM_RELEVANT_TRAINING_BOTS = ("GPTBot", "ClaudeBot", "CCBot")

_MAX_SITEMAP_URLS_CHECKED_FOR_C1 = 500

_NOINDEX_TOKENS = frozenset({"noindex", "none"})
_TDM_RESERVED_VALUES = frozenset({"1", "true", "yes"})


def _degrade_severity(severity: str) -> str:
    """One notch toward `low`. C1 borrows TIER_SEVERITY's causal-chain
    calibration but is a weaker claim than PER-01's (one path, not a whole
    tier), so it is reported one step down."""
    index = SEVERITIES.index(severity)
    return SEVERITIES[min(index + 1, len(SEVERITIES) - 1)]


def _tokenize_directive(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token.strip().lower() for token in value.split(",") if token.strip()}


class _HeadMetaParser(HTMLParser):
    """Collects `<meta name="robots">`, `<meta name="googlebot">`,
    `<meta name="noai">`/`<meta name="noimageai">`, and
    `<meta name="tdm-reservation">` from a page's `<head>`. Stops at
    `</head>` — nothing PER-09 needs lives in `<body>`, and stopping early
    keeps this cheap on large pages."""

    def __init__(self) -> None:
        super().__init__()
        self.robots_tokens: set[str] = set()
        self.googlebot_tokens: set[str] = set()
        self.noai = False
        self.noimageai = False
        self.tdm_reservation: str | None = None
        self._head_done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._head_done or tag != "meta":
            return
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        name = attr_map.get("name", "").strip().lower()
        content = attr_map.get("content", "")
        if name == "robots":
            self.robots_tokens |= _tokenize_directive(content)
        elif name == "googlebot":
            self.googlebot_tokens |= _tokenize_directive(content)
        elif name == "noai":
            self.noai = True
        elif name == "noimageai":
            self.noimageai = True
        elif name == "tdm-reservation":
            self.tdm_reservation = content.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._head_done = True


def parse_meta_directives(html: str) -> dict:
    """Pure parse of the `<head>` signals C2/C3/C4/C5 read. Never raises —
    malformed HTML yields whatever partial state `HTMLParser` collected
    before choking, the same best-effort posture every other HTML-parsing
    check in this marketplace takes."""
    parser = _HeadMetaParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    return {
        "robots_tokens": parser.robots_tokens,
        "googlebot_tokens": parser.googlebot_tokens,
        "noai": parser.noai or "noai" in parser.robots_tokens,
        "noimageai": parser.noimageai or "noimageai" in parser.robots_tokens,
        "tdm_reservation": parser.tdm_reservation,
    }


def fetch_tdmrep(url: str) -> tuple[dict | None, str]:
    """GET `/.well-known/tdmrep.json`. Same three-value status contract as
    `fetch_text`. Malformed JSON on a "present" fetch is treated as "no
    usable reservation signal", not a crash: returns (None, "present") — a
    present-but-broken file is still evidence the owner tried, which matters
    to C5's precision guard, so callers must not collapse it into "absent"."""
    text, status = fetch_text(url)
    if status != "present":
        return None, status
    try:
        parsed = json.loads(text or "")
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "present"
    return (parsed if isinstance(parsed, dict) else None), "present"


def _tdmrep_reserves(tdmrep_data: dict | None) -> bool:
    """TDMRep's `tdm-reservation` field, at the top level or nested under a
    `"policies"."default"` shape some real-world examples use. Deliberately
    shallow — this project claims reservation-signal detection, not full
    TDMRep spec compliance."""
    if not isinstance(tdmrep_data, dict):
        return False
    direct = tdmrep_data.get("tdm-reservation")
    if direct is None:
        direct = tdmrep_data.get("tdm_reservation")
    if direct is not None and str(direct).strip().lower() in _TDM_RESERVED_VALUES:
        return True
    policies = tdmrep_data.get("policies")
    if isinstance(policies, dict):
        default = policies.get("default")
        if isinstance(default, dict):
            value = default.get("tdm-reservation") or default.get("tdm_reservation")
            if value is not None and str(value).strip().lower() in _TDM_RESERVED_VALUES:
                return True
    return False


def _is_blanket_blocked(groups: list[tuple[set[str], list[str]]]) -> bool:
    """True when every AI agent this project tracks is blocked at the root —
    PER-02's condition, restated here so C1 can defer to it rather than
    restate the same root cause as a new contradiction. Uses BOT_TIERS, not
    the widened `resolve_bot_tiers()` snapshot — must stay the exact same
    bot list PER-02 itself uses, or this stops actually restating PER-02's
    condition."""
    tiers = BOT_TIERS
    for tier_bots in tiers.values():
        for bot in tier_bots:
            if can_fetch_root(groups, bot):
                return False
    return True


def _sitemap_urls_from_text(sitemap_text: str | None) -> list[str]:
    root_match = _SITEMAP_ROOT_PATTERN.search((sitemap_text or "")[:2000])
    if root_match and root_match.group(1).lower() == "sitemapindex":
        # A <sitemapindex>'s own <loc> entries are sub-sitemap URLs, not
        # pages — same "do not recurse, do not compare" posture PER-08 takes.
        return []
    return _SITEMAP_LOC_PATTERN.findall(sitemap_text or "")


def _llms_urls_from_text(llms_text: str | None) -> list[str]:
    return _LLMS_LINK_URL_PATTERN.findall(llms_text or "")


def _c1_sitemap_url_ai_disallowed(
    groups: list[tuple[set[str], list[str]]], sitemap_urls: list[str]
) -> Finding | None:
    """C1 — a sitemap-declared URL matches an AI-tier Disallow path rule.

    Overlap control with PER-01/PER-02: a bot only counts here if it CAN
    fetch the site root but CANNOT fetch this specific path — i.e. the block
    is path-specific. A bot already blocked at the root is PER-01/PER-02's
    finding, not a new PER-09 contradiction, and is excluded here even
    though it would trivially also fail the path check. Uses BOT_TIERS, not
    the widened `resolve_bot_tiers()` snapshot, to stay consistent with the
    exact bot list PER-01/PER-02 use for "already blocked at the root".
    """
    tiers = BOT_TIERS
    affected: list[tuple[str, str, list[str]]] = []  # (url, tier, blocked_bots)
    for url in sitemap_urls[:_MAX_SITEMAP_URLS_CHECKED_FOR_C1]:
        path = urllib.parse.urlsplit(url).path or "/"
        for tier, bots in tiers.items():
            blocked_bots = [
                bot
                for bot in bots
                if can_fetch_root(groups, bot) and not can_fetch_path(groups, bot, path)
            ]
            if blocked_bots:
                affected.append((url, tier, blocked_bots))

    if not affected:
        return None

    worst_tier = min(affected, key=lambda item: SEVERITIES.index(TIER_SEVERITY[item[1]][0]))[1]
    severity = _degrade_severity(TIER_SEVERITY[worst_tier][0])
    confidence = TIER_SEVERITY[worst_tier][1]

    shown = affected[:5]
    more = f" (+{len(affected) - 5} more)" if len(affected) > 5 else ""
    detail = "; ".join(f"{url} disallowed for {', '.join(bots)}" for url, _, bots in shown)

    return Finding(
        id="PER-09-sitemap-url-ai-disallowed",
        title="sitemap.xml lists a URL that robots.txt disallows for AI crawlers",
        severity=severity,
        evidence=(
            f"sitemap.xml declares {len(affected)} URL(s) that a path-level robots.txt rule "
            f"disallows for one or more AI-agent tiers, even though those same agents may "
            f"crawl the site root: {detail}{more}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Either remove these URLs from sitemap.xml or update the robots.txt path rule "
                "blocking them for AI agents, so the two files agree."
            ),
            priority=severity,
            details=(
                "A sitemap advertises a URL as canonical, indexable content. A robots.txt path "
                "rule blocking it for AI agents specifically tells those same agents to skip it."
            ),
        ),
        category="discoverability",
        capability_id="PER-09",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "sitemap.xml is how a crawler discovers a page is meant to be indexed; robots.txt "
            "path rules are enforced before any fetch happens. When a URL is in both the "
            "sitemap and a Disallow rule for the same agent, the Disallow always wins — the "
            "sitemap listing is a promise the site itself breaks."
        ),
        gate=1,
        confidence=confidence,
        structured_evidence={
            "affected": [{"url": url, "tier": tier, "blocked_bots": bots} for url, tier, bots in affected],
        },
    )


def _page_declared(url: str, sitemap_keys: set[tuple[str, str]], llms_keys: set[tuple[str, str]]) -> bool:
    key = _normalized_url_key(url)
    return key in sitemap_keys or key in llms_keys


def _c2_noindex_on_declared_url(
    page_results: list[dict], sitemap_urls: list[str], llms_urls: list[str]
) -> Finding | None:
    """C2 — a fetched page carries noindex/noai (header or meta) while being
    declared canonical in sitemap.xml or llms.txt."""
    sitemap_keys = {_normalized_url_key(u) for u in sitemap_urls}
    llms_keys = {_normalized_url_key(u) for u in llms_urls}
    affected: list[dict] = []
    for page in page_results:
        url = page["url"]
        headers = page.get("headers") or {}
        meta = page.get("meta") or {}
        header_tokens = _tokenize_directive(headers.get("x-robots-tag"))
        header_signal = bool(header_tokens & _NOINDEX_TOKENS) or "noai" in header_tokens
        meta_signal = bool(meta.get("robots_tokens", set()) & _NOINDEX_TOKENS) or bool(meta.get("noai"))
        if not (header_signal or meta_signal):
            continue
        if not _page_declared(url, sitemap_keys, llms_keys):
            continue
        affected.append(
            {
                "url": url,
                "x_robots_tag": headers.get("x-robots-tag"),
                "meta_robots": sorted(meta.get("robots_tokens", set())),
                "declared_in": "sitemap.xml" if _normalized_url_key(url) in sitemap_keys else "llms.txt",
            }
        )

    if not affected:
        return None

    shown = affected[:5]
    more = f" (+{len(affected) - 5} more)" if len(affected) > 5 else ""
    detail = "; ".join(
        f"{item['url']} ({item['declared_in']}, X-Robots-Tag: {item['x_robots_tag']!r})" for item in shown
    )

    return Finding(
        id="PER-09-noindex-on-declared-url",
        title="A page declared canonical carries a noindex/noai signal",
        severity="high",
        evidence=(
            f"{len(affected)} page(s) are declared in sitemap.xml or llms.txt as canonical "
            f"content, but respond with a noindex or noai signal: {detail}{more}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Remove the noindex/noai signal from these pages, or remove them from "
                "sitemap.xml/llms.txt if they are genuinely meant to be excluded."
            ),
            priority="high",
            details=(
                "The response header always wins over the meta tag, and both always win over "
                "the sitemap/llms.txt listing — a page's own response tells every compliant "
                "indexer to drop it, no matter what else advertises the page as canonical."
            ),
        ),
        category="discoverability",
        capability_id="PER-09",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A sitemap or llms.txt entry advertises a page as canonical content an AI answer "
            "engine should retrieve from. A noindex/noai signal on that same page's response "
            "instructs every compliant indexer to drop it. The site simultaneously advertises "
            "the page as content and instructs every indexer to remove it."
        ),
        gate=1,
        confidence="high",
        structured_evidence={"affected": affected},
    )


def _c3_tdm_reservation_contradicts_robots(
    groups: list[tuple[set[str], list[str]]], tdm_reserved: bool, tdm_source: str | None
) -> Finding | None:
    """C3 — a TDM reservation signal exists while robots.txt still allows
    one or more training-tier crawlers TDMRep is specifically meant to
    reach."""
    if not tdm_reserved:
        return None
    allowed_bots = [bot for bot in _TDM_RELEVANT_TRAINING_BOTS if can_fetch_root(groups, bot)]
    if not allowed_bots:
        return None

    return Finding(
        id="PER-09-tdm-reservation-contradicts-robots",
        title="TDM rights reserved, but robots.txt still allows training crawlers",
        severity="medium",
        evidence=(
            f"{tdm_source or 'A TDM reservation signal'} reserves text-and-data-mining rights, "
            f"but robots.txt still allows {', '.join(allowed_bots)} to crawl the site."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f"Add Disallow rules for {', '.join(allowed_bots)} in robots.txt if the TDM "
                "reservation is meant to be enforced, or drop the reservation if training access "
                "is actually intended."
            ),
            priority="medium",
            details=(
                "robots.txt and TDMRep answer different questions — 'may this be crawled' versus "
                "'may this be used for training' — and a site can be crawl-permissive and "
                "training-reserved at the same time without noticing, since nothing else checks "
                "the two together."
            ),
        ),
        category="discoverability",
        capability_id="PER-09",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "TDMRep expresses something robots.txt structurally cannot: 'index me, do not train "
            "on me.' A robots.txt that still allows GPTBot/ClaudeBot/CCBot to crawl while a TDM "
            "reservation signal is present leaves the reservation unenforced in practice, since "
            "crawling and training both happen through the same fetch these agents make."
        ),
        gate=1,
        confidence="medium",
        structured_evidence={"tdm_source": tdm_source, "allowed_training_bots": allowed_bots},
    )


def _c4_header_meta_robots_disagree(page_results: list[dict]) -> Finding | None:
    """C4 — X-Robots-Tag and `<meta name="robots">` both carry an explicit
    signal on the same page, and those signals disagree on noindex-ness.
    Requires both channels to be genuinely present and comparable — an
    absent meta tag is C2's contradiction (against sitemap/llms.txt), not
    this one."""
    affected: list[dict] = []
    for page in page_results:
        headers = page.get("headers") or {}
        meta = page.get("meta") or {}
        header_value = headers.get("x-robots-tag")
        meta_tokens = meta.get("robots_tokens", set())
        if not header_value or not meta_tokens:
            continue
        header_noindex = bool(_tokenize_directive(header_value) & _NOINDEX_TOKENS)
        meta_noindex = bool(meta_tokens & _NOINDEX_TOKENS)
        if header_noindex == meta_noindex:
            continue
        affected.append({"url": page["url"], "x_robots_tag": header_value, "meta_robots": sorted(meta_tokens)})

    if not affected:
        return None

    shown = affected[:5]
    more = f" (+{len(affected) - 5} more)" if len(affected) > 5 else ""
    detail = "; ".join(
        f"{item['url']} (header: {item['x_robots_tag']!r}, meta: {item['meta_robots']!r})" for item in shown
    )

    return Finding(
        id="PER-09-header-meta-robots-disagree",
        title='X-Robots-Tag header and <meta name="robots"> disagree',
        severity="medium",
        evidence=(
            f"{len(affected)} page(s) carry conflicting robots signals between the response "
            f"header and the page's own meta tag: {detail}{more}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                'Make the X-Robots-Tag header and the <meta name="robots"> tag agree — pick one '
                "source of truth and remove the other."
            ),
            priority="medium",
            details=(
                "The HTTP header is evaluated before the page body is even parsed, so it always "
                "wins. Content authors who only edit the page's meta tag usually do not know a "
                "server-level header is silently overriding it."
            ),
        ),
        category="discoverability",
        capability_id="PER-09",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A compliant indexer reads X-Robots-Tag first and does not need the page body to act "
            "on it. When the header and the in-page meta tag disagree, the header's instruction "
            "is what actually happens, regardless of what an editor sees or controls in the CMS."
        ),
        gate=1,
        confidence="high",
        structured_evidence={"affected": affected},
    )


def _c5_no_tdm_declaration(groups: list[tuple[set[str], list[str]]], tdmrep_status: str) -> Finding | None:
    """C5 — no TDM declaration exists anywhere, but robots.txt shows the site
    has already taken an explicit position on AI access (a named AI-agent
    group, not just the wildcard). Precision guard, per the plan: only
    suggest TDMRep to owners who have demonstrably already engaged with AI
    access, so this stays silent on every site that has never named an AI
    agent at all. Requires *confirmed* absence (`tdmrep_status == "absent"`,
    a real 404) — the default `"unavailable"` a caller that never attempted
    the fetch passes means "not known", not "missing", and must not be
    treated as a finding, matching PER-05..08's own default-is-unknown
    convention."""
    if tdmrep_status != "absent":
        return None
    all_ai_bots = {bot.lower() for bots in BOT_TIERS.values() for bot in bots}
    named_ai_groups = any(tokens & all_ai_bots for tokens, _rules in groups if "*" not in tokens)
    if not named_ai_groups:
        return None

    return Finding(
        id="PER-09-no-tdm-declaration",
        title="No TDMRep declaration, despite explicit AI-agent rules in robots.txt",
        severity="low",
        evidence=(
            "robots.txt names specific AI agents in its own user-agent groups, showing the site "
            "has already taken a position on AI access — but no /.well-known/tdmrep.json is "
            "published to separately declare a text-and-data-mining rights position."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Publish /.well-known/tdmrep.json to state a TDM rights position explicitly, "
                "since robots.txt cannot express 'index me, do not train on me' on its own."
            ),
            priority="low",
        ),
        category="discoverability",
        capability_id="PER-09",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "robots.txt only ever expresses a crawl decision, never a training-rights decision. "
            "A site that has already gone to the effort of writing named AI-agent rules is the "
            "site most likely to also have (and benefit from stating) a TDM rights position — "
            "TDMRep is the mechanism the EU CDSM Art. 4 / AI Act TDM opt-out expects for that."
        ),
        track="proactive",
        gate=1,
        confidence="medium",
    )


def evaluate_access_contradictions(
    robots_text: str | None,
    robots_status: str,
    sitemap_text: str | None,
    sitemap_status: str,
    llms_text: str | None,
    llms_status: str,
    page_results: list[dict],
    tdmrep_data: dict | None,
    tdmrep_status: str,
) -> tuple[list[Finding], list[UnknownCheck]]:
    """PER-09, all five contradiction rules. `page_results` is a list of
    `{"url": str, "headers": dict, "meta": dict}` — one entry per page
    fetched via `fetch_page_with_headers` + `parse_meta_directives` (default:
    just the root page; widened by repeatable `--page-url`).

    Every rule here reads robots.txt groups in some form, so the whole
    capability reports unknown — not silently skipped — when robots.txt
    itself could not be established.
    """
    if robots_status == "unavailable":
        reason = robots_text or "robots.txt could not be fetched"
        return [], [
            UnknownCheck(
                "PER-09",
                OWNER_SKILL,
                f"{reason}; cross-layer access-signal contradictions cannot be evaluated "
                "without robots.txt",
            )
        ]

    groups = parse_groups(robots_text or "") if robots_status == "present" else []
    sitemap_urls = _sitemap_urls_from_text(sitemap_text) if sitemap_status == "present" else []
    llms_urls = _llms_urls_from_text(llms_text) if llms_status == "present" else []

    findings: list[Finding] = []

    if not _is_blanket_blocked(groups):
        c1 = _c1_sitemap_url_ai_disallowed(groups, sitemap_urls)
        if c1:
            findings.append(c1)

    c2 = _c2_noindex_on_declared_url(page_results, sitemap_urls, llms_urls)
    if c2:
        findings.append(c2)

    from_tdmrep = _tdmrep_reserves(tdmrep_data)
    tdm_reserved = from_tdmrep
    tdm_source = "tdmrep.json" if from_tdmrep else None
    if not tdm_reserved:
        for page in page_results:
            headers = page.get("headers") or {}
            meta = page.get("meta") or {}
            if str(headers.get("tdm-reservation", "")).strip().lower() in _TDM_RESERVED_VALUES:
                tdm_reserved, tdm_source = True, f"the tdm-reservation header on {page['url']}"
                break
            if str(meta.get("tdm_reservation") or "").strip().lower() in _TDM_RESERVED_VALUES:
                tdm_reserved, tdm_source = True, f'the <meta name="tdm-reservation"> tag on {page["url"]}'
                break

    c3 = _c3_tdm_reservation_contradicts_robots(groups, tdm_reserved, tdm_source)
    if c3:
        findings.append(c3)

    c4 = _c4_header_meta_robots_disagree(page_results)
    if c4:
        findings.append(c4)

    c5 = _c5_no_tdm_declaration(groups, tdmrep_status)
    if c5:
        findings.append(c5)

    return findings, []


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


def fetch_page_with_headers(url: str) -> tuple[str | None, dict[str, str], str]:
    """GET a page and capture its response headers alongside the body.

    Returns (text_or_error, headers, status). status is the same three-value
    contract as `fetch_text`: "present", "absent" (404/410) or "unavailable"
    (anything else, including network failure).

    `headers` is built as a plain dict with every header name lowercased —
    chosen over a dedicated case-insensitive mapping type because the only
    thing a caller needs is `.get("some-header")` lookups regardless of the
    casing seen on the wire, and a lowercased-key dict gives that directly
    without adding a new type to the module.

    On "absent" there is no page to have headers from, so headers is `{}`.
    On "unavailable" from a non-HTTPError failure (timeout, DNS, TLS), the
    fetch never completed enough to have any headers, so headers is also
    `{}`. The one case that diverges from `fetch_text`'s pattern: an
    HTTPError that isn't 404/410 still carries response headers on the error
    object (`error.headers`), and those are captured here — a 403 or 500
    response's headers can still carry `X-Robots-Tag` or similar signal a
    later capability needs.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
            content_encoding = response.headers.get("Content-Encoding", "")
            headers = {key.lower(): value for key, value in response.headers.items()}
        raw = decode_content_encoding(raw, content_encoding)
        return raw.decode("utf-8", errors="replace"), headers, "present"
    except urllib.error.HTTPError as error:
        code = error.code
        error_headers = {key.lower(): value for key, value in error.headers.items()} if error.headers else {}
        error.close()
        if code in (404, 410):
            return None, {}, "absent"
        return f"{url} returned HTTP {code}", error_headers, "unavailable"
    except Exception as error:  # timeout, DNS, TLS, redirect loop
        return f"{url} could not be fetched: {type(error).__name__}: {error}", {}, "unavailable"


def site_label(url_or_domain: str) -> str:
    value = url_or_domain.strip()
    for scheme in ("https://", "http://"):
        if value.lower().startswith(scheme):
            value = value[len(scheme) :]
            break
    return value.split("/")[0].strip().lower()


def base_url(url_or_domain: str) -> str:
    value = url_or_domain.strip().rstrip("/")
    if value.lower().startswith(("https://", "http://")):
        return value
    return "https://" + value


def md_variant_url(url_or_domain: str) -> str:
    """PER-07's target: the same page with a `.md` suffix. A bare domain or
    root path has no page to suffix, so it falls back to the `index.md`
    convention rather than producing something like `https://example.com.md`."""
    parsed = urllib.parse.urlparse(base_url(url_or_domain))
    path = parsed.path or "/"
    candidate_path = f"{path}index.md" if path.endswith("/") else f"{path}.md"
    return urllib.parse.urlunparse(parsed._replace(path=candidate_path, query="", fragment=""))


def audit(
    site: str,
    robots_text: str | None,
    robots_status: str,
    llms_text: str | None,
    llms_status: str,
    llms_full_text: str | None = None,
    llms_full_status: str = "unavailable",
    sitemap_text: str | None = None,
    sitemap_status: str = "unavailable",
    md_text: str | None = None,
    md_status: str = "unavailable",
    page_results: list[dict] | None = None,
    tdmrep_data: dict | None = None,
    tdmrep_status: str = "unavailable",
    api_catalog_text: str | None = None,
    api_catalog_headers: dict[str, str] | None = None,
    api_catalog_status: str = "unavailable",
) -> dict:
    """PER-05/06/07/08/09 default to "unavailable" (or, for `page_results`,
    empty): a caller that only passes robots/llms (every test written before
    these cycles) correctly gets an honest `unknown_checks` entry for the
    newer capabilities rather than a silently fabricated result — "reduced
    coverage is reported, never hidden" applies to callers that predate a
    capability too."""
    robots_findings, robots_unknown = evaluate_robots(robots_text, robots_status)
    llms_findings, llms_unknown = evaluate_llms_txt(llms_text, llms_status)
    llms_full_findings, llms_full_unknown = evaluate_llms_full_txt(llms_full_text, llms_full_status)
    sitemap_findings, sitemap_unknown = evaluate_sitemap(sitemap_text, sitemap_status)
    md_findings, md_unknown = evaluate_md_negotiation(md_text, md_status)
    sitemap_disc_findings, sitemap_disc_unknown = evaluate_sitemap_discoverability(
        robots_text, robots_status, sitemap_status
    )
    llms_sitemap_findings, llms_sitemap_unknown = evaluate_llms_sitemap_agreement(
        llms_text, llms_status, sitemap_text, sitemap_status
    )
    contradiction_findings, contradiction_unknown = evaluate_access_contradictions(
        robots_text,
        robots_status,
        sitemap_text,
        sitemap_status,
        llms_text,
        llms_status,
        page_results or [],
        tdmrep_data,
        tdmrep_status,
    )
    api_catalog_findings, api_catalog_unknown = evaluate_api_catalog(
        api_catalog_text, api_catalog_headers, api_catalog_status
    )

    findings = (
        robots_findings
        + llms_findings
        + llms_full_findings
        + sitemap_findings
        + md_findings
        + sitemap_disc_findings
        + llms_sitemap_findings
        + contradiction_findings
        + api_catalog_findings
    )
    unknowns = (
        robots_unknown
        + llms_unknown
        + llms_full_unknown
        + sitemap_unknown
        + md_unknown
        + sitemap_disc_unknown
        + llms_sitemap_unknown
        + contradiction_unknown
        + api_catalog_unknown
    )
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [f.to_dict() for f in findings],
        "unknown_checks": [u.to_dict() for u in unknowns],
    }


def _read_file(path: str) -> tuple[str, str]:
    return Path(path).read_text(encoding="utf-8", errors="replace"), "present"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Target site; fetches /robots.txt and /llms.txt over the network")
    parser.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser.add_argument("--robots-file", help="Read robots.txt from a local file instead of fetching")
    parser.add_argument("--llms-file", help="Read llms.txt from a local file instead of fetching")
    parser.add_argument("--robots-absent", action="store_true", help="Treat robots.txt as a 404")
    parser.add_argument("--llms-absent", action="store_true", help="Treat llms.txt as a 404")
    parser.add_argument("--llms-full-file", help="Read llms-full.txt from a local file instead of fetching")
    parser.add_argument("--llms-full-absent", action="store_true", help="Treat llms-full.txt as a 404")
    parser.add_argument("--sitemap-file", help="Read sitemap.xml from a local file instead of fetching")
    parser.add_argument("--sitemap-absent", action="store_true", help="Treat sitemap.xml as a 404")
    parser.add_argument("--md-file", help="Read the .md page variant from a local file instead of fetching")
    parser.add_argument("--md-absent", action="store_true", help="Treat the .md page variant as a 404")
    parser.add_argument(
        "--headers-file",
        help=(
            "PER-09 offline testing: read the root page's URL/headers/HTML from a local JSON "
            'file ({"url": ..., "headers": {...}, "html": "..."}) instead of fetching'
        ),
    )
    parser.add_argument(
        "--tdmrep-file", help="Read /.well-known/tdmrep.json from a local file instead of fetching"
    )
    parser.add_argument("--tdmrep-absent", action="store_true", help="Treat tdmrep.json as a 404")
    parser.add_argument(
        "--api-catalog-file", help="Read /.well-known/api-catalog's body from a local file instead of fetching"
    )
    parser.add_argument("--api-catalog-absent", action="store_true", help="Treat api-catalog as a 404")
    parser.add_argument(
        "--api-catalog-content-type",
        default="application/linkset+json",
        help="Content-Type to assume for --api-catalog-file (a live fetch reads the real header)",
    )
    parser.add_argument(
        "--page-url",
        action="append",
        default=[],
        help=(
            "Additional page URL to widen PER-09's X-Robots-Tag/meta-robots comparison beyond "
            "the root page (repeatable; live --url mode only)"
        ),
    )
    parser.add_argument(
        "--no-edge-probe",
        action="store_true",
        help="Skip PER-03 (CDN/edge access). PER-03 only ever runs in --url mode; this opts out of it there too.",
    )
    parser.add_argument(
        "--no-content-parity-probe",
        action="store_true",
        help="Skip PER-11 (AI-crawler content-parity diff). PER-11 only ever runs in --url mode.",
    )
    args = parser.parse_args(argv)

    if not args.url and not args.site:
        parser.error("one of --url or --site is required")

    site = site_label(args.site or args.url)

    if args.robots_file:
        robots_text, robots_status = _read_file(args.robots_file)
    elif args.robots_absent:
        robots_text, robots_status = None, "absent"
    elif args.url:
        robots_text, robots_status = fetch_text(base_url(args.url) + "/robots.txt")
    else:
        robots_text, robots_status = "robots.txt was not supplied and no --url was given", "unavailable"

    if args.llms_file:
        llms_text, llms_status = _read_file(args.llms_file)
    elif args.llms_absent:
        llms_text, llms_status = None, "absent"
    elif args.url:
        llms_text, llms_status = fetch_text(base_url(args.url) + "/llms.txt")
    else:
        llms_text, llms_status = "llms.txt was not supplied and no --url was given", "unavailable"

    if args.llms_full_file:
        llms_full_text, llms_full_status = _read_file(args.llms_full_file)
    elif args.llms_full_absent:
        llms_full_text, llms_full_status = None, "absent"
    elif args.url:
        llms_full_text, llms_full_status = fetch_text(base_url(args.url) + "/llms-full.txt")
    else:
        llms_full_text, llms_full_status = None, "unavailable"

    if args.sitemap_file:
        sitemap_text, sitemap_status = _read_file(args.sitemap_file)
    elif args.sitemap_absent:
        sitemap_text, sitemap_status = None, "absent"
    elif args.url:
        sitemap_text, sitemap_status = fetch_text(base_url(args.url) + "/sitemap.xml")
    else:
        sitemap_text, sitemap_status = None, "unavailable"

    if args.md_file:
        md_text, md_status = _read_file(args.md_file)
    elif args.md_absent:
        md_text, md_status = None, "absent"
    elif args.url:
        md_text, md_status = fetch_text(md_variant_url(args.url))
    else:
        md_text, md_status = None, "unavailable"

    page_results: list[dict] = []
    if args.headers_file:
        payload = json.loads(Path(args.headers_file).read_text(encoding="utf-8"))
        page_html = payload.get("html", "")
        page_results.append(
            {
                "url": payload.get("url", base_url(args.site or args.url or site)),
                "headers": {key.lower(): value for key, value in (payload.get("headers") or {}).items()},
                "meta": parse_meta_directives(page_html),
            }
        )
    elif args.url:
        root_url = base_url(args.url)
        root_text, root_headers, root_status = fetch_page_with_headers(root_url)
        if root_status in ("present", "unavailable"):
            page_results.append(
                {"url": root_url, "headers": root_headers, "meta": parse_meta_directives(root_text or "")}
            )
        for extra_url in args.page_url:
            extra_text, extra_headers, extra_status = fetch_page_with_headers(extra_url)
            if extra_status in ("present", "unavailable"):
                page_results.append(
                    {"url": extra_url, "headers": extra_headers, "meta": parse_meta_directives(extra_text or "")}
                )

    if args.tdmrep_file:
        try:
            tdmrep_data = json.loads(Path(args.tdmrep_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            tdmrep_data = None
        tdmrep_status = "present"
    elif args.tdmrep_absent:
        tdmrep_data, tdmrep_status = None, "absent"
    elif args.url:
        tdmrep_data, tdmrep_status = fetch_tdmrep(base_url(args.url) + "/.well-known/tdmrep.json")
    else:
        tdmrep_data, tdmrep_status = None, "unavailable"

    if args.api_catalog_file:
        api_catalog_text = Path(args.api_catalog_file).read_text(encoding="utf-8", errors="replace")
        api_catalog_headers = {"content-type": args.api_catalog_content_type}
        api_catalog_status = "present"
    elif args.api_catalog_absent:
        api_catalog_text, api_catalog_headers, api_catalog_status = None, {}, "absent"
    elif args.url:
        api_catalog_text, api_catalog_headers, api_catalog_status = fetch_page_with_headers(
            base_url(args.url) + "/.well-known/api-catalog"
        )
    else:
        api_catalog_text, api_catalog_headers, api_catalog_status = None, {}, "unavailable"

    output = audit(
        site,
        robots_text,
        robots_status,
        llms_text,
        llms_status,
        llms_full_text,
        llms_full_status,
        sitemap_text,
        sitemap_status,
        md_text,
        md_status,
        page_results,
        tdmrep_data,
        tdmrep_status,
        api_catalog_text,
        api_catalog_headers,
        api_catalog_status,
    )

    if not args.url:
        output["unknown_checks"].append(
            UnknownCheck(
                "PER-03",
                OWNER_SKILL,
                "no --url given; PER-03 needs a live target and does not run against local files",
            ).to_dict()
        )
    elif args.no_edge_probe:
        output["unknown_checks"].append(
            UnknownCheck("PER-03", OWNER_SKILL, "skipped: --no-edge-probe was set").to_dict()
        )
    else:
        edge_findings, edge_unknowns, _ = fetch_and_evaluate_edge_access(base_url(args.url))
        output["findings"].extend(f.to_dict() for f in edge_findings)
        output["unknown_checks"].extend(u.to_dict() for u in edge_unknowns)

    if not args.url:
        output["unknown_checks"].append(
            UnknownCheck(
                "PER-11",
                OWNER_SKILL,
                "no --url given; PER-11 needs a live target and does not run against local files",
            ).to_dict()
        )
    elif args.no_content_parity_probe:
        output["unknown_checks"].append(
            UnknownCheck("PER-11", OWNER_SKILL, "skipped: --no-content-parity-probe was set").to_dict()
        )
    else:
        parity_findings, parity_unknowns = fetch_and_evaluate_content_parity(base_url(args.url))
        output["findings"].extend(f.to_dict() for f in parity_findings)
        output["unknown_checks"].extend(u.to_dict() for u in parity_unknowns)

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
