"""PER-09 — cross-layer access-signal contradiction detection (C1-C5) for perimeter-access-audit — split out of check_perimeter.py.
"""

from __future__ import annotations

import json
import urllib.parse
from html.parser import HTMLParser
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SEVERITIES, SuggestedAction, UnknownCheck  # noqa: E402
from _perimeter_constants import OWNER_SKILL, BOT_TIERS, TIER_SEVERITY  # noqa: E402
from _perimeter_fetch import fetch_text  # noqa: E402
from _perimeter_access_rules import can_fetch_root, can_fetch_path, parse_groups  # noqa: E402
from _perimeter_artifacts import (  # noqa: E402
    _SITEMAP_ROOT_PATTERN,
    _SITEMAP_LOC_PATTERN,
    _LLMS_LINK_URL_PATTERN,
    _normalized_url_key,
)


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

