"""Vendored beautifulsoup4 (stdlib html.parser backend, no lxml) for the
extraction gaps a hand-rolled `html.parser.HTMLParser` subclass genuinely
cannot close well: pairing `<th>`/`<td>` and `<dt>`/`<dd>` siblings by DOM
structure (CQ-07/CQ-08), stripping `<nav>`/`<header>`/`<footer>`/`<aside>`
out of a `<main>`/`<article>` region before windowing for a "does the answer
appear near the top" check (CQ-01), and reading `<nav>`/`<footer>` links back
OUT of a homepage as the zero-sitemap fallback page-discovery path (INF-01
follow-up; see skills/audit-orchestrator/scripts/sample_pages.py).

Deliberately additive, not a replacement for `extract_visible_text()` in
content-quality-audit or any other skill's hand-rolled extractor — those are
separately tested and depended on by every other check in their skill; this
module only adds candidates those extractors cannot produce, and every
caller must keep working when this module returns nothing (a page with no
`<table>`/`<dl>` markup, or no `<main>`/`<article>` tag, is not an error).

third_party/bs4 runs on Python's stdlib `html.parser` backend by design (no
lxml) — see third_party/VENDORED.md. sys.path is extended here, once, before
importing it, so it always resolves to the vendored copy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "third_party"))

from bs4 import BeautifulSoup, Tag  # noqa: E402

_STRIP_FROM_MAIN = ("nav", "header", "footer", "aside")
_LINK_REGIONS = ("nav", "footer")
_NON_PAGE_HREF_PREFIXES = ("#", "mailto:", "tel:", "javascript:")


def _soup(html: str) -> BeautifulSoup | None:
    try:
        return BeautifulSoup(html, "html.parser")
    except Exception:
        # bs4 on the stdlib backend does not raise on malformed markup in
        # practice, but a caller extracting arbitrary fetched HTML should
        # never crash the audit over a parse quirk this module can't predict.
        return None


def extract_labeled_pairs(html: str) -> list[str]:
    """Return synthetic "label: value" lines for every `<th>`+`<td>` pair
    within a `<tr>` and every `<dt>`+`<dd>` pair within a `<dl>` — markup a
    line-oriented text extractor always splits onto separate lines before a
    `Label: value` regex ever sees them (see check_content_quality.py's
    CQ-07/CQ-08). Callers append these lines to their existing extracted text
    rather than replacing it."""
    soup = _soup(html)
    if soup is None:
        return []

    lines: list[str] = []

    for row in soup.find_all("tr"):
        cells = [c for c in row.find_all(["th", "td"], recursive=False) if isinstance(c, Tag)]
        for label_cell, value_cell in zip(cells, cells[1:]):
            label = label_cell.get_text(" ", strip=True)
            value = value_cell.get_text(" ", strip=True)
            if label and value:
                lines.append(f"{label}: {value}")

    for dl in soup.find_all("dl"):
        pending_label: str | None = None
        for child in dl.find_all(["dt", "dd"], recursive=False):
            text = child.get_text(" ", strip=True)
            if not text:
                continue
            if child.name == "dt":
                pending_label = text
            elif child.name == "dd" and pending_label:
                lines.append(f"{pending_label}: {text}")
                pending_label = None

    return lines


def extract_main_content_text(html: str) -> str | None:
    """Return the text of the first `<main>` or `<article>` element, with any
    nested `<nav>`/`<header>`/`<footer>`/`<aside>` removed first, or None if
    the page has neither tag. A page without semantic sectioning tags is not
    a failure of this function — the caller falls back to its existing
    first-N-words window over the whole page, unchanged from before this
    module existed."""
    soup = _soup(html)
    if soup is None:
        return None

    region = soup.find("main") or soup.find("article")
    if region is None:
        return None

    for tag_name in _STRIP_FROM_MAIN:
        for stray in region.find_all(tag_name):
            stray.decompose()

    text = region.get_text("\n", strip=True)
    return text or None


def _same_host(netloc: str, target_host: str) -> bool:
    host = netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host == target_host


def extract_nav_footer_links(html: str, base_url: str) -> list[str]:
    """Absolute, same-host URLs from every `<a href>` inside a `<nav>` or
    `<footer>` element on `html` (assumed fetched from `base_url`) — the
    zero-sitemap fallback page-discovery path: a site with no reachable
    `sitemap.xml` (missing, 403, or blocked by robots.txt) still usually
    links its own key pages from its primary navigation and footer.
    Cross-host links (social icons, third-party badges, legal boilerplate
    pointing off-site) are dropped — this finds the site's OWN pages, not
    everything the homepage happens to link to. Returns `[]`, never raises,
    on markup with no `<nav>`/`<footer>` or no usable links — the caller's
    existing "0 pages sampled" behaviour when this also finds nothing."""
    soup = _soup(html)
    if soup is None:
        return []

    target_host = urlsplit(base_url).netloc.lower()
    if target_host.startswith("www."):
        target_host = target_host[4:]
    if not target_host:
        return []

    links: list[str] = []
    seen: set[str] = set()
    for region_tag in _LINK_REGIONS:
        for region in soup.find_all(region_tag):
            for anchor in region.find_all("a"):
                href = (anchor.get("href") or "").strip()
                if not href or href.startswith(_NON_PAGE_HREF_PREFIXES):
                    continue
                absolute = urljoin(base_url, href)
                parsed = urlsplit(absolute)
                if parsed.scheme not in ("http", "https"):
                    continue
                if not _same_host(parsed.netloc, target_host):
                    continue
                normalized = absolute.split("#")[0]
                if normalized in seen:
                    continue
                seen.add(normalized)
                links.append(normalized)
    return links
