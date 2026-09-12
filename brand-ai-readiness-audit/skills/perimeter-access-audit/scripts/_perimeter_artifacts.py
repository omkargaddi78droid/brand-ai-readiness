"""PER-04/05/06/07/08/10 — the independent artifact validators (llms.txt, llms-full.txt, sitemap.xml, `.md` negotiation, RFC 9727 api-catalog, llms/sitemap agreement) for perimeter-access-audit — split out of check_perimeter.py.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from _perimeter_constants import OWNER_SKILL  # noqa: E402


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
            structured_evidence={"orphaned_urls": shown, "true_orphaned_count": len(orphaned)},
        )
    ], []
