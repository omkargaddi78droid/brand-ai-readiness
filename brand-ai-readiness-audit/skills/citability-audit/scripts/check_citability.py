#!/usr/bin/env python3
"""Citability audit: is this page easy to reach, read, and quote a clear
fact from — the selection function appendix B describes for how assistants
pick sources.

Owns six capabilities, split by whether a verdict is deterministic or needs
judgement — the same split engagement-audit uses between EN-01/03 and EN-06/09:

  CIT-01  Trust-signal authority (About-page discoverability) — SCRIPT DECIDES
  CIT-02  Explicit source attribution — SCRIPT DECIDES
  CIT-06  Statistics density / numeric verifiability — SCRIPT DECIDES
  CIT-07  Citation-position weighting — SCRIPT DECIDES
  CIT-04  Citation recall (load-bearing claims with no source) — AGENT DECIDES,
          against references/citability-judgement-rubric.md
  CIT-13  Off-site corroboration (agent-supplied off-site URLs; cycle 19) —
          AGENT DECIDES, against references/citability-judgement-rubric.md

CIT-01/02/06/07 are objectively checkable from the markup: a conventional
About-page link either exists or doesn't; a substantial page either links
anywhere off-domain or doesn't; a superlative claim either has a number in
its own sentence or doesn't; an outbound citation either falls in the last
20% of the page or doesn't. CIT-04 is not: whether an unsupported claim is
"load-bearing" — central enough to the page's purpose that a reader would
want it sourced — is a judgement about what matters on this specific page,
not a pattern a regex can safely assert. The script extracts every candidate
(a sentence with a number and no nearby link) into `agent_judgement_required`
and stops; asserting "unsourced: yes, this matters" from the pattern alone
would be exactly the false-positive-of-severity failure this project's
calibration discipline exists to prevent.

**CIT-13 is an off-site, cycle-19 addition**, reversed from `DEFERRED`
("off-site provenance tracing exceeds the runtime budget") once hard
constraint 2 (confirmed with the judges, `docs/capability-matrix.md`'s
"Hard constraints" section) permitted bounded, direct queries to named
public sites. This script does not search the web itself — it only fetches
agent-supplied `--offsite-url` candidates, reuses CIT-04's own
`find_citation_recall_candidates` extraction as CIT-13's on-page claim
pool (the same "sentence with a number, no link in the sentence" shape,
same reuse-upstream-infra pattern CIT-07 already established against
CIT-02's `_is_external_link`), and checks — deterministically, via numeric
substring survival — whether that claim's own number appears anywhere in
any fetched off-site page's text at all. A claim whose number appears
nowhere off-site becomes an `agent_judgement_required` candidate; whether
it is genuinely worth flagging as fragile (appendix D: single-source
claims are fragile) rather than an obviously fine unsourced detail (a
price, a date) is, like CIT-04, the agent's call.

Deliberately does NOT own: CIT-03 (citation precision — does a cited source
actually support the claim it's attached to) and CIT-12 (abstractiveness vs
faithfulness) — both need reading comprehension across the claim and its
source, out of scope for this cycle. CIT-05 (quotation density) and CIT-10
(self-interested comparison disclosure) were considered and dropped: CIT-05's
attribution patterns vary too widely to script at this project's
false-positive bar, and CIT-10 would fire on nearly every vendor-authored
comparison page, since disclosure language is rare in practice regardless of
whether the page is legitimate — a pattern that fires on the overwhelming
majority of both good and bad pages is not a detector. CIT-08 (link-graph
structure) and CIT-09 (comparison-content gap) need crawl-wide or off-site
context a single-page script does not have — unlike CIT-13, both are about
the audited site's OWN missing content (no comparison page, no link-graph
separation), not off-site corroboration, so hard constraint 2 does not
reach them. CIT-11 remains `DEFERRED`: matching a page's own declarative
claim text against forum/social opinion for provenance is a fuzzy-matching
complexity problem, not a policy block — see capability matrix.

Category
--------
category: "discoverability", gate: 3 — this cluster is squarely appendix B's
mechanism: which pages an assistant selects as a source when it looks things
up, not whether the perimeter lets the crawler in (gate 1) or whether the
markup is machine-readable at all (gate 2).

Determinism
-----------
CIT-01/02/06's detectors are pure functions of the input HTML. CIT-04's
extraction is also pure; the judgement layered on top of it is not run by
this script, by design — see the module docstring's opening paragraph.

Safety
------
`--url` mode fetches exactly one page, same SSRF guard and Content-Encoding
handling as every other page-level skill in this marketplace.

Usage:
    check_citability.py --url https://example.com/guide
    check_citability.py --site example.com --html-file page.html

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...], "site": ..., "page_url": ...,
     "findings": [...], "agent_judgement_required": [...], "unknown_checks": [...]}
`agent_judgement_required` is intermediate — the SKILL.md procedure resolves
it into `findings` (or drops it) before this file is composed into the final
report, exactly as engagement-audit's does for EN-01/EN-03.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402

OWNER_SKILL = "citability-audit"
CAPABILITY_IDS = ["CIT-01", "CIT-02", "CIT-04", "CIT-06", "CIT-07", "CIT-13"]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5_000_000
MIN_SUBSTANTIAL_WORD_COUNT = 500


# ---------------------------------------------------------------------------
# HTML parsing: links + visible text, one pass
# ---------------------------------------------------------------------------

_SKIP_TAGS = {"script", "style", "code", "pre", "noscript", "template", "svg"}
_BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th",
}

_ABOUT_PATH_SEGMENTS = {
    "about", "about-us", "our-story", "company", "our-team",
    "who-we-are", "meet-the-team", "team",
}


_STATIC_FILE_EXTENSION = re.compile(r"\.(?:html?|php|aspx?|jsp)$")


def _normalize_segment(segment: str) -> str:
    """Two real conventions found live, neither anticipated by a bare
    exact-match: MediaWiki namespace-prefixed titles (`Wikipedia:About`,
    used across the whole MediaWiki ecosystem — Wikipedia, Wiktionary,
    Fandom, and many corporate/community wikis) and static-site-generator
    output with a file extension (`about.html`, e.g. Sphinx-generated docs
    like docs.python.org). Both were caught by running this check against
    real sites, not by anticipating them in advance."""
    seg = segment.lower()
    if ":" in seg:
        seg = seg.rsplit(":", 1)[-1]
    return _STATIC_FILE_EXTENSION.sub("", seg)


def _looks_like_about_path(path: str) -> bool:
    """Segment-based, not a path-anchored regex: `href="about-us"` (no
    leading slash — a completely ordinary same-directory relative link) has
    `urlparse().path == "about-us"`, which a regex requiring a literal
    leading "/" never matches. Splitting into segments handles every link
    form (leading slash, none, "./", trailing slash, query string already
    stripped by urlparse) the same way, and a whole-segment set membership
    check is naturally immune to the "/roundabout-tour" /
    "/company-news/2026" substring false positives a looser regex would
    risk."""
    segments = [seg for seg in path.strip("/").split("/") if seg not in ("", ".", "..")]
    return any(_normalize_segment(seg) in _ABOUT_PATH_SEGMENTS for seg in segments)


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._text_chunks: list[str] = []
        # Deliberately two separate collections, not one. `<link href>` in
        # <head> is a real, distinct convention for the same "where is the
        # About page" information `<a href>` carries in visible nav — e.g.
        # Sphinx-generated docs (docs.python.org among them) publish
        # `<link rel="author" href="../about.html">`, discoverable to a
        # machine but never rendered as a clickable link a human would see.
        # Found live, on exactly the kind of page (developer documentation)
        # this capability cares most about. But `<link>` also covers
        # stylesheets, preloads and icons, none of which are a source
        # citation — folding it into CIT-02's external-link count (which
        # started as a straight rename of this field) would have silently
        # let a CDN stylesheet link suppress a real "no source attribution"
        # finding. `anchor_hrefs` (CIT-02: only real, human-followable links
        # count as a citation) and `all_hrefs` (CIT-01: any href, including
        # <link>, counts as evidence of where the About page is) are kept
        # apart on purpose.
        self.anchor_hrefs: list[str] = []
        self.all_hrefs: list[str] = []
        # CIT-07 only: character offset into the raw text stream at the
        # moment each anchor href appeared, one entry per `anchor_hrefs`
        # entry (same order, same length). Kept alongside the existing
        # fields rather than changing `parse_page`'s stable 3-value return
        # that 22 existing tests and every other capability already unpack.
        self.anchor_offsets: list[int] = []

    def handle_starttag(self, tag, attrs):
        self._open_tag(tag, dict(attrs))

    def handle_startendtag(self, tag, attrs):
        self._open_tag(tag, dict(attrs))
        self._close_tag(tag)

    def handle_endtag(self, tag):
        self._close_tag(tag)

    def _open_tag(self, tag, attr_dict):
        href = attr_dict.get("href")
        if tag == "a" and href:
            self.anchor_hrefs.append(href.strip())
            self.all_hrefs.append(href.strip())
            self.anchor_offsets.append(len("".join(self._text_chunks)))
        elif tag == "link" and href:
            self.all_hrefs.append(href.strip())
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

    def _close_tag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._text_chunks.append(re.sub(r"\s+", " ", data))

    def visible_text(self) -> str:
        raw = "".join(self._text_chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)

    def raw_length(self) -> int:
        return len("".join(self._text_chunks))


def parse_page_with_anchor_positions(html: str) -> tuple[list[tuple[str, int]], int]:
    """CIT-07 only: (href, offset) pairs in document order, plus the raw
    text length they're offsets into. A separate entrypoint from
    `parse_page` for the same reason `anchor_offsets` is a separate field —
    no existing caller's return-value shape changes."""
    parser = _PageParser()
    parser.feed(html)
    return list(zip(parser.anchor_hrefs, parser.anchor_offsets)), parser.raw_length()


def parse_page(html: str) -> tuple[list[str], list[str], str]:
    """Returns (anchor_hrefs, all_hrefs, visible_text). See `_PageParser`'s
    docstring for why the two href collections are kept separate."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    return parser.anchor_hrefs, parser.all_hrefs, parser.visible_text()


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _hostname_of(url_or_domain: str) -> str | None:
    if "://" not in url_or_domain:
        url_or_domain = "https://" + url_or_domain
    return urllib.parse.urlparse(url_or_domain).hostname


def _strip_www(hostname: str) -> str:
    return hostname[4:] if hostname.lower().startswith("www.") else hostname.lower()


# ---------------------------------------------------------------------------
# CIT-01 — Trust-signal authority (About-page discoverability)
# ---------------------------------------------------------------------------


def find_missing_about_link(hrefs: list[str]) -> list[Finding]:
    for href in hrefs:
        path = urllib.parse.urlparse(href).path
        if _looks_like_about_path(path):
            return []
    return [
        Finding(
            id="CIT-01-no-about-link",
            title="No About/company page is linked from this page",
            severity="medium",
            evidence=f"None of the {len(hrefs)} link(s) on this page point to a conventional About/company URL path (e.g. /about, /company, /our-team).",
            suggested_action=SuggestedAction(
                summary="Link to an About/company page from the navigation or footer, naming who publishes this content and how to reach them.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="CIT-01",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A page with no discoverable path to who publishes it gives an assistant "
                "nothing to ground the brand against — no organisation to resolve, no "
                "authority signal to weigh the content's trustworthiness against."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"link_count": len(hrefs)},
        )
    ]


# ---------------------------------------------------------------------------
# CIT-02 — Explicit source attribution
# ---------------------------------------------------------------------------


def _is_external_link(href: str, current_host: str | None) -> bool:
    if not href.lower().startswith(("http://", "https://")):
        return False
    link_host = urllib.parse.urlparse(href).hostname
    if not link_host:
        return False
    return current_host is None or _strip_www(link_host) != current_host


def find_missing_source_attribution(hrefs: list[str], visible_text: str, site: str | None) -> list[Finding]:
    word_count = len(visible_text.split())
    if word_count < MIN_SUBSTANTIAL_WORD_COUNT:
        return []

    current_host = _strip_www(site) if site else None
    external_count = sum(1 for href in hrefs if _is_external_link(href, current_host))

    if external_count > 0:
        return []

    return [
        Finding(
            id="CIT-02-no-source-attribution",
            title="A substantial page cites no outside sources at all",
            severity="medium",
            evidence=f"This page has {word_count} words of visible text and zero links to any other domain.",
            suggested_action=SuggestedAction(
                summary="Link to the sources behind any factual or statistical claims on this page — studies, official data, primary reporting.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="CIT-02",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Appendix D: a claim repeated only in one place, with nothing pointing "
                "outward to corroborate it, is fragile. A page of this length making claims "
                "with zero outbound attribution reads as self-referential — nothing on the "
                "page lets a reader or an assistant check where the substance came from."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"word_count": word_count, "external_link_count": 0},
        )
    ]


# ---------------------------------------------------------------------------
# CIT-07 — Citation-position weighting
# ---------------------------------------------------------------------------

_LATE_CITATION_THRESHOLD = 0.8  # only the last 20% of the page counts as "buried"


def find_late_citations(
    anchor_positions: list[tuple[str, int]], total_length: int, visible_text: str, site: str | None
) -> list[Finding]:
    """CIT-07. Reuses CIT-02's own external-link definition — an outbound,
    off-domain `<a href>` is a citation the same way CIT-02 counts it. The
    new signal is where in the page each one falls, not whether one exists
    at all: that precondition is CIT-02's job, and this capability only has
    something to say once it's satisfied. A model that truncates a long
    page reads and weights early tokens far more heavily than late ones; a
    citation only reachable in the last stretch of a long page may as well
    not exist for that reader.
    """
    word_count = len(visible_text.split())
    if word_count < MIN_SUBSTANTIAL_WORD_COUNT or total_length <= 0:
        return []

    current_host = _strip_www(site) if site else None
    fractions = [
        offset / total_length
        for href, offset in anchor_positions
        if _is_external_link(href, current_host)
    ]
    if not fractions or min(fractions) < _LATE_CITATION_THRESHOLD:
        return []

    return [
        Finding(
            id="CIT-07-late-citation",
            title="Every outbound citation is buried in the last stretch of the page",
            severity="low",
            evidence=(
                f"This page has {word_count} words and {len(fractions)} outbound citation(s), all "
                f"positioned at or past {int(_LATE_CITATION_THRESHOLD * 100)}% of the way through "
                "the page."
            ),
            suggested_action=SuggestedAction(
                summary="Move at least one outbound citation earlier — near the claim it supports, not only in a footer or references section at the end.",
                priority="low",
            ),
            category="discoverability",
            capability_id="CIT-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A model summarising or answering from a long page weights earlier content more "
                "heavily and may truncate before reaching the end at all — a citation that only "
                "ever appears in the final stretch is effectively invisible to exactly the kind "
                "of reader this whole cluster of capabilities is written for."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"word_count": word_count, "citation_fractions": [round(f, 3) for f in fractions]},
        )
    ]


# ---------------------------------------------------------------------------
# CIT-06 — Statistics density / numeric verifiability
# ---------------------------------------------------------------------------

_SUPERLATIVE_PHRASES = (
    "the best", "the fastest", "the leading", "industry-leading", "industry leading",
    "world-class", "world class", "most trusted", "number one", "the number 1",
    "the largest", "the most popular", "cutting-edge", "cutting edge",
    "state-of-the-art", "state of the art", "unmatched", "unrivaled", "unrivalled",
    "best-in-class", "best in class", "the most advanced",
)
_SUPERLATIVE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _SUPERLATIVE_PHRASES) + r")\b", re.IGNORECASE
)
_HAS_NUMBER = re.compile(r"\d")

# A quoted testimonial is someone else's words, not the brand's own claim —
# CIT-06 has no business judging a customer's opinion as an unsourced brand
# superlative. Matches a straight or curly double-quote pair; bounded to
# stay well clear of runaway matching on an unpaired quote elsewhere on the
# page, while still covering a realistic multi-sentence testimonial (a real
# one seen live ran to ~1000 words). Deliberately does not touch single
# quotes/apostrophes — those collide with contractions and possessives far
# too often to use as a quotation signal.
_QUOTED_SPAN_PATTERN = re.compile(r'["“][^"”]{20,3000}["”]')


def _quoted_spans(text: str) -> list[str]:
    return _QUOTED_SPAN_PATTERN.findall(text)


def find_unverifiable_superlatives(visible_text: str) -> list[Finding]:
    quoted_spans = _quoted_spans(visible_text)
    matches: list[tuple[str, str]] = []
    for sentence in _split_sentences(visible_text):
        s = sentence.strip()
        if len(s) < 20 or len(s) > 400:
            continue
        match = _SUPERLATIVE_PATTERN.search(s)
        if not match:
            continue
        if _HAS_NUMBER.search(s):
            continue
        if any(s in span for span in quoted_spans):
            continue
        matches.append((match.group(0), s))

    if not matches:
        return []

    examples = matches[:5]
    quoted = "; ".join(f'"{s}"' for _, s in examples)
    more = f" (+{len(matches) - 5} more)" if len(matches) > 5 else ""

    return [
        Finding(
            id="CIT-06-unverifiable-superlatives",
            title="Superlative claims appear with no number to back them up",
            severity="low",
            evidence=(
                f'Found {len(matches)} sentence(s) using an unqualified superlative '
                f'("the best", "industry-leading", ...) with no statistic in the same '
                f"sentence: {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Replace or support each superlative with a concrete, sourced number — "
                    '"the fastest" becomes "the fastest: 940 Mbps average, per [source]".'
                ),
                priority="low",
            ),
            category="discoverability",
            capability_id="CIT-06",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An unqualified superlative is a claim an assistant cannot verify or quote "
                "as a fact — it can only repeat it as marketing language, which weakens "
                "rather than strengthens a citation. A sourced number is quotable; "
                '"industry-leading" on its own is not.'
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"matches": [{"phrase": p, "sentence": s} for p, s in matches]},
        )
    ]


# ---------------------------------------------------------------------------
# CIT-04 — Citation recall (agent-judged)
# ---------------------------------------------------------------------------

_CLAIM_NUMBER_PATTERN = re.compile(r"\d")
_LINK_MARKER = "\x00LINK\x00"  # placeholder injected where <a> tags were, so a
# sentence's own text can be checked for a nearby link without needing full
# DOM position tracking


def _text_with_link_markers(html: str) -> str:
    """Same extraction as `parse_page`, except every <a ...> open tag leaves a
    marker in the text stream so `find_citation_recall_candidates` can tell
    whether a sentence contains a link without re-parsing the DOM."""
    marked = re.sub(r"<a\b[^>]*>", _LINK_MARKER, html, flags=re.IGNORECASE)
    _anchor_hrefs, _all_hrefs, text = parse_page(marked)
    return text


def find_citation_recall_candidates(html: str) -> list[dict]:
    text = _text_with_link_markers(html)
    candidates = []
    for sentence in _split_sentences(text):
        s = sentence.strip()
        if len(s) < 20 or len(s) > 400:
            continue
        if _LINK_MARKER in s:
            continue
        if not _CLAIM_NUMBER_PATTERN.search(s):
            continue
        candidates.append(s.replace(_LINK_MARKER, ""))
    return candidates[:15]


def build_agent_judgement_requests(
    html: str, visible_text: str, offsite_pages: list[dict] | None = None
) -> list[dict]:
    candidates = find_citation_recall_candidates(html)
    requests = [
        {
            "capability_id": "CIT-04",
            "instructions": (
                "Read references/citability-judgement-rubric.md §CIT-04. For each candidate "
                "sentence below (a sentence containing a number with no link in the same "
                "sentence), decide whether it is a load-bearing claim central to this page's "
                "purpose that a reader would reasonably expect to be sourced — not every "
                "number needs a citation (a price, a model number, a date is often fine "
                "unsourced). Hand-author a Finding only for genuine cases, per the rubric's "
                "worked examples. If none of the candidates are load-bearing, emit nothing."
            ),
            "observations": {
                "candidate_unsourced_claims": candidates,
                "total_candidates_found": len(candidates),
                "total_word_count": len(visible_text.split()),
            },
        }
    ]
    if offsite_pages is not None:
        offsite_candidates = find_offsite_corroboration_candidates(html, offsite_pages)
        requests.append(
            {
                "capability_id": "CIT-13",
                "instructions": (
                    "Read references/citability-judgement-rubric.md §CIT-13. For each candidate "
                    "claim below (a numeric claim on this page whose own number was not found on "
                    "any of the fetched off-site pages), decide whether it is genuinely fragile "
                    "for being single-sourced — a decision-critical claim a reader would want "
                    "independently corroborated — or an obviously fine unsourced detail (a price, "
                    "a model number, an internal metric) that off-site corroboration was never "
                    "going to exist for anyway. Hand-author a Finding only for genuine cases. If "
                    "none of the candidates are fragile in this sense, emit nothing."
                ),
                "observations": {
                    "candidates": offsite_candidates,
                    "offsite_pages_checked": len(offsite_pages),
                },
            }
        )
    return requests


# ---------------------------------------------------------------------------
# CIT-13 — Off-site corroboration; extraction only, the agent judges this
# (hard constraint 2, cycle 19 — see module docstring)
# ---------------------------------------------------------------------------

_NUMBER_TOKEN_PATTERN = re.compile(r"\d[\d,]*\.?\d*%?")
_CIT13_MAX_CANDIDATES = 5


def _significant_number(sentence: str) -> str | None:
    """The longest numeric token in a sentence, as a rough proxy for "the
    specific fact this claim is actually about" — a four-digit year or a
    percentage is more claim-specific than a stray single digit elsewhere
    in the same sentence."""
    matches = _NUMBER_TOKEN_PATTERN.findall(sentence)
    if not matches:
        return None
    return max(matches, key=len)


def _number_appears_in(number: str, text: str) -> bool:
    normalized = number.replace(",", "")
    pattern = r"(?<![\d.])" + re.escape(normalized) + r"(?![\d])"
    return re.search(pattern, text.replace(",", "")) is not None


def find_offsite_corroboration_candidates(html: str, offsite_pages: list[dict]) -> list[dict]:
    """CIT-13. Reuses CIT-04's own claim extraction (a sentence with a
    number and no in-sentence link) as the candidate pool, then keeps only
    the claims whose own significant number does not appear on ANY fetched
    off-site page — a deterministic, numeric survival check, the same shape
    as REN-04/RET-01 elsewhere in this project. Never asserts fragility
    itself: an unmatched number is not proof a claim needs corroboration
    (plenty of perfectly fine claims — a price, an internal model number —
    have no reason to appear elsewhere), only that this project's own
    off-site check found none; the agent judges which candidates are
    genuinely worth flagging."""
    if not offsite_pages:
        return []

    claims = find_citation_recall_candidates(html)
    candidates = []
    for claim in claims:
        number = _significant_number(claim)
        if number is None:
            continue
        if any(_number_appears_in(number, page["text"]) for page in offsite_pages):
            continue  # corroborated by at least one off-site page
        candidates.append({"claim": claim, "number": number})
        if len(candidates) >= _CIT13_MAX_CANDIDATES:
            break
    return candidates


# ---------------------------------------------------------------------------
# Orchestration within the skill
# ---------------------------------------------------------------------------


def audit_html(
    site: str, html: str, page_url: str | None = None, offsite_urls: list[str] | None = None
) -> dict:
    anchor_hrefs, all_hrefs, visible_text = parse_page(html)
    anchor_positions, total_length = parse_page_with_anchor_positions(html)

    findings = (
        find_missing_about_link(all_hrefs)
        + find_missing_source_attribution(anchor_hrefs, visible_text, site)
        + find_late_citations(anchor_positions, total_length, visible_text, site)
        + find_unverifiable_superlatives(visible_text)
    )
    findings = _stamp_page(findings, page_url)

    offsite_pages: list[dict] | None = None
    offsite_unknowns: list[UnknownCheck] = []
    if offsite_urls:
        offsite_pages, offsite_unknowns = fetch_offsite_pages(offsite_urls)

    judgement_requests = build_agent_judgement_requests(html, visible_text, offsite_pages)
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
        "unknown_checks": [u.to_dict() for u in offsite_unknowns],
    }


def _stamp_page(findings: list[Finding], page_url: str | None) -> list[Finding]:
    if not page_url:
        return findings
    for finding in findings:
        finding.evidence = f"On {page_url}: {finding.evidence}"
        finding.structured_evidence = {**(finding.structured_evidence or {}), "page_url": page_url}
    return findings


def _unknown_output(site: str, reason: str, page_url: str | None = None) -> dict:
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "page_url": page_url,
        "findings": [],
        "agent_judgement_required": [],
        "unknown_checks": [UnknownCheck("*", OWNER_SKILL, reason).to_dict()],
    }


# ---------------------------------------------------------------------------
# Fetching (--url mode only)
# ---------------------------------------------------------------------------


def is_public_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


_MAX_DECOMPRESSED_BYTES = 20_000_000


def decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
    """Undo Content-Encoding before the body is treated as text. See the
    identical function in entity-audit/content-quality-audit/engagement-audit
    for the full rationale (found live against python.org's CDN, which gzips
    regardless of client negotiation; urllib never auto-decompresses)."""
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


def fetch_page_html(url: str) -> tuple[str | None, str]:
    hostname = urllib.parse.urlparse(url).hostname
    if not hostname or not is_public_host(hostname):
        return f"{url} does not resolve to a public address", "unavailable"

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            if content_type and "html" not in content_type.lower() and "text" not in content_type.lower():
                return f"{url} returned Content-Type {content_type!r}, not HTML/text", "not_html"
            raw = response.read(MAX_PAGE_BYTES)
            content_encoding = response.headers.get("Content-Encoding", "")
        raw = decode_content_encoding(raw, content_encoding)
        return raw.decode("utf-8", errors="replace"), "present"
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        return f"{url} returned HTTP {code}", "unavailable"
    except Exception as error:
        return f"{url} could not be fetched: {type(error).__name__}: {error}", "unavailable"


def site_label(url_or_domain: str) -> str:
    value = url_or_domain.strip()
    for scheme in ("https://", "http://"):
        if value.lower().startswith(scheme):
            value = value[len(scheme):]
            break
    return value.split("/")[0].strip().lower()


# ---------------------------------------------------------------------------
# Off-site fetching (--offsite-url, CIT-13 only)
# ---------------------------------------------------------------------------


def robots_allows_offsite_fetch(url: str) -> bool:
    """Per-host robots.txt check for a THIRD-PARTY host — see entity-audit's
    identical function for the full rationale (RFC 9309: an unreachable
    robots.txt defaults to allow-all; a reachable one that disallows is
    always honoured). Reimplemented here per this project's independently-
    runnable-skill convention rather than imported."""
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
    pages: list[dict] = []
    unknowns: list[UnknownCheck] = []
    for url in urls:
        if not robots_allows_offsite_fetch(url):
            unknowns.append(UnknownCheck("CIT-13", OWNER_SKILL, f"{url} disallowed by its own robots.txt"))
            continue
        html_or_error, status = fetch_page_html(url)
        if status != "present" or html_or_error is None:
            unknowns.append(UnknownCheck("CIT-13", OWNER_SKILL, f"{url} could not be fetched: {html_or_error}"))
            continue
        _, _, text = parse_page(html_or_error)
        pages.append({"url": url, "text": text})
    return pages, unknowns


def main(argv: list[str] | None = None) -> int:
    parser_ = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser_.add_argument("--url", help="A single page URL to fetch and audit")
    parser_.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser_.add_argument("--html-file", help="Read page HTML from a local file instead of fetching")
    parser_.add_argument("--page-url", help="Label findings with this page URL (default: --url)")
    parser_.add_argument(
        "--offsite-url",
        action="append",
        default=[],
        help=(
            "Enable CIT-13 by adding an off-site URL (repeatable) — a page the calling agent "
            "already found via its own search, checked for corroboration of this page's own "
            "numeric claims. Fetched only if that host's own robots.txt allows it."
        ),
    )
    args = parser_.parse_args(argv)

    if not any((args.url, args.site)):
        parser_.error("one of --url or --site is required")
    site = site_label(args.site or args.url)
    page_url = args.page_url or args.url

    if args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
    elif args.url:
        html_or_error, status = fetch_page_html(args.url)
        if status != "present":
            json.dump(_unknown_output(site, html_or_error or "fetch failed", page_url), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        html = html_or_error
    else:
        json.dump(_unknown_output(site, "no --url or --html-file given", page_url), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    json.dump(audit_html(site, html, page_url=page_url, offsite_urls=args.offsite_url), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
