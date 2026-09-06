"""HTML anchor-link extraction (shared infrastructure, cycle 23 Part 4).

Consolidates the `<a href>` extraction that ENT-07 first built as a
skill-local `_LinkParser` in check_entity.py. Cycle 23's later multi-page
capabilities (EN-04/EN-11/EN-08 in engagement-audit, CIT-08 in
citability-audit) need the same "every outbound link, with its anchor text,
resolved to an absolute URL" extraction ENT-07 needed — duplicating an
HTMLParser subclass a third and fourth time is exactly the kind of
six-near-identical-copies problem shared/page_fetch.py already fixed once
for fetch_page_html (see docs/02-project-plan.md Phase 1). This module is
the same fix for link extraction.

Pure stdlib, pure parsing over caller-supplied HTML text: no network, no
file I/O. `is_internal_link` is the only function that reaches into
shared/public_suffix.py, since "internal" is a registrable-domain question,
not a parsing one.
"""

from __future__ import annotations

import dataclasses
import urllib.parse
from html.parser import HTMLParser

from public_suffix import same_entity


@dataclasses.dataclass(frozen=True)
class LinkRef:
    """One outbound `<a href>` on a page.

    `url` is always absolute (resolved against the page's own URL) and
    always http(s) — mailto:/tel:/javascript:/fragment-only hrefs never
    produce a LinkRef at all. `anchor_text` is the link's visible text with
    interior whitespace collapsed to single spaces; empty when the link
    carries no text of its own (an image-only or icon-only link).
    """

    url: str
    anchor_text: str


class _LinkParser(HTMLParser):
    """Collects `<a href>` targets and the text between each tag pair.
    Nested `<a>` tags are invalid HTML and not expected on a real page; if
    one appears, its text is attributed to whichever `<a>` opened most
    recently, which is a harmless, undefined-by-the-spec edge case rather
    than something worth extra bookkeeping for."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._open_links: list[tuple[str, list[str]]] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._open_links.append((href.strip(), []))

    def handle_startendtag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append((href.strip(), ""))

    def handle_endtag(self, tag):
        if tag == "a" and self._open_links:
            href, parts = self._open_links.pop()
            self.links.append((href, " ".join("".join(parts).split())))

    def handle_data(self, data):
        if self._open_links:
            self._open_links[-1][1].append(data)

    def close(self):
        super().close()
        while self._open_links:
            href, parts = self._open_links.pop()
            self.links.append((href, " ".join("".join(parts).split())))


def extract_links(html: str, page_url: str) -> list[LinkRef]:
    """Every http(s) link on the page, resolved to an absolute URL against
    `page_url`. mailto:/tel:/javascript:/fragment-only hrefs are dropped —
    none of them are a navigable page."""
    parser = _LinkParser()
    parser.feed(html)
    parser.close()
    resolved: list[LinkRef] = []
    for href, anchor_text in parser.links:
        if href.startswith("#"):
            continue
        absolute = urllib.parse.urljoin(page_url, href)
        if urllib.parse.urlparse(absolute).scheme in ("http", "https"):
            resolved.append(LinkRef(url=absolute, anchor_text=anchor_text))
    return resolved


def extract_outbound_links(html: str, page_url: str) -> list[str]:
    """Convenience wrapper over `extract_links` for callers that only need
    the resolved URLs, not anchor text (ENT-07's original shape)."""
    return [link.url for link in extract_links(html, page_url)]


def is_internal_link(link_url: str, site: str) -> bool:
    """Whether `link_url` points at the same registrable-domain entity as
    `site` (see shared/public_suffix.same_entity) — a link with no
    resolvable hostname is never internal."""
    hostname = urllib.parse.urlparse(link_url).hostname or ""
    return bool(hostname) and same_entity(hostname, site)
