#!/usr/bin/env python3
"""Gate-3 content-quality audit: text anti-patterns, script-decided and
agent-judged.

Owns twelve capabilities, split by whether a verdict is deterministic or
needs judgement — the same split `engagement-audit` and `citability-audit`
already use for their agent-judged capabilities:

Script decides (near-zero false-positive risk, high evidence quality,
because each finding shows the exact contradiction or the exact formula
rather than asserting a judgement):
  CQ-03  Template leakage — unrendered templating-engine syntax in production HTML
  CQ-05  Relative-date anchors — a change described as "recently" etc. with no absolute date
  CQ-07  Scope-ambiguous numeric claims — the same labeled metric stated twice with different values, no qualifier
  CQ-08  Computed-stat integrity — a stated average that does not match the arithmetic of the page's own listed numbers
  CQ-11  Fluency/readability — Flesch Reading Ease below the "very difficult" band, on a large enough sample
  CQ-13  Near-duplicate/template dilution — cycle 23 addition, `--sample-file` mode (multi-page, see below)
  CQ-10  Freshness self-contradiction — cycle 23 Phase 2 addition, `--url` mode single-page half (see below;
         CQ-10's other half, cross-page fact collision, is agent-decided and listed below too)

Agent decides, against references/content-judgement-rubric.md (the script
extracts candidate sentences only and emits no verdict — asserting "this
hedge is a non-answer" or "this vagueness is a defect" from a phrase match
alone would be exactly the false-positive-of-severity failure this project's
calibration discipline exists to prevent):
  CQ-01  Answer extractability — no concise canonical answer near the top, or buried under marketing
  CQ-02  Non-answer templates — boilerplate hedging ("it depends") standing in for an answerable fact
  CQ-04  Granularity mismatch — a vague magnitude word where a query needs a precise number
  CQ-09  Marketing/procedure interleaving — promotional language breaking up numbered how-to steps
  CQ-10  Cross-page fact collision — cycle 23 addition, `--sample-file` mode (multi-page, see below)
  CQ-12  Signal-to-filler ratio — substance drowning in stock transitional phrasing

**CQ-10 is a cycle-23 addition, Phase 4 B4, sharing CQ-13's `--sample-file`
mode.** Within the same same-template strata CQ-13 already computes, this
extracts every "Label: value" line whose value is typed (a price, a date, or
a thousands-grouped count) and groups by normalized label across the
stratum's pages. A label stated on 3+ pages with more than one distinct
value is a *candidate*, never a verdict: legitimate per-item variation
(price, SKU, model number differing page to page by design) is the dominant
false positive this capability's own plan calls out, and no script-side
heuristic can safely tell that apart from a genuine collision (the SAME
real-world fact — a founding year, a phone number — stated two different
ways) without reading what the label actually refers to. The agent resolves
`agent_judgement_required` against `references/content-judgement-rubric.md`
§CQ-10, the same procedure as this skill's other agent-judged capabilities.

**CQ-10 also has a single-page half, `find_freshness_contradiction`, a
cycle-23 Phase 2 addition (B7) that runs in `--url` mode.** It compares a
visible "Last updated"/"As of" string (or a JSON-LD `dateModified`) against
the HTTP `Last-Modified` response header captured by `shared/page_fetch.fetch_page`.
A claimed date substantially *newer* than what `Last-Modified` supports is a
freshness claim the transport layer itself contradicts. Unlike the
cross-page half, this is entirely script-decided — the comparison is a plain
date arithmetic, not a judgement call — but it stays capped at Medium
confidence and refuses to fire at all when `Last-Modified` sits within an
hour of the fetch time, since a CDN that stamps `Last-Modified` with serve
time rather than true edit time is the dominant false positive here and a
single fetch cannot tell the two apart. `--html-file`/`--text-file` modes
have no live HTTP headers to compare against, so this half never fires
there — not a defect, just nothing to compare.

**CQ-13 is a cycle-23 addition, `--sample-file` mode.** Cluster A's own
"Deferred, 4" note (docs/capability-matrix.md) previously held near-duplicate/
template-dilution detection as "methodologically broken against this
project's own agent-chosen, variety-biased page sample, which systematically
hides exactly the clusters this would look for" — true before cycle 23's
Phase 1 shipped a template-stratified sampler (`shared/page_sample.py`),
which exists specifically so near-identical pages land in the same stratum
instead of never being sampled together. Given a file of on-site page URLs,
this mode fetches each one, strips lines that repeat verbatim across at
least half the sample (the shared site chrome — nav, footer, boilerplate —
that would otherwise make every page look like a near-duplicate of every
other), groups the remainder by `shared/page_sample.template_key`, and runs
`shared/shingles.near_duplicate_groups` (k-shingle Jaccard, replacing the
`datasketch` package rejected in `docs/02-project-plan.md` Part 1) *within*
each template stratum only — comparing across templates would be
meaningless, since a pricing page and a blog post are expected to differ.
Entirely script-decided; no agent judgement needed for a shingle-overlap
threshold.

Deliberately does NOT own: CQ-06 (decay prediction) — needs a change-history
signal (a diff over time) this project has no way to observe from a single
crawl; not the same shape as CQ-10's within-one-sample label comparison.

This is gate 3: it operates on a single page's visible text, not on whether
the crawler could reach the page (gate 1, perimeter-access-audit) or whether
the page's markup is machine-readable at all (gate 2, not yet built). A
perimeter block upstream makes these findings moot for that page; suppressing
them is the entrypoint's job, not this script's.

Text extraction
---------------
`extract_visible_text()` is a minimal stdlib HTML-to-text step, scoped
narrowly to what these four checks need: strip <script>/<style>/<code>/<pre>
(the primary false-positive source — template syntax and example numbers
inside documentation code blocks are not defects), decode entities, and break
at block-level tag boundaries so sentence-level checks do not merge text
across unrelated elements. It is NOT the render/extraction pipeline (REN-06/07
in the capability matrix): no boilerplate-ratio scoring, no main/article
boundary detection, no JS rendering. A page whose real content depends on
either of those remains that cluster's problem, not this one's.

Determinism
-----------
Every detector is a pure function of the input text. No randomness, no clock
in the detection logic, stable iteration and output order.

Safety
------
`--url` mode fetches exactly one page (never a crawl) and refuses to resolve
to a private, loopback, link-local or reserved address before connecting —
the same SSRF discipline the perimeter skill's `robots.txt`/`llms.txt` fetch
did not need, because this script is the one in the marketplace that accepts
an arbitrary page URL rather than a fixed well-known path. Fetched content is
parsed as data only — pattern matching over text — never executed and never
treated as instruction.

Usage:
    check_content_quality.py --url https://example.com/product/example
    check_content_quality.py --site example.com --html-file page.html
    check_content_quality.py --site example.com --text-file page.txt

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...], "site": ..., "page_url": ...,
     "findings": [...], "agent_judgement_required": [...], "unknown_checks": [...]}
`agent_judgement_required` is intermediate — the calling SKILL.md procedure
resolves it into `findings` (or drops it) before this file is composed into
the final report. It must never reach the entrypoint unresolved;
`compose_report.py` converts any that do into `unknown_checks` rather than
dropping or crashing on them, but resolving it properly is the caller's job.
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import re
import sys
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from text_spans import KEYWORD_FOLDING_STOPWORDS, split_sentences, VISIBLE_TEXT_SKIP_TAGS  # noqa: E402
from page_sample import template_key  # noqa: E402
from shingles import near_duplicate_groups  # noqa: E402
from page_fetch import (  # noqa: E402
    USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    MAX_PAGE_BYTES,
    decode_content_encoding,
    is_public_host,
    fetch_page_html,
    fetch_page,
    fetch_pages_concurrently,
)
from budget import StageBudget, coverage_manifest  # noqa: E402
from html_extract import extract_labeled_pairs, extract_main_content_text  # noqa: E402

OWNER_SKILL = "content-quality-audit"
CAPABILITY_IDS = [
    "CQ-01", "CQ-02", "CQ-03", "CQ-04", "CQ-05", "CQ-07", "CQ-08", "CQ-09", "CQ-10", "CQ-11", "CQ-12", "CQ-13",
]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

# Cycle 24 item 2.5: canonical skip set, shared/text_spans.py — see that
# module. BLOCK_TAGS stays local: this skill's own superset adds dt/dd/
# figcaption (definition-list and figure-caption text CQ's checks scope
# into), a genuine, deliberate difference from the other five skills' set,
# not accidental drift.
SKIP_TAGS = VISIBLE_TEXT_SKIP_TAGS
BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th", "dt", "dd", "figcaption",
}


class _VisibleTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        # Collapse whitespace *within* a text node here, including any
        # newline that is just HTML source formatting, so it becomes a space
        # rather than a paragraph break. Only the literal "\n" chunks pushed
        # in handle_starttag/handle_endtag for BLOCK_TAGS should ever produce
        # a line break in the output — conflating the two used to shred a
        # single word-wrapped sentence into separate "lines" and could split
        # a claim verb from its relative-date phrase across the wrap point.
        if self._skip_depth == 0:
            self._chunks.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def extract_visible_text(html: str) -> str:
    """HTML -> plain text, script/style/code/pre stripped, block-level breaks
    preserved as newlines. Malformed HTML with mismatched tags can confuse the
    skip-depth counter; this is a known, documented limitation, not silently
    corrected, because there is no HTML-repair dependency in this project."""
    parser = _VisibleTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


class _H1Extractor(HTMLParser):
    """Captures the first <h1>'s text only, for CQ-01's opening-answer
    signal. Kept as a wholly separate parser pass from `_VisibleTextExtractor`
    on purpose — extending this one detector's needs must never risk
    perturbing the eight checks that already depend on
    `extract_visible_text`'s exact, separately-tested behaviour."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1_text: str | None = None
        self._depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1" and self.h1_text is None and not self._depth:
            self._depth = 1
            self._buffer = []
        elif self._depth:
            self._depth += 1

    def handle_startendtag(self, tag, attrs):
        pass  # <h1/> is never legally self-closing; there is no content to lose here.

    def handle_endtag(self, tag):
        if tag == "h1" and self._depth:
            self._depth -= 1
            if self._depth == 0 and self.h1_text is None:
                self.h1_text = " ".join("".join(self._buffer).split())
        elif self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth:
            self._buffer.append(data)


def extract_h1(html: str) -> str | None:
    """First <h1>'s text, or None if the page has none. Malformed/mismatched
    tags are the same documented, uncorrected limitation as
    `extract_visible_text`."""
    parser = _H1Extractor()
    parser.feed(html)
    parser.close()
    return parser.h1_text


def _split_sentences(text: str) -> list[str]:
    """Sentence-boundary splits within each line, plus a split on bare
    newlines (menu/list items rarely end in sentence punctuation)."""
    result: list[str] = []
    for line in text.split("\n"):
        result.extend(s.text for s in split_sentences(line))
    return result


# ---------------------------------------------------------------------------
# CQ-03 — Template leakage
# ---------------------------------------------------------------------------

_TEMPLATE_PATTERNS = (
    ("mustache/handlebars/liquid variable", re.compile(r"\{\{\s*[A-Za-z_][\w.\-]{0,40}\s*\}\}")),
    ("liquid/jinja tag", re.compile(r"\{%-?\s*[a-z_]+[^%\n]{0,60}?-?%\}")),
    ("erb/asp tag", re.compile(r"<%[-=]?[^%\n]{1,80}?%>")),
)


def find_template_leakage(text: str) -> list[Finding]:
    matches: list[str] = []
    for _name, pattern in _TEMPLATE_PATTERNS:
        matches.extend(m.group(0).strip() for m in pattern.finditer(text))
    if not matches:
        return []

    unique_tokens: list[str] = []
    for token in matches:
        if token not in unique_tokens:
            unique_tokens.append(token)

    quoted = ", ".join(f"'{t}'" for t in unique_tokens[:8])
    more = f" (+{len(unique_tokens) - 8} more)" if len(unique_tokens) > 8 else ""

    return [
        Finding(
            id="CQ-03-template-leakage",
            title="Unrendered template syntax appears in the page's visible text",
            severity="high",
            evidence=(
                f"Found {len(matches)} instance(s) of unrendered templating syntax in the "
                f"page's visible text (outside <script>/<style>/<code>/<pre>): {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Fix the template rendering so the real value is substituted before the "
                    "page is served, or remove the leftover markup if the feature was retired."
                ),
                priority="high",
            ),
            category="discoverability",
            capability_id="CQ-03",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A templating placeholder like `{{city_name}}` is not the fact it stands in "
                "for — it is the absence of the fact, rendered as if it were the fact. A human "
                "skims past it as a glitch; a machine extracting facts from the page reads it "
                "literally, so the placeholder itself becomes the 'answer' an assistant might quote."
            ),
            gate=3,
            confidence="high",
            structured_evidence={"tokens": unique_tokens, "total_matches": len(matches)},
        )
    ]


# ---------------------------------------------------------------------------
# CQ-05 — Relative-date anchors
# ---------------------------------------------------------------------------

_RELATIVE_TIME_PHRASES = (
    "last year", "next year", "this year", "last month", "next month", "this month",
    "last week", "next week", "this week", "last quarter", "next quarter", "this quarter",
    "recently", "currently", "as of now", "as of today",
    "earlier this year", "later this year",
    "a few years ago", "a few months ago", "a few weeks ago",
    "several years ago", "several months ago", "several weeks ago",
)
# Word-boundary matching: a naive substring check on "this week" also matches
# inside "this weekend" ("this week" is a literal prefix of "weekend").
_RELATIVE_TIME_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(phrase) for phrase in _RELATIVE_TIME_PHRASES) + r")\b",
    re.IGNORECASE,
)

# Requiring one of these alongside a relative-time phrase, in the same
# sentence, is what keeps this check's false-positive rate low: a casual
# mention of "this week" with no claim attached to it is not a decaying fact.
_CLAIM_VERBS = (
    "updated", "update", "updates", "changed", "change", "changes",
    "launched", "launch", "released", "release",
    "increased", "increase", "decreased", "decrease", "reduced", "reduce",
    "opened", "open", "closed", "close",
    "expired", "expires", "expire", "started", "start", "starts",
    "ended", "ends", "end", "added", "add", "removed", "remove",
    "moved", "move", "revised", "revise", "published", "publish",
    "modified", "modify", "raised", "raise", "lowered", "lower",
)

_ABSOLUTE_DATE = re.compile(
    r"\b(?:19|20)\d{2}\b"
    r"|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?"
    r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    re.IGNORECASE,
)

# Cycle 24: how close an absolute date must sit to the relative-time phrase
# it's meant to qualify before it suppresses the finding. Previously any
# absolute date anywhere in the sentence suppressed it — which meant
# "Founded in 2010, prices increased recently" (an unrelated year nowhere
# near the relative claim) went unflagged. A tight character window keeps
# the legitimate case ("updated 3 days ago, on March 2, 2026") suppressed
# while catching the unrelated-date case.
_DATE_PROXIMITY_CHARS = 30


def _span_gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Character distance between two spans in the same string: 0 if they
    touch or overlap, otherwise the gap between the nearer ends."""
    a_start, a_end = a
    b_start, b_end = b
    if a_end <= b_start:
        return b_start - a_end
    if b_end <= a_start:
        return a_start - b_end
    return 0


def find_relative_date_anchors(text: str) -> list[Finding]:
    matches: list[tuple[str, str]] = []
    for sentence in _split_sentences(text):
        s = sentence.strip()
        if not s or len(s) > 400:
            continue
        lowered = s.lower()
        phrase_match = _RELATIVE_TIME_PATTERN.search(lowered)
        if not phrase_match:
            continue
        phrase = phrase_match.group(0)
        if not any(re.search(rf"\b{re.escape(v)}\b", lowered) for v in _CLAIM_VERBS):
            continue
        nearby_absolute_date = any(
            _span_gap(phrase_match.span(), date_match.span()) <= _DATE_PROXIMITY_CHARS
            for date_match in _ABSOLUTE_DATE.finditer(s)
        )
        if nearby_absolute_date:
            continue
        matches.append((phrase, s))

    if not matches:
        return []

    examples = matches[:5]
    quoted = "; ".join(f'"{s}"' for _, s in examples)
    more = f" (+{len(matches) - 5} more)" if len(matches) > 5 else ""

    return [
        Finding(
            id="CQ-05-relative-date-anchors",
            title="Claims of change are dated relatively, not absolutely",
            severity="medium",
            evidence=(
                f"Found {len(matches)} sentence(s) describing a change using a relative time "
                f'phrase (e.g. "last month", "recently") with no absolute date in the same '
                f"sentence: {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Replace the relative time phrase with an absolute date or month/year "
                    'wherever a change, update or figure is being dated — "updated in March 2026" '
                    'rather than "updated recently".'
                ),
                priority="medium",
            ),
            category="discoverability",
            capability_id="CQ-05",
            owner_skill=OWNER_SKILL,
            mechanism=(
                '"Recently" and "last month" are only meaningful relative to when the page is '
                "read. Once an assistant extracts and stores the sentence, that anchor is gone: "
                "the claim reads as current no matter how old the page actually is, and the fact "
                "goes stale without ever looking stale."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={"matches": [{"phrase": p, "sentence": s} for p, s in matches]},
        )
    ]


# ---------------------------------------------------------------------------
# CQ-07 — Scope-ambiguous numeric claims
# ---------------------------------------------------------------------------

_LABELED_METRIC = re.compile(
    r"^[ \t]*([A-Za-z][A-Za-z0-9 /()\-]{2,40}?):\s*\$?(-?\d+(?:\.\d+)?)\s*([A-Za-z%°]{0,15})"
)

_QUALIFIER_WORDS = (
    "up to", "starting at", "from", "average", "approximately", "about",
    "depending on", "varies", "based on", "per", "each", "for the", "in the",
    "minimum", "maximum", "at least", "no more than", "typical", "estimated", "roughly",
)
# Word-boundary matching, not substring containment: a naive `in` check on
# "per" also matches inside "period", "perhaps", "percentage" — the exact
# substring-matching failure mode already fixed once in this project for
# robots.txt user-agent groups (see check_perimeter.py's parse_groups).
_QUALIFIER_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in _QUALIFIER_WORDS) + r")\b", re.IGNORECASE
)


def _normalize_unit(unit: str) -> str:
    """`years` and `year` must group together, or "1 year" / "2 years" reads
    as two different metrics instead of the contradiction it is. Units that
    already end in a bare consonant + s where singular != stem (none in the
    common unit set used here) would need a real exception list; the common
    time/weight/distance units used in practice all singularize by dropping
    a trailing 's'."""
    return unit[:-1] if unit.endswith("s") and len(unit) > 2 else unit


def find_scope_ambiguous_numbers(text: str) -> list[Finding]:
    occurrences: dict[tuple[str, str], list[tuple[float, str, bool]]] = defaultdict(list)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _LABELED_METRIC.match(line)
        if not match:
            continue
        label, value_text, unit = match.group(1).strip(), match.group(2), match.group(3).strip().lower()
        label_norm = re.sub(r"\s+", " ", label.lower())
        if len(label_norm.split()) < 2:
            continue  # a single generic word is not a specific enough label to compare on
        has_qualifier = bool(_QUALIFIER_PATTERN.search(line))
        occurrences[(label_norm, _normalize_unit(unit))].append((float(value_text), line, has_qualifier))

    findings: list[Finding] = []
    for (label_norm, unit), entries in sorted(occurrences.items()):
        distinct_values = {value for value, _, _ in entries}
        if len(distinct_values) < 2:
            continue
        if any(has_qualifier for _, _, has_qualifier in entries):
            continue  # a qualifier anywhere in the group explains the difference
        findings.append(_scope_ambiguous_finding(label_norm, unit, entries))
    return findings


def _scope_ambiguous_finding(label_norm: str, unit: str, entries: list[tuple[float, str, bool]]) -> Finding:
    distinct_sorted = sorted({value for value, _, _ in entries})
    values_str = ", ".join(f"{v:g}{unit}" if unit else f"{v:g}" for v in distinct_sorted)
    quoted_lines = "; ".join(f'"{line}"' for _, line, _ in entries[:4])
    slug = re.sub(r"[^a-z0-9]+", "-", label_norm).strip("-")
    return Finding(
        id=f"CQ-07-scope-ambiguous-{slug}",
        title=f'"{label_norm.title()}" is stated with different values and no qualifier',
        severity="medium",
        evidence=(
            f'"{label_norm}" appears {len(entries)} times with different values ({values_str}) '
            f'and no scope qualifier (e.g. "up to", "starting at", "depending on") near any '
            f"mention: {quoted_lines}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                f'Add a qualifier that explains the difference (model, plan, region, condition) '
                f'to each "{label_norm}" figure, or correct whichever value is wrong.'
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="CQ-07",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "An assistant extracting a single fact has no way to know which of two contradicting "
            "numbers is the right one to quote for a given question, and no way to know the two "
            "are even meant to describe different things rather than one being an error."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={"label": label_norm, "unit": unit, "values": [v for v, _, _ in entries]},
    )


# ---------------------------------------------------------------------------
# CQ-08 — Computed-stat integrity
# ---------------------------------------------------------------------------

_LABELED_NUMBER_LIST = re.compile(
    r"^[ \t]*([A-Za-z][A-Za-z0-9 /()\-]{2,40}?):\s*"
    r"((?:-?\d+(?:\.\d+)?)(?:\s*,\s*-?\d+(?:\.\d+)?){2,})\s*$"
)

_AVERAGE_CLAIM = re.compile(
    r"(?i)\b(?:average|avg\.?|mean)\b[^.\n]{0,40}?(-?\d+(?:\.\d+)?)"
    r"|(-?\d+(?:\.\d+)?)[^.\n]{0,40}?\b(?:average|avg\.?|mean)\b"
)

# Any of these near an average claim means it is legitimately not the simple
# mean of every listed number, so no mismatch is asserted.
_SUPPRESSION_WORDS = ("weighted", "excluding", "filtered", "verified only", "adjusted", "normalized", "normalised")
_SUPPRESSION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in _SUPPRESSION_WORDS) + r")\b", re.IGNORECASE
)

# Cycle 24 item 3.4: canonical set, shared/text_spans.py — see that module.
_STOPWORDS = KEYWORD_FOLDING_STOPWORDS


def _keywords(label: str) -> set[str]:
    """Significant words in `label`, plus a crude singular form for each word
    ending in 's' (`ratings` -> also `rating`), so a list labeled "Customer
    ratings" matches a claim sentence saying "average rating" without a real
    stemmer. Cheap and sufficient for this comparison; not used anywhere
    output is shown to a reader."""
    words = {w for w in re.findall(r"[a-z]+", label.lower()) if w not in _STOPWORDS and len(w) > 2}
    singularized = {w[:-1] for w in words if w.endswith("s") and len(w) > 3}
    return words | singularized


def find_computed_stat_mismatches(text: str) -> list[Finding]:
    lists: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _LABELED_NUMBER_LIST.match(line)
        if not match:
            continue
        values = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", match.group(2))]
        lists.append(
            {
                "label": match.group(1).strip(),
                "values": values,
                "mean": sum(values) / len(values),
                "line": line,
            }
        )
    if not lists:
        return []

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for sentence in _split_sentences(text):
        s = sentence.strip()
        if not s:
            continue
        lowered = s.lower()
        if _SUPPRESSION_PATTERN.search(lowered):
            continue
        match = _AVERAGE_CLAIM.search(s)
        if not match:
            continue
        claimed = float(match.group(1) or match.group(2))
        claim_keywords = _keywords(s)

        for entry in lists:
            if not claim_keywords & _keywords(entry["label"]):
                continue
            tolerance = max(0.15, 0.05 * abs(entry["mean"]))
            if abs(entry["mean"] - claimed) <= tolerance:
                continue
            key = (entry["label"], s)
            if key in seen:
                continue
            seen.add(key)
            findings.append(_computed_stat_finding(entry, claimed, s))
    return findings


def _computed_stat_finding(entry: dict, claimed: float, claim_sentence: str) -> Finding:
    values_str = ", ".join(f"{v:g}" for v in entry["values"])
    slug = re.sub(r"[^a-z0-9]+", "-", entry["label"].lower()).strip("-")
    return Finding(
        id=f"CQ-08-computed-stat-{slug}",
        title=f'Stated average for "{entry["label"]}" does not match its own listed numbers',
        severity="high",
        evidence=(
            f'"{entry["label"]}" lists {len(entry["values"])} values ({values_str}), which '
            f'average to {entry["mean"]:.2f}, but the page states: "{claim_sentence}" ({claimed:g}).'
        ),
        suggested_action=SuggestedAction(
            summary=(
                f'Recompute the stated average from the listed "{entry["label"]}" values, or '
                f"correct whichever number is wrong."
            ),
            priority="high",
        ),
        category="discoverability",
        capability_id="CQ-08",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A summary statistic that contradicts the page's own underlying data is a "
            "self-inconsistency an assistant cannot resolve — quoting either number risks "
            "quoting the wrong one, and quoting both reads as the page contradicting itself, "
            "which is exactly what it is doing."
        ),
        gate=3,
        confidence="high",
        structured_evidence={
            "label": entry["label"],
            "values": entry["values"],
            "computed_mean": entry["mean"],
            "claimed": claimed,
        },
    )


# ---------------------------------------------------------------------------
# CQ-11 — Fluency / readability
# ---------------------------------------------------------------------------

_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_VOWEL_GROUPS = re.compile(r"[aeiouy]+", re.IGNORECASE)

# Below this sample size the Flesch formula is too noisy on this project's
# crude sentence splitter (a handful of nav-menu one-word "sentences" can
# swing the average wildly) — the same "short sample is noise, not signal"
# guard CQ-12's rubric already applies by hand for filler density.
_MIN_WORDS_FOR_READABILITY = 300
# Flesch Reading Ease: 0-30 is the standard "very difficult, college
# graduate" band. Deliberately the strictest published band, not merely
# "difficult" (30-50) — the formula's known false-positive class is
# jargon-dense but perfectly clear technical/legal prose (long domain words
# inflate the syllable count without the text actually being harder to
# parse), so this check only fires where the score is extreme enough that a
# genuinely long-sentence, high-syllable pattern is the more likely
# explanation. See references/content-anti-patterns.md for the accepted
# limitation this does not try to fully solve.
_FLESCH_DIFFICULT_THRESHOLD = 30.0


def _count_syllables(word: str) -> int:
    """Vowel-group heuristic, not a dictionary lookup — cheap and stdlib-only,
    sufficient for a page-level average rather than a per-word claim.

    Cycle 24: a trailing "-ed"/"-es" is silent far more often than not
    ("walked" is one syllable, not two; "makes" is one, not two) — the vowel
    group it forms was being counted as a real syllable, overcounting. The
    suffix is stripped before counting unless the stem it would leave ends in
    a sound that genuinely needs it pronounced as its own syllable ("wanted",
    "needed" for -ed; "boxes", "watches" for -es). "-ly" was evaluated too:
    the vowel-group regex already counts its "y" as a syllable correctly in
    the common case ("quickly" -> 2, matching real usage), so it is left
    alone rather than adding an adjustment with no evidence it is needed."""
    letters = re.sub(r"[^a-zA-Z]", "", word).lower()
    if not letters:
        return 0

    stem = letters
    for suffix, keep_if_stem_ends_in in (
        ("ed", ("t", "d")),
        # "g"/"c" here catch the soft-g/soft-c words the raw suffix already
        # ate the "e" off of ("changes" -> stem "chang", "places" -> "plac")
        # — both need "-es" kept as its own syllable exactly like "boxes".
        ("es", ("s", "x", "z", "ch", "sh", "g", "c")),
    ):
        if letters.endswith(suffix) and len(letters) > len(suffix) + 1:
            candidate = letters[: -len(suffix)]
            if not candidate.endswith(keep_if_stem_ends_in):
                stem = candidate
            break

    count = len(_VOWEL_GROUPS.findall(stem)) or len(_VOWEL_GROUPS.findall(letters))
    if stem.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def measure_readability(text: str) -> Finding | None:
    """CQ-11. Deterministic: the Flesch Reading Ease formula applied to the
    page's visible text, `_MIN_WORDS_FOR_READABILITY`-gated so a short
    excerpt cannot produce a noisy score, and thresholded at the strictest
    published band so a page has to be genuinely dense to fire rather than
    merely no longer easy."""
    words = _WORD_PATTERN.findall(text)
    if len(words) < _MIN_WORDS_FOR_READABILITY:
        return None
    sentences = [s.strip() for s in _split_sentences(text) if _WORD_PATTERN.search(s)]
    if not sentences:
        return None

    syllables = sum(_count_syllables(w) for w in words)
    avg_sentence_length = len(words) / len(sentences)
    avg_syllables_per_word = syllables / len(words)
    score = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
    if score >= _FLESCH_DIFFICULT_THRESHOLD:
        return None

    longest = sorted(sentences, key=len, reverse=True)[:3]
    quoted = "; ".join(f'"{s[:200]}{"..." if len(s) > 200 else ""}"' for s in longest)

    return Finding(
        id="CQ-11-low-readability",
        title="Page text scores as very difficult to read (Flesch Reading Ease)",
        severity="low",
        evidence=(
            f"Flesch Reading Ease is {score:.1f} (0-30 = very difficult, college-graduate "
            f"reading level) across {len(words)} words and {len(sentences)} sentences "
            f"(avg {avg_sentence_length:.1f} words/sentence, {avg_syllables_per_word:.2f} "
            f"syllables/word). Longest sentences: {quoted}."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Shorten the longest sentences and prefer plainer wording where the page's "
                "purpose allows it, to lower parse friction for readers and for an assistant "
                "summarising the page."
            ),
            priority="low",
        ),
        category="discoverability",
        capability_id="CQ-11",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "Long, syllable-dense sentences raise the cost of extracting a clean, quotable "
            "claim, and increase the chance an assistant paraphrases or drops a clause when "
            "summarising rather than quoting the page directly."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "flesch_reading_ease": round(score, 1),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_syllables_per_word": round(avg_syllables_per_word, 3),
        },
    )


# ---------------------------------------------------------------------------
# CQ-01 / CQ-02 / CQ-04 / CQ-09 / CQ-12 — extraction only; the agent judges these
# ---------------------------------------------------------------------------

_NON_ANSWER_PHRASES = (
    "it depends", "there is no one-size-fits-all", "there is no one size fits all",
    "everyone's needs are different", "the answer varies", "there is no clear answer",
    "it varies from person to person", "there is no simple answer", "it's complicated",
    "it is complicated", "results may vary", "your mileage may vary",
)
_NON_ANSWER_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _NON_ANSWER_PHRASES) + r")\b", re.IGNORECASE)


def find_non_answer_candidates(text: str) -> list[dict]:
    """CQ-02. A sentence matching a hedge phrase, plus the sentence before it
    (often carries the implied question the hedge is dodging), for the agent
    to judge — the phrase alone does not say whether the topic is genuinely
    variable (a legitimate answer) or the fact was simply omitted."""
    sentences = _split_sentences(text)
    candidates = []
    for index, sentence in enumerate(sentences):
        s = sentence.strip()
        if not (20 <= len(s) <= 400):
            continue
        if not _NON_ANSWER_PATTERN.search(s):
            continue
        preceding = sentences[index - 1].strip() if index > 0 else ""
        candidates.append({"sentence": s, "preceding_sentence": preceding})
    return candidates[:15]


_VAGUE_MAGNITUDE_WORDS = (
    "large", "small", "medium", "significant", "substantial", "compact",
    "lightweight", "heavy-duty", "a lot", "quite a bit", "fairly big", "pretty big",
)
_SPEC_CONTEXT_WORDS = (
    "size", "weight", "weighs", "weigh", "dimensions", "capacity", "length",
    "width", "height", "diameter", "volume", "speed", "storage", "distance",
    "duration", "load", "measures", "measure", "holds", "spans",
)
_VAGUE_MAGNITUDE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _VAGUE_MAGNITUDE_WORDS) + r")\b", re.IGNORECASE
)
_SPEC_CONTEXT_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _SPEC_CONTEXT_WORDS) + r")\b", re.IGNORECASE
)
_HAS_NUMBER = re.compile(r"\d")


def find_granularity_candidates(text: str) -> list[dict]:
    """CQ-04. A sentence naming a spec-shaped attribute (weight, size, ...)
    with a vague magnitude word and no number at all — a candidate for "this
    needed a precise value and didn't get one," which the agent judges
    against whether the attribute plausibly needed precision here."""
    candidates = []
    for sentence in _split_sentences(text):
        s = sentence.strip()
        if not (20 <= len(s) <= 400):
            continue
        if _HAS_NUMBER.search(s):
            continue
        if not (_VAGUE_MAGNITUDE_PATTERN.search(s) and _SPEC_CONTEXT_PATTERN.search(s)):
            continue
        candidates.append({"sentence": s})
    return candidates[:15]


_STEP_MARKER_PATTERN = re.compile(r"^(?:step\s*\d+\b[:.\)]?|\d{1,2}[.\)])\s*\S", re.IGNORECASE)
_MARKETING_PHRASES = (
    "don't miss", "buy now", "sign up today", "award-winning", "best-in-class",
    "industry-leading", "limited time", "act now", "shop now", "join thousands of",
    "you won't regret it", "our customers love", "risk-free", "money-back guarantee",
)
_MARKETING_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _MARKETING_PHRASES) + r")\b", re.IGNORECASE)


def find_procedure_marketing_candidates(text: str) -> list[dict]:
    """CQ-09. A line that looks like a numbered how-to step (`Step 2:`,
    `3.`) and also contains promotional language — a candidate for
    "marketing interleaved into the procedure," which the agent judges
    against whether the promotional aside is brief and skippable or actually
    breaks the instruction's flow."""
    candidates = []
    for line in text.splitlines():
        stripped = line.strip()
        if not _STEP_MARKER_PATTERN.match(stripped):
            continue
        if not _MARKETING_PATTERN.search(stripped):
            continue
        candidates.append({"step_line": stripped})
    return candidates[:15]


_ANSWER_OPENING_WORD_LIMIT = 150


def find_answer_extractability_signal(
    text: str, h1_text: str | None, main_content_text: str | None = None
) -> dict:
    """CQ-01. A page-level signal, not a verdict, same design as CQ-12: the
    page's H1 (if any) and the first ~150 words of its visible text, plus a
    count of how many of CQ-09's own marketing phrases appear in that
    window. Reuses CQ-09's marketing-phrase vocabulary deliberately — same
    skill, same underlying mechanism (promotional language crowding out a
    fact), only the location differs (top-of-page vs. inside a numbered
    step), so a second, near-duplicate phrase list would add nothing.

    **Deliberately document-start, not H1-anchored — tried and reverted.**
    An earlier version of this function windowed from just after the H1's
    own line instead of document start, specifically to skip nav/header
    chrome. Live validation before freeze found it was not just imprecise
    but actively wrong on real sites, in two independent ways: (1)
    `<title>Page Title - Site Name</title>` makes the H1's exact text appear
    earlier as a literal substring on nearly every page, so a naive
    text-search for that string anchors on the title instead of the real
    H1 (fixed once, by walking lines with a tracked offset instead of
    re-searching); (2) even after that fix, en.wikipedia.org's language-
    switcher panel and stripe.com's logo-as-H1 both produced a false or
    wrong anchor — confirmed by fetching and inspecting the raw HTML, not
    guessed. Reliably finding "where the real content starts" is exactly
    the main/article-boundary detection this project's gate 2 (render/
    extraction) does not build (see module docstring and `SKILL.md`
    Excludes) — chasing it further here would mean re-solving that problem
    one DOM shape at a time. The honest, bounded alternative: window from
    document start, keep `h1_text` as its own separate signal, and tell the
    agent explicitly (references/content-judgement-rubric.md §CQ-01) to
    disregard a nav-dominated opening_block rather than judge it as a
    missing answer — the same "say nothing when you cannot tell" discipline
    already used throughout this project's agent-judged capabilities.

    Cycle 24: `main_content_text`, when the caller has it (see
    shared/html_extract.extract_main_content_text — a <main>/<article>
    region with any nested <nav>/<header>/<footer>/<aside> stripped), is
    windowed instead of `text`. This is a different technique from the
    H1-anchoring tried and reverted above — it strips known-chrome elements
    structurally rather than guessing a text offset — so it does not
    reproduce that failure. A page with neither tag falls back to `text`
    unchanged: no regression versus before this parameter existed. Still
    just a better *candidate*; the agent still judges it, exactly as before."""
    source = main_content_text if main_content_text else text
    words = source.split()
    opening_words = words[:_ANSWER_OPENING_WORD_LIMIT]
    opening_block = " ".join(opening_words)
    marketing_hits = [m.group(0) for m in _MARKETING_PATTERN.finditer(opening_block)]
    opening_sentences = [s.strip() for s in _split_sentences(opening_block) if s.strip()]
    return {
        "h1_text": h1_text,
        "opening_block": opening_block,
        "opening_block_source": "main_content" if main_content_text else "document_start",
        "opening_sentence_count": len(opening_sentences),
        "marketing_phrase_hits_in_opening": marketing_hits,
        "total_word_count": len(words),
        "opening_block_truncated": len(words) > _ANSWER_OPENING_WORD_LIMIT,
    }


_FILLER_PHRASES = (
    "in today's fast-paced world", "in today's digital age", "at the end of the day",
    "it goes without saying", "needless to say", "in this day and age",
    "when all is said and done", "in the grand scheme of things", "last but not least",
    "it is important to note that", "it should be noted that", "without further ado",
    "in the world of", "when it comes to", "the fact of the matter is",
)
_FILLER_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _FILLER_PHRASES) + r")\b", re.IGNORECASE)


def measure_filler_density(text: str) -> dict:
    """CQ-12. A page-level count, not per-sentence candidates: how many
    stock filler phrases appear, against the page's total word count. A
    ratio alone cannot say whether the substance underneath is thin — that
    is exactly the judgement the agent makes, using the quoted examples as
    evidence rather than the count alone."""
    word_count = len(text.split())
    matches = [m.group(0) for m in _FILLER_PATTERN.finditer(text)]
    return {
        "filler_phrase_count": len(matches),
        "total_word_count": word_count,
        "filler_phrases_found": matches[:10],
    }


def build_agent_judgement_requests(
    text: str, h1_text: str | None = None, html: str | None = None
) -> list[dict]:
    main_content_text = extract_main_content_text(html) if html else None
    return [
        {
            "capability_id": "CQ-01",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-01. Using h1_text and "
                "opening_block below (and the live page if you have it open), decide whether "
                "a concise 2-4 sentence canonical answer to the page's own implied question "
                "appears near the top, or is missing or buried under "
                "marketing_phrase_hits_in_opening. Hand-author a Finding only when a real, "
                "answerable question plainly has no direct answer in the opening block. Emit "
                "nothing for pages with no single implied question (a navigation hub, a "
                "listing page)."
            ),
            "observations": find_answer_extractability_signal(text, h1_text, main_content_text),
        },
        {
            "capability_id": "CQ-02",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-02. For each candidate below, "
                "decide whether the hedge is standing in for a fact the page could have given "
                "(a non-answer) or is a legitimately variable topic (a real answer). Hand-author "
                "a Finding only for genuine non-answers. If none qualify, emit nothing."
            ),
            "observations": {"candidates": find_non_answer_candidates(text)},
        },
        {
            "capability_id": "CQ-04",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-04. For each candidate below, "
                "decide whether the vague magnitude word needed a precise number here (a "
                "genuine granularity mismatch) or is fine as a qualitative description. Hand-"
                "author a Finding only for genuine mismatches."
            ),
            "observations": {"candidates": find_granularity_candidates(text)},
        },
        {
            "capability_id": "CQ-09",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-09. For each candidate step "
                "line below, decide whether the promotional language actually disrupts the "
                "instruction (a real defect) or is a brief, skippable aside. Hand-author a "
                "Finding only for genuine disruption."
            ),
            "observations": {"candidates": find_procedure_marketing_candidates(text)},
        },
        {
            "capability_id": "CQ-12",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-12. Using the filler-density "
                "observations below and the page's actual content, decide whether substance is "
                "genuinely drowning in stock phrasing. A nonzero filler count alone is not "
                "sufficient — judge against how much real substance surrounds it."
            ),
            "observations": measure_filler_density(text),
        },
    ]


# ---------------------------------------------------------------------------
# Orchestration within the skill
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CQ-10 — Freshness self-contradiction (single-page half, --url mode; B7)
# ---------------------------------------------------------------------------

_CQ10_FRESHNESS_TEXT_PATTERN = re.compile(
    r"\b(?:Last\s+updated|Last\s+modified|Updated|As\s+of)\s*[:\-]?\s*"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
    re.IGNORECASE,
)
_CQ10_JSONLD_DATEMODIFIED_PATTERN = re.compile(r'"dateModified"\s*:\s*"([^"]+)"')
_CQ10_FRESHNESS_MIN_GAP_DAYS = 30
_CQ10_LAST_MODIFIED_TRUST_WINDOW_SECONDS = 3600


def _header(headers: dict[str, str], name: str) -> str | None:
    lname = name.lower()
    for key, value in headers.items():
        if key.lower() == lname:
            return value
    return None


def _parse_claimed_date(value: str):
    value = value.strip().rstrip(",")
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value.replace(",", ""), fmt).date()
        except ValueError:
            continue
    return None


def find_freshness_contradiction(
    text: str, html: str, headers: dict[str, str], *, fetched_at: datetime | None = None
) -> list[Finding]:
    """CQ-10's single-page freshness half (cycle 23 Phase 2, B7). Compares a
    visible "Last updated"/"As of" claim (or a JSON-LD `dateModified`)
    against the HTTP `Last-Modified` response header. A claimed date
    substantially *newer* than what `Last-Modified` supports is a freshness
    claim the transport layer itself contradicts — the page asserts it was
    touched more recently than the server's own header backs up.

    The dominant false positive: a CDN that stamps `Last-Modified` with the
    time it served (or last cached) the response, not the time the content
    actually changed, would make the header always look "just now" and is
    indistinguishable, from a single fetch, from a genuine recent edit. So
    this refuses to fire at all when `Last-Modified` sits within
    `_CQ10_LAST_MODIFIED_TRUST_WINDOW_SECONDS` of the fetch time — the header
    carries no reliable signal in that window either way — and stays capped
    at Medium confidence even when it does fire.
    """
    last_modified_raw = _header(headers, "Last-Modified")
    if not last_modified_raw:
        return []
    try:
        last_modified_dt = email.utils.parsedate_to_datetime(last_modified_raw)
    except (TypeError, ValueError):
        return []
    if last_modified_dt.tzinfo is None:
        last_modified_dt = last_modified_dt.replace(tzinfo=timezone.utc)

    now = fetched_at or datetime.now(timezone.utc)
    if abs((now - last_modified_dt).total_seconds()) < _CQ10_LAST_MODIFIED_TRUST_WINDOW_SECONDS:
        return []

    claimed_raw = None
    text_match = _CQ10_FRESHNESS_TEXT_PATTERN.search(text)
    if text_match:
        claimed_raw = text_match.group(1)
    else:
        jsonld_match = _CQ10_JSONLD_DATEMODIFIED_PATTERN.search(html)
        if jsonld_match:
            claimed_raw = jsonld_match.group(1)
    if not claimed_raw:
        return []

    claimed_date = _parse_claimed_date(claimed_raw)
    if claimed_date is None:
        return []

    gap_days = (claimed_date - last_modified_dt.date()).days
    if gap_days < _CQ10_FRESHNESS_MIN_GAP_DAYS:
        return []

    finding_id = (
        "CQ-10-freshness-contradiction-"
        + hashlib.sha256(f"{claimed_raw}|{last_modified_raw}".encode()).hexdigest()[:8]
    )
    return [
        Finding(
            id=finding_id,
            title="Page's own stated update date is contradicted by the server's Last-Modified header",
            severity="medium",
            evidence=(
                f"The page claims it was last updated {claimed_raw!r}, but the HTTP "
                f"Last-Modified header reports {last_modified_raw!r} — {gap_days} day(s) "
                f"earlier than the page's own claim."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Either make the visible/JSON-LD update date match when the page's "
                    "content actually last changed, or stop bumping it unless the content "
                    "itself changed."
                ),
                priority="medium",
            ),
            category="discoverability",
            capability_id="CQ-10",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An assistant weighing whether to trust a page's currency reads the page's own "
                "stated freshness as a strong signal. When that claim outruns the server's own "
                "record of when the resource changed, the claim is unverifiable at best and "
                "manipulated at worst — citing it as current risks repeating stale information "
                "under a false recency label."
            ),
            gate=3,
            confidence="medium",
            structured_evidence={
                "claimed_date": claimed_raw,
                "last_modified_header": last_modified_raw,
                "gap_days": gap_days,
            },
        )
    ]


def _stamp_page(findings: list[Finding], page_url: str | None) -> list[Finding]:
    """This skill runs once per page (see SKILL.md), so a report with several
    pages audited will carry several findings sharing the exact same
    `check_id` (the same defect class, found on different pages). Without a
    page reference, a reader has no way to tell which page each finding is
    about short of parsing the evidence string. Stamping the URL onto both
    the evidence text and the structured evidence keeps the report actionable
    per the output-design rubric ("a non-expert could act on it") once the
    entrypoint composes findings from more than one page."""
    if not page_url:
        return findings
    stamped = []
    for finding in findings:
        finding.evidence = f"On {page_url}: {finding.evidence}"
        finding.structured_evidence = {**(finding.structured_evidence or {}), "page_url": page_url}
        stamped.append(finding)
    return stamped


def _text_with_labeled_pairs(text: str, html: str | None) -> str:
    """Append synthetic "label: value" lines extracted structurally from
    <th>/<td> and <dt>/<dd> pairs (shared/html_extract.py) to `text`, for
    CQ-07/CQ-08 only. `extract_visible_text()` always puts each table/dl cell
    on its own line by design — the other checks depend on that exact,
    separately-tested behaviour — so real tabular/definition-list markup can
    never satisfy a same-line `Label: value` regex without this. Additive
    only: callers that pass no `html` see no change from before this existed."""
    if not html:
        return text
    pairs = extract_labeled_pairs(html)
    if not pairs:
        return text
    return text + "\n" + "\n".join(pairs)


def audit_text(
    site: str,
    text: str,
    page_url: str | None = None,
    h1_text: str | None = None,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    fetched_at: datetime | None = None,
) -> dict:
    readability_finding = measure_readability(text)
    freshness_findings = (
        find_freshness_contradiction(text, html or "", headers, fetched_at=fetched_at) if headers else []
    )
    labeled_text = _text_with_labeled_pairs(text, html)
    findings = _stamp_page(
        find_template_leakage(text)
        + find_relative_date_anchors(text)
        + find_scope_ambiguous_numbers(labeled_text)
        + find_computed_stat_mismatches(labeled_text)
        + freshness_findings
        + ([readability_finding] if readability_finding else []),
        page_url,
    )
    judgement_requests = build_agent_judgement_requests(text, h1_text, html)
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


def _unknown_output(site: str, reason: str) -> dict:
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [],
        "agent_judgement_required": [],
        "unknown_checks": [UnknownCheck("*", OWNER_SKILL, reason).to_dict()],
    }


# ---------------------------------------------------------------------------
# CQ-13 — Near-duplicate / template dilution (--sample-file mode only)
# ---------------------------------------------------------------------------

_CQ13_MIN_STRATUM_SIZE = 2
_CQ13_CHROME_LINE_MIN_CHARS = 20
_CQ13_SHINGLE_K = 5
_CQ13_JACCARD_THRESHOLD = 0.7
_CQ13_MIN_CONTENT_WORDS = 30


def _strip_chrome_lines(pages_text: dict[str, str]) -> dict[str, str]:
    """Removes lines that repeat, verbatim, across at least half of
    `pages_text` — the site-wide nav/footer/boilerplate every page shares —
    before near-duplicate comparison, so shared chrome alone does not make
    every page in a site look like a near-duplicate of every other.

    A structural (DOM-based) main-content boundary would be more precise,
    but this project has no such layer (gate 2, not built — see the
    module's own "Text extraction" docstring section); cross-page line
    repetition is a stdlib-only proxy that needs none.
    """
    line_page_counts: dict[str, int] = {}
    for text in pages_text.values():
        seen_this_page: set[str] = set()
        for line in text.split("\n"):
            stripped = line.strip()
            if len(stripped) < _CQ13_CHROME_LINE_MIN_CHARS or stripped in seen_this_page:
                continue
            seen_this_page.add(stripped)
            line_page_counts[stripped] = line_page_counts.get(stripped, 0) + 1

    threshold = max(2, (len(pages_text) + 1) // 2)
    chrome_lines = {line for line, count in line_page_counts.items() if count >= threshold}

    return {
        url: "\n".join(line for line in text.split("\n") if line.strip() not in chrome_lines)
        for url, text in pages_text.items()
    }


def _near_duplicate_finding(template_key_value: str, urls: list[str]) -> Finding:
    slug = hashlib.sha256("|".join(sorted(urls)).encode("utf-8")).hexdigest()[:8]
    shown = ", ".join(urls[:4]) + ("…" if len(urls) > 4 else "")
    return Finding(
        id=f"CQ-13-near-duplicate-cluster-{slug}",
        title=f"{len(urls)} pages under template {template_key_value!r} are near-duplicate content",
        severity="medium",
        evidence=(
            f"{len(urls)} pages sharing the {template_key_value!r} URL template ({shown}) score at "
            f"or above {_CQ13_JACCARD_THRESHOLD:.0%} 5-word-shingle Jaccard similarity on their main "
            "content after shared site chrome (nav, footer, boilerplate repeated across the sample) "
            "is stripped — these pages substantively repeat each other rather than offering distinct "
            "content."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Differentiate these pages' actual content, or canonicalize/consolidate them if they "
                "are not meant to compete for distinct queries — a near-duplicate cluster splits "
                "citation authority across near-identical pages instead of concentrating it on one."
            ),
            priority="medium",
        ),
        category="discoverability",
        capability_id="CQ-13",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "An AI assistant selecting a citation source treats near-identical pages as redundant, "
            "not corroborating, signal — a near-duplicate cluster's combined authority stays split "
            "across several URLs instead of concentrating on one, and cluster members compete with "
            "each other for the same query rather than reinforcing a single canonical answer."
        ),
        gate=3,
        confidence="medium",
        structured_evidence={
            "template_key": template_key_value,
            "urls": urls,
            "shingle_k": _CQ13_SHINGLE_K,
            "jaccard_threshold": _CQ13_JACCARD_THRESHOLD,
        },
    )


def find_near_duplicate_clusters(page_texts: dict[str, str]) -> list[Finding]:
    """CQ-13. Groups `page_texts` (page_url -> visible text) into
    same-template strata via `shared/page_sample.template_key`, then flags
    any stratum where 2 or more pages cluster as near-duplicates by
    k-shingle Jaccard similarity on their post-chrome-stripped text.

    Comparing only *within* a stratum — never across templates — is what
    makes the comparison meaningful: a pricing page and a blog post are
    expected to differ, and a low similarity score between them is not
    evidence of anything. A page with fewer than 30 words of remaining
    content after chrome-stripping is excluded from comparison entirely —
    a near-empty stub page trivially "matches" almost anything at the
    shingle level, which would be noise, not a duplicate-content defect.
    """
    strata: dict[str, list[str]] = {}
    for url in page_texts:
        strata.setdefault(template_key(urllib.parse.urlsplit(url).path or "/"), []).append(url)

    stripped = _strip_chrome_lines(page_texts)

    findings: list[Finding] = []
    for key, urls in strata.items():
        if len(urls) < _CQ13_MIN_STRATUM_SIZE:
            continue
        eligible = [u for u in urls if len(stripped[u].split()) >= _CQ13_MIN_CONTENT_WORDS]
        if len(eligible) < 2:
            continue
        texts = [stripped[u] for u in eligible]
        groups = near_duplicate_groups(texts, k=_CQ13_SHINGLE_K, threshold=_CQ13_JACCARD_THRESHOLD)
        for group in groups:
            if len(group) < 2:
                continue
            findings.append(_near_duplicate_finding(key, [eligible[i] for i in group]))
    return findings


# ---------------------------------------------------------------------------
# CQ-10 — Cross-page fact collision; extraction only, agent judges survivors
# (--sample-file mode, shares CQ-13's fetch pass and template strata)
# ---------------------------------------------------------------------------

_CQ10_LABEL_LINE_PATTERN = re.compile(r"^([A-Z][A-Za-z0-9 /&\-]{1,40}):\s*(.+)$")
_CQ10_VALUE_PATTERNS = (
    re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?"),  # price
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO date
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),  # slash date
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),  # month-name date
    re.compile(r"\b(?:19|20)\d{2}\b"),  # bare year
    re.compile(r"\b\d{1,3}(?:,\d{3})+\b"),  # thousands-grouped count
)
_CQ10_MIN_LABEL_PAGES = 3
_CQ10_MAX_CANDIDATES = 8


def _typed_value(value_text: str) -> str | None:
    for pattern in _CQ10_VALUE_PATTERNS:
        match = pattern.search(value_text)
        if match:
            return match.group(0).strip()
    return None


def extract_labeled_facts(text: str) -> dict[str, str]:
    """(normalized label -> typed value) for every "Label: value" line in
    `text` whose value looks like a price, a date, or a thousands-grouped
    count — the shapes a cross-page comparison can safely line up without a
    reading-comprehension pass. Only the last occurrence of a repeated label
    on one page wins (rare, and there is no principled way to prefer one
    occurrence of the same label over another on the same page)."""
    facts: dict[str, str] = {}
    for line in text.split("\n"):
        match = _CQ10_LABEL_LINE_PATTERN.match(line.strip())
        if not match:
            continue
        label, value_text = match.groups()
        typed_value = _typed_value(value_text)
        if typed_value is None:
            continue
        facts[label.strip().lower()] = typed_value
    return facts


def find_fact_collision_candidates(page_texts: dict[str, str]) -> list[dict]:
    """CQ-10. Within same-template strata (comparing a pricing page against
    a blog post proves nothing), groups every "Label: value" fact by
    normalized label across the stratum's pages. A label stated on
    `_CQ10_MIN_LABEL_PAGES`+ pages of the same stratum with more than one
    distinct value is a candidate — never a verdict: same-template pages
    disagreeing on a label is very often correct, expected per-item
    variation (price, SKU, model number differ page to page by design) —
    the dominant false positive this capability's own plan calls out —
    rather than a genuine collision (the same real-world fact stated two
    different ways). The agent judges each candidate against
    `references/content-judgement-rubric.md` §CQ-10."""
    strata: dict[str, list[str]] = {}
    for url in page_texts:
        strata.setdefault(template_key(urllib.parse.urlsplit(url).path or "/"), []).append(url)

    candidates: list[dict] = []
    for key, urls in strata.items():
        label_values: dict[str, dict[str, list[str]]] = {}
        for url in urls:
            for label, value in extract_labeled_facts(page_texts[url]).items():
                label_values.setdefault(label, {}).setdefault(value, []).append(url)

        for label, values_to_pages in label_values.items():
            pages_with_label = sum(len(pages) for pages in values_to_pages.values())
            if pages_with_label < _CQ10_MIN_LABEL_PAGES or len(values_to_pages) < 2:
                continue
            candidates.append(
                {
                    "template_key": key,
                    "label": label,
                    "values": [{"value": v, "pages": pages} for v, pages in values_to_pages.items()],
                }
            )
    return candidates[:_CQ10_MAX_CANDIDATES]


def build_fact_collision_judgement_requests(candidates: list[dict]) -> list[dict]:
    return [
        {
            "capability_id": "CQ-10",
            "instructions": (
                "Read references/content-judgement-rubric.md §CQ-10. For each candidate below, "
                "decide whether the differing values are a genuine fact collision — the SAME "
                "real-world fact (e.g. a founding year, a phone number, a headline count) stated "
                "differently across pages of the same template — or expected, legitimate per-item "
                "variation (price, SKU, model number differing page to page by design, the "
                "dominant false positive here). Hand-author a Finding only for genuine collisions, "
                "quoting the conflicting values and the pages they came from. If none qualify, "
                "emit nothing."
            ),
            "observations": {"candidates": candidates},
        }
    ]


_SAMPLE_FETCH_BUDGET_SECONDS = 90.0
# Pages per concurrent batch — the budget is rechecked between batches, not
# between individual pages, so this bounds how far a batch can overrun the
# cap before the next check (Defect 2 follow-up to INF-10).
_SAMPLE_FETCH_CHUNK_SIZE = 10


def audit_near_duplicates(site: str, page_urls: list[str], *, clock=None) -> dict:
    """CQ-13's and CQ-10's shared multi-page mode — fetches every on-site
    URL in `page_urls` (the orchestrator's own bounded page sample) once and
    runs both capabilities off that fetch pass. CQ-13's near-duplicate
    clustering is entirely script-decided; CQ-10 only narrows candidates
    into `agent_judgement_required` for the calling agent to resolve.

    A separate, once-per-run mode from `audit_text`'s once-per-page mode.

    The fetch loop is concurrent (Defect 2 follow-up to INF-10: sequential
    fetching made the 90s cap likely to fire on perfectly normal sites) —
    `shared/page_fetch.fetch_pages_concurrently` fetches pages in bounded,
    order-preserving batches of `_SAMPLE_FETCH_CHUNK_SIZE`, with
    `shared/budget.StageBudget` (`_SAMPLE_FETCH_BUDGET_SECONDS`) checked
    between batches — a sample of unresponsive pages each burning their own
    fetch timeout could otherwise run well past what one skill invocation
    should cost inside the audit's overall 5-minute budget. The check is
    still cooperative at batch granularity (an in-flight batch is allowed to
    finish rather than aborted mid-flight), a deliberately coarser version
    of the same tradeoff the old per-page check already made. On expiry the
    loop stops fetching further pages — already-fetched pages still get
    findings computed over them, this is reduced coverage, not a failed
    capability — and the remaining, un-fetched pages each get their own
    `unknown_checks` entry naming the cap as the reason. `coverage_manifest`
    is always attached so a reduced-coverage run is visible in the report
    rather than looking identical to a full one that simply found less."""
    clock_kwargs = {"clock": clock} if clock is not None else {}
    budget = StageBudget(f"{OWNER_SKILL}-sample-fetch", _SAMPLE_FETCH_BUDGET_SECONDS, **clock_kwargs)
    unknowns: list[UnknownCheck] = []
    page_texts: dict[str, str] = {}
    index = 0
    while index < len(page_urls):
        if budget.expired():
            for skipped_url in page_urls[index:]:
                unknowns.append(
                    UnknownCheck(
                        "CQ-13",
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
                    UnknownCheck("CQ-13", OWNER_SKILL, f"{page_url} could not be fetched: {html_or_error}")
                )
                continue
            page_texts[page_url] = extract_visible_text(html_or_error)

    findings = find_near_duplicate_clusters(page_texts)
    judgement_requests = build_fact_collision_judgement_requests(find_fact_collision_candidates(page_texts))
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [f.to_dict() for f in findings],
        "agent_judgement_required": judgement_requests,
        "unknown_checks": [u.to_dict() for u in unknowns],
        "coverage": coverage_manifest([budget]),
    }


# ---------------------------------------------------------------------------
# Fetching (--url mode only)
# ---------------------------------------------------------------------------


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
    parser.add_argument("--text-file", help="Read already-extracted plain text from a local file")
    parser.add_argument(
        "--page-url",
        help="Label findings with this page URL (default: --url). Set explicitly in "
        "--html-file/--text-file mode so a report composed from several pages stays "
        "attributable to the right one.",
    )
    parser.add_argument(
        "--sample-file",
        help=(
            "Run CQ-13's near-duplicate/template-dilution check and CQ-10's cross-page "
            "fact-collision check across a local file of on-site page URLs (one per line — the "
            "sample_urls from audit-orchestrator's sample_pages.py) instead of auditing a single "
            "page's text. Fetches each page itself (same as --url). Requires --site."
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
        json.dump(audit_near_duplicates(site, page_urls), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not any((args.url, args.site)):
        parser.error("one of --url or --site is required")
    site = site_label(args.site or args.url)
    page_url = args.page_url or args.url

    h1_text: str | None = None
    html: str | None = None
    headers: dict[str, str] | None = None
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8", errors="replace")
        # No raw HTML in this mode, so no H1 to extract — CQ-01's agent
        # judgement request carries h1_text: null and judges from
        # opening_block alone, same degraded-but-honest shape as any other
        # observation this project has no source for in a given mode.
    elif args.html_file:
        html = Path(args.html_file).read_text(encoding="utf-8", errors="replace")
        text = extract_visible_text(html)
        h1_text = extract_h1(html)
        # A local file has no live HTTP response, so no Last-Modified header
        # to compare against — CQ-10's freshness half simply never fires here.
    elif args.url:
        bundle = fetch_page(args.url)
        if bundle.status != "present" or bundle.html is None:
            json.dump(_unknown_output(site, bundle.error or "fetch failed"), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        html = bundle.html
        headers = bundle.headers
        text = extract_visible_text(html)
        h1_text = extract_h1(html)
    else:
        json.dump(_unknown_output(site, "no --url, --html-file or --text-file given"), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    json.dump(
        audit_text(site, text, page_url=page_url, h1_text=h1_text, html=html, headers=headers),
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
