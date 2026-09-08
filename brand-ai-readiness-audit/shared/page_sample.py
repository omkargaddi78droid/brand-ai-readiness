"""Template-stratified sitemap sampling (shared infrastructure, INF-01/D1).

Today, page selection for every per-page skill is a prose instruction in
skills/audit-orchestrator/SKILL.md: "pick a small, representative sample of
pages... not every URL on the site." That is exactly the interest-biased
selection that silently disabled near-duplicate detection (B6, a later
phase) — a human or an LLM picking
"interesting" pages tends to pick *different* pages, so a sampler built
this way never happens to select two members of the same template cluster
to compare against each other.

This module replaces that prose instruction with a deterministic algorithm:
cluster a sitemap's URLs by template shape (same path structure, different
instance — "/blog/2024/my-post" and "/blog/2023/other-post" are the same
template, "/blog/*/*"), then allocate a fixed page budget across clusters
proportionally, so the sample actually spans the site's different page
*kinds* instead of just its most numerous kind.

Pure stdlib, pure functions: `xml.etree.ElementTree` for sitemap parsing,
no network, no file I/O. Malformed input degrades to an empty/partial
result rather than raising — sampling is a best-effort convenience step,
and a broken sitemap should never crash the audit pipeline that would
otherwise still run against whatever pages the caller already knows about.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

_DEFAULT_BUDGET = 25

# A page whose function makes it worth checking regardless of which
# template cluster it falls into — the orchestrator's own prose instruction
# named exactly these ("/contact", "/checkout", "/search", "/pricing") as
# process pages worth including on top of proportional sampling.
_FORCE_INCLUDE_PATHS = frozenset({"/", "/contact", "/checkout", "/search", "/pricing"})

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
_LONG_SLUG_MIN_CHARS = 24


def parse_sitemap_urls(xml_text: str) -> list[str]:
    """Extract every `<loc>` URL from a `<urlset>` sitemap.

    A `<sitemapindex>` (a sitemap of sitemaps) returns `[]` here — this
    module is pure/no-network (see the module docstring) and can't fetch
    the sub-sitemaps a `<sitemapindex>` points to itself. The caller that
    can do that fetching, sample_pages.py, does recurse one level into a
    `<sitemapindex>` using `sitemap_root_kind`/`parse_sitemap_index_locs`
    below plus its own network access — this function's own contract for a
    bare `<sitemapindex>` document is unchanged.

    Malformed XML also returns `[]` rather than raising.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    root_tag = root.tag.rsplit("}", 1)[-1]
    if root_tag == "sitemapindex":
        return []

    return [
        element.text.strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text and element.text.strip()
    ]


def sitemap_root_kind(xml_text: str) -> str:
    """Root tag of a sitemap document: `"urlset"` (a leaf sitemap of pages),
    `"sitemapindex"` (a sitemap of sitemaps), or `"unknown"` for malformed
    XML or an unrecognised root. A caller that needs to fetch and recurse
    into a `<sitemapindex>`'s sub-sitemaps (network I/O this module never
    does itself) uses this to decide when to — see
    skills/audit-orchestrator/scripts/sample_pages.py."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "unknown"
    return root.tag.rsplit("}", 1)[-1]


def parse_sitemap_index_locs(xml_text: str) -> list[str]:
    """Extract every `<loc>` URL from a `<sitemapindex>` — each one is a
    sub-sitemap URL, not a page. Returns `[]` for anything that isn't a
    `<sitemapindex>` (including a plain `<urlset>` — use `parse_sitemap_urls`
    for that) or is malformed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    root_tag = root.tag.rsplit("}", 1)[-1]
    if root_tag != "sitemapindex":
        return []

    return [
        element.text.strip()
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "loc" and element.text and element.text.strip()
    ]


def _segment_is_variable(segment: str) -> bool:
    """A path segment that names one specific instance rather than a page
    *kind* — a numeric id, a UUID, or a slug long/complex enough that it is
    almost certainly per-instance content (a blog post title, a product
    name) rather than a fixed route segment like "blog" or "products"."""
    if segment.isdigit():
        return True
    if _UUID_PATTERN.match(segment):
        return True
    if len(segment) >= _LONG_SLUG_MIN_CHARS:
        return True
    if "-" in segment and any(ch.isdigit() for ch in segment):
        return True  # a hyphenated slug carrying a number (a date, an id)
    return False


def template_key(path: str) -> str:
    """Collapse a URL path into its template shape: variable segments
    become `*`, short structural segments stay literal (lowercased, so
    `/Products` and `/products` share a template).

    "/blog/2024/my-post-title" and "/blog/2023/another-post" both collapse
    to "/blog/*/*" — the same template, different instances. "/pricing" and
    "/about" stay distinct templates: both segments are short and
    structural, not instance identifiers.

    Known limitation: a purely alphabetic, short, no-digit slug (e.g.
    "/blog/my-post-title" vs "/blog/another-post") is NOT recognized as
    variable — string shape alone can't tell a per-instance slug from a
    real route segment ("/blog/get-started") without positional context
    this function doesn't use. Under-clustering here is intentional: it
    costs some sample diversity, not a false claim that two different page
    kinds are the same template.
    """
    segments = [s for s in path.split("/") if s]
    if not segments:
        return "/"
    keyed = ["*" if _segment_is_variable(s) else s.lower() for s in segments]
    return "/" + "/".join(keyed)


def _allocate(cluster_sizes: dict[str, int], budget: int) -> dict[str, int]:
    """How many of `budget` slots each cluster gets, floor of 1 per cluster
    whenever the budget can afford one for every cluster, distributing the
    remainder proportionally to cluster size (largest-remainder method) so
    a cluster's share always rounds toward its actual weight rather than
    always up or always down.

    When the budget cannot afford even one slot per cluster, the largest
    `budget` clusters each get exactly 1 and the rest get 0 — a smaller
    template family is a real cost here, but there is no way to represent
    every template kind at all once clusters outnumber the budget.
    """
    keys = sorted(cluster_sizes)
    total = sum(cluster_sizes.values())
    if budget <= 0 or total == 0:
        return {k: 0 for k in keys}

    if budget < len(keys):
        ranked = sorted(keys, key=lambda k: (-cluster_sizes[k], k))
        chosen = set(ranked[:budget])
        return {k: (1 if k in chosen else 0) for k in keys}

    allocation = {k: 1 for k in keys}
    remaining = budget - len(keys)
    shares = {k: (cluster_sizes[k] / total) * remaining for k in keys}
    for k in keys:
        extra = min(int(shares[k]), cluster_sizes[k] - 1)
        allocation[k] += extra
        remaining -= extra

    # Integer truncation leaves a few slots unassigned; hand them out in
    # order of largest fractional remainder, skipping any cluster already
    # at its own size (it has no more URLs to give).
    order = sorted(keys, key=lambda k: shares[k] - int(shares[k]), reverse=True)
    guard = 0
    while remaining > 0 and guard < len(keys) * 2:
        k = order[guard % len(order)]
        if allocation[k] < cluster_sizes[k]:
            allocation[k] += 1
            remaining -= 1
        guard += 1
    return allocation


def _pick_evenly(urls: list[str], count: int) -> list[str]:
    """`count` items spread evenly across `urls`, preserving order — chosen
    over "first N" so a cluster sorted in, say, chronological order doesn't
    have its sample skewed entirely toward one end of it."""
    if count <= 0:
        return []
    if count >= len(urls):
        return list(urls)
    step = len(urls) / count
    return [urls[int(i * step)] for i in range(count)]


def sample_pages(urls: list[str], budget: int = _DEFAULT_BUDGET) -> dict:
    """Cluster `urls` by template shape and return a budgeted, stratified
    sample every per-page skill can consume.

    Deduplicates `urls` first (a sitemap can legitimately list the same URL
    twice) and always includes the homepage and any "process" page
    (`/contact`, `/checkout`, `/search`, `/pricing`) present in `urls`, on
    top of the proportional allocation — `sample_urls` can therefore run a
    few entries past `budget` when a forced page wasn't already picked, by
    design: the whole point of force-including these is to guarantee their
    presence rather than let a proportional split omit them.
    """
    deduped = list(dict.fromkeys(urls))
    if not deduped:
        return {"total_urls": 0, "budget": budget, "strata": [], "sample_urls": [], "forced_included": []}

    clusters: dict[str, list[str]] = {}
    for url in deduped:
        path = urlsplit(url).path or "/"
        clusters.setdefault(template_key(path), []).append(url)

    cluster_sizes = {key: len(members) for key, members in clusters.items()}
    effective_budget = min(budget, len(deduped))
    allocation = _allocate(cluster_sizes, effective_budget)

    sample: list[str] = []
    strata = []
    for key in sorted(clusters):
        picked = _pick_evenly(clusters[key], allocation.get(key, 0))
        sample.extend(picked)
        strata.append(
            {
                "template_key": key,
                "cluster_size": cluster_sizes[key],
                "allocated": len(picked),
                "urls": picked,
            }
        )

    forced: list[str] = []
    for url in deduped:
        normalized_path = (urlsplit(url).path or "/").rstrip("/").lower() or "/"
        if normalized_path in _FORCE_INCLUDE_PATHS and url not in sample:
            forced.append(url)

    return {
        "total_urls": len(deduped),
        "budget": budget,
        "strata": strata,
        "sample_urls": list(dict.fromkeys(sample + forced)),
        "forced_included": forced,
    }
