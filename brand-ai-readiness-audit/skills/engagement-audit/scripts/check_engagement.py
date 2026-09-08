#!/usr/bin/env python3
"""On-site engagement audit: why visitors who arrive don't stay.

Owns eight capabilities, split by whether a verdict can be reached
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
  EN-04  Dead-end/orphan pages (cycle 23, B1+B8, `--sample-file` mode) — SCRIPT DECIDES
  EN-01  Visitor orientation — AGENT DECIDES, against references/engagement-judgement-rubric.md
  EN-03  Conversion-path friction — AGENT DECIDES, against the same rubric
  EN-11  Content-to-action coherence (cycle 23, C1, `--sample-file` mode) — AGENT DECIDES
  EN-08  Findability, link-scent slice (cycle 23, C1, `--sample-file` mode) — AGENT DECIDES

EN-06, EN-09, EN-05, EN-07 and EN-04 are deterministic: a modal with wall
language and no dismiss option, a form field with no accessible name, a
missing viewport tag, an unsized `<img>`, a page with zero internal links
and no CTA — each is objectively present or absent, no interpretation
needed, same evidence-quality bar as every prior detector in this
marketplace. EN-04's orphan-within-sample half is capped at Medium severity
and states its own sample size in its evidence — see the B1+B8 section
below for why.

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
EN-10 (trust signals) — no concrete scriptable signal identified. EN-08's
site-search/navigation-depth half also stays out of scope: only the
link-information-scent slice ships (see C1 below); the rest still needs
crawl-wide context this project does not have.

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
import json
import re
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding, SuggestedAction, UnknownCheck  # noqa: E402
from jsonld_graph import flatten  # noqa: E402
from text_spans import VISIBLE_TEXT_BLOCK_TAGS, VISIBLE_TEXT_SKIP_TAGS  # noqa: E402
from page_fetch import (  # noqa: E402
    USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    MAX_PAGE_BYTES,
    decode_content_encoding,
    is_public_host,
    fetch_page_html,
    fetch_pages_concurrently,
)
from links import LinkRef, extract_links, is_internal_link  # noqa: E402
from fuzzy_match import token_sort_ratio  # noqa: E402
from budget import StageBudget, coverage_manifest  # noqa: E402

OWNER_SKILL = "engagement-audit"
CAPABILITY_IDS = ["EN-01", "EN-03", "EN-05", "EN-06", "EN-07", "EN-08", "EN-09", "EN-11"]


# ---------------------------------------------------------------------------
# HTML parsing: forms + labels, headline/CTA signals, raw text for windowed checks
# ---------------------------------------------------------------------------

# Cycle 24 item 2.5: canonical set, shared/text_spans.py — see that module.
_SKIP_TAGS = VISIBLE_TEXT_SKIP_TAGS
_BLOCK_TAGS = VISIBLE_TEXT_BLOCK_TAGS
_LABELABLE_INPUT_TYPES_EXCLUDED = {"hidden", "submit", "button", "reset", "image"}
_CTA_TAGS = {"button", "a"}
_WEBMCP_FORM_ATTRS = ("toolname", "data-toolname")
_WEBMCP_SCRIPT_PATTERN = re.compile(r"navigator\.modelContext\.registerTool", re.IGNORECASE)


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
        self.has_webmcp_form_attribute = False

        # EN-09's machine-readable-action extension (cycle 23, Phase 2):
        # JSON-LD blocks for schema.org potentialAction detection, and raw
        # inline (no `src`) <script> text for a static WebMCP signature
        # scan. Never fetches an external .js file — same narrowing this
        # skill already applies to CSS/JS/image assets for EN-07.
        self.json_ld_blocks: list[str] = []
        self._in_json_ld = False
        self._json_ld_buffer: list[str] = []
        self._in_inline_script = False
        self._inline_script_buffer: list[str] = []
        self.inline_script_text = ""

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
        if tag == "script":
            script_type = (attr_dict.get("type") or "").strip().lower()
            if script_type == "application/ld+json":
                self._in_json_ld = True
                self._json_ld_buffer = []
            elif "src" not in attr_dict:
                # Only a truly inline script has text this parser will ever
                # see — an external .js file is never fetched (same
                # narrowing this skill already applies for EN-07).
                self._in_inline_script = True
                self._inline_script_buffer = []
        if tag == "label":
            self._label_depth += 1
            for_id = attr_dict.get("for")
            if for_id:
                self._label_for_ids.add(for_id)
        elif tag == "form":
            self._form_depth += 1
            self.form_count += 1
            self._current_form_has_password = False
            if any(key in attr_dict for key in _WEBMCP_FORM_ATTRS):
                self.has_webmcp_form_attribute = True
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
        if tag == "script":
            if self._in_json_ld:
                self.json_ld_blocks.append("".join(self._json_ld_buffer))
                self._in_json_ld = False
            elif self._in_inline_script:
                self.inline_script_text += "".join(self._inline_script_buffer)
                self._in_inline_script = False
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
        if self._in_json_ld:
            self._json_ld_buffer.append(data)
            return
        if self._in_inline_script:
            self._inline_script_buffer.append(data)
            return
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
# EN-09 (extension, cycle 23 Phase 2) — machine-readable action availability
#
# Two independent signals a page can carry to describe what its forms do to
# something other than a human reading labels: schema.org's established
# `potentialAction` (JSON-LD), and the emerging, still-draft WebMCP
# convention (`navigator.modelContext.registerTool`, or a declarative
# `toolname`/`data-toolname` form attribute). This does not attempt to
# match a specific form to a specific potentialAction target — resolving a
# form's `action` URL against a potentialAction's `target`/`urlTemplate`
# (relative vs. absolute, query strings, EntryPoint indirection) is a real
# source of false suppression or false firing that this project's
# calibration discipline does not accept without much stronger evidence
# than a plain string comparison would give. Instead: page-level — if the
# page has any non-trivial form (2+ labelable fields, so a lone
# search/newsletter box doesn't count) and *no* machine-readable action
# signal anywhere on the page at all, suggest adding one. Reported as a
# proactive suggestion only, never a defect: near-zero adoption today for
# either convention, the same posture this skill already takes for llms.txt
# and `.md` negotiation in the sibling perimeter skill.
# ---------------------------------------------------------------------------

_EN09_MIN_NON_TRIVIAL_FIELDS = 2


def find_missing_machine_readable_action(parser: _PageParser) -> list[Finding]:
    if parser.form_count == 0 or len(parser.fields) < _EN09_MIN_NON_TRIVIAL_FIELDS:
        return []

    json_ld_nodes = flatten(parser.json_ld_blocks)
    has_potential_action = any(node.get("potentialAction") for node in json_ld_nodes)
    has_webmcp_script = bool(_WEBMCP_SCRIPT_PATTERN.search(parser.inline_script_text))
    has_webmcp_form_attr = parser.has_webmcp_form_attribute
    if has_potential_action or has_webmcp_script or has_webmcp_form_attr:
        return []

    return [
        Finding(
            id="EN-09-no-machine-readable-action",
            title="Interactive forms exist with no machine-readable description of what they do",
            severity="low",
            evidence=(
                f"This page has {parser.form_count} form(s) with {len(parser.fields)} labelable "
                "field(s) total, but no schema.org potentialAction in its JSON-LD and no WebMCP "
                "declaration (navigator.modelContext.registerTool, or a toolname/data-toolname "
                "form attribute)."
            ),
            suggested_action=SuggestedAction(
                summary=(
                    "Consider adding a schema.org potentialAction (ReserveAction/OrderAction/"
                    "SearchAction, as appropriate) describing what a form on this page does, or "
                    "declaring it via the emerging WebMCP convention "
                    "(navigator.modelContext.registerTool)."
                ),
                priority="low",
                details=(
                    "A forward-compatibility suggestion, not a defect — near-zero adoption today "
                    "for either convention. An autonomous agent completing this form still has to "
                    "infer its purpose from labels and layout alone."
                ),
            ),
            category="engagement",
            capability_id="EN-09",
            owner_skill=OWNER_SKILL,
            mechanism=(
                "A machine-readable action description lets an autonomous agent understand what a "
                "form does and how to invoke it correctly, without inferring intent from visual "
                "layout or label wording alone — the same underlying problem this capability's "
                "other half (unlabelled fields) addresses at the level of one field, this "
                "addresses at the level of the action as a whole."
            ),
            gate=None,
            confidence="medium",
            track="proactive",
            structured_evidence={
                "form_count": parser.form_count,
                "field_count": len(parser.fields),
            },
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
# C1 — Information-scent link/CTA coherence (--sample-file mode only)
# ---------------------------------------------------------------------------
#
# Grounds EN-11 (content-to-action coherence) and the EN-08 findability
# slice in Information Foraging Theory (Pirolli & Card 1999, Psychological
# Review 106:643-675): a visitor follows the cue (a CTA's own wording, or a
# link's anchor text) that promises the best "scent" of what they want; a
# cue with low lexical overlap to what it actually leads to is a weak-scent
# defect, whether the cue and its destination are the same page (EN-11's
# own CTA vs. that page's H1) or two different pages (EN-08's anchor text
# vs. the target page's H1). Both need the bounded page sample, so both
# live in this one --sample-file mode rather than --url mode.
#
# Script narrows candidates only — a low lexical-overlap score is common
# and NOT always a defect (a "Get Started" CTA is legitimate brand voice on
# almost any SaaS page; "Home" linking to a welcome-copy H1 is not weak
# scent, it's a nav landmark). Every candidate below still needs the
# agent's judgement against references/engagement-judgement-rubric.md
# §EN-11/§EN-08, the same agent_judgement_required pattern EN-01/EN-03 use.

_INFO_SCENT_LOW_OVERLAP_THRESHOLD = 35.0
_INFO_SCENT_MAX_CANDIDATES = 8

# Anchor text this common is site-wide navigational chrome, not a
# content-shaped cue — comparing it to a target's H1 is the dominant false
# positive this check must not produce (e.g. a "Home" link to a welcome
# page, or a "Contact" link whose target H1 is "Get in touch").
_NAV_CHROME_ANCHOR_TEXTS = frozenset({
    "home", "about", "about us", "contact", "contact us", "login", "log in",
    "sign in", "sign up", "register", "cart", "shop", "search", "menu",
    "blog", "careers", "privacy policy", "terms", "terms of service",
    "terms & conditions", "faq", "help", "support", "back", "next",
    "previous", "read more", "learn more", "more", "here", "click here",
})


def _primary_cta(parser: _PageParser) -> str | None:
    """The page's first call-to-action text in document order — the
    hero/primary action a real visitor sees first. Later CTAs (footer
    links, secondary buttons) are out of scope: EN-11 is about the one
    action a page foregrounds, not every clickable element on it."""
    return parser.cta_texts[0] if parser.cta_texts else None


def _cta_coherence_candidate(page_url: str, h1_text: str, primary_cta: str) -> dict | None:
    score = token_sort_ratio(primary_cta, h1_text)
    if score >= _INFO_SCENT_LOW_OVERLAP_THRESHOLD:
        return None
    return {
        "page_url": page_url,
        "h1_text": h1_text,
        "primary_cta_text": primary_cta,
        "lexical_overlap_score": round(score, 1),
    }


def _link_scent_candidates(
    page_h1: dict[str, str], internal_links: dict[str, list[LinkRef]]
) -> list[dict]:
    """One candidate per (source, target) internal link whose anchor text
    scores below threshold against the target page's own H1. Only a link
    whose target is itself in the sampled set is considered — a target
    outside the sample has no known H1 to score against. Capped and sorted
    lowest-score-first so a page with many weak links doesn't flood the
    agent with redundant candidates."""
    candidates = []
    for source_url, links in internal_links.items():
        for link in links:
            target_h1 = page_h1.get(link.url)
            if not target_h1 or not link.anchor_text:
                continue
            score = token_sort_ratio(link.anchor_text, target_h1)
            if score < _INFO_SCENT_LOW_OVERLAP_THRESHOLD:
                candidates.append({
                    "source_page_url": source_url,
                    "target_page_url": link.url,
                    "anchor_text": link.anchor_text,
                    "target_h1_text": target_h1,
                    "lexical_overlap_score": round(score, 1),
                })
    candidates.sort(key=lambda c: c["lexical_overlap_score"])
    return candidates[:_INFO_SCENT_MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# B1 + B8 — Dead-end and orphan pages (--sample-file mode only)
# ---------------------------------------------------------------------------
#
# EN-04's two sub-questions get different evidentiary treatment on purpose
# (docs/02-project-plan.md Phase 4, adopting the minority objection's
# discipline while still shipping the majority view):
#
# B8a (dead end) is a direct fact about the fetched page itself — zero
# internal outbound links AND no call-to-action — and can be stated plainly
# at ordinary confidence, no sample-scope caveat needed.
#
# B1 (orphan-within-sample) is a structurally biased estimate: a page with
# zero inbound internal links *among the pages sampled* is not proven to be
# a site-wide orphan — pages reachable only via pagination, deep facets, or
# a nav menu this sampler's template-stratified pass never selected are
# structurally invisible to this check, and that exclusion correlates with
# the very starvation being measured. Every such finding is capped at
# Medium severity and states its own sample size in its evidence string, so
# it can never be misread as a site-wide claim.

_HOMEPAGE_PATHS = ("", "/")


def _is_homepage(url: str) -> bool:
    """The sample's entry point is expected to have few or no *inbound*
    internal links — visitors and search engines arrive at it from outside
    the site, not by following an internal link — so it is excluded from
    the orphan check entirely rather than flagged as a false positive."""
    return urllib.parse.urlparse(url).path in _HOMEPAGE_PATHS


def _dead_end_finding(page_url: str) -> Finding:
    slug = _stable_slug(page_url)
    return Finding(
        id=f"EN-04-dead-end-{slug}",
        title="Page offers no next action",
        severity="medium",
        evidence=(
            f"{page_url} has no internal outbound link and no call-to-action element — a visitor "
            "(or an autonomous agent following links) who lands here has nowhere to go next on "
            "this site."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Add at least one relevant internal link or call-to-action to this page so "
                "visitors and crawling agents have a next step from it."
            ),
            priority="medium",
        ),
        category="engagement",
        capability_id="EN-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A page with zero internal links and no CTA is a structural dead end: neither a "
            "human visitor nor a crawling agent has any path onward from it, isolating whatever "
            "value the page has from the rest of the site."
        ),
        gate=None,
        confidence="high",
        structured_evidence={"page_url": page_url},
    )


def find_dead_end_pages(
    raw_internal_links: dict[str, list[LinkRef]], page_cta: dict[str, str]
) -> list[Finding]:
    """B8a: a sampled page with zero internal outbound links and no primary
    CTA at all. Stated plainly — this is a direct fact about the fetched
    page's own markup, not an estimate over the bounded sample."""
    return [
        _dead_end_finding(page_url)
        for page_url, links in raw_internal_links.items()
        if not links and page_url not in page_cta
    ]


def _orphan_finding(page_url: str, sample_size: int) -> Finding:
    slug = _stable_slug(page_url)
    return Finding(
        id=f"EN-04-orphan-in-sample-{slug}",
        title="No internal link to this page found within the sampled pages",
        severity="medium",
        evidence=(
            f"Within the {sample_size} pages sampled for this audit, no internal link pointed to "
            f"{page_url} — this does not prove site-wide orphan status, only that no link path to "
            "it was found within the sampled subset."
        ),
        suggested_action=SuggestedAction(
            summary=(
                "Add an internal link to this page from elsewhere on the site (navigation, a "
                "related-content section, or a sitemap) so both visitors and crawlers can reach "
                "it by following links, not only by a direct URL."
            ),
            priority="medium",
        ),
        category="engagement",
        capability_id="EN-04",
        owner_skill=OWNER_SKILL,
        mechanism=(
            "A page reachable only by a direct URL — never via an internal link from the pages "
            "this audit sampled — is invisible to link-following crawlers and to visitors "
            "browsing rather than typing a known address, starving it of whatever internal link "
            "authority the rest of the site could pass to it. A bounded sample cannot rule out an "
            "inbound link from a page outside it, which is exactly why this is capped at Medium "
            "severity and states its own sample size rather than claiming site-wide scope."
        ),
        gate=None,
        confidence="medium",
        structured_evidence={"page_url": page_url, "sample_size": sample_size},
    )


def find_orphan_pages(raw_internal_links: dict[str, list[LinkRef]]) -> list[Finding]:
    """B1: a sampled page (other than the homepage) with zero inbound
    internal links from any other page in the same sample."""
    sample_size = len(raw_internal_links)
    in_degree = {page_url: 0 for page_url in raw_internal_links}
    for links in raw_internal_links.values():
        for link in links:
            if link.url in in_degree:
                in_degree[link.url] += 1
    return [
        _orphan_finding(page_url, sample_size)
        for page_url, count in in_degree.items()
        if count == 0 and not _is_homepage(page_url)
    ]


_SAMPLE_FETCH_BUDGET_SECONDS = 90.0
# Pages per concurrent batch — the budget is rechecked between batches, not
# between individual pages, so this bounds how far a batch can overrun the
# cap before the next check (Defect 2 follow-up to INF-10).
_SAMPLE_FETCH_CHUNK_SIZE = 10


def _gather_sample_pages(
    site: str, page_urls: list[str], *, clock=None
) -> tuple[
    dict[str, str], dict[str, str], dict[str, list[LinkRef]], dict[str, list[LinkRef]], list[UnknownCheck], StageBudget
]:
    """One fetch pass over `page_urls`, shared by C1 (EN-08/EN-11) and B1+B8
    (EN-04) so the sample is only ever fetched once per script invocation.
    Returns (page_h1, page_cta, raw_internal_links, scent_internal_links,
    unknowns, budget) — `raw_internal_links` keeps every internal link
    (EN-04's dead-end/orphan checks need to know a link exists at all,
    including a plain "Home" link); `scent_internal_links` drops
    navigational chrome (EN-08's information-scent check needs only
    content-shaped links).

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
    of the same tradeoff the old per-page check already made. On expiry,
    fetching stops; already-fetched pages still get findings computed over
    them (reduced coverage, not a failed capability), and every remaining
    un-fetched page gets its own `unknown_checks` entry naming the cap as
    the reason. The caller attaches `coverage_manifest([budget])` to its
    output."""
    clock_kwargs = {"clock": clock} if clock is not None else {}
    budget = StageBudget(f"{OWNER_SKILL}-sample-fetch", _SAMPLE_FETCH_BUDGET_SECONDS, **clock_kwargs)
    unknowns: list[UnknownCheck] = []
    page_h1: dict[str, str] = {}
    page_cta: dict[str, str] = {}
    raw_internal_links: dict[str, list[LinkRef]] = {}
    scent_internal_links: dict[str, list[LinkRef]] = {}

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
            parser = parse_page(html_or_error)
            if parser.h1_text:
                page_h1[page_url] = parser.h1_text
            primary_cta = _primary_cta(parser)
            if primary_cta:
                page_cta[page_url] = primary_cta
            links = extract_links(html_or_error, page_url)
            internal = [link for link in links if is_internal_link(link.url, site)]
            raw_internal_links[page_url] = internal
            scent_internal_links[page_url] = [
                link for link in internal if link.anchor_text.lower() not in _NAV_CHROME_ANCHOR_TEXTS
            ]

    return page_h1, page_cta, raw_internal_links, scent_internal_links, unknowns, budget


def audit_sampled_pages(site: str, page_urls: list[str], *, clock=None) -> dict:
    """The combined multi-page mode — fetches every on-site URL in
    `page_urls` (the orchestrator's own bounded page sample) once, then runs
    two independent capability clusters over that one fetch: C1's
    information-scent narrowing (EN-11, the EN-08 slice — agent-judged) and
    B1+B8's dead-end/orphan detection (EN-04 — script-decided). A separate,
    once-per-run mode from `audit_html`'s once-per-page mode, the same
    relationship ENT-07's `audit_service_domains` has to `audit_html` in
    entity-audit."""
    page_h1, page_cta, raw_internal_links, scent_internal_links, unknowns, budget = _gather_sample_pages(
        site, page_urls, clock=clock
    )

    findings = find_dead_end_pages(raw_internal_links, page_cta)
    findings += find_orphan_pages(raw_internal_links)

    cta_candidates = []
    for page_url, cta_text in page_cta.items():
        h1_text = page_h1.get(page_url)
        if not h1_text:
            continue
        candidate = _cta_coherence_candidate(page_url, h1_text, cta_text)
        if candidate:
            cta_candidates.append(candidate)
    cta_candidates.sort(key=lambda c: c["lexical_overlap_score"])
    cta_candidates = cta_candidates[:_INFO_SCENT_MAX_CANDIDATES]

    link_candidates = _link_scent_candidates(page_h1, scent_internal_links)

    judgement_requests = []
    if cta_candidates:
        judgement_requests.append({
            "capability_id": "EN-11",
            "instructions": (
                "Read references/engagement-judgement-rubric.md §EN-11. For each candidate, the "
                "page's own H1/topic and its primary (first, most prominent) call-to-action text "
                "scored below the lexical-overlap threshold. Decide whether the CTA is actually "
                "unrelated to the intent that brought a visitor to this page's content, or is a "
                "legitimate generic/brand-voice action (e.g. 'Get Started' on almost any SaaS "
                "page) that a low lexical score alone does not condemn. Only hand-author a "
                "Finding, capped at Medium severity, for a candidate where the mismatch is real."
            ),
            "observations": {"candidates": cta_candidates},
        })
    if link_candidates:
        judgement_requests.append({
            "capability_id": "EN-08",
            "instructions": (
                "Read references/engagement-judgement-rubric.md §EN-08. For each candidate, an "
                "internal link's anchor text scored below the lexical-overlap threshold against "
                "the target page's own H1 — the link's wording may not set correct expectations "
                "for what the visitor will find (weak information scent, Pirolli & Card 1999). "
                "Common navigational chrome is already excluded from these candidates; judge "
                "whether a content-shaped link (an in-body reference, a related-article teaser, "
                "a category link) actually misleads about its destination. Only hand-author a "
                "Finding, capped at Medium severity, where the wording is genuinely misleading, "
                "not merely a reasonable paraphrase."
            ),
            "observations": {"candidates": link_candidates},
        })

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
# Orchestration within the skill
# ---------------------------------------------------------------------------


def audit_html(site: str, html: str, page_url: str | None = None) -> dict:
    parser = parse_page(html)
    visible_text = parser.visible_text()

    findings = (
        find_unlabelled_fields(parser)
        + find_missing_machine_readable_action(parser)
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
    parser_.add_argument(
        "--sample-file",
        help=(
            "Run only the multi-page checks (C1's information-scent, EN-11 + the EN-08 slice; "
            "and B1+B8's dead-end/orphan detection, EN-04) across a local file of on-site page "
            "URLs (one per line — the sample_urls from audit-orchestrator's sample_pages.py) "
            "instead of auditing a single page. Fetches each page itself (same as --url). "
            "Requires --site."
        ),
    )
    args = parser_.parse_args(argv)

    if args.sample_file:
        if not args.site:
            parser_.error("--site is required with --sample-file")
        site = site_label(args.site)
        page_urls = [
            line.strip()
            for line in Path(args.sample_file).read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        json.dump(audit_sampled_pages(site, page_urls), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

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
