#!/usr/bin/env python3
"""Gate-3 retrieval-readiness audit: does a single page's own markup structure
serve sparse retrieval, or actively work against it?

Owns ten capabilities — six script-decided, four agent-judged:
  RET-10  Chunk self-containment — a content block opens with an unresolved
          reference ("It reduced onboarding time by 40%") and never names
          its own subject inside the block, which hurts both a chunk's
          dense-retrieval embedding and a model's ability to answer from
          that chunk alone, per three independent 2025 coreference/RAG
          papers.
  RET-09  Positional fact interment — a page's load-bearing figures (price,
          spec, headline statistic) appear only in the middle third of a long
          document and are never restated in the title, a heading, either
          margin, a table cell, a definition, or JSON-LD, which published
          attention-bias research ties to a measurably higher omission rate
          during synthesis.
  RET-08  Heading hierarchy integrity — a skipped heading level (h2 -> h4 with
          no h3 in between) or an empty heading element, either of which
          destroys the document outline a retrieval system uses to segment
          and weight a page's content.
  RET-01  BM25 exact-match retention — a technical identifier the page's own
          structured data declares (a Product's `sku`/`mpn`/`gtin*`) that
          does not survive into the page's extracted visible text at all,
          so a sparse/exact-match retrieval system has nothing to match the
          identifier against even though the page is genuinely about it.
  RET-04  Keyword stuffing — a phrase repeated at unnatural density in the
          page's own prose (table/list/glossary regions excluded before
          counting), the kind of manipulation signal generative engines and
          modern search ranking actively demote rather than reward.
  RET-07  Retrieval-oriented structure — a substantial page with none of
          the three structural aids that let a retrieval system chunk it
          into self-contained pieces: no headings at all, no Q&A-style
          framing, and no definition block.
  RET-02  Dense/semantic coverage & synonym variation (agent-judged) — does
          the page's core topic ever get expressed a genuinely different
          way, or only ever in one fixed phrasing.
  RET-03  Query-intent coverage (agent-judged) — do the obvious question
          forms for the page's own category go unaddressed anywhere on it.
  RET-05  Domain-specific terminology balance (agent-judged) — is the
          page's language skewed entirely to all-jargon or all-layman
          rather than balancing both.
  RET-06  Chunk quality / atomic paragraphs (agent-judged) — does a long
          paragraph genuinely blend several distinct ideas that would
          muddy a single retrieval chunk built from it.

RET-02/03/05/06 follow this project's `agent_judgement_required` pattern,
proven six times already (`content-quality-audit`'s CQ-01/02/04/09/12,
`engagement-audit`'s EN-01/03, `citability-audit`'s CIT-04, `entity-audit`'s
ENT-09): each extraction function below returns structural observations
only and asserts no verdict; the calling agent resolves each entry against
`references/retrieval-judgement-rubric.md` before this file's output
reaches the entrypoint.

The capability matrix's own wording for RET-08 also names "decorative"
heading levels — a heading tag used purely for visual styling with no real
structural role. That half is deliberately NOT built here: telling a
"decorative" heading from a real, if terse, structural one needs to know how
it renders (font size, visual weight relative to surrounding text), which is
exactly the render/extraction gate-2 boundary this project has drawn
consistently elsewhere (`content-quality-audit`'s CQ-01 opening-window
limitation, every "no main-content/render inspection" note across this
project's completion notes). This script instead owns the two sub-defects
that are fully verifiable from static markup alone: a skipped level between
consecutive headings, and a heading with no text content at all — both
near-zero false-positive-risk, the same "front-load the deterministic,
low-FP checks" discipline `content-quality-audit`'s CQ-03/05/07/08 and CQ-11
already established for this project.

Also deliberately not checked, and why: whether the page starts at h1. This
is a genuinely disputed rule — modern component-based layouts legitimately
put the visual masthead/logo in a non-heading element and start real content
at h2, or use more than one h1 per sectioning root (permitted by the HTML5
spec, even if debated SEO folklore says otherwise). Firing on either would
raise this check's false-positive rate on real, correctly-built pages for a
rule that isn't actually settled — so only the *skip between two headings
that are both present* is checked, not the starting level.

Cluster D (retrieval readiness) is now fully shipped in this one skill —
the ten capabilities above are all of RET-01 through RET-10.

**RET-10's own scope, and its overlap control vs RET-06.** RET-06
(agent-judged, this same file) triggers on a paragraph's *length* (≥80
words and ≥5 sentences) and asks whether it blends several distinct ideas.
RET-10 is fully deterministic, triggers on *anaphora* (an unresolved
pronoun/demonstrative/generic-definite reference that the block never
resolves internally), and asks whether a block names its own subject.
Orthogonal signals — a long paragraph can blend ideas *and* open with an
unresolved "it" — so both can legitimately co-fire on the same block. See
`OverlapControlTests` in the test file for the composition proof.

**RET-09's own scope, and its overlap control vs CQ-01.** CQ-01
(`content-quality-audit`, agent-judged) asks whether a *canonical answer*
sits near the top of the page; its documented blind spot is that the opening
block is document-start and is often nav chrome, not real content. RET-09
asks a narrower, fully deterministic question over the *whole* document:
are load-bearing *values* (prices, specs, dates, measurements) anchored at
**either** margin, a heading, a table, a definition, or JSON-LD — not
whether the page opens well. Different trigger (position of values vs.
quality of the opening), different remedy (restate the number vs. write a
lede), different owner. Both can legitimately fire on the same page — a
weak opening *and* buried mid-document figures are independent defects —
and `tests/test_retrieval_readiness.py::OverlapControlTests` proves that
composing both skills' outputs does not trip `compose_report.py`'s
duplicate-finding-id guard, since the two capabilities never share an id.

**RET-01's own scope, narrowed on purpose.** The matrix's "Detects" column
for RET-01 names product SKUs, model numbers, statute names and technical
terms broadly, with `bm25s` as the named resource. Real BM25 ranking math is
not what this capability's actual defect needs: the failure mode described is
binary presence/absence, not a relevance score. This script checks exactly
one narrow, deterministic, low-FP slice of that: a technical identifier a
page's own JSON-LD already declares (`Product.sku`, `.mpn`, `.gtin*`) that
never appears in the page's extracted visible text — i.e. it exists only
inside a `<script type="application/ld+json">` block, an `<img alt="...">`,
or nowhere else a text-based retrieval system would ever see it. "Model
numbers in `<title>`" and "statute names" are deliberately NOT attempted: both
need a free-text pattern-matching heuristic (what does a model number or a
statute citation *look like* in prose) with real false-positive risk this
project's own discipline (front-load only near-zero-FP checks; see RET-08's
own scope note above) says should not ship without a fixture built
specifically to break it first — deferred to a future cycle, not silently
dropped. JSON-LD-declared identifiers need no such heuristic: the page
already told us, structurally, that this exact string matters.

**RET-04's own scope, and its FP guard.** The capability matrix's own risk
note for RET-04 is explicit: it "fires on legitimately repetitive pages
(spec tables, glossaries); exclude structured regions before counting."
This script takes that literally as the design, not an afterthought —
`extract_prose_text()` excludes `<table>`, `<dl>`, `<ul>`, `<ol>` and
`<select>` regions from the corpus before any n-gram counting happens, so a
spec table's or glossary's inherent repetition (the same column headers or
term-definition shape recurring row after row) is structurally invisible to
this check rather than filtered post-hoc. `advertools` (the matrix's named
resource) is rejected as an actual dependency for the same reason `bm25s`
was rejected for RET-01: this is a straightforward n-gram frequency count in
stdlib, not a capability that needs a scraping/analytics library.

**RET-07's own scope, narrowed to its structural (deterministic) half.**
The matrix names three named aids ("Absent headings, Q&A framing, or
definition blocks that make chunks self-contained") whose collective
absence is the failure mode. Whether a page's chunks are *actually*
self-contained once you have headings is a semantic judgement (a heading
alone doesn't guarantee the text under it stands alone without earlier
context) — out of scope here, the same class of exclusion RET-02/03/05
already carry in this cluster. What this script checks instead is fully
structural and deterministic: does a substantial page (≥300 words of visible
text) have *none* of the three named aids present at all — zero heading elements,
no heading ending in "?" and no `FAQPage`/`QAPage` JSON-LD (Q&A framing),
and no `<dt>`/`<dd>` definition-list markup anywhere. Any one of the three
being present is enough to stay silent; this only fires on the genuine
"none of the above" case, which is the actual chunking failure mode named
in the matrix, not a proxy for content quality.

**RET-02/03/05/06, and why each ships agent-judged rather than script-
decided.** All four names a genuinely semantic question no structural
pattern match can safely answer: whether a repeated phrase means the page
lacks synonym variety (needs knowing what counts as a synonym), whether
the "obvious" questions for an arbitrary brand's category go unaddressed
(needs the category itself, which this script cannot infer with any
confidence a fixed rule could defend), whether language is jargon/layman-
imbalanced (a reading judgement, not a fixed threshold — a raw jargon-word
ratio alone would flag any genuinely technical page that is in fact fine),
and whether a long paragraph blends distinct ideas (length is a filter,
never the verdict). Each extraction function below is deliberately partial
— a phrase, a topic, some ratios, a paragraph — never the full page, and
the agent is expected to read the live page before judging rather than
deciding from the extraction alone.

Text/markup extraction
-----------------------
`extract_headings()` is a minimal, single-purpose stdlib HTML parse: it
collects every <h1>-<h6> element's level and flattened text content in
document order, and nothing else. It is NOT the render/extraction pipeline
(REN-06/07 in the capability matrix): no boilerplate-ratio scoring, no
main/article boundary detection, no JS rendering. Malformed HTML with
mismatched or improperly nested heading tags is a known, documented,
uncorrected limitation, the same disposition every other HTML-parsing
script in this project already states for its own extraction step.

`extract_json_ld_and_text()` is a second, separate single-purpose parse
(deliberately not merged into `_HeadingExtractor` — two narrow parsers, same
"don't grow one class's blast radius to cover an unrelated concern" reasoning
`content-quality-audit` used to keep its own H1 pass separate from its
existing visible-text pass) that collects raw JSON-LD blocks and a lightly
scoped visible-text string (script/style/code/pre excluded), reimplemented
here rather than imported from `entity-audit` so this skill stays
independently runnable per this project's convention
(`skill-engineering-principles.md` §5.3).

`extract_prose_text()` is a third, separate single-purpose parse: the same
scoped visible-text extraction, plus `<table>`/`<dl>`/`<ul>`/`<ol>`/
`<select>` regions excluded — RET-04's own corpus, distinct from RET-01's
(which deliberately keeps everything, since a token swallowed by a list or
table is still a real survival gap for that capability).

`has_definition_block()` is a fourth, separate single-purpose parse: does
the page contain at least one `<dt>` and at least one `<dd>` anywhere, with
no requirement that they pair up within the same `<dl>` — real pages nest
inconsistently, and presence of both tags anywhere is itself RET-07's
load-bearing signal, not perfect pairing.

`extract_paragraphs()` is a fifth, separate single-purpose parse: every
`<p>` element's own flattened text, kept as a distinct entry rather than
merged into one corpus — RET-06 judges paragraph-level chunk quality,
which needs paragraph boundaries preserved, unlike every other extraction
in this file.

**A block-boundary bug found live in cycle 14, fixed project-wide within
this file.** `extract_json_ld_and_text()`'s and `extract_prose_text()`'s
parsers originally inserted no separator at block-level tag boundaries
(`</h1><p>` producing one run-together word instead of two). Fixtures never
caught it because hand-written test HTML almost always has whitespace
between tags; gymshark.com's real, minified markup does not, and produced
438 corrupted word artifacts in `visible_text` before the fix. Both parsers
now insert a `\n` at every open/close of a `_BLOCK_TAGS` element — the same
set and mechanism `entity-audit`'s `_PageParser` and `content-quality-
audit`'s `_VisibleTextExtractor` already use, confirmed to reduce this
skill's residual artifact rate to exact parity with `content-quality-
audit`'s own extractor on the same live page (45 remaining, both — the
shared, accepted limitation of not inserting a boundary at *inline* tags
like `<span>`/`<a>`/`<strong>`, which every text-extracting script in this
project already carries).

Determinism
-----------
Every detector is a pure function of the input text. No randomness, no clock
in the detection logic, stable iteration and output order.

Safety
------
`--url` mode fetches exactly one page (never a crawl) with the same SSRF
guard as every other page-fetching script in this marketplace: hostname
resolved and every returned address checked against private/loopback/
link-local/reserved/multicast ranges before connecting. Fetched HTML is
parsed as data only — structural pattern matching over parsed elements —
never executed and never treated as instruction.

Usage:
    check_retrieval_readiness.py --url https://example.com/product/example
    check_retrieval_readiness.py --site example.com --html-file page.html

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
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from text_spans import Block, extract_blocks, normalized_position, proper_noun_tokens, split_sentences  # noqa: E402

OWNER_SKILL = "retrieval-readiness-audit"
CAPABILITY_IDS = [
    "RET-01", "RET-02", "RET-03", "RET-04", "RET-05", "RET-06", "RET-07", "RET-08", "RET-09", "RET-10",
]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5_000_000


# ---------------------------------------------------------------------------
# HTML parsing: heading elements only
# ---------------------------------------------------------------------------

_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _HeadingExtractor(HTMLParser):
    """Collects (level, text) for every h1-h6 element in document order.

    Headings cannot legally nest another heading, so this tracks the single
    currently-open heading tag by name and a depth counter for any other tag
    nested inside it, closing only when that exact tag name returns to depth
    zero. A second heading tag opening while one is already open is invalid
    HTML this parser does not attempt to repair — its content is folded into
    the outer heading's buffer and it is never recorded as its own heading,
    the same "malformed HTML is a known, uncorrected limitation" disposition
    every other HTML-parsing script in this project already states."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings: list[dict] = []
        self._open_tag: str | None = None
        self._depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self._open_tag is None and tag in _HEADING_LEVELS:
            self._open_tag = tag
            self._depth = 1
            self._buffer = []
        elif self._open_tag is not None:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):
        pass  # h1-h6 are never legally self-closing; there is no content to lose here.

    def handle_endtag(self, tag):
        if self._open_tag is None:
            return
        if tag == self._open_tag:
            self._depth -= 1
            if self._depth == 0:
                text = " ".join("".join(self._buffer).split())
                self.headings.append({"level": _HEADING_LEVELS[self._open_tag], "text": text})
                self._open_tag = None
                self._buffer = []
        else:
            self._depth -= 1

    def handle_data(self, data):
        if self._open_tag is not None:
            self._buffer.append(data)


def extract_headings(html: str) -> list[dict]:
    """Every h1-h6 element's level and flattened text, in document order."""
    parser = _HeadingExtractor()
    parser.feed(html)
    parser.close()
    return parser.headings


# ---------------------------------------------------------------------------
# HTML parsing: JSON-LD blocks + visible text (RET-01)
# ---------------------------------------------------------------------------

_SKIP_TEXT_TAGS = {"script", "style", "code", "pre", "noscript", "template", "svg"}

# A block-level tag boundary must insert a separator into the text stream,
# or two adjacent elements' text runs together into one corrupted word — the
# same _BLOCK_TAGS set entity-audit's _PageParser and content-quality-audit's
# _VisibleTextExtractor already use. Found live, not in a fixture: this
# project's own gymshark.com live-validation target (RET-08's field
# validation, cycle 10) produces 438 run-together word artifacts in this
# skill's visible_text without this insertion — an extraction bug present
# since this skill's cycle-11 corpus (extract_json_ld_and_text), never a
# regression specific to this cycle's new capabilities, but caught here
# because RET-02/05's word- and phrase-level statistics are the first
# checks in this skill sensitive enough to make the corruption visible.
_BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th",
}


class _JsonLdTextParser(HTMLParser):
    """One pass collects raw JSON-LD script bodies and a lightly-scoped
    visible-text string, script/style/code/pre excluded — the same scoped
    extraction `entity-audit`'s `_PageParser` and `content-quality-audit`'s
    `_VisibleTextExtractor` both use, reimplemented here per this project's
    independently-runnable-skill convention."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.json_ld_blocks: list[str] = []
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
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        # Delegate rather than override blank — a self-closed <script/> or
        # skip-tag is a start tag with no separate content; see
        # entity-audit's _PageParser for the live bug (apple.com) this
        # delegation guards against for a different tag.
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_json_ld:
            self.json_ld_blocks.append("".join(self._json_ld_buffer))
            self._in_json_ld = False
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_buffer.append(data)
            return
        if self._skip_depth == 0:
            self._text_chunks.append(data)

    def visible_text(self) -> str:
        raw = "".join(self._text_chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


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


def extract_json_ld_and_text(html: str) -> tuple[list[dict], str]:
    """Returns (json_ld_nodes, visible_text). A JSON-LD block that fails to
    parse is silently skipped here — RET-01 only needs whatever identifiers
    successfully parsed; malformed JSON-LD is entity-audit's ENT-01 concern,
    not this capability's."""
    parser = _JsonLdTextParser()
    parser.feed(html)
    parser.close()

    nodes: list[dict] = []
    for block in parser.json_ld_blocks:
        stripped = block.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        nodes.extend(_flatten_json_ld(value))

    return nodes, parser.visible_text()


# ---------------------------------------------------------------------------
# RET-01 — BM25 exact-match retention (technical-identifier survival)
# ---------------------------------------------------------------------------

_TECHNICAL_ID_FIELDS = ("sku", "mpn", "gtin", "gtin8", "gtin12", "gtin13", "gtin14")


def _node_types(node: dict) -> set[str]:
    type_value = node.get("@type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {t for t in type_value if isinstance(t, str)}
    return set()


def extract_technical_tokens(json_ld_nodes: list[dict]) -> list[dict]:
    """Every non-empty `sku`/`mpn`/`gtin*` value on a JSON-LD `Product` node.
    Scoped to `Product` only, not any node carrying one of these field names —
    the same field name on an unrelated type is not this capability's
    concern, and widening the type check would raise false-positive risk for
    no evidence of real benefit."""
    tokens: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for node in json_ld_nodes:
        if "Product" not in _node_types(node):
            continue
        for field in _TECHNICAL_ID_FIELDS:
            value = node.get(field)
            if not isinstance(value, str):
                continue
            token = value.strip()
            if not token:
                continue
            key = (field, token)
            if key in seen:
                continue
            seen.add(key)
            tokens.append({"field": field, "token": token})
    return tokens


def _token_survives(token: str, visible_text: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
    return re.search(pattern, visible_text, flags=re.IGNORECASE) is not None


def find_token_survival_gaps(tokens: list[dict], visible_text: str) -> list[Finding]:
    missing = [t for t in tokens if not _token_survives(t["token"], visible_text)]
    if not missing:
        return []

    examples = missing[:5]
    quoted = "; ".join(f'{t["field"]} "{t["token"]}"' for t in examples)
    more = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""

    return [
        Finding(
            id="RET-01-token-not-in-text",
            title="A structured-data identifier does not appear in the page's own visible text",
            severity="medium",
            evidence=(
                f"{len(missing)} identifier(s) declared in this page's JSON-LD Product data "
                f"do not appear anywhere in its extracted visible text: {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Include the identifier (SKU/model number) as real visible text on the page, not only inside JSON-LD, an image alt attribute, or script-rendered content.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="RET-01",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Sparse/exact-match retrieval matches query tokens against a page's extracted "
                "text, not its structured data. A visitor or assistant searching for this exact "
                "SKU or model number has nothing on the page's own text to match against, even "
                "though the page's own markup confirms the page is genuinely about it."
            ),
            gate=3,
            confidence="high",
            structured_evidence={
                "missing_tokens": [{"field": t["field"], "token": t["token"]} for t in missing],
                "count": len(missing),
            },
        )
    ]


# ---------------------------------------------------------------------------
# HTML parsing: prose text only, structured regions excluded (RET-04)
# ---------------------------------------------------------------------------

_STRUCTURED_TAGS = {"table", "dl", "ul", "ol", "select"}


class _ProseTextExtractor(HTMLParser):
    """Visible text with `<table>`/`<dl>`/`<ul>`/`<ol>`/`<select>` regions
    excluded — RET-04's own capability-matrix risk note ("exclude structured
    regions before counting") applied directly during extraction rather than
    as a post-hoc filter. A single aggregate depth counter tracks "inside
    any structured region," the same pattern `_SKIP_TEXT_TAGS`/`_skip_depth`
    already uses elsewhere in this file: opens and closes of these tags pair
    up 1:1 in well-formed HTML regardless of which specific tag nests inside
    which, so an aggregate counter reflects the right boolean without
    tracking each tag name separately."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._structured_depth = 0
        self._text_chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth += 1
        if tag in _STRUCTURED_TAGS:
            self._structured_depth += 1
        if tag in _BLOCK_TAGS and self._skip_depth == 0 and self._structured_depth == 0:
            self._text_chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _SKIP_TEXT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag in _STRUCTURED_TAGS:
            self._structured_depth = max(0, self._structured_depth - 1)
        if tag in _BLOCK_TAGS and self._skip_depth == 0 and self._structured_depth == 0:
            self._text_chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and self._structured_depth == 0:
            self._text_chunks.append(data)

    def prose_text(self) -> str:
        raw = "".join(self._text_chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def extract_prose_text(html: str) -> str:
    """Visible text with structured (table/list/glossary) regions excluded."""
    parser = _ProseTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.prose_text()


# ---------------------------------------------------------------------------
# RET-04 — Keyword stuffing
# ---------------------------------------------------------------------------

_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")

_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "for",
        "with", "as", "is", "are", "was", "were", "be", "been", "being",
        "this", "that", "these", "those", "it", "its", "at", "by", "from",
        "into", "over", "under", "up", "down", "out", "about", "than",
        "then", "so", "if", "not", "no", "yes", "you", "your", "we", "our",
        "they", "their", "he", "she", "his", "her", "them", "i", "my", "me",
    }
)

_KEYWORD_STUFFING_NGRAM_LENGTH = 4
_KEYWORD_STUFFING_MIN_OCCURRENCES = 5
_KEYWORD_STUFFING_MIN_DENSITY = 0.08
_KEYWORD_STUFFING_MIN_PROSE_WORDS = 80


def _tokenize_words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_TOKEN_PATTERN.findall(text)]


def _split_sentences(text: str) -> list[str]:
    """Crude but sufficient: RET-02/03/05/06's agent-judged extraction needs
    sentence-ish boundaries, not linguistically correct ones — same
    reimplementation `content-quality-audit` and `citability-audit` each
    carry independently rather than import, per this project's
    independently-runnable-skill convention."""
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _count_ngrams(words: list[str], n: int) -> Counter:
    """Overlapping n-gram counts, stopword-only grams excluded. Shared by
    RET-04 (keyword stuffing) and RET-02 (semantic-coverage extraction) —
    the same n-gram-frequency mechanism at two different window sizes and
    thresholds, not two independent implementations."""
    counts: "Counter[tuple[str, ...]]" = Counter()
    for i in range(len(words) - n + 1):
        gram = tuple(words[i : i + n])
        if all(w in _STOPWORDS for w in gram):
            continue
        counts[gram] += 1
    return counts


def find_keyword_stuffing(prose_text: str) -> list[Finding]:
    """RET-04. Counts overlapping n-grams (default: 4-word phrases) across
    the whole prose corpus — not just adjacent repeats, so a phrase spread
    throughout the page is still caught. A phrase composed entirely of
    stopwords never counts (natural connective text repeats constantly and
    means nothing about stuffing); pages under the minimum word count are
    skipped entirely, since density is not a meaningful signal on a short
    page. Both the occurrence-count and density thresholds must be met —
    density alone would flag a short but genuinely on-topic phrase; count
    alone would flag long pages that simply mention a real topic often."""
    words = _tokenize_words(prose_text)
    total_words = len(words)
    if total_words < _KEYWORD_STUFFING_MIN_PROSE_WORDS:
        return []

    counts = _count_ngrams(words, _KEYWORD_STUFFING_NGRAM_LENGTH)

    stuffed = [
        (gram, count)
        for gram, count in counts.items()
        if count >= _KEYWORD_STUFFING_MIN_OCCURRENCES
        and (count * _KEYWORD_STUFFING_NGRAM_LENGTH) / total_words >= _KEYWORD_STUFFING_MIN_DENSITY
    ]
    if not stuffed:
        return []

    stuffed.sort(key=lambda item: (-item[1], item[0]))
    examples = stuffed[:5]
    quoted = "; ".join(f'"{" ".join(gram)}" ({count}x)' for gram, count in examples)
    more = f" (+{len(stuffed) - 5} more)" if len(stuffed) > 5 else ""

    return [
        Finding(
            id="RET-04-keyword-stuffing",
            title="A phrase is repeated at unnatural density in the page's own prose",
            severity="medium",
            evidence=(
                f"{len(stuffed)} phrase(s) repeat at a density generative engines associate with "
                f"keyword stuffing, out of {total_words} prose word(s) (table/list/glossary regions "
                f"excluded from this count): {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Rewrite the repeated phrase's occurrences with natural variation, or reduce how often it appears verbatim in body copy.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="RET-04",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Generative engines and modern search ranking treat unnaturally dense exact-phrase "
                "repetition as a manipulation signal and demote the page for it — the opposite of the "
                "intended effect."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={
                "repeated_phrases": [{"phrase": " ".join(gram), "count": count} for gram, count in stuffed],
                "prose_word_count": total_words,
            },
        )
    ]


# ---------------------------------------------------------------------------
# HTML parsing: definition-block presence (RET-07)
# ---------------------------------------------------------------------------


class _DefinitionBlockDetector(HTMLParser):
    """Detects whether the page markup contains at least one <dt> and at
    least one <dd> element anywhere. Deliberately not scoped to matching
    pairs within the same <dl> — real pages nest deeply and inconsistently,
    and the presence of both tags anywhere on the page is itself the
    load-bearing signal RET-07 needs, not perfect pairing."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.has_dt = False
        self.has_dd = False

    def handle_starttag(self, tag, attrs):
        if tag == "dt":
            self.has_dt = True
        elif tag == "dd":
            self.has_dd = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def has_definition_block(html: str) -> bool:
    parser = _DefinitionBlockDetector()
    parser.feed(html)
    parser.close()
    return parser.has_dt and parser.has_dd


# ---------------------------------------------------------------------------
# RET-07 — Retrieval-oriented structure
# ---------------------------------------------------------------------------

_QA_SCHEMA_TYPES = {"FAQPage", "QAPage"}
_RET07_MIN_CONTENT_WORDS = 300


def has_qa_heading_framing(headings: list[dict]) -> bool:
    return any(h["text"].rstrip().endswith("?") for h in headings if h["text"])


def has_qa_schema(json_ld_nodes: list[dict]) -> bool:
    return any(_node_types(node) & _QA_SCHEMA_TYPES for node in json_ld_nodes)


def find_missing_retrieval_structure(
    headings: list[dict],
    json_ld_nodes: list[dict],
    has_dt_dd: bool,
    content_word_count: int,
) -> list[Finding]:
    """RET-07. Fires only when a substantial page has *none* of the three
    named structural aids at all — any single one present is enough to stay
    silent. A page under the word-count floor is skipped entirely: a short
    page (a contact page, a single-product landing page) has little enough
    content that "no headings" says nothing about chunking quality.

    `content_word_count` must come from the full visible-text corpus
    (`extract_json_ld_and_text()`'s second return value), not
    `extract_prose_text()`'s structured-region-excluded one RET-04 uses.
    Found live: pages that use `<table>` purely for visual layout (old-
    school HTML, e.g. paulgraham.com's essays) have essentially their
    entire body wrapped in table cells, so RET-04's exclusion — correct for
    that capability's own FP guard — would silently zero out this
    capability's word count and suppress the check entirely on exactly
    those pages, a false negative RET-07 has no reason to inherit."""
    if content_word_count < _RET07_MIN_CONTENT_WORDS:
        return []

    has_headings = len(headings) > 0
    has_qa = has_qa_heading_framing(headings) or has_qa_schema(json_ld_nodes)
    if has_headings or has_qa or has_dt_dd:
        return []

    return [
        Finding(
            id="RET-07-no-retrieval-structure",
            title="A substantial page has no headings, Q&A framing, or definition blocks",
            severity="medium",
            evidence=(
                f"This page has {content_word_count} word(s) of visible text but no heading "
                f"elements, no Q&A-style heading or FAQPage/QAPage markup, and no definition-list "
                f"(<dt>/<dd>) block anywhere — none of the structural aids that let a retrieval "
                f"system split it into self-contained chunks."
            ),
            suggested_action=SuggestedAction(
                summary="Break the page into headed sections, add Q&A framing for common questions, or add a definition list for its key terms, so a retrieval system can chunk it into self-contained pieces.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="RET-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A retrieval system chunks a page along whatever structural boundaries it can find. "
                "With none of these three present, chunking falls back to arbitrary paragraph or "
                "token splits that can cut a single idea in half or merge two unrelated ones into "
                "one chunk."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={
                "content_word_count": content_word_count,
                "has_headings": has_headings,
                "has_qa_framing": has_qa,
                "has_definition_block": has_dt_dd,
            },
        )
    ]


# ---------------------------------------------------------------------------
# HTML parsing: paragraph text (RET-06)
# ---------------------------------------------------------------------------


class _ParagraphExtractor(HTMLParser):
    """Collects each <p> element's flattened text as one entry, in document
    order. Same single-tag-tracking shape as `_HeadingExtractor` — <p> does
    not legally nest another <p>, so a second one opening while one is
    already open closes the first implicitly in real HTML, but this parser
    does not attempt that repair; nested-<p> malformed HTML folds the inner
    content into the outer paragraph's buffer, the same documented,
    uncorrected limitation every HTML-parsing script in this project
    already states for its own extraction step."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._open = False
        self._depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "p" and not self._open:
            self._open = True
            self._depth = 1
            self._buffer = []
        elif self._open:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):
        pass  # an empty self-closed <p/> has no content to lose here.

    def handle_endtag(self, tag):
        if not self._open:
            return
        if tag == "p":
            self._depth -= 1
            if self._depth == 0:
                text = " ".join("".join(self._buffer).split())
                if text:
                    self.paragraphs.append(text)
                self._open = False
                self._buffer = []
        else:
            self._depth -= 1

    def handle_data(self, data):
        if self._open:
            self._buffer.append(data)


def extract_paragraphs(html: str) -> list[str]:
    """Every non-empty <p> element's flattened text, in document order."""
    parser = _ParagraphExtractor()
    parser.feed(html)
    parser.close()
    return parser.paragraphs


# ---------------------------------------------------------------------------
# RET-02 / RET-03 / RET-05 / RET-06 — agent-judged extraction only
# ---------------------------------------------------------------------------
#
# These four capabilities are semantic judgement calls this script does not
# attempt to resolve on its own — the same `agent_judgement_required`
# pattern this project has now proven six times (content-quality-audit's
# CQ-01/02/04/09/12, engagement-audit's EN-01/03, citability-audit's CIT-04,
# entity-audit's ENT-09). Each function below extracts structural
# observations only and emits no verdict; the calling agent resolves each
# entry against `references/retrieval-judgement-rubric.md` before this
# skill's output reaches the entrypoint.

_ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")
_LONG_WORD_MIN_CHARS = 9
_RET06_LONG_PARAGRAPH_MIN_WORDS = 80
_RET06_LONG_PARAGRAPH_MIN_SENTENCES = 5
_MAX_CANDIDATES = 10


def find_semantic_coverage_candidates(prose_text: str) -> dict:
    """RET-02. Finds the single most-repeated 3-word phrase in the page's
    prose (≥3 occurrences, not entirely stopwords) and a few sentences that
    use it. Not a verdict: a phrase repeating is not itself a defect (that
    is RET-04's job at a much higher threshold) — the agent's actual
    judgement is whether the page ever expresses the same underlying
    concept a *different* way anywhere else, which this extraction cannot
    determine on its own."""
    words = _tokenize_words(prose_text)
    counts = _count_ngrams(words, 3)
    candidates = [(gram, count) for gram, count in counts.items() if count >= 3]
    if not candidates:
        return {"dominant_phrase": None, "occurrences": 0, "example_sentences": []}

    candidates.sort(key=lambda item: (-item[1], item[0]))
    top_gram, top_count = candidates[0]
    phrase = " ".join(top_gram)
    examples = [s.strip() for s in _split_sentences(prose_text) if phrase in s.lower()][:3]
    return {"dominant_phrase": phrase, "occurrences": top_count, "example_sentences": examples}


def find_query_intent_candidates(
    headings: list[dict], json_ld_nodes: list[dict], prose_text: str
) -> dict:
    """RET-03. Extracts what the page already has (its stated topic and any
    existing Q&A-shaped content) — deciding what the "obvious question
    forms" for this brand's own category actually are needs the agent's own
    world knowledge of that category, which no script has access to."""
    primary_heading = headings[0]["text"] if headings and headings[0]["text"] else None
    qa_headings = [h["text"] for h in headings if h["text"].rstrip().endswith("?")]
    sentences = _split_sentences(prose_text)
    return {
        "primary_heading": primary_heading,
        "existing_qa_headings": qa_headings,
        "has_qa_schema": has_qa_schema(json_ld_nodes),
        "opening_excerpt": " ".join(sentences[:3]),
    }


_RET05_MIN_SAMPLE_WORDS = 8
_RET05_SHOUTED_MAX_WORDS = 6


def _is_shouted_chrome_sentence(sentence: str) -> bool:
    """A short, entirely-uppercase fragment ('BOOK A CLASS', 'CHIPOTLE HAM
    BRIOCHE SANDWICH') is a UI label or menu-item heading, not prose — real
    acronym usage sits inside ordinary mixed-case sentences (see the
    rubric's own 'The API leverages OAuth2 PKCE...' example), never as an
    entire short sentence in caps."""
    words = sentence.split()
    if not words or len(words) > _RET05_SHOUTED_MAX_WORDS:
        return False
    letters = [c for c in sentence if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def find_terminology_balance_candidates(prose_text: str) -> dict:
    """RET-05. Extracts quantified jargon-density signals plus a spread of
    sample sentences (opening, middle, closing) — the agent reads these
    directly to judge whether the page balances domain terminology with
    plain-language explanation, or leans entirely to one side.

    Small templated sites repeat an entire nav/menu block verbatim 2-3
    times (desktop state, expanded state, mobile "Folder:" state) — each
    repeat is its own block-boundary-newline-split entry in `sentences`.
    An exact-duplicate entry is the same content counted again, not new
    signal, and skewed acronym_count/long_word_ratio toward pure UI chrome
    on a real yogaoffeast.com page (acronym_count: 14, almost entirely
    "BOOK A CLASS" — a button label, not an acronym — repeated across
    duplicated menu states). De-duplicating first fixes the count at its
    root cause instead of patching around it downstream."""
    sentences = _split_sentences(prose_text)
    deduped_sentences = list(dict.fromkeys(sentences))
    deduped_text = "\n".join(deduped_sentences)

    words = _tokenize_words(deduped_text)
    total_words = len(words)
    long_word_count = sum(1 for w in words if len(w) >= _LONG_WORD_MIN_CHARS)
    acronym_count = sum(
        len(_ACRONYM_PATTERN.findall(s)) for s in deduped_sentences if not _is_shouted_chrome_sentence(s)
    )

    stripped = [s.strip() for s in deduped_sentences]
    # A short nav label or button ("MENU", "BOOK A CLASS") is not
    # representative prose; prefer real sentences long enough to actually
    # show the page's terminology register, falling back to whatever
    # exists if nothing clears the bar.
    real_sentences = [s for s in stripped if len(_tokenize_words(s)) >= _RET05_MIN_SAMPLE_WORDS]
    pool = real_sentences or stripped

    samples = []
    if pool:
        indices = sorted({0, len(pool) // 2, len(pool) - 1})
        samples = [pool[i] for i in indices]

    return {
        "total_words": total_words,
        "long_word_ratio": round(long_word_count / total_words, 3) if total_words else 0.0,
        "acronym_count": acronym_count,
        "sample_sentences": samples,
    }


def find_chunk_quality_candidates(paragraphs: list[str]) -> list[dict]:
    """RET-06. Flags paragraphs long enough (by word and sentence count) to
    plausibly blend several distinct ideas — length alone is not the
    defect; the agent reads each candidate and judges whether it actually
    does, per the rubric's worked examples."""
    candidates = []
    for paragraph in paragraphs:
        sentences = _split_sentences(paragraph)
        words = _tokenize_words(paragraph)
        if len(words) >= _RET06_LONG_PARAGRAPH_MIN_WORDS and len(sentences) >= _RET06_LONG_PARAGRAPH_MIN_SENTENCES:
            candidates.append(
                {"paragraph": paragraph, "word_count": len(words), "sentence_count": len(sentences)}
            )
    return candidates[:_MAX_CANDIDATES]


def build_agent_judgement_requests(
    headings: list[dict],
    json_ld_nodes: list[dict],
    prose_text: str,
    paragraphs: list[str],
) -> list[dict]:
    return [
        {
            "capability_id": "RET-02",
            "instructions": (
                "Read references/retrieval-judgement-rubric.md §RET-02. dominant_phrase below "
                "is this page's most-repeated 3-word phrase; example_sentences shows it in "
                "context. Using the full page (not just these excerpts), decide whether the "
                "page ever expresses the same underlying concept a genuinely different way "
                "(a synonym, a conversational rephrasing, a question form) anywhere else, or "
                "only ever states it this one way. Hand-author a Finding only when the page's "
                "core topic is covered by a single phrasing throughout with no variation "
                "anywhere. If dominant_phrase is null, or the page shows real variation, emit "
                "nothing."
            ),
            "observations": find_semantic_coverage_candidates(prose_text),
        },
        {
            "capability_id": "RET-03",
            "instructions": (
                "Read references/retrieval-judgement-rubric.md §RET-03. Using primary_heading "
                "and opening_excerpt below to infer the page's own category, use your own "
                "knowledge of that category to name the 3-5 most obvious questions a real "
                "visitor would ask about it. Check whether existing_qa_headings, has_qa_schema, "
                "or the page's own body content already addresses each one. Hand-author a "
                "Finding only when multiple genuinely obvious questions for this category go "
                "entirely unaddressed anywhere on the page. If the page's category is unclear, "
                "or the obvious questions are already covered, emit nothing."
            ),
            "observations": find_query_intent_candidates(headings, json_ld_nodes, prose_text),
        },
        {
            "capability_id": "RET-05",
            "instructions": (
                "Read references/retrieval-judgement-rubric.md §RET-05. Using long_word_ratio, "
                "acronym_count and sample_sentences below alongside the full page, decide "
                "whether the page's language is skewed entirely to one extreme — all "
                "unexplained jargon with no plain-language framing, or so simplified it never "
                "names the actual technical terms a domain expert would expect — rather than "
                "genuinely balancing both. Hand-author a Finding only for a real, page-wide "
                "skew, not an isolated sentence. If the page reads as reasonably balanced, "
                "emit nothing."
            ),
            "observations": find_terminology_balance_candidates(prose_text),
        },
        {
            "capability_id": "RET-06",
            "instructions": (
                "Read references/retrieval-judgement-rubric.md §RET-06. For each candidate "
                "paragraph below (flagged only for length, not content), decide whether it "
                "genuinely blends several distinct ideas that would muddy a single retrieval "
                "chunk, or is simply a long paragraph about one coherent idea. Hand-author a "
                "Finding only for genuine blending, quoting the paragraph as evidence. If none "
                "qualify, emit nothing."
            ),
            "observations": {"candidate_paragraphs": find_chunk_quality_candidates(paragraphs)},
        },
    ]


# ---------------------------------------------------------------------------
# RET-08 — Heading hierarchy integrity
# ---------------------------------------------------------------------------


def find_empty_headings(headings: list[dict]) -> list[Finding]:
    empty = [h for h in headings if not h["text"]]
    if not empty:
        return []

    levels = ", ".join(f"h{h['level']}" for h in empty[:8])
    more = f" (+{len(empty) - 8} more)" if len(empty) > 8 else ""

    return [
        Finding(
            id="RET-08-empty-heading",
            title="A heading element has no text content",
            severity="low",
            evidence=f"{len(empty)} heading element(s) with no text content at all: {levels}{more}.",
            suggested_action=SuggestedAction(
                summary="Give the heading real, descriptive text, or remove the element if it was left over from a template.",
                priority="low",
            ),
            category="discoverability",
            capability_id="RET-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An empty heading contributes a document-outline entry with no content to "
                "anchor it to — a retrieval system segmenting the page by heading finds a "
                "section boundary with nothing on one side of it."
            ),
            gate=3,
            confidence="high",
            structured_evidence={"empty_heading_levels": [h["level"] for h in empty], "count": len(empty)},
        )
    ]


def find_skipped_heading_levels(headings: list[dict]) -> list[Finding]:
    skips = []
    for previous, current in zip(headings, headings[1:]):
        if current["level"] > previous["level"] + 1:
            skips.append((previous, current))
    if not skips:
        return []

    examples = skips[:5]
    quoted = "; ".join(
        f'h{p["level"]} ("{p["text"][:60]}") -> h{c["level"]} ("{c["text"][:60]}")' for p, c in examples
    )
    more = f" (+{len(skips) - 5} more)" if len(skips) > 5 else ""

    return [
        Finding(
            id="RET-08-skipped-heading-level",
            title="A heading level is skipped in the page's document outline",
            severity="low",
            evidence=(
                f"Found {len(skips)} place(s) where a heading jumps more than one level "
                f"deeper than the heading before it, with no intermediate level in between: "
                f"{quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Insert the missing intermediate heading level, or lower the deeper heading to be exactly one level below the one before it.",
                priority="low",
            ),
            category="discoverability",
            capability_id="RET-08",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A skipped level breaks the document outline a retrieval system uses to "
                "segment and weight a page's content into chunks — the missing level reads "
                "as a section with no heading of its own, or two unrelated sections merged "
                "into one chunk."
            ),
            gate=3,
            confidence="high",
            structured_evidence={
                "skips": [
                    {"from_level": p["level"], "from_text": p["text"], "to_level": c["level"], "to_text": c["text"]}
                    for p, c in skips
                ]
            },
        )
    ]


# ---------------------------------------------------------------------------
# RET-09 — Positional fact interment
# ---------------------------------------------------------------------------
#
# A page's load-bearing values (price, spec, headline statistic) can be
# genuinely present in the extracted text and still be effectively invisible
# to an LLM synthesizing an answer, if the only place they appear is the
# middle of a long document with no restatement anywhere a reader (or a
# retrieval/attention mechanism) is likely to land first. Liu et al. ("Lost
# in the Middle", TACL 2024), Hsieh et al. (2024, positional attention bias /
# RoPE long-term decay) and Chroma's 2025 "Context Rot" study all document
# this as a live, unsolved property of long-context LLMs, not a retrieval
# failure — the fact can be retrieved and still get under-weighted purely by
# where it sits in the context window.
#
# This is a fresh value extractor and a fresh HTML anchor-text scan,
# deliberately not reusing `extract_prose_text` (RET-04's structured-region
# exclusion is the wrong corpus here — a value inside a spec table is exactly
# the kind of anchor RET-09 wants to credit, not exclude) or
# `extract_json_ld_and_text`'s own flattener (this file's `_flatten_json_ld`
# already does the job `extract_json_ld_and_text` needs; RET-09 reuses that
# same already-flattened `json_ld_nodes` list rather than re-parsing JSON-LD
# a third way).

_RET09_MIN_PROSE_WORDS = 800
_RET09_MAX_VALUES = 20
_RET09_MIN_DISTINCT_INTERRED = 3
_RET09_MIN_INTERRED_RATIO = 0.40
_RET09_MARGIN_FRACTION = 0.15
_RET09_MIDDLE_BAND_LOW = 0.25
_RET09_MIDDLE_BAND_HIGH = 0.75
_RET09_CHRONOLOGY_YEAR_RATIO = 0.70
_RET09_SUMMARY_HEADING_RE = re.compile(r"summary|tl;?dr|key takeaways|at a glance|overview", re.IGNORECASE)

_RET09_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)

# Patterns run in this priority order and claim non-overlapping spans in the
# prose stream, so e.g. "January 15, 2024" is captured once as a date, never
# again as a bare year, and "$1,299" is never also re-captured by the
# unit-word pattern. Each entry is (compiled pattern, kind) — `kind` drives
# only the chronology guard below (it needs to know which values are bare
# 4-digit years).
_RET09_VALUE_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"[$£€]\s?\d(?:[\d,]*\d)?(?:\.\d+)?"), "currency"),
    (
        re.compile(
            rf"\b(?:{_RET09_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b"
            rf"|\b\d{{4}}-\d{{2}}-\d{{2}}\b"
            rf"|\b\d{{1,2}}/\d{{1,2}}/\d{{4}}\b"
        ),
        "date",
    ),
    (re.compile(r"\b\d+(?:\.\d+)?\s?[x×]\s?\d+(?:\.\d+)?(?:\s?[x×]\s?\d+(?:\.\d+)?)?\b"), "dimension"),
    (re.compile(r"\b\d(?:[\d,]*\d)?(?:\.\d+)?\s?(?:%|°[CF]?)"), "unit"),
    (
        re.compile(
            r"\b\d(?:[\d,]*\d)?(?:\.\d+)?\s?(?:kg|g|lbs?|mi|km|m|cm|mm|ft|inch(?:es)?|hrs?|"
            r"hours?|mins?|minutes?|secs?|seconds?|ms|days?|weeks?|months?|years?|yrs?|"
            r"GB|MB|TB|KB)\b"
        ),
        "unit",
    ),
    (re.compile(r"\b\d+(?:\.\d+)?x\b"), "unit"),
    (re.compile(r"\b(?:19|20)\d{2}\b"), "year"),
)


def extract_load_bearing_values(prose_stream: str) -> list[dict]:
    """Up to 20 distinct load-bearing values from `prose_stream` — the same
    concatenated-with-single-space text stream `shared.text_spans.extract_blocks`
    builds, so a returned `char_offset` is directly usable with
    `normalized_position`. Currency amounts, explicit dates (month-name,
    ISO, or slash-form), dimension/spec patterns (`1920x1080`), and numbers
    carrying a unit (`%`, degrees, weight/distance/time/data units, or a
    bare multiplier like `2.4x`) are all in scope; a bare 4-digit year is
    also captured (tagged `kind: "year"`) purely so the chronology FP guard
    below has something to reason about.

    A value is deduplicated by its exact matched string, keeping the first
    occurrence's offset — the margin-restatement test that follows is a
    global presence check, not tied to a specific occurrence, so only one
    representative position per distinct value is needed."""
    claimed: list[tuple[int, int]] = []

    def _overlaps(start: int, end: int) -> bool:
        return any(start < c_end and end > c_start for c_start, c_end in claimed)

    raw_matches: list[tuple[int, str, str]] = []
    for pattern, kind in _RET09_VALUE_PATTERNS:
        for match in pattern.finditer(prose_stream):
            start, end = match.start(), match.end()
            if _overlaps(start, end):
                continue
            claimed.append((start, end))
            raw_matches.append((start, match.group(0).strip(), kind))

    raw_matches.sort(key=lambda item: item[0])

    seen: set[str] = set()
    values: list[dict] = []
    for offset, value, kind in raw_matches:
        if value in seen:
            continue
        seen.add(value)
        values.append({"value": value, "char_offset": offset, "kind": kind})
        if len(values) >= _RET09_MAX_VALUES:
            break
    return values


def _is_chronology_page(values: list[dict]) -> bool:
    """Chronology FP guard. A page whose extracted values are overwhelmingly
    bare years, in non-decreasing document order, is a timeline — the thing
    RET-09's own mechanism research names as its stated false-positive risk —
    not a page burying facts. Silent in that case, regardless of the other
    thresholds."""
    if not values:
        return False
    years = [v for v in values if v["kind"] == "year"]
    if len(years) / len(values) < _RET09_CHRONOLOGY_YEAR_RATIO:
        return False
    ordered = [int(v["value"]) for v in sorted(years, key=lambda v: v["char_offset"])]
    return ordered == sorted(ordered)


class _RET09MarginAnchorExtractor(HTMLParser):
    """Single pass collecting the text of every structural anchor site RET-09
    checks that isn't already covered by `extract_headings` (h1/h2) or the
    prose stream's own opening/closing 15%: `<title>`, every `<dt>`/`<dd>`,
    and every `<td>`/`<th>` table cell. `<dt>`/`<dd>` and `<td>`/`<th>` share
    one depth counter — RET-09 only needs "inside any of these anchor tags
    or not", the same aggregate-depth pattern `_ProseTextExtractor` already
    uses for its own, unrelated boolean."""

    _ANCHOR_TAGS = {"dt", "dd", "td", "th"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._title_parts: list[str] = []
        self._anchor_parts: list[str] = []
        self._in_title = False
        self._anchor_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag in self._ANCHOR_TAGS:
            self._anchor_depth += 1

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self._ANCHOR_TAGS:
            self._anchor_depth = max(0, self._anchor_depth - 1)

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        if self._anchor_depth > 0:
            self._anchor_parts.append(data)

    def title_text(self) -> str:
        return " ".join("".join(self._title_parts).split())

    def anchor_text(self) -> str:
        return " ".join("".join(self._anchor_parts).split())


def extract_margin_anchor_text(html: str) -> tuple[str, str]:
    """Returns (title_text, dt_dd_and_table_cell_text) for `html`."""
    parser = _RET09MarginAnchorExtractor()
    parser.feed(html)
    parser.close()
    return parser.title_text(), parser.anchor_text()


def _json_ld_leaf_strings(json_ld_nodes: list[dict]) -> list[str]:
    """Every string/number leaf value anywhere in `json_ld_nodes`, flattened
    into a flat list — used only as a text corpus to search a value against,
    so structure/nesting doesn't matter, only whether the literal value
    appears anywhere in the page's own structured data."""
    leaves: list[str] = []

    def _walk(value):
        if isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for v in value:
                _walk(v)
        elif isinstance(value, str):
            leaves.append(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            leaves.append(str(value))

    for node in json_ld_nodes:
        _walk(node)
    return leaves


def _summary_block_ranges(blocks: list[Block]) -> list[tuple[int, int]]:
    return [
        (block.start_char, block.end_char)
        for block in blocks
        if block.nearest_heading and _RET09_SUMMARY_HEADING_RE.search(block.nearest_heading)
    ]


def _in_any_range(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def find_interred_facts(html: str, headings: list[dict], json_ld_nodes: list[dict]) -> list[Finding]:
    """RET-09. Needs raw `html` directly (not only pre-extracted structures,
    unlike this file's other `find_*` functions) because the margin-anchor
    scan — `<title>`, `<dt>`/`<dd>`, `<td>`/`<th>` — has no other extraction
    pass in this file to reuse; `headings` and `json_ld_nodes` are still
    accepted as already-extracted arguments since `audit_html` computes both
    anyway for other capabilities."""
    blocks = extract_blocks(html)
    prose_word_count = sum(block.word_count for block in blocks)
    if prose_word_count < _RET09_MIN_PROSE_WORDS:
        return []

    prose_stream = " ".join(block.text for block in blocks)
    total_chars = len(prose_stream)
    values = extract_load_bearing_values(prose_stream)
    if not values or _is_chronology_page(values):
        return []

    title_text, dt_dd_table_text = extract_margin_anchor_text(html)
    h1_h2_text = " ".join(h["text"] for h in headings if h["level"] in (1, 2) and h["text"])
    margin_len = max(0, round(total_chars * _RET09_MARGIN_FRACTION))
    opening_text = prose_stream[:margin_len]
    closing_text = prose_stream[max(0, total_chars - margin_len):]
    json_ld_text = " ".join(_json_ld_leaf_strings(json_ld_nodes))
    anchor_blob = "\n".join(
        [title_text, h1_h2_text, opening_text, closing_text, dt_dd_table_text, json_ld_text]
    ).lower()

    summary_ranges = _summary_block_ranges(blocks)

    interred = []
    for entry in values:
        offset = entry["char_offset"]
        position = normalized_position(offset, total_chars)
        if not (_RET09_MIDDLE_BAND_LOW < position < _RET09_MIDDLE_BAND_HIGH):
            continue
        if entry["value"].lower() in anchor_blob:
            continue
        if _in_any_range(offset, summary_ranges):
            continue
        interred.append({"value": entry["value"], "normalized_position": round(position, 4), "restated_at": None})

    if len(interred) < _RET09_MIN_DISTINCT_INTERRED:
        return []
    interred_ratio = len(interred) / len(values)
    if interred_ratio < _RET09_MIN_INTERRED_RATIO:
        return []

    examples = interred[:8]
    quoted = ", ".join(item["value"] for item in examples)
    more = f" (+{len(interred) - 8} more)" if len(interred) > 8 else ""

    return [
        Finding(
            id="RET-09-facts-interred-mid-document",
            title="Load-bearing values appear only in the middle of the page, restated nowhere",
            severity="medium",
            evidence=(
                f"This page runs {prose_word_count} word(s). {len(interred)} of its {len(values)} "
                f"extracted load-bearing figure(s) — {quoted}{more} — each appear only in the "
                f"document's middle band (normalized position between {_RET09_MIDDLE_BAND_LOW} and "
                f"{_RET09_MIDDLE_BAND_HIGH}), with no restatement in the title, any h1/h2, the "
                f"opening or closing 15% of prose, a table cell, a definition, or JSON-LD. "
                f"Published attention-bias research (Liu et al. 2024; Chroma 2025) identifies this "
                f"band as the highest-risk zone for omission during synthesis."
            ),
            suggested_action=SuggestedAction(
                summary="Restate the key figure(s) in a heading, the page's opening or closing section, a spec table, or JSON-LD — not only in the middle of the body copy.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="RET-09",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "Published research (Liu et al., 'Lost in the Middle', TACL 2024; Hsieh et al. "
                "2024; Chroma's 'Context Rot' study, 2025) shows LLMs systematically under-attend "
                "to information positioned in the middle of a long context, with the degradation "
                "replicated across frontier models including GPT-4.1, Claude 4 and Gemini 2.5. A "
                "fact that exists only at normalized depth ~0.5 is measurably more likely to be "
                "omitted from a synthesized answer than the same fact restated at either margin, "
                "independent of retrieval succeeding."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={
                "prose_word_count": prose_word_count,
                "values": interred,
                "interred_ratio": round(interred_ratio, 4),
            },
        )
    ]


# ---------------------------------------------------------------------------
# RET-10 — Chunk self-containment
# ---------------------------------------------------------------------------
#
# A RAG pipeline retrieves blocks, not pages. A block that opens "It cut
# onboarding time by 40% for their enterprise tier." and never names what
# "it" or "their" refers to anywhere inside itself is a block whose
# dense-retrieval embedding drifts away from queries naming the entity
# explicitly, and whose content a model must guess or invent an antecedent
# for if the block *is* retrieved alone. Three independent 2025 papers
# (CoRAG, CLAP, and an ACL SRW coreference-in-RAG study) converge on this
# from different methodologies. This also absorbs the defensible core of
# this project's deferred "chunk fracture" idea: a block whose value sits
# far from its own subject is exactly a block that fails the anchor test
# below, without needing an arbitrary window offset.
#
# Deliberately reuses `shared.text_spans.extract_blocks`,
# `split_sentences` and `proper_noun_tokens` rather than adding a second
# block/sentence splitter — RET-09 (this file, Task 7) already exercised
# and hardened `extract_blocks`'s offset semantics, which this capability
# depends on for `nearest_heading` but not for offsets themselves (RET-10
# is not itself a position check).

_RET10_MIN_BLOCK_WORDS = 25
_RET10_MIN_JUDGED_BLOCKS = 4
_RET10_MIN_CONTEXT_DEPENDENT_RATIO = 0.25
_RET10_MAX_EXAMPLES = 5
_RET10_ANCHOR_WORD_MIN_CHARS = 4

_RET10_PRONOUNS = {"it", "they", "he", "she", "them", "its", "their"}
_RET10_DEMONSTRATIVES = {"this", "that", "these", "those"}
_RET10_GENERIC_DEFINITE_RE = re.compile(
    r"^the\s+(company|product|platform|service|tool|team)\b", re.IGNORECASE
)
# Self-referential deixis names the document itself ("This guide explains
# ..."), not an external antecedent — the research's own stated FP risk.
# Checked before the generic anaphor test, and always wins: a block that
# matches this is never context-dependent, regardless of anchoring.
_RET10_SELF_DEIXIS_RE = re.compile(
    r"^(this|that|these|those)\s+(guide|article|page|post|section|table|chapter)\b", re.IGNORECASE
)


def _ret10_first_sentence(block_text: str) -> str:
    sentences = split_sentences(block_text)
    return sentences[0].text if sentences else block_text


def _is_anaphoric_opening(first_sentence: str) -> bool:
    """Leading personal pronoun, leading demonstrative not immediately
    followed by a proper-noun-like (capitalized) word — 'This approach...'
    is anaphoric, 'This Widget Pro...' names its own subject and is not —
    or a generic definite description ('the company', 'the product', ...)."""
    stripped = first_sentence.strip()
    words = stripped.split()
    if not words:
        return False
    first = words[0].strip(".,;:!?\"'").lower()
    if first in _RET10_PRONOUNS:
        return True
    if first in _RET10_DEMONSTRATIVES:
        if len(words) >= 2:
            second = words[1].strip(".,;:!?\"'")
            if second and second[0].isupper():
                return False
        return True
    return bool(_RET10_GENERIC_DEFINITE_RE.match(stripped))


def _ret10_content_words(text: str) -> set[str]:
    return {
        word
        for word in _tokenize_words(text)
        if word not in _STOPWORDS and len(word) >= _RET10_ANCHOR_WORD_MIN_CHARS
    }


def _has_in_block_anchor(block_text: str, title_h1_words: set[str], heading_words: set[str]) -> bool:
    """A block is anchored — names its own subject — if it contains any
    proper-noun token anywhere, any content word shared with the page's own
    `<title>`/`<h1>`, or a topic term repeated from its nearest heading."""
    if proper_noun_tokens(block_text):
        return True
    block_words = _ret10_content_words(block_text)
    if title_h1_words & block_words:
        return True
    if heading_words & block_words:
        return True
    return False


def _ret10_heading_has_anchor(nearest_heading: str | None) -> bool:
    """Whether the block's own nearest preceding heading carries a proper
    noun or topic term — a signal a heading-aware chunker could use to
    resolve the reference even though this file's own anchor test (above)
    only credits an anchor found *inside* the block itself. Drives the
    page-level confidence downgrade, never suppression (most naive
    chunkers do not carry headings forward)."""
    if not nearest_heading:
        return False
    return bool(proper_noun_tokens(nearest_heading) or _ret10_content_words(nearest_heading))


def find_context_dependent_blocks(html: str, headings: list[dict]) -> list[Finding]:
    """RET-10. Judges every block of >=25 words for whether it opens with an
    unresolved reference and never names its own subject inside itself.
    Fires once per page (not once per block, to avoid flooding the report)
    when the context-dependent ratio is >=25% across >=4 judged blocks."""
    blocks = extract_blocks(html)
    title_text, _ = extract_margin_anchor_text(html)
    h1_text = " ".join(h["text"] for h in headings if h["level"] == 1 and h["text"])
    title_h1_words = _ret10_content_words(f"{title_text} {h1_text}")

    judged = [block for block in blocks if block.word_count >= _RET10_MIN_BLOCK_WORDS]
    if len(judged) < _RET10_MIN_JUDGED_BLOCKS:
        return []

    context_dependent: list[dict] = []
    any_heading_anchor = False
    for index, block in enumerate(judged, start=1):
        first_sentence = _ret10_first_sentence(block.text)
        if _RET10_SELF_DEIXIS_RE.match(first_sentence.strip()):
            continue
        if not _is_anaphoric_opening(first_sentence):
            continue
        heading_words = _ret10_content_words(block.nearest_heading or "")
        if _has_in_block_anchor(block.text, title_h1_words, heading_words):
            continue
        heading_anchored = _ret10_heading_has_anchor(block.nearest_heading)
        any_heading_anchor = any_heading_anchor or heading_anchored
        context_dependent.append(
            {
                "index": index,
                "text": block.text,
                "first_sentence": first_sentence,
                "nearest_heading": block.nearest_heading,
                "heading_anchored": heading_anchored,
            }
        )

    total_judged = len(judged)
    ratio = len(context_dependent) / total_judged if total_judged else 0.0
    if ratio < _RET10_MIN_CONTEXT_DEPENDENT_RATIO:
        return []

    confidence = "medium" if any_heading_anchor else "high"
    examples = context_dependent[:_RET10_MAX_EXAMPLES]
    lead = examples[0]
    lead_quote = lead["text"] if len(lead["text"]) <= 200 else lead["text"][:197] + "..."

    return [
        Finding(
            id="RET-10-context-dependent-blocks",
            title="Content blocks open with an unresolved reference and never name their own subject",
            severity="medium",
            evidence=(
                f"{len(context_dependent)} of {total_judged} content blocks "
                f"({ratio * 100:.0f}%) open with an unresolved reference and never name their "
                f"subject inside the block. Read alone — the unit a RAG pipeline retrieves — "
                f"block {lead['index']} reads: '{lead_quote}' Nothing in that block says what "
                f"the leading pronoun, demonstrative, or generic reference refers to."
            ),
            suggested_action=SuggestedAction(
                summary="Name the subject explicitly within each flagged block (repeat the product/company/topic name), rather than relying on context carried over from an earlier block or heading.",
                priority="medium",
            ),
            category="discoverability",
            capability_id="RET-10",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A RAG pipeline retrieves chunks, not pages, and a chunk's dense-retrieval "
                "embedding is computed only from the text inside it. If a block never names its "
                "own subject, the embedding drifts away from queries that name the entity "
                "explicitly, hurting recall; and if the chunk is retrieved anyway, the model must "
                "guess or invent the antecedent. Three independent 2025 studies (CoRAG, CLAP, and "
                "an ACL SRW coreference-in-RAG study) converge on this from different methodologies."
            ),
            gate=3,
            confidence=confidence,
            structured_evidence={
                "total_blocks_judged": total_judged,
                "context_dependent_count": len(context_dependent),
                "ratio": round(ratio, 4),
                "examples": [
                    {
                        "text": example["text"],
                        "first_sentence": example["first_sentence"],
                        "nearest_heading": example["nearest_heading"],
                    }
                    for example in examples
                ],
            },
        )
    ]


# ---------------------------------------------------------------------------
# Orchestration within the skill
# ---------------------------------------------------------------------------


def _stamp_page(findings: list[Finding], page_url: str | None) -> list[Finding]:
    """Same rationale as every other page-level skill in this marketplace:
    this script runs once per page, so a multi-page report needs each
    finding attributable to its source page."""
    if not page_url:
        return findings
    stamped = []
    for finding in findings:
        finding.evidence = f"On {page_url}: {finding.evidence}"
        finding.structured_evidence = {**(finding.structured_evidence or {}), "page_url": page_url}
        stamped.append(finding)
    return stamped


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    headings = extract_headings(html)
    json_ld_nodes, visible_text = extract_json_ld_and_text(html)
    tokens = extract_technical_tokens(json_ld_nodes)
    prose_text = extract_prose_text(html)
    content_word_count = len(_tokenize_words(visible_text))
    has_dt_dd = has_definition_block(html)
    paragraphs = extract_paragraphs(html)
    findings = _stamp_page(
        find_empty_headings(headings)
        + find_skipped_heading_levels(headings)
        + find_token_survival_gaps(tokens, visible_text)
        + find_keyword_stuffing(prose_text)
        + find_missing_retrieval_structure(headings, json_ld_nodes, has_dt_dd, content_word_count)
        + find_interred_facts(html, headings, json_ld_nodes)
        + find_context_dependent_blocks(html, headings),
        page_url,
    )

    judgement_requests = build_agent_judgement_requests(headings, json_ld_nodes, prose_text, paragraphs)
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
    """Undo Content-Encoding before the body is treated as text — see
    content-quality-audit's own copy of this function for the live-found bug
    (python.org gzips regardless of client negotiation) this guards against.
    Reimplemented here per this project's "independently runnable" skill
    convention rather than imported."""
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
