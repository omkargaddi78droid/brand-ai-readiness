"""Offset-preserving text extraction from raw HTML (shared infrastructure).

Three in-flight capabilities depend on this module without seeing its
implementation: RET-09 (positional-fact-interment), RET-10
(chunk-self-containment), and REN-12 (text-node collection). The contract
below is everything they rely on, so the offset semantics are documented
precisely and are not to be treated as an implementation detail.

Pure stdlib, pure text processing: this module reads an HTML string already
in memory and returns dataclasses. No network, no file I/O, no third-party
imports, no browser/DOM/JS.

Two independent coordinate systems are in play:

- `extract_blocks` builds its own "visible text stream": the sequential
  concatenation of every extracted block's text, in document order, joined
  by exactly one space. `start_char`/`end_char` on each returned `Block` are
  offsets into *that* stream, not into the raw HTML string. Text inside
  script/style/code/pre/kbd/samp/noscript/template/svg is skipped entirely
  before the stream is built, so it never appears in the text and never
  shifts a later block's offsets.
- `split_sentences` is unrelated: its `start_char`/`end_char` are offsets
  into whatever `text` string was passed to it (e.g. a single `Block.text`),
  independent of `extract_blocks`'s coordinate system.

`normalized_position` converts an offset in either system into a [0.0, 1.0]
fraction of the whole, given the total length of that system's stream.

content-quality-audit, citability-audit, and retrieval-readiness-audit each
call this via a thin local `_split_sentences(text) -> list[str]` wrapper
that also splits on bare newlines (list/menu items rarely end in sentence
punctuation) — see any of those scripts for the wrapper.
"""

from __future__ import annotations

import dataclasses
import re
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "li", "dd", "blockquote"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {
    "script",
    "style",
    "code",
    "pre",
    "kbd",
    "samp",
    "noscript",
    "template",
    "svg",
}
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

# Canonical tag sets for the "scoped visible text" extraction pattern used
# independently by content-quality-audit, citability-audit, engagement-audit,
# entity-audit, retrieval-readiness-audit, and static-extraction-audit — a
# broader, div/section/table-aware walk than this module's own _BLOCK_TAGS/
# _SKIP_TAGS above (which serve extract_blocks()'s narrower, offset-preserving
# paragraph/list-item block model and are not for reuse here). Consolidated
# per docs/cycle-24.md item 2.5: the six skills' own definitions were
# byte-for-byte identical (bar content-quality-audit's own, deliberately
# wider superset — see that skill's script for why), so this removes six
# places the same set could silently drift, without changing any skill's
# extraction algorithm or control flow — each skill still owns its own
# HTMLParser subclass and imports only the constant.
VISIBLE_TEXT_SKIP_TAGS = {"script", "style", "code", "pre", "noscript", "template", "svg"}
VISIBLE_TEXT_BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th",
}

# Cycle 24 item 3.4: entity-audit's and content-quality-audit's own
# `_STOPWORDS` were byte-for-byte identical (both used for the same
# "significant words in a label" keyword-folding pattern, CQ-08 / ENT-09).
# retrieval-readiness-audit's own, larger 37-word stopword set is a genuinely
# different, separately-tuned list for a different precision/recall
# tradeoff and stays local there rather than merging into this one.
KEYWORD_FOLDING_STOPWORDS = {
    "the", "a", "an", "of", "for", "and", "or", "is", "are", "on", "in", "to", "by", "this", "that",
}

# Cycle 24 item 3.8: canonical, calendar-ordered tuple, also consolidating
# retrieval-readiness-audit's own separate `_RET09_MONTHS` (a "|"-joined
# regex-alternation string built from this same list of names, order
# irrelevant to a regex alternation but kept calendar-ordered here for
# determinism — set iteration order is not guaranteed stable across
# processes, a tuple's insertion order always is).
MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_MONTHS = frozenset(MONTH_NAMES)
_WEEKDAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}
# Short and defensible on purpose: words that convention capitalises even
# mid-sentence but that are not proper nouns. "I" is the clean, uncontested
# case; anything else belongs to a real stopword corpus, out of scope here.
_COMMON_CAPITALISED_WORDS = {"I"}

_SENTENCE_END_RE = re.compile(r"[.!?]+")
_OPENING_QUOTES = "\"'‘“"
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

_ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "dr.",
    "st.",
    "e.g.",
    "i.e.",
    "vs.",
    "etc.",
    "approx.",
    "no.",
    "u.s.",
    "u.k.",
}


@dataclasses.dataclass
class Block:
    """A unit of visible text extracted from an HTML page.

    `start_char`/`end_char` are offsets into `extract_blocks`'s own
    concatenated visible-text stream (see module docstring), not into the
    raw HTML.
    """

    text: str
    start_char: int
    end_char: int
    tag: str | None
    nearest_heading: str | None
    word_count: int


@dataclasses.dataclass
class Span:
    """A slice of a string, with offsets into that same string.

    `text` always equals the string that was sliced at `[start_char:end_char]`.
    """

    text: str
    start_char: int
    end_char: int


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _BlockParser(HTMLParser):
    """Walks the HTML once, emitting (text, tag, nearest_heading) triples.

    Design: a stack for open block tags (`p`/`li`/`dd`/`blockquote`) so
    nested block tags (e.g. `<blockquote><p>...</p></blockquote>`) each
    become their own block, in document order — the enclosing frame flushes
    what it has buffered so far before a nested block tag opens, and keeps
    accumulating (as a separate, later block) after the nested tag closes,
    rather than splicing the before/after fragments into one out-of-order
    block. A single "bare text run" buffer holds text that sits outside
    those tags (e.g. a bare text node under a `<section>`) but is still
    visible. A skip-depth counter silently drops any text under a skip tag,
    wherever it is nested.

    Entering a block tag or a heading flushes the current bare-text run —
    each contiguous stretch of bare text, uninterrupted by a heading or a
    block tag, becomes exactly one block. This is a judgment call: the brief
    specifies bare-text-between-headings as blocks but not whether a block
    tag in the middle of a bare run should split it. Splitting is the
    simpler, more predictable rule and is documented in the task report.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._tag_stack: list[str] = []
        self._skip_depth = 0
        self._in_heading = False
        self._heading_buffer: list[str] = []
        self._last_heading: str | None = None
        self._bare_buffer: list[str] = []
        self._bare_tag: str | None = None
        self._block_stack: list[dict] = []
        self.pending_blocks: list[tuple[str, str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self._open(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._open(tag)
        self._close(tag)

    def handle_endtag(self, tag: str) -> None:
        self._close(tag)

    def handle_data(self, text_chunk: str) -> None:
        if self._skip_depth > 0:
            return
        if self._block_stack:
            self._block_stack[-1]["buffer"].append(text_chunk)
            return
        if self._in_heading:
            self._heading_buffer.append(text_chunk)
            return
        if not self._bare_buffer:
            # Capture the enclosing tag now, at the start of this run: by
            # the time the run is flushed, an end tag may already have
            # popped this ancestor off the stack.
            self._bare_tag = self._tag_stack[-1] if self._tag_stack else None
        self._bare_buffer.append(text_chunk)

    def finalize(self) -> None:
        """Flush anything still buffered once the document has ended."""
        self._flush_bare()
        for frame in self._block_stack:
            text = _collapse_whitespace("".join(frame["buffer"]))
            if text:
                self.pending_blocks.append((text, frame["tag"], frame["heading"]))
        self._block_stack = []

    def _open(self, raw_tag: str) -> None:
        tag = raw_tag.lower()
        if tag in _HEADING_TAGS:
            self._flush_bare()
            self._in_heading = True
            self._heading_buffer = []
            self._tag_stack.append(tag)
            return
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            self._tag_stack.append(tag)
            return
        if tag in _BLOCK_TAGS:
            self._flush_bare()
            if self._block_stack:
                # A block tag nested inside another (e.g. <blockquote><p>) —
                # flush whatever the enclosing frame has buffered so far as
                # its own block *now*, in document order, rather than
                # merging it with text that resumes after the nested tag
                # closes. The frame stays on the stack, reset, to catch that
                # resumed text as a later block under the same tag.
                self._flush_top_block_frame()
            self._block_stack.append({"tag": tag, "buffer": [], "heading": self._last_heading})
            self._tag_stack.append(tag)
            return
        if tag not in _VOID_TAGS:
            self._tag_stack.append(tag)

    def _close(self, raw_tag: str) -> None:
        tag = raw_tag.lower()
        if tag in _HEADING_TAGS:
            heading_text = _collapse_whitespace("".join(self._heading_buffer))
            if heading_text:
                self._last_heading = heading_text
            self._in_heading = False
            self._heading_buffer = []
            self._pop_tag_stack(tag)
            return
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            self._pop_tag_stack(tag)
            return
        if tag in _BLOCK_TAGS:
            frame = self._pop_block_frame(tag)
            if frame is not None:
                text = _collapse_whitespace("".join(frame["buffer"]))
                if text:
                    self.pending_blocks.append((text, frame["tag"], frame["heading"]))
            self._pop_tag_stack(tag)
            return
        self._pop_tag_stack(tag)

    def _flush_top_block_frame(self) -> None:
        frame = self._block_stack[-1]
        text = _collapse_whitespace("".join(frame["buffer"]))
        frame["buffer"] = []
        if text:
            self.pending_blocks.append((text, frame["tag"], frame["heading"]))

    def _pop_block_frame(self, tag: str) -> dict | None:
        for index in range(len(self._block_stack) - 1, -1, -1):
            if self._block_stack[index]["tag"] == tag:
                frame = self._block_stack[index]
                del self._block_stack[index]
                return frame
        return None

    def _pop_tag_stack(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
            return
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == tag:
                del self._tag_stack[index]
                return

    def _flush_bare(self) -> None:
        text = _collapse_whitespace("".join(self._bare_buffer))
        self._bare_buffer = []
        tag = self._bare_tag
        self._bare_tag = None
        if text:
            self.pending_blocks.append((text, tag, self._last_heading))


def extract_blocks(html: str) -> list[Block]:
    """Parse `html` into offset-preserving visible-text blocks.

    Blocks are `<p>`, `<li>`, `<dd>`, `<blockquote>` elements, plus runs of
    bare text found outside those tags (e.g. text directly under a
    `<section>` or `<div>`), each run ending at the next heading or block
    tag. Text under script/style/code/pre/kbd/samp/noscript/template/svg is
    skipped entirely: it never appears in any block's text and never shifts
    the offsets of blocks that follow, because offsets are computed after
    parsing, from the filtered block list alone.

    Offsets are into the concatenated stream of block texts, joined by a
    single space, in document order — not into the raw HTML.
    """
    parser = _BlockParser()
    parser.feed(html)
    parser.close()
    parser.finalize()

    blocks: list[Block] = []
    position = 0
    for text, tag, heading in parser.pending_blocks:
        start = position
        end = start + len(text)
        blocks.append(
            Block(
                text=text,
                start_char=start,
                end_char=end,
                tag=tag,
                nearest_heading=heading,
                word_count=len(text.split()),
            )
        )
        position = end + 1
    return blocks


def _is_decimal_point(text: str, match: re.Match) -> bool:
    if match.group(0) != ".":
        return False
    start, end = match.start(), match.end()
    if start == 0 or end >= len(text):
        return False
    return text[start - 1].isdigit() and text[end].isdigit()


def _starts_new_sentence(stripped: str) -> bool:
    idx = 0
    while idx < len(stripped) and stripped[idx] in _OPENING_QUOTES:
        idx += 1
    return idx < len(stripped) and stripped[idx].isupper()


def _ends_with_abbreviation(text: str, end: int) -> bool:
    word_start = end - 1
    while word_start > 0 and (text[word_start - 1].isalnum() or text[word_start - 1] == "."):
        word_start -= 1
    return text[word_start:end].lower() in _ABBREVIATIONS


def split_sentences(text: str) -> list[Span]:
    """Split `text` into sentence Spans, offsets into `text` itself.

    Splits on a run of `.`/`!`/`?` followed by whitespace and an uppercase
    letter (optionally preceded by an opening quote mark, e.g. a quoted
    testimonial), or by end of string. Does not split on a short, fixed
    list of common abbreviations (Mr., Mrs., Dr., St., e.g., i.e., vs., etc.,
    approx., no., U.S., U.K.) or on a decimal point directly between two
    digits (e.g. "3.5" stays intact).
    """
    if not text:
        return []

    boundaries: list[int] = []
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        if _is_decimal_point(text, match):
            continue
        if _ends_with_abbreviation(text, end):
            continue
        rest = text[end:]
        if rest == "":
            boundaries.append(end)
            continue
        stripped = rest.lstrip()
        if stripped == rest:
            # No whitespace follows the punctuation: not a sentence break.
            continue
        if stripped and not _starts_new_sentence(stripped):
            continue
        boundaries.append(end)

    spans: list[Span] = []
    cursor = 0
    for end in boundaries:
        start = cursor
        while start < end and text[start].isspace():
            start += 1
        if start < end:
            spans.append(Span(text=text[start:end], start_char=start, end_char=end))
        cursor = end

    start = cursor
    n = len(text)
    while start < n and text[start].isspace():
        start += 1
    if start < n:
        spans.append(Span(text=text[start:n], start_char=start, end_char=n))

    return spans


def normalized_position(char_offset: int, total_chars: int) -> float:
    """Fraction of the way through a `total_chars`-long stream, clamped to [0, 1]."""
    if total_chars <= 0:
        return 0.0
    fraction = char_offset / total_chars
    if fraction < 0.0:
        return 0.0
    if fraction > 1.0:
        return 1.0
    return fraction


def proper_noun_tokens(text: str) -> set[str]:
    """Capitalised word tokens that are not sentence-initial.

    Finds words capitalised for reasons other than starting a sentence —
    typically brand names, product names, person/place names — by excluding
    each sentence's first word (per `split_sentences`), month and weekday
    names, and a short common-word list (see `_COMMON_CAPITALISED_WORDS`).
    Returns the raw token strings, case preserved, deduplicated via the set.
    """
    tokens: set[str] = set()
    for sentence in split_sentences(text):
        words = _WORD_RE.findall(sentence.text)
        for index, word in enumerate(words):
            if index == 0:
                continue
            if not word[0].isupper():
                continue
            if word in _MONTHS or word in _WEEKDAYS or word in _COMMON_CAPITALISED_WORDS:
                continue
            tokens.add(word)
    return tokens
