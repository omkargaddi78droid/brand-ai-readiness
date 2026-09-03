#!/usr/bin/env python3
"""On-site engagement audit: why visitors who arrive don't stay.

Owns six capabilities, split by whether a verdict can be reached
deterministically or needs judgement — the project's standing resolution for
this split (skill-engineering-principles.md §3, §1c): "the host agent is the
LLM." A script only ever hands the agent evidence; it never fabricates a
judgement it cannot support with a rule.

  EN-06  Interstitial & consent-wall friction — SCRIPT DECIDES
  EN-09  Autonomous-agent usability (unlabelled form fields) — SCRIPT DECIDES
  EN-05  Mobile usability (viewport config + fixed-width overflow only;
         narrowed, cycle 21 — see below) — SCRIPT DECIDES
  EN-07  Perceived-performance friction (static proxies: payload weight,
         render-blocking head resources, unsized images; cycle 21) — SCRIPT DECIDES
  EN-01  Visitor orientation — AGENT DECIDES, against references/engagement-judgement-rubric.md
  EN-03  Conversion-path friction — AGENT DECIDES, against the same rubric

EN-06, EN-09, EN-05 and EN-07 are deterministic: a modal with wall language
and no dismiss option, a form field with no accessible name, a missing
viewport tag, an unsized `<img>` — each is objectively present or absent, no
interpretation needed, same evidence-quality bar as every prior detector in
this marketplace.

**EN-05's own scope, narrowed on purpose (cycle 21).** The capability
matrix's fuller description names viewport config, tap-target sizing, font
legibility, and horizontal overflow. Tap-target sizing and font legibility
need resolved CSS layout — actual pixel geometry after the cascade and box
model are applied — which needs either computed rendering (banned by this
project's hard constraints) or a full CSS cascade resolver (a large,
separately risky undertaking with no proven low-FP path). Neither is
attempted. What ships is the two-fifths of the matrix's own description
that are purely static markup facts: a missing/non-responsive
`<meta name="viewport">`, and an inline fixed-pixel width wide enough to
force horizontal scroll on a mobile viewport with no responsive override in
the same style attribute.

**EN-07's own scope, narrowed on purpose (cycle 21).** All three signals are
proxies computed from the fetched HTML document alone — this skill never
fetches linked CSS, JS, or image assets, so "payload weight" means the HTML
document's own byte size, not the full page weight a browser would load.
Stated as a real narrowing, not hidden: a page with a small HTML document
but enormous linked assets is invisible to this check.

Deliberately does NOT own: EN-02 (context retention across a deep link),
EN-04 (dead-end/orphan pages), EN-08 (findability/site search), EN-10
(trust signals), EN-11 (content-to-action coherence). Considered for
cycle 21 alongside EN-05/EN-07 and discarded — see
`docs/capability-matrix.md`'s per-row notes for each. Each needs either
cross-page/crawl-wide context this single-page script does not have, or is
a judgement call with no concrete scriptable signal identified.

Category
--------
Every finding here is `category: "engagement"`, the first skill in this
marketplace to use it — everything before this audited discoverability.
Engagement findings carry `gate: null`: they are not part of the
crawler-reachability gate chain (perimeter -> render -> retrieval); a site
can be perfectly reachable and still lose the visitors who arrive, and vice
versa. They are never suppressed by an upstream discoverability gate failure.

Determinism
-----------
EN-06 and EN-09 are pure functions of the input HTML. EN-01/EN-03's
extraction is also pure; the judgement layered on top of it, by design, is
not run by this script at all.

Safety
------
`--url` mode fetches exactly one page, same SSRF guard as the other
page-level skills in this marketplace. Never submits a form, never traverses
a checkout, inspects markup only.

Usage:
    check_engagement.py --url https://example.com/
    check_engagement.py --site example.com --html-file page.html

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...], "site": ..., "page_url": ...,
     "findings": [...], "agent_judgement_required": [...], "unknown_checks": [...]}
`agent_judgement_required` is intermediate — the SKILL.md procedure resolves
it into `findings` (or drops it, if no defect) before this file is composed
into the final report. It must never reach the entrypoint unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
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

OWNER_SKILL = "engagement-audit"
CAPABILITY_IDS = ["EN-01", "EN-03", "EN-05", "EN-06", "EN-07", "EN-09"]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5_000_000


# ---------------------------------------------------------------------------
# HTML parsing: forms + labels, headline/CTA signals, raw text for windowed checks
# ---------------------------------------------------------------------------

_SKIP_TAGS = {"script", "style", "code", "pre", "noscript", "template", "svg"}
_BLOCK_TAGS = {
    "p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "blockquote", "ul", "ol",
    "table", "td", "th",
}
_LABELABLE_INPUT_TYPES_EXCLUDED = {"hidden", "submit", "button", "reset", "image"}
_CTA_TAGS = {"button", "a"}


class _PageParser(HTMLParser):
    """One pass collects everything EN-06/EN-09 decide on and everything
    EN-01/EN-03 need handed to the agent: form field labeling state, visible
    text, the first heading's text, and candidate call-to-action text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._text_chunks: list[str] = []

        self.fields: list[dict] = []  # {"tag", "type", "labeled", "identifier"}
        self._label_depth = 0
        self._label_for_ids: set[str] = set()
        self._id_text: dict[str, list[str]] = {}
        self._current_ids_open: list[str] = []
        self._pending_fields: list[dict] = []  # fields awaiting aria-labelledby resolution

        self.h1_text: str | None = None
        self._h1_depth = 0
        self._h1_buffer: list[str] = []

        self.cta_texts: list[str] = []
        self._cta_depth = 0
        self._cta_buffer: list[str] = []

        self.form_count = 0
        self._form_depth = 0
        self._current_form_has_password = False
        self.forms_with_password: list[bool] = []  # one bool per form: had a password field

    # -- element-attribute bookkeeping -----------------------------------

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self._open_tag(tag, attr_dict)

    def handle_startendtag(self, tag, attrs):
        attr_dict = dict(attrs)
        self._open_tag(tag, attr_dict)
        self._close_tag(tag)

    def handle_endtag(self, tag):
        self._close_tag(tag)

    def _open_tag(self, tag, attr_dict):
        if tag == "label":
            self._label_depth += 1
            for_id = attr_dict.get("for")
            if for_id:
                self._label_for_ids.add(for_id)
        elif tag == "form":
            self._form_depth += 1
            self.form_count += 1
            self._current_form_has_password = False
        elif tag in ("input", "select", "textarea"):
            field_type = (attr_dict.get("type") or "text").lower() if tag == "input" else tag
            if tag == "input" and field_type == "password":
                self._current_form_has_password = True
            if field_type in _LABELABLE_INPUT_TYPES_EXCLUDED:
                return
            aria_label = (attr_dict.get("aria-label") or "").strip()
            labelled_by = attr_dict.get("aria-labelledby")
            field_id = attr_dict.get("id")
            labeled = bool(aria_label) or bool(self._label_depth) or (
                field_id is not None and field_id in self._label_for_ids
            )
            self._pending_fields.append(
                {
                    "tag": tag,
                    "type": field_type,
                    "id": field_id,
                    "labelled_by": labelled_by,
                    "labeled_so_far": labeled,
                }
            )
        elif tag == "h1" and self.h1_text is None:
            self._h1_depth = 1
            self._h1_buffer = []
        elif self._h1_depth:
            self._h1_depth += 1

        if tag in _CTA_TAGS and not self._cta_depth:
            self._cta_depth = 1
            self._cta_buffer = []
        elif self._cta_depth:
            self._cta_depth += 1

        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

        element_id = attr_dict.get("id")
        if element_id:
            self._current_ids_open.append(element_id)
            self._id_text.setdefault(element_id, [])

    def _close_tag(self, tag):
        if tag == "label" and self._label_depth:
            self._label_depth -= 1
        elif tag == "form" and self._form_depth:
            self._form_depth -= 1
            self.forms_with_password.append(self._current_form_has_password)
        elif tag == "h1" and self._h1_depth:
            self._h1_depth -= 1
            if self._h1_depth == 0 and self.h1_text is None:
                self.h1_text = " ".join("".join(self._h1_buffer).split())
        elif self._h1_depth:
            self._h1_depth -= 1

        if tag in _CTA_TAGS and self._cta_depth:
            self._cta_depth -= 1
            if self._cta_depth == 0:
                text = " ".join("".join(self._cta_buffer).split())
                if text:
                    self.cta_texts.append(text)
        elif self._cta_depth:
            self._cta_depth -= 1

        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._text_chunks.append("\n")

        if self._current_ids_open and tag not in ("input", "select", "textarea", "img", "br", "hr"):
            closed_id = self._current_ids_open.pop() if self._current_ids_open else None
            if closed_id:
                self._resolve_pending_fields_for(closed_id)

    def _resolve_pending_fields_for(self, element_id: str):
        text = " ".join("".join(self._id_text.get(element_id, [])).split())
        if not text:
            return
        for field in self._pending_fields:
            if field["labelled_by"] == element_id:
                field["labeled_so_far"] = True

    def handle_data(self, data):
        normalized = re.sub(r"\s+", " ", data)
        if self._skip_depth == 0:
            self._text_chunks.append(normalized)
        if self._h1_depth:
            self._h1_buffer.append(data)
        if self._cta_depth:
            self._cta_buffer.append(data)
        for element_id in self._current_ids_open:
            self._id_text.setdefault(element_id, []).append(data)

    def finalize(self):
        # `<label for="x">` is legally allowed either before or after its
        # field in document order (a common pattern with checkbox-then-label
        # markup or floating-label CSS). `labeled_so_far` was computed against
        # `_label_for_ids` at the moment the field tag opened, which only
        # contains labels seen *so far* — a label appearing later in the
        # document was invisible to that check. `_label_for_ids` is complete
        # only now, after the whole page has been parsed, so the for-based
        # check is redone here rather than trusted from open-tag time.
        for field in self._pending_fields:
            labeled = field["labeled_so_far"] or (
                field["id"] is not None and field["id"] in self._label_for_ids
            )
            self.fields.append(
                {"tag": field["tag"], "type": field["type"], "id": field["id"], "labeled": labeled}
            )

    def visible_text(self) -> str:
        raw = "".join(self._text_chunks)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return "\n".join(line for line in lines if line)


def parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    parser.finalize()
    return parser


# ---------------------------------------------------------------------------
# EN-09 — Autonomous-agent usability (form field labeling)
# ---------------------------------------------------------------------------


def find_unlabelled_fields(parser: _PageParser) -> list[Finding]:
    unlabelled = [f for f in parser.fields if not f["labeled"]]
    if not unlabelled:
        return []

    total = len(parser.fields)
    by_tag: dict[str, int] = {}
    for field in unlabelled:
        key = field["type"] if field["tag"] == "input" else field["tag"]
        by_tag[key] = by_tag.get(key, 0) + 1
    breakdown = ", ".join(f"{count} {kind}" for kind, count in sorted(by_tag.items()))

    return [
        Finding(
            id="EN-09-unlabelled-form-fields",
            title="Form fields have no accessible name",
            severity="high",
            evidence=(
                f"{len(unlabelled)} of {total} form field(s) have no associated <label>, "
                f"aria-label, or aria-labelledby: {breakdown}."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Add a <label for=\"...\"> (or wrap the field in a <label>) or an "
                    "aria-label naming each field's purpose. A placeholder is not a substitute "
                    "— it disappears once the field has a value and most assistive and "
                    "autonomous-agent tooling does not treat it as the field's name."
                ),
                priority="high",
            ),
            category="engagement",
            capability_id="EN-09",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An unlabelled field has no reliable way to communicate its purpose to "
                "anything that isn't visually reading the page layout — a screen reader, or "
                "an autonomous agent trying to complete a contact or booking form on the "
                "visitor's behalf. Both fail the same way: unable to determine what belongs "
                "in the field, so the action does not get completed."
            ),
            gate=None,
            confidence="high",
            structured_evidence={"unlabelled_count": len(unlabelled), "total_fields": total, "by_type": by_tag},
        )
    ]


# ---------------------------------------------------------------------------
# EN-05 — Mobile usability (viewport config + fixed-width overflow only;
# tap-target sizing and font legibility need resolved CSS layout, not built —
# see module docstring)
# ---------------------------------------------------------------------------

_VIEWPORT_META_PATTERN = re.compile(r'<meta\s+[^>]*name\s*=\s*["\']viewport["\'][^>]*>', re.IGNORECASE)
_VIEWPORT_CONTENT_PATTERN = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)
_DEVICE_WIDTH_PATTERN = re.compile(r'width\s*=\s*device-width', re.IGNORECASE)


def find_missing_viewport(html: str) -> list[Finding]:
    """EN-05, first half. A missing viewport tag leaves a mobile browser to
    render at a desktop-width virtual viewport and scale the whole page down
    — every element on the page becomes too small to read or tap without
    zooming. Present-but-not-`device-width` is a real but lesser variant
    (a fixed pixel width still misrenders on some devices), so the two get
    distinct findings rather than being collapsed into one."""
    match = _VIEWPORT_META_PATTERN.search(html)
    if not match:
        return [
            Finding(
                id="EN-05-missing-viewport",
                title="No viewport meta tag",
                severity="medium",
                evidence="No <meta name=\"viewport\"> element was found anywhere on the page.",
                suggested_action=SuggestedAction(
                    summary='Add <meta name="viewport" content="width=device-width, initial-scale=1"> to the page <head>.',
                    priority="medium",
                ),
                category="engagement",
                capability_id="EN-05",
                owner_skill=OWNER_SKILL,
                mechanism=(
                    "Without a viewport tag, a mobile browser renders at a desktop-width virtual "
                    "viewport and scales the whole page down to fit — every element becomes too "
                    "small to read or tap without the visitor manually zooming in."
                ),
                gate=None,
                confidence="high",
            )
        ]

    content_match = _VIEWPORT_CONTENT_PATTERN.search(match.group(0))
    content = content_match.group(1) if content_match else ""
    if _DEVICE_WIDTH_PATTERN.search(content):
        return []

    return [
        Finding(
            id="EN-05-viewport-not-responsive",
            title="Viewport meta tag does not set width=device-width",
            severity="low",
            evidence=f'A viewport meta tag exists but its content ({content!r}) does not include "width=device-width".',
            suggested_action=SuggestedAction(
                summary='Set the viewport content to "width=device-width, initial-scale=1" rather than a fixed value.',
                priority="low",
            ),
            category="engagement",
            capability_id="EN-05",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A viewport tag with a fixed width (or no width) does not adapt to the visiting "
                "device's actual screen width, which reproduces the same too-small-to-read-or-tap "
                "problem a missing viewport tag causes."
            ),
            gate=None,
            confidence="medium",
            structured_evidence={"viewport_content": content},
        )
    ]


_STYLE_ATTR_PATTERN = re.compile(r'''style\s*=\s*(?:"([^"]*)"|'([^']*)')''', re.IGNORECASE)
_FIXED_WIDTH_PATTERN = re.compile(r'width\s*:\s*(\d+)\s*px', re.IGNORECASE)
_RESPONSIVE_OVERRIDE_PATTERN = re.compile(r'max-width\s*:\s*100%|width\s*:\s*100%', re.IGNORECASE)
_MOBILE_VIEWPORT_WIDTH_PX = 480
_EN05_MAX_EXAMPLES = 5


def find_fixed_width_overflow(html: str) -> list[Finding]:
    """EN-05, second half. An inline `style="width:NNNpx"` wider than a
    typical mobile viewport, with no `max-width:100%`/`width:100%`
    responsive override in the same style attribute, forces horizontal
    scroll on a mobile device regardless of the viewport tag's own state.
    Scoped to inline styles only — a fixed width set in a linked stylesheet
    is invisible to this check (this skill does not fetch linked CSS), a
    stated narrowing, not a silent gap."""
    offenders: list[int] = []
    for match in _STYLE_ATTR_PATTERN.finditer(html):
        style = match.group(1) or match.group(2) or ""
        width_match = _FIXED_WIDTH_PATTERN.search(style)
        if not width_match:
            continue
        if int(width_match.group(1)) <= _MOBILE_VIEWPORT_WIDTH_PX:
            continue
        if _RESPONSIVE_OVERRIDE_PATTERN.search(style):
            continue
        offenders.append(int(width_match.group(1)))

    if not offenders:
        return []

    examples = offenders[:_EN05_MAX_EXAMPLES]
    quoted = ", ".join(f"{w}px" for w in examples)
    more = f" (+{len(offenders) - _EN05_MAX_EXAMPLES} more)" if len(offenders) > _EN05_MAX_EXAMPLES else ""

    return [
        Finding(
            id="EN-05-fixed-width-overflow",
            title="Elements with a fixed pixel width wider than a mobile viewport",
            severity="medium",
            evidence=(
                f"{len(offenders)} element(s) have an inline style setting a fixed width above "
                f"{_MOBILE_VIEWPORT_WIDTH_PX}px with no responsive (max-width:100%/width:100%) "
                f"override in the same style attribute: {quoted}{more}."
            ),
            suggested_action=SuggestedAction(
                summary="Replace the fixed pixel width with a responsive unit (%, max-width:100%, or a media query) so the element fits a mobile viewport.",
                priority="medium",
            ),
            category="engagement",
            capability_id="EN-05",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "An element wider than the mobile viewport forces horizontal scrolling on the "
                "whole page — a visitor on a phone has to scroll sideways to read content that "
                "should simply fit."
            ),
            gate=None,
            confidence="medium",
            structured_evidence={"fixed_widths_px": offenders, "count": len(offenders)},
        )
    ]


# ---------------------------------------------------------------------------
# EN-07 — Perceived-performance friction (static proxies only — see module
# docstring for what "payload weight" means here: HTML document only)
# ---------------------------------------------------------------------------

_HEAD_PATTERN = re.compile(r'<head[^>]*>(.*?)</head>', re.IGNORECASE | re.DOTALL)
_SCRIPT_TAG_PATTERN = re.compile(r'<script\b[^>]*>', re.IGNORECASE)
_LINK_STYLESHEET_PATTERN = re.compile(r'<link\b[^>]*rel\s*=\s*["\']stylesheet["\'][^>]*>', re.IGNORECASE)
_RENDER_BLOCKING_MIN_COUNT = 5


def find_render_blocking_resources(html: str) -> list[Finding]:
    """EN-07, first signal. Counts synchronous (no `async`/`defer`)
    `<script src=...>` tags and `<link rel="stylesheet">` tags inside
    `<head>` — both block the browser's first paint until fetched and
    (for scripts) executed. Scoped to `<head>` only, since a script tag
    placed at the end of `<body>` does not block initial rendering the same
    way. A page with no `<head>`/`</head>` pair at all is skipped rather
    than guessed at, to avoid false positives on malformed-but-rare markup."""
    head_match = _HEAD_PATTERN.search(html)
    if not head_match:
        return []
    head_html = head_match.group(1)

    blocking_scripts = 0
    for tag in _SCRIPT_TAG_PATTERN.findall(head_html):
        lowered = tag.lower()
        if "src=" not in lowered:
            continue
        if "async" in lowered or "defer" in lowered:
            continue
        blocking_scripts += 1

    stylesheets = len(_LINK_STYLESHEET_PATTERN.findall(head_html))
    total = blocking_scripts + stylesheets
    if total < _RENDER_BLOCKING_MIN_COUNT:
        return []

    return [
        Finding(
            id="EN-07-render-blocking-resources",
            title="Many render-blocking resources load before first paint",
            severity="medium",
            evidence=(
                f"{blocking_scripts} synchronous <script src> tag(s) with no async/defer, and "
                f"{stylesheets} <link rel=\"stylesheet\"> tag(s), found inside <head> — "
                f"{total} render-blocking resource(s) total."
            ),
            suggested_action=SuggestedAction(
                summary="Add async/defer to non-critical <script> tags, and inline or defer non-critical stylesheets.",
                priority="medium",
            ),
            category="engagement",
            capability_id="EN-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A browser must fetch (and, for scripts, execute) every render-blocking resource "
                "in <head> before it paints anything — a visitor sees a blank page for longer the "
                "more of these accumulate."
            ),
            gate=None,
            confidence="medium",
            structured_evidence={"blocking_script_count": blocking_scripts, "stylesheet_count": stylesheets, "total": total},
        )
    ]


_IMG_TAG_PATTERN = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
_WIDTH_ATTR_PATTERN = re.compile(r'\bwidth\s*=\s*["\']?\d', re.IGNORECASE)
_HEIGHT_ATTR_PATTERN = re.compile(r'\bheight\s*=\s*["\']?\d', re.IGNORECASE)
_ASPECT_RATIO_STYLE_PATTERN = re.compile(r'aspect-ratio\s*:', re.IGNORECASE)
_UNSIZED_IMAGE_MIN_COUNT = 3


def find_unsized_images(html: str) -> list[Finding]:
    """EN-07, second signal. An <img> with neither `width`/`height`
    attributes nor an inline `aspect-ratio` gives the browser no space to
    reserve before the image loads — the classic layout-shift cause. A
    small number of unsized images (an icon, a one-off decorative image) is
    common and not worth flagging; only a non-trivial count is."""
    total = 0
    unsized = 0
    for tag in _IMG_TAG_PATTERN.findall(html):
        total += 1
        has_size = bool(_WIDTH_ATTR_PATTERN.search(tag) and _HEIGHT_ATTR_PATTERN.search(tag))
        has_aspect_ratio = bool(_ASPECT_RATIO_STYLE_PATTERN.search(tag))
        if not has_size and not has_aspect_ratio:
            unsized += 1

    if unsized < _UNSIZED_IMAGE_MIN_COUNT:
        return []

    return [
        Finding(
            id="EN-07-unsized-images",
            title="Multiple images have no reserved size, risking layout shift",
            severity="low",
            evidence=(
                f"{unsized} of {total} <img> element(s) have neither width/height attributes nor "
                f"an inline aspect-ratio — the browser has no space reserved for them before they load."
            ),
            suggested_action=SuggestedAction(
                summary="Add width and height attributes (or CSS aspect-ratio) to <img> elements so the browser reserves their space before loading.",
                priority="low",
            ),
            category="engagement",
            capability_id="EN-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "When an image loads without a reserved size, the surrounding layout shifts once "
                "it arrives — content a visitor was about to read or tap jumps out from under them."
            ),
            gate=None,
            confidence="medium",
            structured_evidence={"unsized_count": unsized, "total_images": total},
        )
    ]


_HEAVY_HTML_PAYLOAD_BYTES = 300_000


def find_payload_weight(html: str) -> list[Finding]:
    """EN-07, third signal. The fetched HTML document's own UTF-8 byte
    size — not the full page weight a browser would load, since this skill
    never fetches linked CSS/JS/image assets. A stated, real narrowing: a
    page with a small HTML document but enormous linked assets is invisible
    to this specific check."""
    byte_count = len(html.encode("utf-8"))
    if byte_count < _HEAVY_HTML_PAYLOAD_BYTES:
        return []

    return [
        Finding(
            id="EN-07-heavy-html-payload",
            title="The HTML document itself is unusually large",
            severity="low",
            evidence=(
                f"This page's HTML document is {byte_count:,} bytes — over the "
                f"{_HEAVY_HTML_PAYLOAD_BYTES:,}-byte threshold this check treats as heavy for HTML "
                f"alone (not counting linked CSS, JS, or image assets, which this skill does not fetch)."
            ),
            suggested_action=SuggestedAction(
                summary="Reduce inline scripts/styles or excessive markup duplication in the HTML document itself.",
                priority="low",
            ),
            category="engagement",
            capability_id="EN-07",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A large HTML document delays the browser from finishing the initial parse before "
                "it can even begin fetching the resources referenced inside it, adding to time to "
                "first paint on top of whatever those linked assets themselves cost."
            ),
            gate=None,
            confidence="low",
            structured_evidence={"byte_count": byte_count},
        )
    ]


# ---------------------------------------------------------------------------
# EN-06 — Interstitial & consent-wall friction
# ---------------------------------------------------------------------------

_MODAL_SIGNAL = re.compile(
    r'role\s*=\s*["\']dialog["\']'
    r'|aria-modal\s*=\s*["\']true["\']'
    r'|(?:class|id)\s*=\s*["\'][^"\']*(?:modal|overlay|popup|interstitial|'
    r'consent-wall|cookie-wall|gdpr|newsletter-popup|subscribe-modal)[^"\']*["\']',
    re.IGNORECASE,
)

_WALL_PHRASES = (
    "accept all cookies", "accept cookies", "we use cookies", "this site uses cookies",
    "subscribe to continue", "sign up to continue", "sign in to continue",
    "create an account to continue", "log in to continue", "enable cookies to continue",
    "subscribe to read", "subscribe to view", "register to continue",
)
_DISMISS_PHRASES = (
    "reject", "decline", "no thanks", "not now", "maybe later", "close",
    "manage preferences", "necessary only", "continue without accepting",
    "reject all", "deny", "opt out", "skip",
)
_WALL_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _WALL_PHRASES) + r")\b", re.IGNORECASE)
_DISMISS_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _DISMISS_PHRASES) + r")\b", re.IGNORECASE)

_WINDOW_CHARS = 2000
_DEDUP_DISTANCE = 1000


def find_interstitial_walls(html: str) -> list[Finding]:
    """Windowed heuristic, not true DOM scoping: for each modal-like signal
    found in the raw HTML, tags are stripped from the next `_WINDOW_CHARS`
    characters and checked for wall language with no nearby dismiss option.
    A deliberate simplification — see references/engagement-checks.md — that
    trades some precision on very large modal blocks for not needing full
    element-boundary tracking, which the false-positive risk here does not
    justify building."""
    findings: list[Finding] = []
    flagged_positions: list[int] = []

    for match in _MODAL_SIGNAL.finditer(html):
        position = match.start()
        if any(abs(position - flagged) < _DEDUP_DISTANCE for flagged in flagged_positions):
            continue

        window = html[position : position + _WINDOW_CHARS]
        window_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", window)).strip()

        wall_match = _WALL_PATTERN.search(window_text)
        if not wall_match:
            continue
        if _DISMISS_PATTERN.search(window_text):
            continue

        flagged_positions.append(position)
        findings.append(_interstitial_wall_finding(wall_match.group(0), window_text))

    return findings


def _stable_slug(text: str) -> str:
    """Python's built-in hash() is randomised per process (PYTHONHASHSEED),
    which would make the same page produce different finding ids on
    different runs — a direct violation of "same site audited twice -> same
    report". sha256 is deterministic across runs and processes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def _interstitial_wall_finding(matched_phrase: str, window_text: str) -> Finding:
    quote = window_text[:220]
    return Finding(
        id=f"EN-06-interstitial-wall-{_stable_slug(quote)}",
        title="A consent/subscription overlay blocks content with no visible way to dismiss it",
        severity="high",
        evidence=(
            f'An overlay containing "{matched_phrase}" was found with no nearby reject, '
            f'decline, close or "not now" option: "{quote}..."'
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Add a clearly visible reject/decline/close control to the overlay, or make it "
                "dismissible without requiring the visitor to accept, subscribe or sign in."
            ),
            priority="high",
        ),
        category="engagement",
        capability_id="EN-06",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "An overlay with no opt-out is a dead end for a visitor who does not want to "
            "accept, subscribe, or sign in — they cannot reach the content that brought them "
            "to the page at all. This is a human-engagement problem regardless of whether the "
            "underlying content is present in the HTML: a visitor who cannot get past the wall "
            "never reads it either way."
        ),
        gate=None,
        confidence="medium",
        structured_evidence={"matched_phrase": matched_phrase, "window_excerpt": quote},
    )


# ---------------------------------------------------------------------------
# EN-01 / EN-03 — extraction only; the agent judges these
# ---------------------------------------------------------------------------


def extract_orientation_signals(parser: _PageParser, visible_text: str) -> dict:
    words = visible_text.split()
    first_150 = " ".join(words[:150])
    cta_before_150 = [c for c in parser.cta_texts[:5]]
    return {
        "h1_text": parser.h1_text,
        "first_150_words": first_150,
        "total_word_count": len(words),
        "candidate_cta_texts": cta_before_150,
    }


def extract_conversion_path_signals(parser: _PageParser, visible_text: str) -> dict:
    lowered = visible_text.lower()
    guest_checkout_mentioned = bool(
        re.search(r"\bguest\s+(?:checkout|order)\b|\bcontinue\s+as\s+a?\s*guest\b", lowered)
    )
    fee_disclosure_hits = re.findall(
        r"[^.\n]{0,60}\b(?:shipping|tax(?:es)?|fees?)\b[^.\n]{0,60}", lowered
    )
    return {
        "form_count": parser.form_count,
        "forms_with_password_field": sum(1 for has_pw in parser.forms_with_password if has_pw),
        "guest_checkout_language_present": guest_checkout_mentioned,
        "fee_or_tax_disclosure_snippets": fee_disclosure_hits[:5],
        "total_word_count": len(visible_text.split()),
    }


def build_agent_judgement_requests(parser: _PageParser, visible_text: str) -> list[dict]:
    return [
        {
            "capability_id": "EN-01",
            "instructions": (
                "Read references/engagement-judgement-rubric.md §EN-01. Using h1_text and "
                "first_150_words below (and the live page if you have it open), decide whether "
                "a first-time visitor can tell within seconds what this is, who it is for, and "
                "what to do next. If not, hand-author a Finding per the rubric's schema and "
                "append it to this file's findings array. If the page plainly orients the "
                "visitor, or is not a landing/orientation page (e.g. a deep utility page), "
                "emit nothing for EN-01."
            ),
            "observations": extract_orientation_signals(parser, visible_text),
        },
        {
            "capability_id": "EN-03",
            "instructions": (
                "Read references/engagement-judgement-rubric.md §EN-03. Using the observations "
                "below, decide whether the page shows signs of needlessly high conversion "
                "friction (forced account creation with no guest option, undisclosed fees). "
                "Note: true step-count-to-conversion needs navigating the actual flow, which "
                "this single-page audit cannot do — only flag what these observations "
                "actually support, and say so if the page is not a conversion page at all."
            ),
            "observations": extract_conversion_path_signals(parser, visible_text),
        },
    ]


# ---------------------------------------------------------------------------
# Orchestration within the skill
# ---------------------------------------------------------------------------


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    parser = parse_page(html)
    visible_text = parser.visible_text()

    findings = (
        find_unlabelled_fields(parser)
        + find_interstitial_walls(html)
        + find_missing_viewport(html)
        + find_fixed_width_overflow(html)
        + find_render_blocking_resources(html)
        + find_unsized_images(html)
        + find_payload_weight(html)
    )
    findings = _stamp_page(findings, page_url)

    judgement_requests = build_agent_judgement_requests(parser, visible_text)
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
    """Undo Content-Encoding before the body is treated as text.

    `urllib.request` never auto-decompresses (unlike `requests`), and some
    CDNs gzip responses regardless of whether the client's Accept-Encoding
    advertised support for it — observed live against python.org: raw gzip
    bytes were decoded as UTF-8 text, producing binary garbage in every
    extracted-text field, and every detector kept running against it rather
    than failing loudly, because nothing checked for this.

    Bounded to guard against a decompression-bomb response: this reads from
    the audited site, which is trusted to be a legitimate target but not to
    be well-behaved.
    """
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


def main(argv: list[str] | None = None) -> int:
    parser_ = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser_.add_argument("--url", help="A single page URL to fetch and audit")
    parser_.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser_.add_argument("--html-file", help="Read page HTML from a local file instead of fetching")
    parser_.add_argument("--page-url", help="Label findings with this page URL (default: --url)")
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

    json.dump(audit_html(site, html, page_url=page_url), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
