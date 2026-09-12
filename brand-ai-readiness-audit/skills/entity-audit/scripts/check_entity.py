#!/usr/bin/env python3
"""Gate-3 entity audit: is the brand a resolved entity, and does its markup
agree with itself?

Owns ten capabilities — the identity multiplier, cross-cutting because
every other gate-3 finding is worth more once an assistant can resolve
*which* brand it is looking at (Round-2 appendix D: shared names cause
entity mix-ups unless something clearly distinguishes them):
  ENT-01  Schema.org/JSON-LD presence & validity
  ENT-02  Knowledge-graph grounding — sameAs links to Wikidata/authoritative IDs
  ENT-03  Markup/text agreement — a marked-up rating that disagrees with the visible page
  ENT-04  Canonicalisation — missing, conflicting, malformed or off-domain rel=canonical
  ENT-05  Brand-name entity collision (agent-judged; off-site — see below)
  ENT-06  Lookalike domain impersonation (agent-judged; off-site — see below)
  ENT-07  Cross-domain service attribution (multi-page; --sample-file mode — see below)
  ENT-08  Address/NAP clustering — a stated address that disagrees across sampled
          pages of the same brand (multi-page; --sample-file mode — see below)
  ENT-09  Taxonomy consistency — a declared category/section contradicting the page's
          own body text (agent-judged; see below)
  ENT-11  JSON-LD graph referential integrity — dangling/cross-page @id references
  ENT-12  JSON-LD entity-graph fragmentation — a valid graph split into disconnected clusters

**ENT-05/ENT-06 are off-site, cycle-19 additions.** Cycle 9 through 18 kept
these `DEFERRED`, reasoning that an off-site lookup conflicts with this
project's "self-contained, no external service" design rule (hard
constraint M5). Confirmed with the judges in cycle 19, that rule was
narrowed rather than removed: direct, bounded HTTP queries to named public
sites (Reddit, Quora, forums, review sites), robots.txt-respecting,
computing the verdict ourselves, are permitted — a third-party *scoring*
API is still rejected. This script does not pick which off-site pages to
look at (that stays the calling agent's own search step); it only fetches
agent-supplied `--offsite-url` candidates
within the same SSRF/timeout/size bounds as every other fetch in this
file, plus a new per-host robots.txt check before fetching a third-party
host, and hands extracted snippets to
`agent_judgement_required` — "is this genuinely the same brand" and "is
this genuinely impersonation" are exactly the fuzzy semantic calls this
project's Phase 0.1(c) stance pushes to agent judgement, never a script
verdict.

**ENT-07 is a cycle-23 addition, `--sample-file` mode.** Cycle 21 deferred it
as needing "either off-site reasoning or comparing several pages, neither of
which this single-page script does" — true at the time, and no longer a
blocker once cycle 23's Phase 1 shipped a page sampler
(shared/page_sample.py) and a Public Suffix List module
(shared/public_suffix.py). Given a file of on-site page URLs (the
orchestrator's own bounded sample), this mode fetches each one, extracts
outbound links, and flags a recurring, brand-named, service-shaped
third-party domain (a help desk, a status page) whose own homepage carries
no `sameAs`/`url` reference back to this site — the same reasoning ENT-05/06
established in cycle 19 for when an off-site or multi-page lookup is
permitted (hard constraint 2): direct, bounded, robots.txt-respecting HTTP
queries this script picks candidates for itself, computing the verdict here
rather than deferring it to agent judgement, since "does this hostname
contain our brand name and a service keyword, and does its own markup name
us back" is fully mechanical.

**ENT-08 is a cycle-23 addition, Phase 4 B3, same `--sample-file` mode as
ENT-07.** Earlier cycles deferred it as "needs comparing several pages'
visible address text against each other — a genuinely semantic clustering
problem." Cycle 23's `shared/fuzzy_match.py` (single-linkage clustering over
`difflib.SequenceMatcher`, no external dependency) makes the clustering half
mechanical; the remaining judgement call — a chain or any real multi-location
business legitimately has several different, all-correct addresses — is
handled by a script-decided gate, not agent judgement: if any sampled page
uses multiple-location language ("store locator", "find a location", ...),
the check stays silent entirely, per the plan's explicit instruction to
gate the clustering behind this check as the dominant false positive.

Deliberately does NOT own: ENT-04's crawl-wide half (slug variants,
trailing-slash forks across many URLs) — that needs a sitemap and a
canonical map spanning the whole site, not one page.

**ENT-09 is agent-judged**, unlike ENT-01–04. The capability matrix's own
wording — "a page's assigned category tag contradicting its own body text"
— is a same-page check (no crawl, no off-site lookup needed), which an
earlier version of this docstring and `SKILL.md` incorrectly grouped with
ENT-07/08 as needing cross-page comparison; corrected in cycle 9. But
"does this category relate to this body text" is a semantic-relatedness
question a keyword match cannot safely answer alone — a category of
"Laptops" and body text saying only "notebook computers" would look like
zero overlap to a keyword check and yet agree completely. Per this
project's Phase 0.1(c) stance (the host agent is the LLM; semantic
judgement belongs in procedure text and rubrics, not a script verdict), the
script extracts a declared category/section label plus a visible-text
excerpt only, and the agent judges relatedness against
`references/entity-judgement-rubric.md` — the same extraction-only pattern
`content-quality-audit`, `engagement-audit` and `citability-audit` already
use for their own semantic calls.

Scope narrowing, stated rather than hidden (see references/entity-checks.md
for the full reasoning behind each):
  ENT-01 checks only Organization/WebSite/LocalBusiness/Product against a
    small required-field table — not every schema.org type, which would
    raise the false-positive rate on legitimate but unusual markup.
  ENT-02 only fires when an Organization/LocalBusiness node exists; if none
    exists at all, ENT-01 already reports the absence and a second finding
    saying "no sameAs either" would be redundant noise for the same root cause.
  ENT-03 checks only aggregateRating against an explicit "N out of 5" / "N/5"
    / "rated N" text pattern — not price, which needs more care to avoid
    comparing against the wrong one of several prices on a page.

Determinism
-----------
Every detector is a pure function of parsed input (JSON-LD nodes, canonical
hrefs, extracted text). No randomness, no clock in the detection logic.

Safety
------
`--url` mode fetches exactly one page (never a crawl) with the same SSRF
guard as content-quality-audit — refuses to resolve to a private, loopback,
link-local or reserved address before connecting. Fetched content is parsed
as data only, never executed, never treated as instruction.

Usage:
    check_entity.py --url https://example.com/
    check_entity.py --site example.com --html-file page.html

Emits one JSON object on stdout, the same shape as the other audit skills:
    {"owner_skill": ..., "capability_ids": [...], "site": ..., "page_url": ...,
     "findings": [...], "agent_judgement_required": [...], "unknown_checks": [...]}
`agent_judgement_required` is intermediate — the calling SKILL.md procedure
resolves it into `findings` (or drops it) before this file is composed into
the final report, the same contract content-quality-audit's own module
docstring documents in more detail.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck, cap_list  # noqa: E402
from jsonld_graph import Reference, build_id_index, classify_target, flatten, iter_references  # noqa: E402
from graph_metrics import connected_components  # noqa: E402
from text_spans import KEYWORD_FOLDING_STOPWORDS, VISIBLE_TEXT_BLOCK_TAGS, VISIBLE_TEXT_SKIP_TAGS  # noqa: E402
from page_fetch import (  # noqa: E402
    USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    MAX_PAGE_BYTES,
    decode_content_encoding,
    is_public_host,
    fetch_page_html,
    fetch_pages_concurrently,
)
from public_suffix import registrable_domain, same_entity  # noqa: E402
from links import extract_outbound_links  # noqa: E402
from fuzzy_match import single_linkage_clusters  # noqa: E402
from budget import StageBudget, coverage_manifest  # noqa: E402
from report_shape import site_label, stamp_page as _stamp_page, unknown_output  # noqa: E402
from skill_cli import add_page_arguments, resolve_page_html  # noqa: E402

OWNER_SKILL = "entity-audit"
CAPABILITY_IDS = [
    "ENT-01", "ENT-02", "ENT-03", "ENT-04", "ENT-05", "ENT-06", "ENT-07", "ENT-08", "ENT-09", "ENT-11", "ENT-12",
]


# ---------------------------------------------------------------------------
# HTML parsing: JSON-LD blocks, canonical links, visible text
# ---------------------------------------------------------------------------


class _PageParser(HTMLParser):
    """One pass over the HTML collects everything these four checks need:
    raw <script type="application/ld+json"> bodies, every rel=canonical
    href, and a lightly-extracted visible-text string (for ENT-03's
    markup/text comparison) with script/style/code/pre excluded — the same
    scoped extraction content-quality-audit uses. The tag-set constants are
    now shared (`shared/text_spans.py`, cycle 24 item 2.5 — genuinely
    cross-cutting infrastructure, not skill-specific logic); the parsing
    algorithm itself stays reimplemented here rather than importing another
    skill's script, per this project's independently-runnable-skill
    convention (`skill-engineering-principles.md` §5.3, and see
    `shared/page_fetch.py`'s docstring on which side of that line shared/
    infrastructure now falls)."""

    # Cycle 24 item 2.5: canonical set, shared/text_spans.py — see that module.
    _SKIP_TAGS = VISIBLE_TEXT_SKIP_TAGS
    _BLOCK_TAGS = VISIBLE_TEXT_BLOCK_TAGS

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_ld_blocks: list[str] = []
        self.canonical_hrefs: list[str] = []
        self._in_json_ld = False
        self._json_ld_buffer: list[str] = []
        self._skip_depth = 0
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "script" and (attr_dict.get("type") or "").strip().lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_ld_buffer = []
            self._skip_depth += 1
            return
        if tag == "link":
            rel_values = (attr_dict.get("rel") or "").lower().split()
            if "canonical" in rel_values and "href" in attr_dict:
                # Capture even an empty href: a canonical tag with no target
                # is a different, more specific defect (ENT-04-canonical-empty)
                # than no canonical tag at all, and checking truthiness here
                # would silently fold the two together.
                self.canonical_hrefs.append((attr_dict["href"] or "").strip())

        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self._text_chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        # A self-closed tag (`<link ... />`, common XHTML-style markup for
        # <link>/<meta>/<br>) is exactly a start tag with no separate content,
        # so it must run the same logic as handle_starttag — canonical-link
        # extraction included. Overriding this method without delegating to
        # handle_starttag silently drops that logic for every self-closed
        # tag. Found live: apple.com's `<link rel="canonical" ... />` was
        # being reported as a missing canonical entirely. Matches
        # HTMLParser's own documented default behaviour (starttag, then
        # endtag), which this override had replaced.
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json_ld:
            self.json_ld_blocks.append("".join(self._json_ld_buffer))
            self._in_json_ld = False
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCK_TAGS:
            self._text_chunks.append("\n")

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_buffer.append(data)
            return
        if self._skip_depth == 0:
            self._text_chunks.append(re.sub(r"\s+", " ", data))

    def visible_text(self) -> str:
        raw = "".join(self._text_chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def parse_page(html: str) -> tuple[list[dict], list[str], list[str], str]:
    """Returns (json_ld_nodes, json_ld_parse_errors, canonical_hrefs, visible_text).

    Flattening (the @graph/array walk) delegates to `shared/jsonld_graph.flatten`
    — this skill's own error-collection loop stays local, since `flatten`
    itself silently skips a block that fails to parse (matching the other
    two skills' identical wrapper) and has no way to hand back *why* a block
    failed, which ENT-01's malformed-json-ld finding needs verbatim."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()

    nodes: list[dict] = []
    errors: list[str] = []
    for block in parser.json_ld_blocks:
        stripped = block.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError as error:
            errors.append(f"{error}: {stripped[:120]!r}")
            continue
        nodes.extend(flatten([stripped]))

    return nodes, errors, parser.canonical_hrefs, parser.visible_text()


def _node_types(node: dict) -> set[str]:
    type_value = node.get("@type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {t for t in type_value if isinstance(t, str)}
    return set()


# ---------------------------------------------------------------------------
# ENT-01 — Schema.org / JSON-LD presence & validity
# ---------------------------------------------------------------------------

_IDENTITY_TYPES = ("Organization", "WebSite", "LocalBusiness")

_REQUIRED_FIELDS = {
    "Organization": ("name", "url"),
    "LocalBusiness": ("name", "url"),
    "WebSite": ("name", "url"),
    "Product": ("name",),
}


_ENT01_HOMEPAGE_PATHS = ("", "/")


def _is_homepage(page_url: str) -> bool:
    """Scribd live-testing false positive: a content-detail page (document,
    media object) legitimately carries only Product/MediaObject/BreadcrumbList
    markup, with no Organization/WebSite node of its own — the identity node
    belongs on the homepage, not on every page. Mirrors engagement-audit's
    own `_is_homepage`."""
    return urllib.parse.urlparse(page_url).path in _ENT01_HOMEPAGE_PATHS


def find_schema_issues(
    nodes: list[dict], parse_errors: list[str], page_url: str | None = None
) -> tuple[list[Finding], list[UnknownCheck]]:
    findings: list[Finding] = []

    if parse_errors:
        findings.append(_malformed_json_ld_finding(parse_errors))

    if not nodes and not parse_errors:
        findings.append(_no_structured_data_finding())
        return findings, []

    if nodes and not any(_node_types(n) & set(_IDENTITY_TYPES) for n in nodes):
        if page_url is None or _is_homepage(page_url):
            findings.append(_no_identity_type_finding(sorted({t for n in nodes for t in _node_types(n)})))

    for node in nodes:
        types = _node_types(node) & set(_REQUIRED_FIELDS)
        for schema_type in sorted(types):
            missing = [f for f in _REQUIRED_FIELDS[schema_type] if not node.get(f)]
            if missing:
                findings.append(_missing_required_field_finding(schema_type, missing, node))

    return findings, []


def _no_structured_data_finding() -> Finding:
    return Finding(
        id="ENT-01-no-structured-data",
        title="No schema.org/JSON-LD structured data found on this page",
        severity="medium",
        evidence="No <script type=\"application/ld+json\"> block was found anywhere on the page.",
        suggested_action=SuggestedAction(
            summary=(
                "Add an Organization or WebSite JSON-LD block naming the brand, its canonical "
                "URL and a `sameAs` link to an authoritative profile (Wikidata, LinkedIn, ...)."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-01",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Structured data is how a machine resolves the page from a string of prose into a "
            "typed entity with named properties. Without it, the brand's name, identity and "
            "relationships have to be inferred from prose, which is exactly the condition under "
            "which name collisions and misattribution happen. Framed for entity resolution and "
            "rich results, not citation lift — an Ahrefs test found roughly +2.4% AI-Mode citation "
            "lift from adding JSON-LD, within noise, so this is not sold as a ranking lever."
        ),
        gate=3,
        confidence="high",
    )


_ENT01_MAX_ERRORS = 3


def _malformed_json_ld_finding(errors: list[str]) -> Finding:
    shown_errors, true_error_count = cap_list(errors, _ENT01_MAX_ERRORS)
    quoted = "; ".join(shown_errors)
    more = f" (+{true_error_count - _ENT01_MAX_ERRORS} more)" if true_error_count > _ENT01_MAX_ERRORS else ""
    return Finding(
        id="ENT-01-malformed-json-ld",
        title="A JSON-LD block on this page is not valid JSON",
        severity="high",
        evidence=f"{true_error_count} <script type=\"application/ld+json\"> block(s) failed to parse: {quoted}{more}.",
        suggested_action=SuggestedAction(
            summary="Fix the JSON syntax error in the affected block(s), or remove them if the feature was retired.",
            priority="high",
        ),
        category="discoverability",
        capability_id="ENT-01",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A structured-data block that fails to parse provides zero value to anything reading "
            "it and is strictly worse than no block: it costs maintenance, signals the markup is "
            "untested, and a strict consumer discards it entirely rather than salvaging the parts "
            "that would have parsed."
        ),
        gate=3,
        confidence="high",
        structured_evidence={"parse_errors": shown_errors, "true_error_count": true_error_count},
    )


def _no_identity_type_finding(found_types: list[str]) -> Finding:
    found = ", ".join(found_types) if found_types else "none recognised"
    return Finding(
        id="ENT-01-no-identity-type",
        title="Structured data is present but does not identify the brand itself",
        severity="medium",
        evidence=(
            f"JSON-LD is present, but no node declares @type Organization, WebSite or "
            f"LocalBusiness. Types found instead: {found}."
        ),
        suggested_action=SuggestedAction(
            summary="Add an Organization or WebSite node alongside the existing structured data, naming the brand and its canonical URL.",
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-01",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Product, Article or FAQ markup describes what the page is about, not who published "
            "it. Without an Organization or WebSite node, the entity behind the content is still "
            "unresolved even though the page carries structured data."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={"types_found": found_types},
    )


def _missing_required_field_finding(schema_type: str, missing: list[str], node: dict) -> Finding:
    slug = re.sub(r"[^a-z0-9]+", "-", schema_type.lower())
    return Finding(
        id=f"ENT-01-{slug}-missing-fields",
        title=f'{schema_type} structured data is missing required properties',
        severity="medium",
        evidence=(
            f'A {schema_type} node is missing: {", ".join(missing)}. Node carries: '
            f'{", ".join(sorted(k for k in node.keys() if not k.startswith("@")))[:200] or "no other properties"}.'
        ),
        suggested_action=SuggestedAction(
            summary=f'Add {", ".join(missing)} to the {schema_type} JSON-LD node.',
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-01",
        owner_skill=OWNER_SKILL,
        mechanism=(
            f"{schema_type} without {', '.join(missing)} is a node a consumer cannot fully resolve — "
            f"the type declaration promises a shape the data does not deliver."
        ),
        gate=3,
        confidence="high",
        structured_evidence={"schema_type": schema_type, "missing_fields": missing},
    )


# ---------------------------------------------------------------------------
# ENT-02 — Knowledge-graph grounding
# ---------------------------------------------------------------------------

_AUTHORITY_DOMAINS = (
    "wikidata.org", "wikipedia.org", "linkedin.com", "crunchbase.com",
    "twitter.com", "x.com", "facebook.com", "instagram.com", "youtube.com", "github.com",
)


def find_knowledge_graph_gaps(nodes: list[dict]) -> list[Finding]:
    identity_nodes = [n for n in nodes if _node_types(n) & {"Organization", "LocalBusiness"}]
    findings: list[Finding] = []
    for node in identity_nodes:
        same_as = node.get("sameAs")
        urls = same_as if isinstance(same_as, list) else ([same_as] if isinstance(same_as, str) else [])
        urls = [u for u in urls if isinstance(u, str) and u]
        grounded = [u for u in urls if any(domain in u.lower() for domain in _AUTHORITY_DOMAINS)]
        if grounded:
            continue
        findings.append(_knowledge_graph_finding(node, urls))
    return findings


_ENT02_MAX_URLS = 3


def _knowledge_graph_finding(node: dict, urls: list[str]) -> Finding:
    name = node.get("name", "the organization")
    shown_urls, true_url_count = cap_list(urls, _ENT02_MAX_URLS)
    if urls:
        evidence = (
            f'"{name}"\'s sameAs lists {true_url_count} URL(s) ({", ".join(shown_urls)}), none of which '
            "point to a recognised authority (Wikidata, Wikipedia, LinkedIn, Crunchbase, or a "
            "major verified social profile)."
        )
    else:
        evidence = f'"{name}" has no sameAs property at all.'
    return Finding(
        id="ENT-02-no-knowledge-graph-link",
        title="Organization markup has no link to an authoritative identity source",
        severity="medium",
        evidence=evidence,
        suggested_action=SuggestedAction(
            summary=(
                'Add a `sameAs` array to the Organization node listing the brand\'s Wikidata '
                "entity (if one exists), Wikipedia article, and verified LinkedIn/Crunchbase/"
                "social profiles."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-02",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Without a link to a resolved external identity, the brand stays a probabilistic "
            "string match rather than a resolved entity. Appendix D: a name shared by several "
            "things is disambiguated by something that clearly distinguishes them — sameAs to "
            "Wikidata or an authoritative profile is exactly that distinguishing signal."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={"name": name, "same_as_found": shown_urls, "true_url_count": true_url_count},
    )


# ---------------------------------------------------------------------------
# ENT-03 — Markup/text agreement
# ---------------------------------------------------------------------------

_RATING_TEXT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:out of|/)\s*5\b|\brated\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE
)


def _find_aggregate_ratings(nodes: list[dict]) -> list[dict]:
    ratings = []
    for node in nodes:
        rating = node.get("aggregateRating")
        if isinstance(rating, dict) and rating.get("ratingValue") is not None:
            ratings.append(rating)
        for value in node.values():
            if isinstance(value, dict) and isinstance(value.get("aggregateRating"), dict):
                nested = value["aggregateRating"]
                if nested.get("ratingValue") is not None:
                    ratings.append(nested)
    return ratings


def find_markup_text_disagreement(nodes: list[dict], visible_text: str) -> list[Finding]:
    ratings = _find_aggregate_ratings(nodes)
    if not ratings:
        return []

    text_matches = [
        float(m.group(1) or m.group(2)) for m in _RATING_TEXT_PATTERN.finditer(visible_text)
    ]
    if not text_matches:
        return []

    findings = []
    for rating in ratings:
        try:
            markup_value = float(rating["ratingValue"])
        except (TypeError, ValueError):
            continue
        disagreeing = [v for v in text_matches if abs(v - markup_value) > 0.3]
        if disagreeing and all(abs(v - markup_value) > 0.3 for v in text_matches):
            findings.append(_rating_disagreement_finding(markup_value, text_matches))
    return findings


def _rating_disagreement_finding(markup_value: float, text_values: list[float]) -> Finding:
    return Finding(
        id="ENT-03-rating-markup-text-mismatch",
        title="The marked-up rating does not match the rating stated in the page text",
        severity="high",
        evidence=(
            f"JSON-LD aggregateRating.ratingValue is {markup_value:g}, but the page's visible "
            f"text states {', '.join(f'{v:g}' for v in text_values)} (out of 5)."
        ),
        suggested_action=SuggestedAction(
            summary="Correct whichever value is stale — the JSON-LD block or the visible rating text — so both agree.",
            priority="high",
        ),
        category="discoverability",
        capability_id="ENT-03",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Structured data and visible text are two independent sources for the same fact. "
            "When they disagree, an assistant extracting the rating has no principled way to "
            "choose the right one, and quoting the wrong one is a factual error the page itself "
            "caused."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={"markup_value": markup_value, "text_values": text_values},
    )


# ---------------------------------------------------------------------------
# ENT-04 — Canonicalisation
# ---------------------------------------------------------------------------


def find_canonical_issues(canonical_hrefs: list[str], page_url: str | None) -> list[Finding]:
    if not canonical_hrefs:
        return [_missing_canonical_finding()]

    distinct = list(dict.fromkeys(canonical_hrefs))
    if len(distinct) > 1:
        return [_conflicting_canonical_finding(distinct)]

    href = distinct[0]
    if not href.strip():
        return [_empty_canonical_finding()]

    if page_url:
        canonical_host = urllib.parse.urlparse(urllib.parse.urljoin(page_url, href)).hostname
        page_host = urllib.parse.urlparse(page_url).hostname
        if canonical_host and page_host and _strip_www(canonical_host) != _strip_www(page_host):
            return [_off_domain_canonical_finding(href, page_host, canonical_host)]

    return []


def _strip_www(hostname: str) -> str:
    """www.example.com and example.com are the same site, not a domain switch."""
    return hostname[4:] if hostname.lower().startswith("www.") else hostname.lower()


def _missing_canonical_finding() -> Finding:
    return Finding(
        id="ENT-04-canonical-missing",
        title="No rel=canonical link on this page",
        severity="medium",
        evidence='No <link rel="canonical"> element was found on the page.',
        suggested_action=SuggestedAction(
            summary="Add a self-referencing <link rel=\"canonical\" href=\"...\"> naming this page's preferred URL.",
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Without a canonical, URL variants of the same page (tracking parameters, trailing "
            "slash, http vs https) are indexed and cited as separate pages, splitting authority "
            "and citation signal that a canonical would consolidate onto one URL."
        ),
        gate=3,
        confidence="high",
    )


def _empty_canonical_finding() -> Finding:
    return Finding(
        id="ENT-04-canonical-empty",
        title="rel=canonical is present but its href is empty",
        severity="medium",
        evidence='<link rel="canonical"> was found with an empty or missing href attribute.',
        suggested_action=SuggestedAction(
            summary="Set the canonical link's href to this page's preferred absolute URL.",
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-04",
        owner_skill=OWNER_SKILL,
        mechanism="A canonical tag with no target provides no consolidation signal at all — equivalent to having none, at the cost of the maintenance and markup.",
        gate=3,
        confidence="high",
    )


_ENT04_MAX_HREFS = 4


def _conflicting_canonical_finding(hrefs: list[str]) -> Finding:
    shown_hrefs, true_href_count = cap_list(hrefs, _ENT04_MAX_HREFS)
    return Finding(
        id="ENT-04-canonical-conflicting",
        title="Multiple different rel=canonical links declared on one page",
        severity="high",
        evidence=f"{true_href_count} distinct canonical URLs declared on the same page: {', '.join(shown_hrefs)}.",
        suggested_action=SuggestedAction(
            summary="Keep exactly one <link rel=\"canonical\">; remove the conflicting duplicate(s).",
            priority="high",
        ),
        category="discoverability",
        capability_id="ENT-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A page declaring more than one canonical target has no single answer to 'what is "
            "the preferred URL', and different consumers resolve the conflict differently — some "
            "use the first, some the last, some ignore all of them. The signal is unreliable "
            "exactly when it matters most."
        ),
        gate=3,
        confidence="high",
        structured_evidence={"hrefs": shown_hrefs, "true_href_count": true_href_count},
    )


def _off_domain_canonical_finding(href: str, page_host: str, canonical_host: str) -> Finding:
    return Finding(
        id="ENT-04-canonical-off-domain",
        title="rel=canonical points to a different domain than the page itself",
        severity="high",
        evidence=f'Page served from {page_host} declares its canonical as {href!r}, on {canonical_host}.',
        suggested_action=SuggestedAction(
            summary="Verify this is intentional (e.g. deliberate syndication); if not, point the canonical back to this domain.",
            priority="high",
        ),
        category="discoverability",
        capability_id="ENT-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "An off-domain canonical tells crawlers this page's authority belongs to a different "
            "site entirely. That is a legitimate pattern for deliberate content syndication, and "
            "an easy, costly accident (a staging or copy-paste artifact) everywhere else — "
            "reported at reduced confidence because the deliberate case exists."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={"page_host": page_host, "canonical_host": canonical_host, "href": href},
    )


def _fork_key(url: str) -> tuple[str, str, str]:
    """(scheme-folded, www.-stripped host, trailing-slash-stripped path) —
    the well-established, near-zero-FP equivalences citability-audit's
    `_strip_www` and this file's own ENT-04 off-domain fix already use,
    plus scheme (http/https almost always serve the same resource on a
    real site). Deliberately does not fold case or query strings: those
    can be genuinely different resources, and this check's whole point is
    staying safe enough to run on a sitemap's full URL list unattended."""
    parsed = urllib.parse.urlparse(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"
    return ("https", host, path)


def find_sitemap_url_forks(sitemap_urls: list[str]) -> list[Finding]:
    """ENT-04's crawl-wide half, scoped to what a sitemap's own declared URL
    list can show without a real crawl: two distinct listed URLs that are
    the same resource once trailing-slash/www/scheme differences are
    normalised split a page's authority and citation signal across two
    URLs instead of one, exactly the failure this capability names."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for url in sitemap_urls:
        groups.setdefault(_fork_key(url), []).append(url.strip())

    fork_groups = [sorted(set(members)) for members in groups.values() if len(set(members)) > 1]
    if not fork_groups:
        return []

    shown = fork_groups[:5]
    more = f" (+{len(fork_groups) - 5} more)" if len(fork_groups) > 5 else ""
    lines = "; ".join(" vs. ".join(group) for group in shown)
    return [
        Finding(
            id="ENT-04-sitemap-url-fork",
            title="Sitemap lists slug-variant/trailing-slash/scheme forks of the same page",
            severity="medium",
            evidence=(
                f"{len(fork_groups)} URL group(s) in sitemap.xml resolve to the same page under "
                f"different URLs: {lines}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="List only the canonical form of each URL in the sitemap, and set rel=canonical on each page so both forms consolidate to one.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="ENT-04",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A sitemap listing both forms of the same URL (a trailing-slash variant, a "
                "www./bare-domain pair, or an http/https pair) tells crawlers two different pages "
                "exist where there is really one, splitting whatever authority and citation "
                "signal a single consolidated URL would otherwise carry."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"fork_groups": shown, "true_fork_group_count": len(fork_groups)},
        )
    ]


# ---------------------------------------------------------------------------
# ENT-11 — JSON-LD graph referential integrity
# ---------------------------------------------------------------------------
#
# ENT-01 validates individual nodes. ENT-03 compares markup to visible text.
# Neither follows an @id edge. A page's JSON-LD can be entirely valid
# per-node and still be a broken graph: a Product whose brand points at
# {"@id": "#organization-1"} when no node with that @id exists anywhere on
# the page. Entity resolution and knowledge-graph grounding work by walking
# the graph to assemble one coherent entity; a dangling @id is the
# structured-data equivalent of an undefined symbol, and the failure is
# silent because every per-node validator still passes.
#
# Uses ENT-11, not ENT-10: ENT-10 is already reserved by a different,
# deferred capability in the project's capability matrix.

_MAX_DANGLING_FINDINGS_PER_CLASS = 5
_ORPHAN_IDENTITY_TYPES = {"Organization", "Person", "LocalBusiness"}
_ORPHAN_CONTENT_TYPES = {"Product", "Article", "Review"}
_ORPHAN_LINK_PROPERTIES = ("brand", "publisher", "author")


def find_graph_integrity_issues(nodes: list[dict], page_url: str | None) -> list[Finding]:
    """ENT-11. Caller-side overlap control: only invoked when `nodes` is
    non-empty and carries no JSON-LD parse errors — never report a broken
    graph on a page that has no parseable graph at all (ENT-01's
    no-structured-data/malformed-json-ld findings already own that case)."""
    index = build_id_index(nodes)
    defined_ids = sorted(index.keys())
    resolved_page_url = page_url or ""

    findings: list[Finding] = []
    fragment_count = 0
    same_origin_count = 0
    referenced_targets: set[str] = set()

    for reference in iter_references(nodes):
        referenced_targets.add(reference.target_id)
        classification = classify_target(reference.target_id, index, resolved_page_url)
        if classification == "dangling_fragment" and fragment_count < _MAX_DANGLING_FINDINGS_PER_CLASS:
            findings.append(_dangling_reference_finding(reference, defined_ids, cross_page=False))
            fragment_count += 1
        elif classification == "dangling_same_origin" and same_origin_count < _MAX_DANGLING_FINDINGS_PER_CLASS:
            findings.append(_dangling_reference_finding(reference, defined_ids, cross_page=True))
            same_origin_count += 1

    orphan = _orphan_identity_finding(nodes, referenced_targets)
    if orphan:
        findings.append(orphan)

    return findings


_ENT11_MAX_DEFINED_IDS = 10


def _defined_ids_clause(defined_ids: list[str]) -> str:
    if not defined_ids:
        return "defines no @ids at all"
    shown, true_count = cap_list(defined_ids, _ENT11_MAX_DEFINED_IDS)
    quoted = ", ".join(f"'{i}'" for i in shown)
    more = f" (+{true_count - _ENT11_MAX_DEFINED_IDS} more)" if true_count > _ENT11_MAX_DEFINED_IDS else ""
    return f"defines {true_count} @id(s) — {quoted}{more} — none of which match"


def _dangling_reference_finding(reference: Reference, defined_ids: list[str], cross_page: bool) -> Finding:
    # sha256, not id(), so the same page audited twice produces the same
    # finding id — see EN-06's identical rationale for _stable_slug.
    slug = hashlib.sha256(f"{reference.property_path}|{reference.target_id}".encode("utf-8")).hexdigest()[:8]
    clause = _defined_ids_clause(defined_ids)

    if cross_page:
        return Finding(
            id=f"ENT-11-cross-page-id-reference-{slug}",
            title="Structured data references an @id not defined on this page",
            severity="low",
            evidence=(
                f"{reference.property_path} references @id '{reference.target_id}'. The page "
                f"{clause}. It is a same-origin absolute URL, so it may legitimately be defined "
                "on another page of this site."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    f"Confirm '{reference.target_id}' is defined on the page it points to, or add "
                    "it to this page's own JSON-LD if it should resolve locally."
                ),
                priority="low",
            ),
            category="discoverability",
            capability_id="ENT-11",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Entity resolution works by walking @id references to assemble one coherent "
                "entity. A same-origin reference that doesn't resolve on this page may be "
                "legitimate cross-page structured data — the cross-page convention is itself "
                "legitimate — but a consumer that only fetched this page still follows the "
                "pointer and gets nothing."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={
                "property_path": reference.property_path,
                "target": reference.target_id,
                "defined_ids": cap_list(defined_ids, _ENT11_MAX_DEFINED_IDS)[0],
                "true_defined_id_count": len(defined_ids),
            },
        )

    return Finding(
        id=f"ENT-11-dangling-id-reference-{slug}",
        title="Structured data references an @id that is not defined anywhere on the page",
        severity="medium",
        evidence=(
            f"{reference.property_path} references @id '{reference.target_id}'. The page {clause}. "
            "A consumer resolving this entity from the graph follows the pointer and gets nothing."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f"Define a node with @id '{reference.target_id}' on this page, or fix the "
                "reference to point at an @id that exists."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-11",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A fragment @id is page-scoped by definition — if it isn't defined by this page's own "
            "nodes, it cannot be defined anywhere else. Entity resolution and knowledge-graph "
            "grounding work by walking @id references to assemble one coherent entity; a dangling "
            "pointer is the structured-data equivalent of an undefined symbol, and the failure is "
            "silent because every per-node validator still passes."
        ),
        gate=3,
        confidence="high",
        structured_evidence={
            "property_path": reference.property_path,
            "target": reference.target_id,
            "defined_ids": defined_ids,
        },
    )


def _orphan_identity_finding(nodes: list[dict], referenced_targets: set[str]) -> Finding | None:
    """An Organization/Person/LocalBusiness node with an @id nothing
    references, on a page that also carries a Product/Article/Review node
    with no brand/publisher/author link at all — the identity node is
    declared but never connected to the content it is supposed to ground."""
    identity_nodes = [
        node for node in nodes if (_node_types(node) & _ORPHAN_IDENTITY_TYPES) and isinstance(node.get("@id"), str)
    ]
    orphan_ids = [node["@id"] for node in identity_nodes if node["@id"] not in referenced_targets]
    if not orphan_ids:
        return None

    disconnected_content = [
        node
        for node in nodes
        if (_node_types(node) & _ORPHAN_CONTENT_TYPES) and not any(prop in node for prop in _ORPHAN_LINK_PROPERTIES)
    ]
    if not disconnected_content:
        return None

    content_types = sorted({t for node in disconnected_content for t in (_node_types(node) & _ORPHAN_CONTENT_TYPES)})
    shown_ids, true_orphan_count = cap_list(orphan_ids, 5)
    more = f" (+{true_orphan_count - 5} more)" if true_orphan_count > 5 else ""

    return Finding(
        id="ENT-11-orphan-identity-node",
        title="An identity node exists but is never connected to the page's content",
        severity="medium",
        evidence=(
            f"{true_orphan_count} identity node(s) ({', '.join(shown_ids)}{more}) are never "
            f"referenced by any other node's @id, while this page also carries "
            f"{len(disconnected_content)} {'/'.join(content_types)} node(s) with no "
            "brand/publisher/author link at all."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Link the content node(s) to the identity node via brand/publisher/author (as "
                "appropriate), or remove the unused identity node if it isn't meant to ground "
                "this content."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-11",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "An Organization/Person/LocalBusiness node is declared to give a consumer something "
            "to resolve the content to. When nothing on the page actually points at it, and the "
            "content itself has no brand/publisher/author link either, the identity node and the "
            "content it should ground never connect — the entity is declared but never attached "
            "to what it is supposed to identify."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "orphan_ids": shown_ids,
            "true_orphan_id_count": true_orphan_count,
            "disconnected_content_types": content_types,
        },
    )


# ---------------------------------------------------------------------------
# ENT-12 — JSON-LD entity-graph fragmentation (cycle 23, Phase 2)
#
# Distinct from ENT-11: ENT-11 catches a *broken* graph (an @id reference
# pointing at nothing). This catches a *valid but poorly-connected* graph —
# every reference resolves, but the page's entities form two or more
# disconnected clusters instead of one cohesive graph, so nothing about
# Organization/Product/Review being the same coherent story is machine-
# visible. Deliberately does NOT also restate ENT-11's own
# orphan-identity-node check (an Organization/Person/LocalBusiness node with
# nothing pointing at it, paired with disconnected content) — that is a
# tighter, already-shipped version of the same underlying signal for one
# specific node-type gate; re-flagging the identical root cause under a
# second capability id would be noise, not new evidence.
# ---------------------------------------------------------------------------

_ENT12_MIN_ENTITIES = 5
_ENT12_MIN_SUBSTANTIAL_COMPONENT_SIZE = 2


def find_entity_graph_fragmentation(nodes: list[dict], page_url: str | None) -> Finding | None:
    """ENT-12. Gated to ≥5 entities: a small page's JSON-LD (a single
    Organization node, say) is expected to have little or nothing to
    connect to, and flagging that as "fragmented" would be noise on the
    overwhelming majority of pages this project audits."""
    if len(nodes) < _ENT12_MIN_ENTITIES:
        return None

    index = build_id_index(nodes)
    resolved_page_url = page_url or ""
    vertex_ids = [node.get("@id") if isinstance(node.get("@id"), str) else f"$node[{i}]" for i, node in enumerate(nodes)]

    edges: list[tuple[str, str]] = []
    for reference in iter_references(nodes):
        if reference.source_node_id is None:
            continue
        if classify_target(reference.target_id, index, resolved_page_url) != "resolved":
            continue
        edges.append((reference.source_node_id, reference.target_id))

    components = connected_components(vertex_ids, edges)
    substantial = [c for c in components if len(c) >= _ENT12_MIN_SUBSTANTIAL_COMPONENT_SIZE]
    if len(substantial) < 2:
        return None

    types_by_vertex = {
        (node.get("@id") if isinstance(node.get("@id"), str) else f"$node[{i}]"): (_node_types(node) or {"Unknown"})
        for i, node in enumerate(nodes)
    }
    substantial.sort(key=len, reverse=True)
    cluster_summaries = [
        "{" + ", ".join(sorted({t for v in cluster for t in types_by_vertex.get(v, {"Unknown"})})) + "}"
        for cluster in substantial[:4]
    ]
    more = f" (+{len(substantial) - 4} more)" if len(substantial) > 4 else ""

    return Finding(
        id="ENT-12-entity-graph-fragmented",
        title="Structured-data graph splits into disconnected clusters",
        severity="low",
        evidence=(
            f"This page's {len(nodes)} JSON-LD entities form {len(substantial)} disconnected "
            f"clusters of 2 or more nodes each: {', '.join(cluster_summaries)}{more}. Every @id "
            "reference resolves correctly — nothing is broken — but nothing links these clusters "
            "to each other."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Link the disconnected clusters together where they describe the same site — e.g. "
                "a Product's brand pointing at the page's Organization node, or a Review's itemReviewed "
                "pointing at the Product it reviews — so a consumer walking the graph can assemble one "
                "coherent entity instead of several unrelated ones."
            ),
            priority="low",
        ),
        category="discoverability",
        capability_id="ENT-12",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Entity resolution and knowledge-graph grounding work by walking @id references to "
            "assemble one coherent entity out of several JSON-LD nodes. A valid graph that is "
            "nonetheless fragmented into disconnected clusters gives a consumer no path from one "
            "cluster to another, even though every individual reference it does have resolves "
            "correctly — a different failure mode from a dangling reference (ENT-11), and invisible "
            "to any check that validates one node or one reference at a time."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "entity_count": len(nodes),
            "substantial_component_count": len(substantial),
            "component_sizes": sorted((len(c) for c in components), reverse=True),
        },
    )


# ---------------------------------------------------------------------------
# ENT-05 / ENT-06 — off-site brand visibility; extraction only, the agent
# judges these (hard constraint 2, cycle 19 — see module docstring)
# ---------------------------------------------------------------------------

_OFFSITE_SNIPPET_RADIUS_CHARS = 200
_OFFSITE_MAX_CANDIDATES = 10
_LOOKALIKE_DOMAIN_MIN_SIMILARITY = 0.75


def _brand_mention_snippet(brand_name: str, text: str) -> str | None:
    """The text window around the first case-insensitive, word-boundary
    mention of `brand_name` in `text` — enough context for the agent to
    read without re-fetching the page, never a verdict on its own."""
    if not brand_name.strip():
        return None
    pattern = r"(?<![A-Za-z0-9])" + re.escape(brand_name.strip()) + r"(?![A-Za-z0-9])"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    start = max(0, match.start() - _OFFSITE_SNIPPET_RADIUS_CHARS)
    end = min(len(text), match.end() + _OFFSITE_SNIPPET_RADIUS_CHARS)
    return text[start:end].strip()


def find_brand_collision_candidates(brand_name: str, offsite_pages: list[dict]) -> list[dict]:
    """ENT-05. For every successfully fetched off-site page that mentions
    `brand_name` at all, a snippet of surrounding context — never a verdict.
    Whether the mention refers to the same brand, an unrelated entity that
    happens to share the name, or a genuine collision worth flagging is a
    judgement about real-world entities this script has no way to make;
    the agent reads the snippet (and the live page, if needed) and decides
    against `references/entity-judgement-rubric.md` §ENT-05."""
    candidates = []
    for page in offsite_pages:
        snippet = _brand_mention_snippet(brand_name, page["text"])
        if snippet is None:
            continue
        candidates.append({"url": page["url"], "snippet": snippet})
    return candidates[:_OFFSITE_MAX_CANDIDATES]


def _domain_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _strip_www(a), _strip_www(b)).ratio()


def find_lookalike_domain_candidates(site: str, offsite_pages: list[dict]) -> list[dict]:
    """ENT-06. The domain-string-similarity half is scriptable and
    deterministic: for each off-site page whose own host is similar to (but
    not the same as, and not a subdomain of) the audited site's own domain,
    a similarity ratio (stdlib `difflib.SequenceMatcher`, no external
    dependency) plus a content snippet. The subdomain exclusion is a
    live-found guard, not a hypothetical: `meta.discourse.org` scored 0.839
    similarity against `discourse.org` on a real fetch and would otherwise
    have surfaced the project's own official community subdomain as a
    lookalike-domain candidate. A high string-similarity score is not
    itself evidence of impersonation — a legitimately different business
    can share a similar name — so this only surfaces candidates; whether
    the fetched page's own content plausibly impersonates the brand is the
    agent's call, against `references/entity-judgement-rubric.md` §ENT-06."""
    candidates = []
    for page in offsite_pages:
        hostname = urllib.parse.urlparse(page["url"]).hostname
        if not hostname:
            continue
        stripped_host = _strip_www(hostname)
        stripped_site = _strip_www(site)
        if stripped_host == stripped_site or stripped_host.endswith("." + stripped_site):
            continue  # the audited site's own domain, or one of its own subdomains — not a lookalike
        similarity = _domain_similarity(hostname, site)
        if similarity < _LOOKALIKE_DOMAIN_MIN_SIMILARITY:
            continue
        candidates.append(
            {
                "url": page["url"],
                "domain": hostname,
                "similarity": round(similarity, 3),
                "content_excerpt": page["text"][:400],
            }
        )
    return candidates[:_OFFSITE_MAX_CANDIDATES]


def build_offsite_judgement_requests(site: str, brand_name: str, offsite_pages: list[dict]) -> list[dict]:
    return [
        {
            "capability_id": "ENT-05",
            "instructions": (
                "Read references/entity-judgement-rubric.md §ENT-05. For each candidate below, "
                "decide whether the mention of the brand name in snippet refers to this same "
                "brand (no defect), or a different, unrelated entity that happens to share the "
                "name closely enough that an assistant could plausibly merge their attributes "
                "(location, rating, offerings) — a genuine collision. Hand-author a Finding only "
                "for a genuine collision; if uncertain, prefer no finding over a false accusation. "
                "If none qualify, emit nothing."
            ),
            "observations": {"candidates": find_brand_collision_candidates(brand_name, offsite_pages)},
        },
        {
            "capability_id": "ENT-06",
            "instructions": (
                "Read references/entity-judgement-rubric.md §ENT-06. For each candidate below "
                "(flagged only for domain-string similarity, not content), read content_excerpt "
                "and decide whether this domain plausibly impersonates the brand (claims to be, "
                "or could be mistaken for, the official site) rather than being a legitimately "
                "different business with a similar name. Hand-author a Finding only for genuine, "
                "plausible impersonation; a wrong accusation is a serious false positive, so "
                "prefer no finding when uncertain. If none qualify, emit nothing."
            ),
            "observations": {"candidates": find_lookalike_domain_candidates(site, offsite_pages)},
        },
    ]


# ---------------------------------------------------------------------------
# ENT-09 — Taxonomy consistency; extraction only, the agent judges this
# ---------------------------------------------------------------------------

# Cycle 24 item 3.4: canonical set, shared/text_spans.py — see that module.
_STOPWORDS = KEYWORD_FOLDING_STOPWORDS


def _keywords(label: str) -> set[str]:
    """Significant words in `label`, plus a crude singular form for each word
    ending in 's', the same folding `content-quality-audit`'s CQ-08 uses —
    reimplemented here rather than imported, so this skill stays
    independently runnable per project convention (see
    skill-engineering-principles.md §5.3, and `_PageParser`'s own docstring
    above for the same reasoning applied to text extraction)."""
    words = {w for w in re.findall(r"[a-z]+", label.lower()) if w not in _STOPWORDS and len(w) > 2}
    singularized = {w[:-1] for w in words if w.endswith("s") and len(w) > 3}
    return words | singularized


_GENERIC_CATEGORY_LABELS = {
    "home", "blog", "news", "general", "other", "misc", "miscellaneous",
    "uncategorized", "uncategorised", "articles", "posts", "shop", "store",
}


def _breadcrumb_labels(node: dict) -> list[str]:
    """The deepest (highest-`position`) name in a BreadcrumbList — the most
    specific category a breadcrumb states — excluding a lone "Home" root.
    `item` can be a bare URL string or a nested object carrying its own
    `name`; both forms appear in real markup."""
    items = node.get("itemListElement")
    if not isinstance(items, list) or not items:
        return []

    def _position(entry: dict) -> float:
        pos = entry.get("position")
        return pos if isinstance(pos, (int, float)) else -1

    entries = [e for e in items if isinstance(e, dict)]
    entries.sort(key=_position)
    if not entries:
        return []
    deepest = entries[-1]
    name = deepest.get("name")
    if not name and isinstance(deepest.get("item"), dict):
        name = deepest["item"].get("name")
    if not isinstance(name, str) or not name.strip():
        return []
    return [name.strip()]


def extract_category_labels(nodes: list[dict]) -> list[tuple[str, str]]:
    """(label, source) pairs from every category-shaped JSON-LD signal this
    project recognises: `Product.category` (schema.org explicitly allows a
    free-text or breadcrumb-style path here), `articleSection` on an
    Article/BlogPosting/NewsArticle, and a `BreadcrumbList`'s deepest item.
    Deduplicated by normalised label text — the same category stated twice
    (e.g. both a breadcrumb and a Product.category) is one thing to judge,
    not two."""
    labels: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(value, source: str):
        if isinstance(value, str) and value.strip():
            candidates = [value.strip()]
        elif isinstance(value, list):
            candidates = [v.strip() for v in value if isinstance(v, str) and v.strip()]
        elif isinstance(value, dict) and isinstance(value.get("name"), str):
            candidates = [value["name"].strip()]
        else:
            candidates = []
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            labels.append((candidate, source))

    for node in nodes:
        if "category" in node:
            _add(node["category"], "product_category")
        if "articleSection" in node:
            _add(node["articleSection"], "article_section")
        if _node_types(node) & {"BreadcrumbList"}:
            for name in _breadcrumb_labels(node):
                _add(name, "breadcrumb")

    return labels


_MIN_VISIBLE_TEXT_WORDS = 50
_TEXT_EXCERPT_WORDS = 200


def find_taxonomy_judgement_candidates(nodes: list[dict], visible_text: str) -> list[dict]:
    """ENT-09. A declared category label plus a text excerpt, for every label
    that shares *zero* keywords with the page's own visible text — the agent
    judges whether that is a genuine mismatch or just a synonym/paraphrase a
    bare keyword match cannot see (e.g. "Laptops" vs. body text that only
    ever says "notebook computers"). Zero overlap is the extraction's own
    guard against noise: any shared keyword at all is treated as agreement
    and never becomes a candidate, so this only surfaces the cases with no
    lexical basis for agreement at all — the ones most worth a second,
    semantic look.

    Guards: a label with no significant (non-generic, >2-char, non-stopword)
    keyword of its own (e.g. "Home", "Blog", "General") is not evaluated —
    there is nothing specific enough to check agreement on. A page with
    fewer than `_MIN_VISIBLE_TEXT_WORDS` words of visible text is not
    evaluated either — too little text for "no overlap" to mean anything
    beyond "not enough content was extracted"."""
    words = visible_text.split()
    if len(words) < _MIN_VISIBLE_TEXT_WORDS:
        return []

    text_keywords = _keywords(visible_text)
    excerpt = " ".join(words[:_TEXT_EXCERPT_WORDS])

    candidates = []
    for label, source in extract_category_labels(nodes):
        if label.strip().lower() in _GENERIC_CATEGORY_LABELS:
            continue
        label_keywords = _keywords(label)
        if not label_keywords:
            continue
        if label_keywords & text_keywords:
            continue  # some shared vocabulary: not a candidate, agreement assumed
        candidates.append({"category_label": label, "source": source, "visible_text_excerpt": excerpt})
    return candidates


def build_agent_judgement_requests(nodes: list[dict], visible_text: str) -> list[dict]:
    return [
        {
            "capability_id": "ENT-09",
            "instructions": (
                "Read references/entity-judgement-rubric.md §ENT-09. For each candidate "
                "below, decide whether category_label genuinely describes what "
                "visible_text_excerpt is about (a synonym or paraphrase counts as agreement) "
                "or is a real mismatch. Hand-author a Finding only for genuine mismatches. "
                "If none qualify, emit nothing."
            ),
            "observations": {"candidates": find_taxonomy_judgement_candidates(nodes, visible_text)},
        },
    ]


# ---------------------------------------------------------------------------
# Orchestration within the skill
# ---------------------------------------------------------------------------


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    nodes, parse_errors, canonical_hrefs, visible_text = parse_page(html)

    schema_findings, schema_unknowns = find_schema_issues(nodes, parse_errors, page_url)
    findings = (
        schema_findings
        + find_knowledge_graph_gaps(nodes)
        + find_markup_text_disagreement(nodes, visible_text)
        + find_canonical_issues(canonical_hrefs, page_url)
    )
    if nodes and not parse_errors:
        # Overlap control: never report a broken graph on a page ENT-01
        # already flagged as having no parseable graph at all.
        findings += find_graph_integrity_issues(nodes, page_url)
        fragmentation = find_entity_graph_fragmentation(nodes, page_url)
        if fragmentation:
            findings.append(fragmentation)
    findings = _stamp_page(findings, page_url)

    judgement_requests = build_agent_judgement_requests(nodes, visible_text)
    if page_url:
        for request in judgement_requests:
            request["observations"]["page_url"] = page_url

    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "page_url": page_url,
        "findings": [f.to_dict() for f in findings],
        "agent_judgement_required": judgement_requests,
        "unknown_checks": [u.to_dict() for u in schema_unknowns],
    }


def _unknown_output(site: str, reason: str, page_url: str | None = None) -> dict:
    return unknown_output(OWNER_SKILL, CAPABILITY_IDS, site, reason, page_url=page_url)


def audit_sitemap(site: str, sitemap_urls: list[str]) -> dict:
    """ENT-04's sitemap-scoped crawl-wide half — a separate, once-per-site
    mode from `audit_html`'s once-per-page mode, since it operates on the
    sitemap's own declared URL list rather than one page's markup."""
    findings = find_sitemap_url_forks(sitemap_urls)
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [f.to_dict() for f in findings],
        "agent_judgement_required": [],
        "unknown_checks": [],
    }


# ---------------------------------------------------------------------------
# ENT-07 — Cross-domain service attribution (--sample-file mode only)
# ---------------------------------------------------------------------------

_SERVICE_KEYWORDS = ("support", "help", "docs", "status")
_ENT07_MIN_SOURCE_PAGES = 2


def _brand_token(site: str) -> str:
    """The first label of `site`'s own registrable domain, lowercased —
    "acme" from "acme.com" or "www.acme.co.uk". See
    `find_service_domain_candidates` for why this gates candidate domains."""
    result = registrable_domain(site)
    if not result.registrable_domain:
        return ""
    return result.registrable_domain.split(".")[0]


def find_service_domain_candidates(site: str, page_links: dict[str, list[str]]) -> list[dict]:
    """Third-party domains worth checking for a `sameAs` bridge back to
    `site`: linked from at least two distinct sampled pages (recurs, not a
    one-off footer link), whose full URL looks service-related (contains
    "support", "help", "docs", or "status" — a real help-desk platform link
    typically carries this in the path, e.g. "acme.zendesk.com/hc", not
    necessarily the hostname) and whose hostname contains the site's own
    brand token.

    The dominant false positive this guards against is a commonly-linked
    but genuinely unrelated third party — a payment processor, a generic
    statuspage.io-hosted status page for some *other* company — that merely
    happens to be linked often. Requiring the brand's own name in the
    candidate's hostname is what distinguishes "this looks like it might be
    OUR support site" from "we link to a popular tool a lot"; recurrence
    across ≥2 distinct pages (not ≥2 raw links, which one footer alone could
    supply) is what distinguishes a site-wide pattern from a single
    incidental mention.
    """
    brand_token = _brand_token(site)
    by_domain: dict[str, dict] = {}
    for page_url, links in page_links.items():
        seen_domains_this_page: set[str] = set()
        for link in links:
            hostname = (urllib.parse.urlparse(link).hostname or "").lower()
            if not hostname or same_entity(hostname, site):
                continue
            if not any(keyword in link.lower() for keyword in _SERVICE_KEYWORDS):
                continue
            if brand_token and brand_token not in hostname:
                continue
            candidate_domain = registrable_domain(hostname).registrable_domain
            if not candidate_domain or candidate_domain in seen_domains_this_page:
                continue
            seen_domains_this_page.add(candidate_domain)
            entry = by_domain.setdefault(
                candidate_domain, {"domain": candidate_domain, "example_url": link, "source_pages": []}
            )
            entry["source_pages"].append(page_url)

    return [entry for entry in by_domain.values() if len(entry["source_pages"]) >= _ENT07_MIN_SOURCE_PAGES]


def _bridges_back_to_site(nodes: list[dict], site: str) -> bool:
    """Whether any JSON-LD node on the candidate's own homepage names `site`
    via `sameAs` or `url` — the reciprocal reference this check verifies is
    missing when it returns False."""
    for node in nodes:
        for field in ("sameAs", "url"):
            value = node.get(field)
            values = value if isinstance(value, list) else [value] if value else []
            for candidate in values:
                if not isinstance(candidate, str):
                    continue
                hostname = urllib.parse.urlparse(candidate).hostname or ""
                if hostname and same_entity(hostname, site):
                    return True
    return False


_ENT07_MAX_SOURCE_PAGES = 10


def _cross_domain_unattributed_finding(candidate: dict) -> Finding:
    domain = candidate["domain"]
    pages = candidate["source_pages"]
    capped_pages, true_page_count = cap_list(pages, _ENT07_MAX_SOURCE_PAGES)
    slug = hashlib.sha256(domain.encode("utf-8")).hexdigest()[:8]
    shown_pages = ", ".join(pages[:3]) + ("…" if len(pages) > 3 else "")
    return Finding(
        id=f"ENT-07-cross-domain-service-unattributed-{slug}",
        title=f"{domain} looks like this brand's service domain but has no structured-data bridge back",
        severity="low",
        evidence=(
            f"{domain} is linked as a support/help/docs/status destination from {len(pages)} sampled "
            f"pages ({shown_pages}) and its hostname carries this brand's own name, but {domain}'s "
            "own homepage carries no sameAs or url reference back to this site."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f"Add a reciprocal sameAs (or Organization.url) reference between this site and "
                f"{domain} so an AI assistant can resolve them as one entity instead of two "
                "unrelated sites."
            ),
            priority="low",
        ),
        category="discoverability",
        capability_id="ENT-07",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Entity resolution walks sameAs/url references to confirm two domains describe the same "
            "organization. A brand-named, service-shaped third-party domain that recurs across the "
            "sampled pages but never names this site back leaves an AI assistant unable to attribute "
            "that domain's content to this brand, splitting what should be one entity's authority "
            "and citations across two unconnected ones."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "domain": domain,
            "source_pages": capped_pages,
            "source_page_count": true_page_count,
            "example_url": candidate["example_url"],
        },
    )


def find_cross_domain_service_attribution(
    site: str, candidates: list[dict], budget: StageBudget
) -> tuple[list[Finding], list[UnknownCheck]]:
    """Fetches each service-domain candidate's homepage to check whether it
    bridges back to `site`. Previously ran its own separate, unbudgeted
    fetch loop after `audit_service_domains`'s own `StageBudget`-guarded
    on-site loop had already finished — an unbounded, uncounted second fetch
    pass on a site with many distinct off-site service-domain candidates
    (Defect 2 finding). Now shares the SAME `budget` instance its caller
    passes in, so total on-site + off-site fetch time stays within one cap
    rather than the off-site pass running for however long it takes
    regardless of how much of the budget the on-site loop already spent.
    Fetching is concurrent and batched (`_SAMPLE_FETCH_CHUNK_SIZE`) exactly
    like the on-site loop, for the same reason."""
    findings: list[Finding] = []
    unknowns: list[UnknownCheck] = []

    allowed: dict[str, dict] = {}  # homepage_url -> candidate, robots-allowed only
    for candidate in candidates:
        domain = candidate["domain"]
        homepage_url = f"https://{domain}/"
        if not robots_allows_offsite_fetch(homepage_url):
            unknowns.append(UnknownCheck("ENT-07", OWNER_SKILL, f"{domain} disallowed by its own robots.txt"))
            continue
        allowed[homepage_url] = candidate

    homepage_urls = list(allowed)
    index = 0
    while index < len(homepage_urls):
        if budget.expired():
            for skipped_url in homepage_urls[index:]:
                domain = allowed[skipped_url]["domain"]
                unknowns.append(
                    UnknownCheck(
                        "ENT-07",
                        OWNER_SKILL,
                        f"{domain} was not fetched: {budget.stage} budget of "
                        f"{budget.cap_seconds}s was exceeded",
                    )
                )
            break
        chunk = homepage_urls[index : index + _SAMPLE_FETCH_CHUNK_SIZE]
        index += len(chunk)
        for homepage_url, html_or_error, status in fetch_pages_concurrently(chunk):
            candidate = allowed[homepage_url]
            domain = candidate["domain"]
            if status != "present" or html_or_error is None:
                unknowns.append(
                    UnknownCheck("ENT-07", OWNER_SKILL, f"{domain} could not be fetched: {html_or_error}")
                )
                continue
            nodes, _, _, _ = parse_page(html_or_error)
            if not _bridges_back_to_site(nodes, site):
                findings.append(_cross_domain_unattributed_finding(candidate))

    return findings, unknowns


# ---------------------------------------------------------------------------
# ENT-08 — Address/NAP clustering (--sample-file mode, cycle 23 Phase 4 B3)
# ---------------------------------------------------------------------------
#
# NAP (name/address/phone) consistency is a foundational local-entity-
# resolution signal. This half checks only the "A": whether the brand's own
# pages state the same address. Phone-number consistency overlaps REN-10
# (see capability matrix) and is not duplicated here.

_ENT08_ADDRESS_PATTERN = re.compile(
    r"\d{1,5}\s[\w.\-]+(?:\s[\w.\-]+){0,4}?\s"
    r"(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|"
    r"Plaza|Suite|Ste|Circle|Cir|Place|Pl)\.?,?\s*(?:[\w.\-]+,\s*)?[A-Z]{2}\s+\d{5}(?:-\d{4})?"
)
_ENT08_MULTI_LOCATION_PATTERN = re.compile(
    r"\b(?:multiple locations|several locations|various locations|find a location|"
    r"store locator|locations near you|all our locations|all of our locations|"
    r"one of our (?:many )?locations)\b",
    re.IGNORECASE,
)
_ENT08_MIN_PAGES_WITH_ADDRESS = 2
_ENT08_CLUSTER_THRESHOLD = 65.0


def extract_address_candidate(visible_text: str) -> str | None:
    """First US-style street-address-shaped match in `visible_text` — number,
    street name, suffix, optional city, two-letter state, zip. Only the
    first match per page (not every one): a page listing several addresses
    itself (a store locator) is a different, already-legitimate shape this
    check does not compare against itself — see `find_address_inconsistencies`
    for the multi-location language gate that gets the final say instead."""
    match = _ENT08_ADDRESS_PATTERN.search(visible_text)
    return match.group(0).strip() if match else None


def find_address_inconsistencies(page_addresses: dict[str, str], all_page_texts: list[str]) -> list[Finding]:
    """ENT-08. Clusters one address candidate per sampled page by fuzzy
    text similarity (`shared/fuzzy_match.single_linkage_clusters`); if two
    or more pages land in mutually dissimilar clusters, the brand's stated
    address disagrees across its own pages — an assistant reading two of
    this brand's pages gets two different answers to "where is this
    business."

    Gated behind an explicit multi-location check, the dominant false
    positive this capability's own plan calls out: a chain, or any brand
    with several real locations, legitimately has different, all-correct
    addresses on different pages. If ANY sampled page uses multiple-location
    language ("store locator", "find a location", ...), this stays silent
    entirely rather than guess which address is the "real" one."""
    if len(page_addresses) < _ENT08_MIN_PAGES_WITH_ADDRESS:
        return []
    if any(_ENT08_MULTI_LOCATION_PATTERN.search(text) for text in all_page_texts):
        return []

    pages = list(page_addresses.keys())
    addresses = [page_addresses[p] for p in pages]
    clusters = single_linkage_clusters(addresses, _ENT08_CLUSTER_THRESHOLD)
    if len(clusters) < 2:
        return []

    clusters = sorted(clusters, key=len, reverse=True)
    return [_address_inconsistency_finding(clusters, pages, addresses)]


_ENT08_MAX_ITEMS = 10


def _address_inconsistency_finding(clusters: list[list[int]], pages: list[str], addresses: list[str]) -> Finding:
    shown = clusters[:3]
    lines = []
    for cluster in shown:
        example_idx = cluster[0]
        cluster_pages = ", ".join(pages[i] for i in cluster[:3])
        lines.append(f'"{addresses[example_idx]}" (on {cluster_pages})')
    more = f" (+{len(clusters) - 3} more distinct address(es))" if len(clusters) > 3 else ""
    slug = hashlib.sha256("|".join(sorted(addresses)).encode("utf-8")).hexdigest()[:8]

    return Finding(
        id=f"ENT-08-address-inconsistency-{slug}",
        title="This brand states different addresses on different pages of the same sampled set",
        severity="medium",
        evidence=(
            f"Across {len(pages)} sampled pages that carry an address, {len(clusters)} mutually "
            f"dissimilar addresses were found: {'; '.join(lines)}{more}. No sampled page used "
            'multiple-location language ("store locator", "find a location", ...), so this does '
            "not look like a legitimate multi-location brand. This is a within-sample finding "
            f"only, over {len(pages)} page(s) carrying an address — a page outside the sample may "
            "resolve or explain the disagreement."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Confirm the brand's correct address and make it consistent across every page "
                "(footer, About, Contact, LocalBusiness JSON-LD) — or, if this is genuinely a "
                "multi-location business, add explicit location-selector language so an assistant "
                "does not treat the pages as contradicting each other."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="ENT-08",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "NAP (name/address/phone) consistency is a foundational local-entity-resolution "
            "signal: when a brand's own pages disagree on its address, an assistant has no "
            "principled way to decide which is current, and may quote the wrong one, or treat "
            "the brand as ambiguous for location-based queries."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "sample_size": len(pages),
            "cluster_count": len(clusters),
            "addresses": addresses[:_ENT08_MAX_ITEMS],
            "pages": pages[:_ENT08_MAX_ITEMS],
        },
    )


_SAMPLE_FETCH_BUDGET_SECONDS = 90.0
# Pages per concurrent batch — the budget is rechecked between batches, not
# between individual pages, so this bounds how far a batch can overrun the
# cap before the next check (Defect 2 follow-up to INF-10).
_SAMPLE_FETCH_CHUNK_SIZE = 10


def audit_service_domains(site: str, page_urls: list[str], *, clock=None) -> dict:
    """ENT-07 and ENT-08's shared multi-page mode — fetches every on-site
    URL in `page_urls` (the orchestrator's own bounded page sample) once,
    extracting both outbound links (ENT-07) and visible text (ENT-08) from
    the same fetch pass, then runs each capability's own detector.

    A separate, once-per-run mode from `audit_html`'s once-per-page mode,
    the same relationship `audit_offsite` has to it for ENT-05/06.

    The fetch loop is concurrent (Defect 2 follow-up to INF-10: sequential
    fetching made the 90s cap likely to fire on perfectly normal sites) —
    `shared/page_fetch.fetch_pages_concurrently` fetches pages in bounded,
    order-preserving batches of `_SAMPLE_FETCH_CHUNK_SIZE`, with `budget`
    checked between batches — a sample of unresponsive pages each burning
    their own fetch timeout could otherwise run well past what one skill
    invocation should cost inside the audit's overall 5-minute budget. The
    check is still cooperative at batch granularity (an in-flight batch is
    allowed to finish rather than aborted mid-flight), a deliberately
    coarser version of the same tradeoff the old per-page check already
    made. On expiry, fetching stops; already-fetched pages still get
    findings computed over them (reduced coverage, not a failed
    capability), and every remaining un-fetched page gets its own
    `unknown_checks` entry naming the cap as the reason. The SAME `budget`
    instance is then passed to `find_cross_domain_service_attribution`
    (below), so its own off-site fetch pass shares this loop's time budget
    rather than running afterward with no cap of its own — previously an
    unbounded, uncounted second fetch pass this function's own budget said
    nothing about. `coverage_manifest` is always attached to the output."""
    clock_kwargs = {"clock": clock} if clock is not None else {}
    budget = StageBudget(f"{OWNER_SKILL}-sample-fetch", _SAMPLE_FETCH_BUDGET_SECONDS, **clock_kwargs)
    unknowns: list[UnknownCheck] = []
    page_links: dict[str, list[str]] = {}
    page_addresses: dict[str, str] = {}
    all_page_texts: list[str] = []
    index = 0
    while index < len(page_urls):
        if budget.expired():
            for skipped_url in page_urls[index:]:
                unknowns.append(
                    UnknownCheck(
                        "ENT-07",
                        OWNER_SKILL,
                        f"{skipped_url} was not fetched: {budget.stage} budget of "
                        f"{budget.cap_seconds}s was exceeded",
                    )
                )
            break
        chunk = page_urls[index : index + _SAMPLE_FETCH_CHUNK_SIZE]
        index += len(chunk)
        for page_url, html_or_error, status in fetch_pages_concurrently(chunk):
            if status != "present" or html_or_error is None:
                unknowns.append(
                    UnknownCheck("ENT-07", OWNER_SKILL, f"{page_url} could not be fetched: {html_or_error}")
                )
                continue
            page_links[page_url] = extract_outbound_links(html_or_error, page_url)
            _, _, _, visible_text = parse_page(html_or_error)
            all_page_texts.append(visible_text)
            address = extract_address_candidate(visible_text)
            if address:
                page_addresses[page_url] = address

    candidates = find_service_domain_candidates(site, page_links)
    findings, fetch_unknowns = find_cross_domain_service_attribution(site, candidates, budget)
    unknowns.extend(fetch_unknowns)
    findings += find_address_inconsistencies(page_addresses, all_page_texts)

    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [f.to_dict() for f in findings],
        "agent_judgement_required": [],
        "unknown_checks": [u.to_dict() for u in unknowns],
        "coverage": coverage_manifest([budget]),
    }


# ---------------------------------------------------------------------------
# Off-site fetching (--offsite-url mode only) — ENT-05/ENT-06
# ---------------------------------------------------------------------------


def robots_allows_offsite_fetch(url: str) -> bool:
    """Per-host robots.txt check for a THIRD-PARTY host, distinct from this
    project's on-site fetch guard: fetches that host's own /robots.txt
    (same SSRF/timeout/size bounds as any other fetch in this file) and
    asks whether this user agent may fetch `url`. A robots.txt that could
    not be fetched at all (missing, unreachable, non-200) is treated as
    allow-all — the standard, de-facto convention (RFC 9309: absence of
    robots.txt means unrestricted access) — but a robots.txt that WAS
    fetched and disallows the path is always honoured. Never fetch a
    third-party URL without checking first."""
    hostname = urllib.parse.urlparse(url).hostname
    if not hostname:
        return False
    robots_url = f"https://{hostname}/robots.txt"
    robots_text, status = fetch_page_html(robots_url)
    if status != "present" or robots_text is None:
        return True
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def fetch_offsite_pages(urls: list[str]) -> tuple[list[dict], list[UnknownCheck]]:
    """Fetches every agent-supplied off-site URL that robots.txt allows,
    returning (successfully fetched pages, one UnknownCheck per URL that was
    skipped or failed). A disallowed or unreachable URL is reported, never
    silently dropped — "reduced coverage is reported, never hidden" applies
    here exactly as it does everywhere else in this project."""
    pages: list[dict] = []
    unknowns: list[UnknownCheck] = []
    for url in urls:
        if not robots_allows_offsite_fetch(url):
            unknowns.append(UnknownCheck("*", OWNER_SKILL, f"{url} disallowed by its own robots.txt"))
            continue
        html_or_error, status = fetch_page_html(url)
        if status != "present" or html_or_error is None:
            unknowns.append(UnknownCheck("*", OWNER_SKILL, f"{url} could not be fetched: {html_or_error}"))
            continue
        _, _, _, visible_text = parse_page(html_or_error)
        pages.append({"url": url, "text": visible_text})
    return pages, unknowns


def audit_offsite(site: str, brand_name: str, offsite_urls: list[str]) -> dict:
    """ENT-05/ENT-06's off-site mode — a separate, once-per-run mode from
    `audit_html`'s once-per-page mode, since it operates on agent-supplied
    off-site URLs rather than the audited site's own markup. Every
    candidate is extraction-only; the agent resolves `agent_judgement_required`
    per the SKILL.md procedure before this output reaches the entrypoint."""
    pages, unknowns = fetch_offsite_pages(offsite_urls)
    judgement_requests = build_offsite_judgement_requests(site, brand_name, pages)
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [],
        "agent_judgement_required": judgement_requests,
        "unknown_checks": [u.to_dict() for u in unknowns],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_page_arguments(parser)
    parser.add_argument(
        "--sitemap-file",
        help=(
            "Run only ENT-04's sitemap-scoped fork check against a local file of sitemap URLs "
            "(one <loc> URL per line, e.g. extracted from perimeter-access-audit's PER-06 fetch) "
            "instead of auditing a single page's HTML."
        ),
    )
    parser.add_argument(
        "--offsite-url",
        action="append",
        default=[],
        help=(
            "Run only ENT-05/ENT-06's off-site mode against this URL (repeatable) — a page the "
            "calling agent already found via its own search, on a public site such as Reddit, "
            "Quora, a forum, or a review site. Fetched only if that host's own robots.txt allows it."
        ),
    )
    parser.add_argument(
        "--brand-name",
        help="Brand name to search off-site pages for (ENT-05). Defaults to --site if omitted.",
    )
    parser.add_argument(
        "--sample-file",
        help=(
            "Run ENT-07's cross-domain service-attribution check and ENT-08's address/NAP "
            "clustering check across a local file of on-site page URLs (one per line — the "
            "sample_urls from audit-orchestrator's sample_pages.py) instead of auditing a single "
            "page's HTML. Fetches each on-site page directly (same as --url), plus, for any "
            "surviving ENT-07 candidate domain, that candidate's own third-party homepage "
            "(robots.txt-checked, same as --offsite-url). Requires --site."
        ),
    )
    args = parser.parse_args(argv)

    if args.sample_file:
        if not args.site:
            parser.error("--site is required with --sample-file")
        site = site_label(args.site)
        page_urls = [
            line.strip()
            for line in Path(args.sample_file).read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        json.dump(audit_service_domains(site, page_urls), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.sitemap_file:
        site = site_label(args.site or "")
        urls = [
            line.strip()
            for line in Path(args.sitemap_file).read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        json.dump(audit_sitemap(site, urls), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.offsite_url:
        if not args.site:
            parser.error("--site is required with --offsite-url")
        site = site_label(args.site)
        brand_name = args.brand_name or site
        json.dump(audit_offsite(site, brand_name, args.offsite_url), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not any((args.url, args.site)):
        parser.error("one of --url, --site, --sitemap-file, --offsite-url or --sample-file is required")
    site = site_label(args.site or args.url)
    page_url = args.page_url or args.url

    html, exit_code = resolve_page_html(args, site, page_url, _unknown_output)
    if html is None:
        return exit_code

    json.dump(audit_html(site, html, page_url=page_url), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
