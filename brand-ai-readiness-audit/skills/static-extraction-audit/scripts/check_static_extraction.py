#!/usr/bin/env python3
"""Gate-2 static-extraction audit: does a single page's own static HTTP
response carry the facts a non-JS fetcher needs, or only its rendered DOM?

Cluster B, cycle 19. This cluster was originally scoped around a headless
render (`crawl4ai`/Playwright) comparing a rendered DOM against the raw HTML
a fetcher sees. Hard constraint 1, confirmed with the judges cycle 19: no
headless browser anywhere, including as an optional fallback. Every
capability below is redefined against static artifacts only — raw HTML,
JSON-LD, and any hydration-state JSON a framework embeds in the response
itself (Next.js's `__NEXT_DATA__`, Nuxt 3's `__NUXT_DATA__`) — never a
rendered page. Several rows (REN-06/07/08) never actually needed a browser
to begin with; they were mis-scoped into this cluster by inheriting its
original framing, not by their own detection logic.

Owns nine capabilities:
  REN-01  Fetch foundation (infrastructure only, no finding)
  REN-02  Hydration-state coverage diff — a text fragment present in an
          embedded hydration-state JSON blob but absent from the page's own
          extracted visible text. Covers legacy `__NEXT_DATA__`/
          `__NUXT_DATA__`, plus `window.__NUXT__`/`window.__remixContext`
          where the assigned value is JSON-parseable; Next.js App Router's
          `self.__next_f.push(...)` RSC stream is detected but not decoded
          (a framed, non-JSON protocol), surfaced as its own presence-only
          finding rather than silently skipped
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
  REN-12  Concealed agent-directed instruction scanner — text a visitor
          cannot see (hidden by CSS, an HTML comment, or embedded only in
          JSON-LD/meta content) but a text extractor reads, carrying
          imperative language addressed at an AI system. The opposite
          direction of this skill's other checks: REN-02/04/10 detect facts
          hidden *from machines* (present visually, missing from extracted
          text); REN-12 detects text hidden *from humans* (present in
          extracted text, invisible on screen) — this skill's stated concern
          widens to cover both directions of the human/machine view gap.

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
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from budget import StageBudget, coverage_manifest  # noqa: E402
from report_shape import site_label, stamp_page as _stamp_page, unknown_output  # noqa: E402
from skill_cli import add_page_arguments, resolve_page_html  # noqa: E402
from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from jsonld_graph import flatten  # noqa: E402
from page_fetch import (  # noqa: E402
    USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    MAX_PAGE_BYTES,
    decode_content_encoding,
    is_public_host,
    fetch_page_html,
    fetch_pages_concurrently,
)
from phone_numbers import find_phone_numbers  # noqa: E402
from text_spans import VISIBLE_TEXT_BLOCK_TAGS, VISIBLE_TEXT_SKIP_TAGS  # noqa: E402

OWNER_SKILL = "static-extraction-audit"
CAPABILITY_IDS = [
    "REN-01", "REN-02", "REN-04", "REN-05", "REN-06", "REN-07", "REN-08", "REN-10", "REN-11", "REN-12",
]


# ---------------------------------------------------------------------------
# HTML parsing: one pass, every static signal this skill needs
# ---------------------------------------------------------------------------

# Cycle 24 item 2.5: canonical set, shared/text_spans.py — see that module.
_SKIP_TEXT_TAGS = VISIBLE_TEXT_SKIP_TAGS
_BLOCK_TAGS = VISIBLE_TEXT_BLOCK_TAGS
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
        "script_chunks": parser.script_text_chunks,
    }


_MAIN_ARTICLE_TAG_PATTERN = re.compile(r"</?(main|article)\b", re.IGNORECASE)


def _has_main_or_article(html: str) -> bool:
    """Cheap, reliable presence check independent of the main parser's own
    depth bookkeeping — a regex over raw markup, since REN-06 only needs to
    know whether the tag exists anywhere, not track its nesting."""
    return bool(_MAIN_ARTICLE_TAG_PATTERN.search(html))


def _node_types(node: dict) -> set[str]:
    type_value = node.get("@type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {t for t in type_value if isinstance(t, str)}
    return set()


def extract_json_ld_nodes(json_ld_blocks: list[str]) -> list[dict]:
    return flatten(json_ld_blocks)


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


# Modern hydration markers beyond legacy __NEXT_DATA__/__NUXT_DATA__ (both
# `type="application/json"` or an `id` the parser already classifies as
# "hydration" — see _HYDRATION_IDS above). These three are plain, untyped
# inline <script> STATEMENTS a framework emits, not a distinctly-typed
# script tag, so they show up in `script_text_chunks` regardless of the
# parser's type/id-based classification — no parser change needed, just a
# second pass over the same raw script text every script already yields.
_MODERN_HYDRATION_ASSIGNMENT_MARKERS = {
    "__NUXT__": "window.__NUXT__",  # Nuxt 2, and Nuxt 3 configured for a plain-JSON payload
    "__remixContext": "window.__remixContext",  # Remix
}
# Next.js App Router's RSC streaming payload — a framed, line-oriented
# protocol, NOT JSON (each pushed chunk can itself be a further-encoded
# string). Presence-only: this project does not attempt to decode it.
_NEXT_APP_ROUTER_MARKER = "self.__next_f.push("


def _find_object_literal_start(text: str, after_index: int) -> int | None:
    """Index of the first `{` or `[` after `after_index`, skipping only
    whitespace and a single `=` — None if an assignment operator followed by
    an object/array literal isn't there (the marker string appearing
    incidentally elsewhere — inside a comment, a different value — is not a
    real hydration assignment)."""
    i = after_index
    n = len(text)
    while i < n and text[i] in " \t\r\n":
        i += 1
    if i < n and text[i] == "=":
        i += 1
        while i < n and text[i] in " \t\r\n":
            i += 1
    if i < n and text[i] in "{[":
        return i
    return None


def _scan_balanced_literal(text: str, start: int) -> str | None:
    """From `start` (a `{` or `[`), return the substring up to and including
    its matching closing bracket, tracking string/escape state so a `}`/`]`
    inside a quoted value (a code sample, a JSON-describing-JSON field,
    an escaped `\\"`, a `</script>` decoy inside a string) never closes the
    literal early — a plain depth-counting scan over raw text gets this
    wrong on real-world payloads that legitimately contain brackets inside
    string content. `{`/`[`/`}`/`]` share one depth counter rather than
    being matched pairwise: a syntactically valid source always balances its
    own bracket types correctly, and any output this misjudges simply fails
    the caller's later `json.loads` and degrades to presence-only detection
    — never a wrong extraction. Returns None if the text ends before the
    literal closes (truncated/malformed input)."""
    depth = 0
    in_string: str | None = None  # the quote character currently open, or None
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if in_string is not None:
            if ch == "\\":
                i += 2  # an escaped character never toggles or ends the string
                continue
            if ch == in_string:
                in_string = None
        else:
            if ch in "\"'`":
                in_string = ch
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


def _extract_assignment_literal(text: str, marker: str) -> str | None:
    """The object/array literal assigned to `marker` (e.g.
    `"window.__NUXT__"`) inside `text`, or None if `marker` isn't present or
    isn't followed by an extractable literal."""
    idx = text.find(marker)
    if idx == -1:
        return None
    literal_start = _find_object_literal_start(text, idx + len(marker))
    if literal_start is None:
        return None
    return _scan_balanced_literal(text, literal_start)


def extract_modern_hydration_signals(script_chunks: list[str]) -> tuple[list[tuple[str, str]], bool]:
    """Widen hydration detection beyond legacy `__NEXT_DATA__`/`__NUXT_DATA__`
    to the markers modern frameworks actually emit as plain, untyped inline
    `<script>` statements: `window.__NUXT__`, `window.__remixContext`, and
    Next.js App Router's `self.__next_f.push(...)` RSC stream.

    Returns `(extra_hydration_blocks, next_app_router_detected)`:
    - `extra_hydration_blocks` is in the same `(source_id, raw_json)` shape
      `extract_hydration_text_fragments` already consumes, for the two
      assignment forms whose value is JSON-parseable — extraction is
      attempted, not guaranteed; a payload that doesn't parse as JSON after
      isolation is simply not added, the same as any other unparseable
      block already handled there.
    - `next_app_router_detected` is presence-only: the RSC stream isn't JSON
      (a framed, line-oriented protocol; a pushed chunk can itself be a
      further-encoded string), so this project does not attempt to decode
      it — a caller surfaces this as its own "modern hydration pattern
      detected, extraction unsupported" signal instead of staying silent.
    """
    extra_blocks: list[tuple[str, str]] = []
    next_app_router_detected = False

    for chunk in script_chunks:
        if _NEXT_APP_ROUTER_MARKER in chunk:
            next_app_router_detected = True
        for source_id, marker in _MODERN_HYDRATION_ASSIGNMENT_MARKERS.items():
            literal = _extract_assignment_literal(chunk, marker)
            if literal is not None:
                extra_blocks.append((source_id, literal))

    return extra_blocks, next_app_router_detected


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


def find_next_app_router_hydration_detected(detected: bool) -> list[Finding]:
    """Presence-only counterpart to `find_hydration_coverage_gaps` for
    Next.js App Router's `self.__next_f.push(...)` RSC stream: this project
    can detect the pattern but does not decode it (see
    `extract_modern_hydration_signals`), so rather than staying silent about
    a hydration mechanism it knows it can't fully analyze, it says so."""
    if not detected:
        return []

    return [
        Finding(
            id="REN-02-modern-hydration-detected",
            title="Next.js App Router hydration stream detected; content coverage cannot be verified",
            severity="low",
            evidence=(
                "This page embeds a Next.js App Router RSC hydration stream "
                "(`self.__next_f.push(...)`). Unlike the legacy `__NEXT_DATA__`/`__NUXT_DATA__` "
                "JSON blobs this capability compares against extracted visible text, the RSC stream "
                "is a framed, non-JSON protocol this project does not decode, so it cannot confirm "
                "whether content inside it is also present in the page's static text."
            ),
            suggested_action=SuggestedAction(
                summary="Manually verify that content rendered via streamed Server Components is also present in the initial static HTML response.",
                priority="low",
            ),
            category="discoverability",
            capability_id="REN-02",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A non-JS fetcher reads the static response body, never a framework's client-side "
                "hydration payload. This project can recognize the App Router's RSC streaming "
                "signature but cannot parse its framed payload the way it parses plain JSON "
                "hydration blobs, so a gap here is flagged as unverifiable rather than silently "
                "reported as clean."
            ),
            gate=2,
            confidence="low",
            structured_evidence={},
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

# "US" rather than the more conservative None/"ZZ": the detector this
# replaced was itself NANP-only (a bare 3-3-4 regex with no "+" required), so
# a bare "202-555-0173" with no country code must keep matching to avoid
# regressing already-shipped, already-tested behavior. phonenumbers still
# recognizes any explicitly "+"-prefixed international number regardless of
# this default — "US" only supplies the assumed country for a number with no
# "+", which is exactly what the old regex always assumed implicitly.
_REN10_DEFAULT_REGION = "US"


def find_nap_script_only_phone(script_text: str, visible_text: str) -> list[Finding]:
    script_phones = set(find_phone_numbers(script_text, default_region=_REN10_DEFAULT_REGION))
    if not script_phones:
        return []
    visible_phones = set(find_phone_numbers(visible_text, default_region=_REN10_DEFAULT_REGION))
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
# REN-12 — Concealed agent-directed instruction scanner
# ---------------------------------------------------------------------------
#
# This is a second, separate HTML parse building a lightweight DOM tree
# (tag, attrs, children, parent pointer) — deliberately not `_PageParser`'s
# flat single pass above. Concealment is inherently ancestor-aware (a node
# with no `style` of its own is still invisible if its parent declares
# `display:none`) and `<style>`-block rule matching needs to test arbitrary
# nodes against arbitrary selectors after the whole page is known — neither
# fits a single forward streaming pass the way `_PageParser`'s nine other
# capabilities do. Highest complexity, highest false-positive risk in this
# skill: the effective-visibility resolver below is deliberately
# conservative throughout (no CSS cascade/specificity engine, no combinator/
# pseudo-class selector support) — when a case is ambiguous, it stays
# silent rather than guesses, per the plan's own explicit instruction.

_REN12_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
_REN12_EXCLUDED_TEXT_TAGS = {"code", "pre", "kbd", "samp"}
_REN12_CONCEALMENT_STYLE_PROPS = {
    "display", "visibility", "opacity", "font-size", "text-indent", "clip",
    "width", "height", "position", "left", "top",
}


class _TextRun:
    # Plain classes, not `@dataclasses.dataclass`, deliberately: this
    # module is loaded elsewhere in this project via
    # `importlib.util.spec_from_file_location` + `module_from_spec`
    # without registering in `sys.modules` (this project's own test-loading
    # convention, shared across every skill script) — Python 3.14's
    # dataclasses machinery needs `sys.modules[cls.__module__]` to resolve
    # a self-referential forward-reference annotation (`_ElementNode`'s own
    # `parent` field) and raises `AttributeError` when that lookup returns
    # `None`, which it does under that loading convention. A plain `__init__`
    # sidesteps annotation resolution entirely.
    def __init__(self, text: str):
        self.text = text


class _CommentRun:
    def __init__(self, text: str):
        self.text = text


class _ElementNode:
    def __init__(self, tag: str, attrs: dict, children: list | None = None, parent: "_ElementNode | None" = None):
        self.tag = tag
        self.attrs = attrs
        self.children = children if children is not None else []
        self.parent = parent


class _DomTreeParser(HTMLParser):
    """Builds a lightweight DOM tree plus side-channels for `<style>` and
    `<script>` bodies (never added as text-run children — their content is
    not a human-visible text node, it is CSS/JS/JSON-LD source)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _ElementNode(tag="#root", attrs={}, children=[])
        self._stack: list[_ElementNode] = [self.root]
        self.style_blocks: list[str] = []
        self.script_blocks: list[tuple[_ElementNode, str, str]] = []  # (node, type, text)
        self._in_style = False
        self._style_buffer: list[str] = []
        self._in_script = False
        self._script_type = ""
        self._script_node: _ElementNode | None = None
        self._script_buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        self._open(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag, attrs, self_closing=True)

    def _open(self, tag: str, attrs, self_closing: bool) -> None:
        tag = tag.lower()
        attr_dict = dict(attrs)
        node = _ElementNode(tag=tag, attrs=attr_dict, children=[], parent=self._stack[-1])
        self._stack[-1].children.append(node)

        if tag == "style":
            self._in_style = True
            self._style_buffer = []
        elif tag == "script":
            self._in_script = True
            self._script_type = (attr_dict.get("type") or "").strip().lower()
            self._script_node = node
            self._script_buffer = []

        if not self_closing and tag not in _REN12_VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "style" and self._in_style:
            self.style_blocks.append("".join(self._style_buffer))
            self._in_style = False
            self._style_buffer = []
        elif tag == "script" and self._in_script:
            self.script_blocks.append((self._script_node, self._script_type, "".join(self._script_buffer)))
            self._in_script = False
            self._script_type = ""
            self._script_node = None
            self._script_buffer = []
        self._pop(tag)

    def _pop(self, tag: str) -> None:
        if len(self._stack) > 1 and self._stack[-1].tag == tag:
            self._stack.pop()
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index]
                return

    def handle_data(self, data):
        if self._in_style:
            self._style_buffer.append(data)
            return
        if self._in_script:
            self._script_buffer.append(data)
            return
        self._stack[-1].children.append(_TextRun(text=data))

    def handle_comment(self, data):
        if self._in_style or self._in_script:
            return
        self._stack[-1].children.append(_CommentRun(text=data))


def _dom_path(node: _ElementNode) -> str:
    """A best-effort, non-normative DOM path (`body > main > div[3]`) for
    evidence display only — never used for selector matching."""
    segments: list[str] = []
    current: _ElementNode | None = node
    while current is not None and current.tag != "#root":
        parent = current.parent
        if parent is not None:
            siblings = [c for c in parent.children if isinstance(c, _ElementNode) and c.tag == current.tag]
            if len(siblings) > 1:
                segments.append(f"{current.tag}[{siblings.index(current) + 1}]")
            else:
                segments.append(current.tag)
        else:
            segments.append(current.tag)
        current = parent
    segments.reverse()
    return " > ".join(segments) or "(root)"


def _parse_declarations(decl_text: str) -> dict[str, str]:
    """`prop: value; prop2: value2` -> `{"prop": "value", ...}`, lower-cased.
    Shared by inline `style="..."` attributes and `<style>` block rule
    bodies — same syntax, same parser."""
    declarations: dict[str, str] = {}
    for decl in (decl_text or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, value = decl.partition(":")
        declarations[prop.strip().lower()] = value.strip().lower()
    return declarations


_REN12_STYLE_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _strip_at_rule_blocks(css_text: str) -> str:
    """Removes every `@media`/`@keyframes`/`@supports`/etc. block, including
    its full nested content, via manual brace-depth matching — the flat
    single-level `_REN12_STYLE_RULE_RE` below cannot itself skip a nested
    block (it would otherwise match the *inner* rule directly, silently
    dropping the `@media` condition it was written under, which is not the
    conservative "never mis-apply a rule" behavior this scanner promises).
    A malformed `@`-block with no matching `{` at all is left as a signal
    to stop scanning further, rather than guess at a repair."""
    out: list[str] = []
    i, n = 0, len(css_text)
    while i < n:
        if css_text[i] == "@":
            brace_start = css_text.find("{", i)
            if brace_start == -1:
                break
            depth = 1
            j = brace_start + 1
            while j < n and depth > 0:
                if css_text[j] == "{":
                    depth += 1
                elif css_text[j] == "}":
                    depth -= 1
                j += 1
            i = j
            continue
        out.append(css_text[i])
        i += 1
    return "".join(out)


def parse_style_rules(css_text: str) -> list[tuple[list[str], dict[str, str]]]:
    """Extracts top-level `selector(s) { declarations }` rules from raw CSS
    text, after `@`-rule blocks (`@media`, `@keyframes`, ...) have been
    stripped out entirely by `_strip_at_rule_blocks`."""
    rules: list[tuple[list[str], dict[str, str]]] = []
    for match in _REN12_STYLE_RULE_RE.finditer(_strip_at_rule_blocks(css_text)):
        selector_text = match.group(1).strip()
        if not selector_text or "@" in selector_text:
            continue
        selectors = [s.strip() for s in selector_text.split(",") if s.strip()]
        if not selectors:
            continue
        declarations = _parse_declarations(match.group(2))
        if declarations:
            rules.append((selectors, declarations))
    return rules


_REN12_SIMPLE_SELECTOR_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*")
_REN12_CLASS_RE = re.compile(r"\.([a-zA-Z0-9_-]+)")
_REN12_ID_RE = re.compile(r"#([a-zA-Z0-9_-]+)")


def _selector_matches(selector: str, node: _ElementNode) -> bool:
    """Only simple and simple-compound selectors are supported (`div`,
    `.hidden`, `#foo`, `div.hidden`) — no descendant/child/sibling
    combinators, no pseudo-classes/elements. A selector this function
    cannot parse never matches anything, the same conservative-by-design
    disposition `parse_style_rules` already takes for `@`-rules."""
    if any(ch in selector for ch in (" ", ">", "+", "~", ":")):
        return False
    tag_match = _REN12_SIMPLE_SELECTOR_RE.match(selector)
    remainder = selector[tag_match.end():] if tag_match else selector
    if tag_match and tag_match.group(0) != node.tag:
        return False
    classes = set(_REN12_CLASS_RE.findall(remainder))
    node_classes = set((node.attrs.get("class") or "").split())
    if classes and not classes.issubset(node_classes):
        return False
    id_match = _REN12_ID_RE.search(remainder)
    if id_match and id_match.group(1) != (node.attrs.get("id") or ""):
        return False
    if not tag_match and not classes and not id_match:
        return False
    return True


def _is_very_negative(value: str, threshold: float) -> bool:
    match = re.match(r"^-?\d+(?:\.\d+)?", value.strip())
    if not match:
        return False
    try:
        return float(match.group(0)) <= threshold
    except ValueError:
        return False


def _style_conceals(declarations: dict[str, str]) -> str | None:
    """Returns the concealment technique name if `declarations` (already
    resolved from either an inline `style` or a matching `<style>`-block
    rule) declares any of the plan's named concealment properties, else
    `None`."""
    if declarations.get("display") == "none":
        return "display:none"
    if declarations.get("visibility") == "hidden":
        return "visibility:hidden"
    if declarations.get("opacity") in ("0", "0.0", "0%"):
        return "opacity:0"
    if declarations.get("font-size") in ("0", "0px", "0em", "0rem", "0%"):
        return "font-size:0"
    if _is_very_negative(declarations.get("text-indent", ""), -9999):
        return "text-indent:-9999px"
    if declarations.get("clip", "").replace(" ", "") in ("rect(0,0,0,0)", "rect(0px,0px,0px,0px)"):
        return "clip:rect(0,0,0,0)"
    if declarations.get("width") in ("0", "0px") or declarations.get("height") in ("0", "0px"):
        return "zero-dimensions"
    if declarations.get("position") == "absolute":
        if _is_very_negative(declarations.get("left", ""), -1000) or _is_very_negative(
            declarations.get("top", ""), -1000
        ):
            return "position:absolute;offscreen"
    return None


def _node_concealment(
    node: _ElementNode, style_rules: list[tuple[list[str], dict[str, str]]]
) -> tuple[bool, str | None, str | None]:
    """Whether `node` is itself concealed (not counting inherited ancestor
    concealment, handled separately by the caller), and by what technique/
    rule. Checked in the plan's own order: `hidden` attribute,
    `aria-hidden="true"`, inline style, then `<style>`-block rules (with
    later matching rules overriding earlier same-property values — a
    simplified, deliberately non-cascading approximation of "last rule
    wins," per the plan's own "no cascade/specificity engine" instruction)."""
    if "hidden" in node.attrs:
        return True, "hidden-attribute", "the `hidden` attribute"
    if (node.attrs.get("aria-hidden") or "").strip().lower() == "true":
        return True, "aria-hidden", 'aria-hidden="true"'

    inline = _parse_declarations(node.attrs.get("style") or "")
    technique = _style_conceals(inline)
    if technique:
        return True, technique, f"the inline rule {(node.attrs.get('style') or '').strip()}"

    resolved: dict[str, str] = {}
    matched_selector = None
    for selectors, declarations in style_rules:
        if any(_selector_matches(sel, node) for sel in selectors):
            resolved.update({k: v for k, v in declarations.items() if k in _REN12_CONCEALMENT_STYLE_PROPS})
            matched_selector = ", ".join(selectors)
    technique = _style_conceals(resolved)
    if technique:
        return True, technique, f"a <style> block rule ({matched_selector}) declaring {technique}"

    return False, None, None


def _flatten_descendant_text(node: _ElementNode) -> str:
    """All text (and comment) content anywhere under `node`, skipping
    `<code>`/`<pre>`/`<kbd>`/`<samp>` subtrees entirely — a blog post
    *documenting* prompt injection inside a code sample must never
    contribute to a concealed fragment's text."""
    parts: list[str] = []

    def _walk(current: _ElementNode) -> None:
        for child in current.children:
            if isinstance(child, _TextRun):
                parts.append(child.text)
            elif isinstance(child, _CommentRun):
                parts.append(child.text)
            elif isinstance(child, _ElementNode) and child.tag not in _REN12_EXCLUDED_TEXT_TAGS:
                _walk(child)

    _walk(node)
    return " ".join(" ".join(parts).split())


def find_concealed_fragments(
    node: _ElementNode, style_rules: list[tuple[list[str], dict[str, str]]]
) -> list[dict]:
    """Walks the tree looking for the *outermost* concealed element on each
    branch (a concealed element's entire subtree becomes one fragment —
    a nested, more-specifically-hidden child inside an already-hidden
    parent is not reported a second time), plus every `<meta content>`
    value and every HTML comment found along the way. `<noscript>` is
    deliberately given no special treatment here at all — it is not a skip
    tag and nothing marks it concealed by virtue of being `<noscript>`;
    the plan's own exclusion ("not concealment — visible to a human
    without JS") is satisfied simply by never having written a rule that
    would have flagged it."""
    fragments: list[dict] = []
    if node.tag in _REN12_EXCLUDED_TEXT_TAGS or node.tag in ("script", "style"):
        return fragments

    if node.tag == "meta":
        content = (node.attrs.get("content") or "").strip()
        if content:
            fragments.append(
                {
                    "tag": "meta",
                    "text": content,
                    "technique": "meta-content",
                    "concealment_rule": "a <meta> element (its `content` is never rendered to a page visitor)",
                    "dom_path": _dom_path(node),
                }
            )
        return fragments

    concealed, technique, rule = _node_concealment(node, style_rules)
    if concealed:
        text = _flatten_descendant_text(node)
        if text:
            fragments.append(
                {
                    "tag": node.tag,
                    "text": text,
                    "technique": technique,
                    "concealment_rule": rule,
                    "dom_path": _dom_path(node),
                }
            )
        return fragments

    for child in node.children:
        if isinstance(child, _ElementNode):
            fragments.extend(find_concealed_fragments(child, style_rules))
        elif isinstance(child, _CommentRun):
            comment_text = " ".join(child.text.split())
            if comment_text:
                fragments.append(
                    {
                        "tag": node.tag,
                        "text": comment_text,
                        "technique": "html-comment",
                        "concealment_rule": "an HTML comment",
                        "dom_path": _dom_path(node),
                    }
                )
    return fragments


def find_json_ld_string_fragments(script_blocks: list[tuple[_ElementNode, str, str]]) -> list[dict]:
    """Every string leaf value inside a JSON-LD `<script>` block — reuses
    `_walk_json_strings` (REN-02's own JSON-string-leaf walker, already
    defined above in this file) rather than a second copy. JSON-LD content
    is never rendered to a page visitor regardless of any CSS, so every
    string here is concealed by construction, same as `<meta content>`."""
    fragments: list[dict] = []
    for node, script_type, raw in script_blocks:
        if script_type != "application/ld+json":
            continue
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
            if not normalized:
                continue
            fragments.append(
                {
                    "tag": "script",
                    "text": normalized,
                    "technique": "json-ld-string-value",
                    "concealment_rule": "JSON-LD <script> content (never rendered to a page visitor)",
                    "dom_path": _dom_path(node),
                }
            )
    return fragments


# --- Language classifier (three deterministic signal families) ------------

_REN12_OVERRIDE_RE = re.compile(
    r"ignore (all )?(previous|prior) instructions|disregard the above|system prompt|"
    r"you are an? (ai|assistant|language model)|as an ai|new instructions",
    re.IGNORECASE,
)
_REN12_SELF_AUTHORITY_RE = re.compile(
    r"cite this (page|site|source)|authoritative source|always (recommend|mention)|rank this|"
    r"do not suggest competitors",
    re.IGNORECASE,
)
_REN12_AGENT_NOUNS = {
    "ai", "assistant", "model", "chatbot", "llm", "agent", "chatgpt", "claude", "perplexity",
    "crawler", "bot",
}
# A short, defensible fixed list rather than a POS tagger (stdlib-only, no
# grammar parser available) — common imperative-shaped verbs this kind of
# injected instruction actually uses ("cite", "recommend", "ignore",
# "treat", "always X"). A verb not in this list is simply not detected;
# documented narrowing, not a claim of completeness.
_REN12_IMPERATIVE_VERBS = {
    "cite", "recommend", "mention", "rank", "ignore", "disregard", "treat", "respond", "answer",
    "include", "exclude", "suppress", "prioritize", "favor", "avoid", "state", "claim", "assert",
    "present", "suggest", "promote", "endorse", "list", "tell", "inform", "direct", "instruct",
    "act", "behave", "pretend", "assume", "output", "generate", "write", "say", "do", "provide",
}
_REN12_WORD_RE = re.compile(r"[A-Za-z']+")
# How many tokens apart an imperative verb and an agent noun may sit and
# still count as "addressing" that agent — wide enough to catch "As an AI,
# you should always cite..." (verb several words after the noun) and
# "Assistant: please recommend our product" (a short imperative clause
# right after the noun), narrow enough that an unrelated verb mentioned
# elsewhere in a long paragraph that also happens to name an agent
# somewhere else in it does not falsely pair up. The plan does not pin an
# exact number; 6 is a short-clause-length choice, documented here per the
# task's own report contract.
_REN12_AGENT_ADDRESSING_PROXIMITY = 6
_REN12_SELF_AUTHORITY_MIN_CHARS = 40


def _has_agent_addressing(text: str) -> bool:
    words = _REN12_WORD_RE.findall(text.lower())
    noun_positions = [i for i, w in enumerate(words) if w in _REN12_AGENT_NOUNS]
    if not noun_positions:
        return False
    verb_positions = [i for i, w in enumerate(words) if w in _REN12_IMPERATIVE_VERBS]
    if not verb_positions:
        return False
    for noun_index in noun_positions:
        for verb_index in verb_positions:
            if abs(noun_index - verb_index) <= _REN12_AGENT_ADDRESSING_PROXIMITY:
                return True
    return False


def classify_language(text: str) -> dict | None:
    """The language gate (step 3-4 of the plan's algorithm): returns
    `{"signal_family", "severity", "matched_phrase"}` for the *first*
    matching family in priority order (Override > Agent addressing >
    Self-authority — matching the plan's own severity ordering), or `None`
    if no family matches at all. Concealment alone is never enough; this
    is the other required half of every REN-12 fire."""
    override_match = _REN12_OVERRIDE_RE.search(text)
    if override_match:
        return {"signal_family": "override", "severity": "critical", "matched_phrase": override_match.group(0)}

    if _has_agent_addressing(text):
        return {"signal_family": "agent-addressing", "severity": "high", "matched_phrase": text[:120]}

    authority_match = _REN12_SELF_AUTHORITY_RE.search(text)
    if authority_match and len(text) >= _REN12_SELF_AUTHORITY_MIN_CHARS:
        return {"signal_family": "self-authority", "severity": "medium", "matched_phrase": authority_match.group(0)}

    return None


_REN12_MAX_FINDINGS = 5
_REN12_MAX_EVIDENCE_TEXT_CHARS = 300
_REN12_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2}


def find_concealed_agent_instructions(html: str) -> list[Finding]:
    parser = _DomTreeParser()
    parser.feed(html)
    parser.close()

    style_rules: list[tuple[list[str], dict[str, str]]] = []
    for block in parser.style_blocks:
        style_rules.extend(parse_style_rules(block))

    fragments = find_concealed_fragments(parser.root, style_rules)
    fragments.extend(find_json_ld_string_fragments(parser.script_blocks))

    hits: list[dict] = []
    for fragment in fragments:
        classification = classify_language(fragment["text"])
        if classification is None:
            continue
        hits.append({**fragment, **classification})

    if not hits:
        return []

    hits.sort(key=lambda h: _REN12_SEVERITY_RANK.get(h["severity"], 99))
    findings: list[Finding] = []
    for hit in hits[:_REN12_MAX_FINDINGS]:
        concealed_text = hit["text"]
        display_text = (
            concealed_text if len(concealed_text) <= _REN12_MAX_EVIDENCE_TEXT_CHARS
            else concealed_text[:_REN12_MAX_EVIDENCE_TEXT_CHARS - 3] + "..."
        )
        node_id = hashlib.sha256(f"{hit['dom_path']}|{hit['technique']}|{concealed_text}".encode()).hexdigest()[:8]

        findings.append(
            Finding(
                id=f"REN-12-concealed-agent-instruction-{node_id}",
                title="Concealed text carries an instruction addressed at an AI system",
                severity=hit["severity"],
                evidence=(
                    f"A <{hit['tag']}> at {hit['dom_path']} is concealed by {hit['concealment_rule']}. "
                    f"It is invisible to a visitor and fully readable by any text extractor. Its "
                    f"content reads: '{display_text}'"
                ),
                suggested_action=SuggestedAction(
                    summary="Remove this concealed text, or if it is a legitimate accessibility pattern, confirm it carries no agent-directed instruction language.",
                    priority=hit["severity"] if hit["severity"] != "critical" else "critical",
                ),
                category="discoverability",
                capability_id="REN-12",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "Indirect prompt injection: text invisible to a human visitor but present in the "
                    "page's own static HTML is read by any text extractor, retrieval pipeline, or "
                    "autonomous agent that fetches the page, and can steer its output toward the "
                    "injected instruction — independently documented in the wild by Zscaler ThreatLabz, "
                    "Unit 42, Forcepoint X-Labs, and Brave's red-team work on Perplexity Comet."
                ),
                gate=2,
                confidence="high",
                structured_evidence={
                    "dom_path": hit["dom_path"],
                    "concealment_technique": hit["technique"],
                    "concealment_rule": hit["concealment_rule"],
                    "matched_phrase": hit["matched_phrase"],
                    "signal_family": hit["signal_family"],
                    "concealed_text": display_text,
                },
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    parsed = parse_page(html)
    json_ld_nodes = extract_json_ld_nodes(parsed["json_ld_blocks"])
    modern_hydration_blocks, next_app_router_detected = extract_modern_hydration_signals(
        parsed["script_chunks"]
    )
    hydration_fragments = extract_hydration_text_fragments(
        parsed["hydration_blocks"] + modern_hydration_blocks
    )
    offer_prices = extract_offer_prices(json_ld_nodes)

    findings = _stamp_page(
        find_hydration_coverage_gaps(hydration_fragments, parsed["visible_text"])
        + find_next_app_router_hydration_detected(next_app_router_detected)
        + find_price_render_gaps(offer_prices, parsed["visible_text"])
        + find_missing_freshness_signal(json_ld_nodes, parsed["visible_text"])
        + find_missing_semantic_boundary(parsed["has_main_or_article"], parsed["visible_text"])
        + find_low_content_ratio(parsed["has_main_or_article"], parsed["main_article_text"], parsed["visible_text"])
        + find_missing_alt_text(parsed["images"])
        + find_missing_media_tracks(parsed["media_results"])
        + find_nap_script_only_phone(parsed["script_text"], parsed["visible_text"])
        + find_pdf_restatement_suggestion(parsed["pdf_links"])
        + find_concealed_agent_instructions(html),
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
    return unknown_output(OWNER_SKILL, CAPABILITY_IDS, site, reason, page_url=page_url)


_SAMPLE_FETCH_BUDGET_SECONDS = 90.0
# Pages per concurrent batch — the budget is rechecked between batches, not
# between individual pages, so this bounds how far a batch can overrun the
# cap before the next check (Defect 2 follow-up to INF-10).
_SAMPLE_FETCH_CHUNK_SIZE = 10


def audit_sample(site: str, page_urls: list[str], *, clock=None) -> dict:
    """Runs every REN capability across a whole page sample in one process,
    the same `--sample-file` shape content-quality-audit/citability-audit/
    engagement-audit/entity-audit already offer — this skill previously had
    only `audit_html`'s once-per-page mode, meaning the orchestrator's own
    up-to-25-page sample meant 25 separate sequential subprocess spawns of
    this script with no concurrency possible between them (Defect 2).

    Fetches `page_urls` concurrently in bounded, order-preserving batches of
    `_SAMPLE_FETCH_CHUNK_SIZE` (`shared/page_fetch.fetch_pages_concurrently`),
    with `shared/budget.StageBudget` (`_SAMPLE_FETCH_BUDGET_SECONDS`) checked
    between batches — the same cooperative-at-batch-granularity cap the
    other four skills' bulk mode uses. Each successfully fetched page runs
    through the existing, unmodified `audit_html`; its findings are merged
    into one combined report (this skill has no agent-judged capabilities,
    so `agent_judgement_required` is always empty). On expiry, fetching
    stops and every remaining un-fetched page gets its own `unknown_checks`
    entry naming the cap as the reason — reduced coverage, not a failed
    capability. `coverage_manifest` is always attached."""
    clock_kwargs = {"clock": clock} if clock is not None else {}
    budget = StageBudget(f"{OWNER_SKILL}-sample-fetch", _SAMPLE_FETCH_BUDGET_SECONDS, **clock_kwargs)
    unknowns: list[UnknownCheck] = []
    findings: list[dict] = []

    index = 0
    while index < len(page_urls):
        if budget.expired():
            for skipped_url in page_urls[index:]:
                unknowns.append(
                    UnknownCheck(
                        "*",
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
                unknowns.append(UnknownCheck("*", OWNER_SKILL, f"{page_url} could not be fetched: {html_or_error}"))
                continue
            findings.extend(audit_html(site, html_or_error, page_url=page_url)["findings"])

    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": findings,
        "agent_judgement_required": [],
        "unknown_checks": [u.to_dict() for u in unknowns],
        "coverage": coverage_manifest([budget]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_page_arguments(parser)
    parser.add_argument(
        "--sample-file",
        help="Run every REN capability across a whole page sample: a file of one page URL per "
        "line (e.g. audit-orchestrator's page-sample.json sample_urls), fetched concurrently "
        "and merged into one report instead of one process per page.",
    )
    args = parser.parse_args(argv)

    if args.sample_file:
        if not args.site:
            parser.error("--sample-file requires --site")
        page_urls = [
            line.strip()
            for line in Path(args.sample_file).read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        json.dump(audit_sample(site_label(args.site), page_urls), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not any((args.url, args.site)):
        parser.error("one of --url, --site, or --sample-file is required")
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
