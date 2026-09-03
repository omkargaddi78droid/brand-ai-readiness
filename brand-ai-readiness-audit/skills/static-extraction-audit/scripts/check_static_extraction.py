#!/usr/bin/env python3
"""Gate-2 static-extraction audit: does a single page's own static HTTP
response carry the facts a non-JS fetcher needs, or only its rendered DOM?

Cluster B, cycle 19. This cluster was originally scoped around a headless
render (`crawl4ai`/Playwright) comparing a rendered DOM against the raw HTML
a fetcher sees. Hard constraint 1, confirmed with the judges cycle 19 (see
`docs/capability-matrix.md`'s "Hard constraints" section): no headless
browser anywhere, including as an optional fallback. Every capability below
is redefined against static artifacts only — raw HTML, JSON-LD, and any
hydration-state JSON a framework embeds in the response itself (Next.js's
`__NEXT_DATA__`, Nuxt 3's `__NUXT_DATA__`) — never a rendered page. Several
rows (REN-06/07/08) never actually needed a browser to begin with; they were
mis-scoped into this cluster by inheriting its original framing, not by
their own detection logic.

Owns nine capabilities:
  REN-01  Fetch foundation (infrastructure only, no finding)
  REN-02  Hydration-state coverage diff — a text fragment present in an
          embedded hydration-state JSON blob but absent from the page's own
          extracted visible text
  REN-04  Price-render gating — a JSON-LD `Offer.price` not restated
          anywhere in visible text (numeric-format-tolerant)
  REN-05  Real-time availability exposure — a JSON-LD availability/stock
          field with no freshness signal anywhere on the page
  REN-06  Semantic HTML5 extraction compatibility — no `<main>`/`<article>`
          boundary anywhere on a substantial page
  REN-07  Boilerplate/content separation — the ratio of `<main>`/`<article>`
          text to whole-page text, when that boundary exists
  REN-08  Multimodal accessibility — `<img>` with no `alt` (decorative
          images excluded), `<video>`/`<audio>` with no `<track>`
  REN-10  NAP render asymmetry — a phone number assembled inside inline
          `<script>` text but absent from visible text (address patterns
          NOT attempted — see Excludes)
  REN-11  PDF-only fact lock — proactive suggestion only. No PDF-parsing
          library exists in this project's stdlib-only dependency set, so
          this cannot verify whether a PDF's content is restated in HTML;
          it can only note that a PDF link exists and suggest restating key
          facts as real text. Never a defect finding for this reason.

REN-03 (pagination/infinite scroll) and REN-09 (image-of-text facts) are
NOT built here. REN-03's only static proxy — a "Load more"-shaped control
with no `rel=next`/paginated href nearby — is weak enough it risks this
project's false-positive bar without a fixture built to prove it first.
REN-09 needs OCR/vision, a capability this project does not have; unrelated
to the browser constraint, blocked on a different missing capability
entirely. Both stay `NOT_STARTED` in the capability matrix, documented, not
silently dropped.

Determinism
-----------
Every detector is a pure function of parsed input. No randomness, no clock
in the detection logic.

Safety
------
`--url` mode fetches exactly one page (never a crawl) with the same SSRF
guard as every other page-fetching script in this marketplace: hostname
resolved and every returned address checked against private/loopback/
link-local/reserved/multicast ranges before connecting. Fetched HTML is
parsed as data only — structural pattern matching over parsed elements,
never executed, never treated as instruction.

Usage:
    check_static_extraction.py --url https://example.com/product/example
    check_static_extraction.py --site example.com --html-file page.html

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...], "site": ..., "page_url": ...,
     "findings": [...], "unknown_checks": [...]}
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
import zlib
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402

OWNER_SKILL = "static-extraction-audit"
CAPABILITY_IDS = [
    "REN-01", "REN-02", "REN-04", "REN-05", "REN-06", "REN-07", "REN-08", "REN-10", "REN-11",
]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5_000_000


# ---------------------------------------------------------------------------
# HTML parsing: one pass, every static signal this skill needs
# ---------------------------------------------------------------------------

_SKIP_TEXT_TAGS = {"script", "style", "code", "pre", "noscript", "template", "svg"}
_BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th",
}
_MAIN_ARTICLE_TAGS = {"main", "article"}
_HYDRATION_IDS = {"__NEXT_DATA__", "__NUXT_DATA__"}


class _PageParser(HTMLParser):
    """One-pass parse collecting every static signal this skill's nine
    capabilities need: JSON-LD blocks, hydration-state JSON blocks, whole-
    page visible text, main/article-scoped text, image alt-attribute state,
    video/audio track-child state, PDF link hrefs, and every inline
    <script>'s raw text (for REN-10's script-vs-text NAP check). One parser
    rather than several, unlike retrieval-readiness-audit's five separate
    single-purpose passes — this skill's nine capabilities share enough of
    the same page-shape signals (text extraction, block-boundary handling)
    that five overlapping passes would mean five copies of the same bug
    surface instead of one."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_ld_blocks: list[str] = []
        self.hydration_blocks: list[tuple[str, str]] = []  # (source_id, raw_json)
        self.images: list[dict] = []
        self.pdf_links: list[str] = []
        self.script_text_chunks: list[str] = []

        self._skip_depth = 0
        self._text_chunks: list[str] = []
        self._main_article_depth = 0
        self._main_article_chunks: list[str] = []

        self._script_kind: str | None = None  # "json-ld" | "hydration" | "other" | None
        self._script_id: str | None = None
        self._script_buffer: list[str] = []

        self._media_stack: list[dict] = []  # [{"tag": "video"|"audio", "has_track": bool}]
        self.media_results: list[dict] = []

    # -- start tags -----------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)

        if tag == "script":
            script_type = (attr_dict.get("type") or "").strip().lower()
            script_id = (attr_dict.get("id") or "").strip()
            if script_type == "application/ld+json":
                self._script_kind = "json-ld"
            elif script_type == "application/json" or script_id in _HYDRATION_IDS:
                self._script_kind = "hydration"
            else:
                self._script_kind = "other"
            self._script_id = script_id or script_type or "script"
            self._script_buffer = []
            self._skip_depth += 1
            return

        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")
            if self._main_article_depth > 0:
                self._main_article_chunks.append("\n")

        if tag in _MAIN_ARTICLE_TAGS:
            self._main_article_depth += 1

        if tag == "img":
            alt = attr_dict.get("alt")
            role = (attr_dict.get("role") or "").strip().lower()
            aria_hidden = (attr_dict.get("aria-hidden") or "").strip().lower()
            decorative = role == "presentation" or aria_hidden == "true"
            self.images.append({
                "has_alt": bool(alt and alt.strip()),
                "decorative": decorative,
            })

        if tag in ("video", "audio"):
            self._media_stack.append({"tag": tag, "has_track": False})

        if tag == "track" and self._media_stack:
            self._media_stack[-1]["has_track"] = True

        if tag == "a":
            href = (attr_dict.get("href") or "").strip()
            if href.split("?")[0].split("#")[0].lower().endswith(".pdf"):
                self.pdf_links.append(href)

    def handle_startendtag(self, tag, attrs):
        # Delegate to both handlers so depth counters (including a
        # self-closed <script/>, which has no body to buffer) stay balanced.
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            body = "".join(self._script_buffer)
            if self._script_kind == "json-ld":
                self.json_ld_blocks.append(body)
            elif self._script_kind == "hydration":
                self.hydration_blocks.append((self._script_id or "script", body))
            if body.strip():
                self.script_text_chunks.append(body)
            self._script_kind = None
            self._script_id = None
            self._script_buffer = []
            self._skip_depth = max(0, self._skip_depth - 1)
            return

        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")
            if self._main_article_depth > 0:
                self._main_article_chunks.append("\n")

        if tag in _MAIN_ARTICLE_TAGS and self._main_article_depth > 0:
            self._main_article_depth -= 1

        if tag in ("video", "audio") and self._media_stack:
            media = self._media_stack.pop()
            self.media_results.append({"tag": media["tag"], "has_track": media["has_track"]})

    def handle_data(self, data):
        if self._script_kind is not None:
            self._script_buffer.append(data)
            return
        if self._skip_depth == 0:
            self._text_chunks.append(data)
            if self._main_article_depth > 0:
                self._main_article_chunks.append(data)

    def visible_text(self) -> str:
        return _clean_text_chunks(self._text_chunks)

    def main_article_text(self) -> str:
        return _clean_text_chunks(self._main_article_chunks)


def _clean_text_chunks(chunks: list[str]) -> str:
    raw = "".join(chunks)
    lines = (" ".join(line.split()) for line in raw.splitlines())
    return "\n".join(line for line in lines if line)


def parse_page(html: str) -> dict:
    """Runs `_PageParser` and returns every extracted signal as a plain
    dict, the shape every `find_*` function below consumes."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()

    return {
        "json_ld_blocks": parser.json_ld_blocks,
        "hydration_blocks": parser.hydration_blocks,
        "visible_text": parser.visible_text(),
        "main_article_text": parser.main_article_text(),
        "has_main_or_article": _has_main_or_article(html),
        "images": parser.images,
        "media_results": parser.media_results,
        "pdf_links": parser.pdf_links,
        "script_text": "\n".join(parser.script_text_chunks),
    }


_MAIN_ARTICLE_TAG_PATTERN = re.compile(r"</?(main|article)\b", re.IGNORECASE)


def _has_main_or_article(html: str) -> bool:
    """Cheap, reliable presence check independent of the main parser's own
    depth bookkeeping — a regex over raw markup, since REN-06 only needs to
    know whether the tag exists anywhere, not track its nesting."""
    return bool(_MAIN_ARTICLE_TAG_PATTERN.search(html))


def _flatten_json_ld(value) -> list[dict]:
    if isinstance(value, list):
        flattened = []
        for item in value:
            flattened.extend(_flatten_json_ld(item))
        return flattened
    if isinstance(value, dict):
        if isinstance(value.get("@graph"), list):
            flattened = []
            for item in value["@graph"]:
                flattened.extend(_flatten_json_ld(item))
            return flattened
        return [value]
    return []


def _node_types(node: dict) -> set[str]:
    type_value = node.get("@type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {t for t in type_value if isinstance(t, str)}
    return set()


def extract_json_ld_nodes(json_ld_blocks: list[str]) -> list[dict]:
    nodes: list[dict] = []
    for block in json_ld_blocks:
        stripped = block.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        nodes.extend(_flatten_json_ld(value))
    return nodes


# ---------------------------------------------------------------------------
# REN-02 — Hydration-state coverage diff
# ---------------------------------------------------------------------------

_REN02_MIN_FRAGMENT_CHARS = 20
_REN02_MIN_FRAGMENT_WORDS = 3
_REN02_MAX_CANDIDATES = 5


def _walk_json_strings(value, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _walk_json_strings(v, out)
    elif isinstance(value, list):
        for item in value:
            _walk_json_strings(item, out)


def extract_hydration_text_fragments(hydration_blocks: list[tuple[str, str]]) -> list[dict]:
    """Every string value inside an embedded hydration-state JSON blob that
    looks like real content rather than an id/slug/URL: at least
    `_REN02_MIN_FRAGMENT_CHARS` characters, at least `_REN02_MIN_FRAGMENT_WORDS`
    words (a value with no internal whitespace is far more likely an
    identifier than prose). This is a narrowed, documented scope, the same
    discipline RET-01 applies to its own JSON-LD field list: it will miss
    short hydrated facts (a price, a single-word status) by design — REN-04/
    REN-05 own JSON-LD-declared facts specifically; this row is about
    hydrated *prose*, not every hydrated value."""
    fragments: list[dict] = []
    seen: set[str] = set()
    for source_id, raw in hydration_blocks:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        strings: list[str] = []
        _walk_json_strings(value, strings)
        for s in strings:
            normalized = " ".join(s.split())
            if len(normalized) < _REN02_MIN_FRAGMENT_CHARS:
                continue
            if len(normalized.split()) < _REN02_MIN_FRAGMENT_WORDS:
                continue
            if normalized.lower().startswith(("http://", "https://", "/")):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            fragments.append({"source_id": source_id, "text": normalized})
    return fragments


def find_hydration_coverage_gaps(fragments: list[dict], visible_text: str) -> list[Finding]:
    if not fragments:
        return []

    normalized_visible = " ".join(visible_text.split()).lower()
    missing = [f for f in fragments if f["text"].lower() not in normalized_visible]
    if not missing:
        return []

    examples = missing[:_REN02_MAX_CANDIDATES]
    quoted = "; ".join(f'"{m["text"][:80]}"' for m in examples)
    more = f" (+{len(missing) - _REN02_MAX_CANDIDATES} more)" if len(missing) > _REN02_MAX_CANDIDATES else ""

    return [
        Finding(
            id="REN-02-hydration-content-not-in-text",
            title="Content embedded in the page's own hydration-state JSON does not appear in its extracted visible text",
            severity="medium",
            evidence=(
                f"{len(missing)} text fragment(s) found inside this page's embedded hydration-state "
                f"JSON do not appear anywhere in its extracted visible text: {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Restate this content as real server-rendered text, not only inside client-side hydration state.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="REN-02",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A non-JS fetcher (and most retrieval/indexing pipelines) reads the static response "
                "body, never a framework's client-side hydration payload. Content that exists only "
                "inside that payload is invisible to them even though a browser would show it."
            ),
            gate=2,
            confidence="medium",
            structured_evidence={"missing_fragments": missing, "count": len(missing)},
        )
    ]


# ---------------------------------------------------------------------------
# REN-04 — Price-render gating
# ---------------------------------------------------------------------------

_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def extract_offer_prices(json_ld_nodes: list[dict]) -> list[dict]:
    """Every `price` value found on a JSON-LD `Offer` node, or inside a
    `Product` node's `offers` field (a dict, or a list of dicts — schema.org
    permits both). Scoped to `price`/`priceSpecification.price` only, the
    same narrow, deterministic slice RET-01 takes for its own identifier
    fields."""
    prices: list[dict] = []
    for node in json_ld_nodes:
        candidates: list[dict] = []
        if "Offer" in _node_types(node) or "AggregateOffer" in _node_types(node):
            candidates.append(node)
        offers = node.get("offers")
        if isinstance(offers, dict):
            candidates.append(offers)
        elif isinstance(offers, list):
            candidates.extend(o for o in offers if isinstance(o, dict))

        for offer in candidates:
            value = offer.get("price")
            if value is None:
                spec = offer.get("priceSpecification")
                if isinstance(spec, dict):
                    value = spec.get("price")
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            prices.append({"price": text})
    return prices


def _prices_equal(a: str, b: str) -> bool:
    try:
        return abs(float(a.replace(",", "")) - float(b.replace(",", ""))) < 0.005
    except ValueError:
        return False


def _price_survives(price: str, visible_text: str) -> bool:
    for match in _NUMBER_PATTERN.finditer(visible_text):
        if _prices_equal(match.group(), price):
            return True
    return False


def find_price_render_gaps(prices: list[dict], visible_text: str) -> list[Finding]:
    if not prices:
        return []

    missing = [p for p in prices if not _price_survives(p["price"], visible_text)]
    if not missing:
        return []

    seen: list[str] = []
    for p in missing:
        if p["price"] not in seen:
            seen.append(p["price"])
    quoted = ", ".join(seen[:5])
    more = f" (+{len(seen) - 5} more)" if len(seen) > 5 else ""

    return [
        Finding(
            id="REN-04-price-not-in-text",
            title="A structured-data price does not appear in the page's own visible text",
            severity="high",
            evidence=(
                f"{len(seen)} distinct price(s) declared in this page's JSON-LD Offer data do not "
                f"appear anywhere in its extracted visible text (numeric match, currency-symbol- and "
                f"comma-tolerant): {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Restate the price as real visible text, not only inside JSON-LD or client-rendered content.",
                priority="high",
            ),
            category="discoverability",
            capability_id="REN-04",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An assistant or fetcher reading only the static text has no price to quote, or may "
                "surface a stale one from elsewhere on the page, even though the page's own structured "
                "data confirms a specific price is intended to be shown."
            ),
            gate=2,
            confidence="high",
            structured_evidence={"missing_prices": seen, "count": len(seen)},
        )
    ]


# ---------------------------------------------------------------------------
# REN-05 — Real-time availability exposure
# ---------------------------------------------------------------------------

_FRESHNESS_PATTERN = re.compile(
    r"\bas of\b|\blast updated\b|\bupdated on\b|\bchecked on\b|\bin stock as of\b", re.IGNORECASE
)


def has_availability_field(json_ld_nodes: list[dict]) -> bool:
    for node in json_ld_nodes:
        offers = node.get("offers")
        candidates = [node]
        if isinstance(offers, dict):
            candidates.append(offers)
        elif isinstance(offers, list):
            candidates.extend(o for o in offers if isinstance(o, dict))
        for candidate in candidates:
            if candidate.get("availability"):
                return True
    return False


def has_freshness_signal(json_ld_nodes: list[dict], visible_text: str) -> bool:
    if any(node.get("dateModified") for node in json_ld_nodes):
        return True
    return bool(_FRESHNESS_PATTERN.search(visible_text))


def find_missing_freshness_signal(json_ld_nodes: list[dict], visible_text: str) -> list[Finding]:
    """Page-level, not proximity-scoped to the specific availability claim —
    a coarser check than the matrix's ideal, documented narrowing: knowing
    whether a freshness phrase sits *near* the volatile fact it qualifies
    needs DOM proximity this static text stream does not preserve reliably.
    Fires only when a volatile availability fact is declared and the page
    carries no freshness signal anywhere at all."""
    if not has_availability_field(json_ld_nodes):
        return []
    if has_freshness_signal(json_ld_nodes, visible_text):
        return []

    return [
        Finding(
            id="REN-05-no-freshness-signal",
            title="A volatile availability fact is shown with no freshness signal anywhere on the page",
            severity="low",
            evidence=(
                "This page's JSON-LD declares an offer availability/stock value, but no "
                "`dateModified` field and no freshness phrase (\"as of\", \"last updated\", "
                "\"checked on\") appears anywhere in its visible text."
            ),
            suggested_action=SuggestedAction(
                summary="Add a visible timestamp or 'as of' statement near volatile facts like stock or availability.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-05",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A volatile fact served as a static snapshot with no freshness marker gives a reader "
                "or assistant no way to judge whether it is still current."
            ),
            gate=2,
            confidence="medium",
            structured_evidence={"has_availability_field": True, "has_freshness_signal": False},
        )
    ]


# ---------------------------------------------------------------------------
# REN-06 / REN-07 — Semantic HTML5 boundaries + boilerplate ratio
# ---------------------------------------------------------------------------

_WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
_REN06_MIN_CONTENT_WORDS = 150
_REN07_MIN_CONTENT_WORDS = 150
_REN07_LOW_RATIO_THRESHOLD = 0.3


def _word_count(text: str) -> int:
    return len(_WORD_PATTERN.findall(text))


def find_missing_semantic_boundary(has_main_or_article: bool, visible_text: str) -> list[Finding]:
    total_words = _word_count(visible_text)
    if total_words < _REN06_MIN_CONTENT_WORDS or has_main_or_article:
        return []

    return [
        Finding(
            id="REN-06-no-semantic-boundary",
            title="The page has no <main> or <article> boundary anywhere",
            severity="low",
            evidence=(
                f"This page has {total_words} word(s) of visible text but no <main> or <article> "
                f"element anywhere in its markup."
            ),
            suggested_action=SuggestedAction(
                summary="Wrap the page's primary content in a <main> or <article> element so extraction tools can separate it from navigation/chrome.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-06",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Without a semantic content boundary, an extraction pipeline has no reliable way to "
                "strip navigation/footer boilerplate from the page's real content, so noise floods the "
                "context an assistant reasons over."
            ),
            gate=2,
            confidence="high",
            structured_evidence={"content_word_count": total_words, "has_main_or_article": False},
        )
    ]


def find_low_content_ratio(has_main_or_article: bool, main_article_text: str, visible_text: str) -> list[Finding]:
    """Silent when no `<main>`/`<article>` boundary exists at all — REN-06
    owns that case; a ratio has nothing to divide by without a boundary."""
    if not has_main_or_article:
        return []

    total_words = _word_count(visible_text)
    if total_words < _REN07_MIN_CONTENT_WORDS:
        return []

    main_words = _word_count(main_article_text)
    ratio = main_words / total_words if total_words else 0.0
    if ratio >= _REN07_LOW_RATIO_THRESHOLD:
        return []

    return [
        Finding(
            id="REN-07-low-content-ratio",
            title="Most of the page's extractable text sits outside its own <main>/<article> boundary",
            severity="low",
            evidence=(
                f"Only {main_words} of this page's {total_words} visible-text word(s) "
                f"({ratio:.0%}) fall inside a <main> or <article> element — the rest is "
                f"navigation/chrome/boilerplate."
            ),
            suggested_action=SuggestedAction(
                summary="Move primary content fully inside the <main>/<article> boundary, or reduce chrome outside it.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A low ratio of content-boundary text to total text means an extraction pipeline that "
                "trusts the semantic boundary still pulls in mostly chrome, or discards real content "
                "sitting outside it."
            ),
            gate=2,
            confidence="medium",
            structured_evidence={"main_article_word_count": main_words, "total_word_count": total_words, "ratio": round(ratio, 3)},
        )
    ]


# ---------------------------------------------------------------------------
# REN-08 — Multimodal accessibility
# ---------------------------------------------------------------------------


def find_missing_alt_text(images: list[dict]) -> list[Finding]:
    missing = [img for img in images if not img["has_alt"] and not img["decorative"]]
    if not missing:
        return []

    return [
        Finding(
            id="REN-08-missing-alt-text",
            title="Images have no alt text",
            severity="low",
            evidence=(
                f"{len(missing)} <img> element(s) have no `alt` attribute (or an empty one) and are "
                f"not marked decorative (`role=\"presentation\"`/`aria-hidden=\"true\"`)."
            ),
            suggested_action=SuggestedAction(
                summary="Add descriptive alt text to every content image; mark purely decorative images with role=\"presentation\".",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An assistant reasoning over extracted text has no description of what an image shows "
                "— a price, spec, or hours rendered only inside an image is invisible to it."
            ),
            gate=2,
            confidence="high",
            structured_evidence={"missing_alt_count": len(missing)},
        )
    ]


def find_missing_media_tracks(media_results: list[dict]) -> list[Finding]:
    missing = [m for m in media_results if not m["has_track"]]
    if not missing:
        return []

    tags = ", ".join(sorted({m["tag"] for m in missing}))
    return [
        Finding(
            id="REN-08-missing-media-track",
            title="Video/audio elements have no <track> captions or transcript",
            severity="low",
            evidence=f"{len(missing)} <{tags}> element(s) have no <track> child (captions/transcript/descriptions).",
            suggested_action=SuggestedAction(
                summary="Add a <track> element (captions or a transcript) to every video/audio element.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Audio/video content with no text alternative is entirely invisible to a text-based "
                "extraction or retrieval pipeline."
            ),
            gate=2,
            confidence="high",
            structured_evidence={"missing_track_count": len(missing)},
        )
    ]


# ---------------------------------------------------------------------------
# REN-10 — NAP render asymmetry (phone numbers only — see module docstring)
# ---------------------------------------------------------------------------

_PHONE_PATTERN = re.compile(r"(?:\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def find_nap_script_only_phone(script_text: str, visible_text: str) -> list[Finding]:
    script_phones = {_normalize_phone(m.group()) for m in _PHONE_PATTERN.finditer(script_text)}
    if not script_phones:
        return []
    visible_phones = {_normalize_phone(m.group()) for m in _PHONE_PATTERN.finditer(visible_text)}
    missing = sorted(script_phones - visible_phones)
    if not missing:
        return []

    return [
        Finding(
            id="REN-10-phone-only-in-script",
            title="A phone number appears only inside inline script text, not in visible text",
            severity="medium",
            evidence=(
                f"{len(missing)} phone number(s) found inside this page's inline <script> content do "
                f"not appear in its extracted visible text — likely assembled client-side (e.g. "
                f"'click to reveal')."
            ),
            suggested_action=SuggestedAction(
                summary="Include the phone number as plain visible text, not only assembled by client-side script.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="REN-10",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A non-JS fetcher never runs the script that assembles the number, so it never sees a "
                "contact detail a human visitor would."
            ),
            gate=2,
            confidence="medium",
            structured_evidence={"missing_phone_count": len(missing)},
        )
    ]


# ---------------------------------------------------------------------------
# REN-11 — PDF-only fact lock (proactive only — see module docstring)
# ---------------------------------------------------------------------------

_REN11_MAX_LINKS_SHOWN = 3


def find_pdf_restatement_suggestion(pdf_links: list[str]) -> list[Finding]:
    if not pdf_links:
        return []

    unique_links = sorted(set(pdf_links))
    shown = unique_links[:_REN11_MAX_LINKS_SHOWN]
    more = f" (+{len(unique_links) - _REN11_MAX_LINKS_SHOWN} more)" if len(unique_links) > _REN11_MAX_LINKS_SHOWN else ""

    return [
        Finding(
            id="REN-11-pdf-content-unverified",
            title="This page links to PDF content whose restatement in HTML could not be checked",
            severity="low",
            evidence=(
                f"{len(unique_links)} PDF link(s) found on this page: {', '.join(shown)}{more}. This "
                f"skill has no PDF text-extraction capability (stdlib-only), so it cannot confirm "
                f"whether the PDF's key facts are also restated in HTML — this is a suggestion, not a "
                f"confirmed defect."
            ),
            suggested_action=SuggestedAction(
                summary="If the PDF carries decision-critical facts (prices, specs, hours), restate them directly in page HTML, not only inside the PDF.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-11",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Many fetchers and retrieval pipelines do not extract PDF text; facts that exist only "
                "inside a linked PDF, with no HTML restatement, are invisible to them."
            ),
            gate=2,
            confidence="low",
            track="proactive",
            structured_evidence={"pdf_link_count": len(unique_links), "pdf_links": shown},
        )
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _stamp_page(findings: list[Finding], page_url: str | None) -> list[Finding]:
    if not page_url:
        return findings
    stamped = []
    for finding in findings:
        finding.evidence = f"On {page_url}: {finding.evidence}"
        finding.structured_evidence = {**(finding.structured_evidence or {}), "page_url": page_url}
        stamped.append(finding)
    return stamped


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    parsed = parse_page(html)
    json_ld_nodes = extract_json_ld_nodes(parsed["json_ld_blocks"])
    hydration_fragments = extract_hydration_text_fragments(parsed["hydration_blocks"])
    offer_prices = extract_offer_prices(json_ld_nodes)

    findings = _stamp_page(
        find_hydration_coverage_gaps(hydration_fragments, parsed["visible_text"])
        + find_price_render_gaps(offer_prices, parsed["visible_text"])
        + find_missing_freshness_signal(json_ld_nodes, parsed["visible_text"])
        + find_missing_semantic_boundary(parsed["has_main_or_article"], parsed["visible_text"])
        + find_low_content_ratio(parsed["has_main_or_article"], parsed["main_article_text"], parsed["visible_text"])
        + find_missing_alt_text(parsed["images"])
        + find_missing_media_tracks(parsed["media_results"])
        + find_nap_script_only_phone(parsed["script_text"], parsed["visible_text"])
        + find_pdf_restatement_suggestion(parsed["pdf_links"]),
        page_url,
    )

    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "page_url": page_url,
        "findings": [f.to_dict() for f in findings],
        "agent_judgement_required": [],
        "unknown_checks": [],
    }


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

_MAX_DECOMPRESSED_BYTES = 20_000_000


def decode_content_encoding(raw: bytes, content_encoding: str) -> bytes:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="A single page URL to fetch and audit")
    parser.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser.add_argument("--html-file", help="Read page HTML from a local file instead of fetching")
    parser.add_argument("--page-url", help="Label findings with this page URL (default: --url)")
    args = parser.parse_args(argv)

    if not any((args.url, args.site)):
        parser.error("one of --url or --site is required")
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

    json.dump(audit_html(site, html, page_url=page_url), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
