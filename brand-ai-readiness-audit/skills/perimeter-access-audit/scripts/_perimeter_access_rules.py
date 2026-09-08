"""Bot-taxonomy resolution and robots.txt parsing/evaluation (PER-01/PER-02) for perimeter-access-audit — split out of check_perimeter.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.robotparser import RobotFileParser

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from _perimeter_constants import (  # noqa: E402
    OWNER_SKILL,
    BOT_TIERS,
    TIER_LABELS,
    TIER_SEVERITY,
    TIER_MECHANISM,
)


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
