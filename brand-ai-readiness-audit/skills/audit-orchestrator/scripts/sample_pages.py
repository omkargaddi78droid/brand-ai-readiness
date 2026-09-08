#!/usr/bin/env python3
"""Template-stratified sitemap sampling — the orchestrator's own CLI over
shared/page_sample.py (INF-01/D1).

Replaces the orchestrator's former prose instruction ("pick a small,
representative sample of pages") with a deterministic algorithm: fetch (or
read) a sitemap, cluster its URLs by template shape, and allocate a fixed
page budget across clusters proportionally. See shared/page_sample.py's own
module docstring for why interest-biased picking (by a human or an LLM)
under-samples near-duplicate content specifically.

A `<sitemapindex>` root (WordPress, Shopify, and Next.js all generate one by
default) is recursed one level via `collect_sitemap_urls` below — fetching
each sub-sitemap it lists and concatenating their pages — rather than
treated as zero pages. A site with no sitemap.xml at all (missing, 403, or
empty after recursion) falls back to `fallback_nav_footer_urls`: the
homepage's own `<nav>`/`<footer>` links, best-effort rather than a
guarantee (a JS-only-navigation SPA can still yield nothing).

Usage:
    sample_pages.py --url https://example.com [--budget 25]
    sample_pages.py --sitemap-file sitemap.xml [--budget 25]

Emits one JSON object on stdout: {"total_urls": ..., "budget": ...,
"strata": [...], "sample_urls": [...], "forced_included": [...]}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from html_extract import extract_nav_footer_links  # noqa: E402
from page_fetch import fetch_page_html, fetch_text  # noqa: E402
from page_sample import (  # noqa: E402
    parse_sitemap_index_locs,
    parse_sitemap_urls,
    sample_pages,
    sitemap_root_kind,
)

# A <sitemapindex> pointing at more sub-sitemaps than this is either an
# unusually large site or a misbehaving/malicious one; bounding the fetch
# count keeps this script's own runtime predictable either way.
_MAX_SUB_SITEMAPS = 10


def base_url(url: str) -> str:
    value = url.strip()
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    return value.rstrip("/")


def collect_sitemap_urls(sitemap_text: str) -> list[str]:
    """Every page URL a fetched sitemap.xml names — recursing one level
    into a `<sitemapindex>` by fetching each sub-sitemap it lists (bounded
    to `_MAX_SUB_SITEMAPS`) and extracting their `<loc>` entries. WordPress,
    Shopify, and Next.js all generate a `<sitemapindex>` by default, so
    treating one as "no pages" (the old behaviour) silently disabled every
    multi-page check on most real sites. One level of recursion only: a
    sub-sitemap that is itself another index is skipped rather than chased
    further — real sitemap indexes are one level deep, and unbounded
    recursion risks an attacker-controlled site trapping this script in a
    fetch loop."""
    kind = sitemap_root_kind(sitemap_text)
    if kind != "sitemapindex":
        return parse_sitemap_urls(sitemap_text)

    urls: list[str] = []
    for sub_sitemap_url in parse_sitemap_index_locs(sitemap_text)[:_MAX_SUB_SITEMAPS]:
        sub_text, status = fetch_text(sub_sitemap_url)
        if status != "present" or not sub_text:
            continue
        if sitemap_root_kind(sub_text) == "sitemapindex":
            continue  # one level of recursion only
        urls.extend(parse_sitemap_urls(sub_text))
    return urls


def fallback_nav_footer_urls(target: str) -> list[str]:
    """Zero-sitemap fallback: a site whose sitemap.xml is missing, blocked
    (403), or empty after recursion still usually links its own key pages
    off the homepage's `<nav>`/`<footer>`. Fetches the homepage itself and
    reads those links back out via shared/html_extract.py's
    `extract_nav_footer_links` (already used the same way, in the other
    direction, by content-quality-audit's CQ-01 main-region extraction).
    Best-effort, not a guarantee: a single-page app with JS-only navigation,
    or a homepage that also fails to fetch, still yields `[]` here exactly
    as it did before this fallback existed."""
    html, status = fetch_page_html(target)
    if status != "present" or not html:
        return []
    return extract_nav_footer_links(html, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Target site; fetches /sitemap.xml over the network")
    parser.add_argument("--sitemap-file", help="Read sitemap.xml from a local file instead of fetching")
    parser.add_argument(
        "--budget", type=int, default=25, help="Maximum sampled pages before forced inclusions (default 25)"
    )
    args = parser.parse_args(argv)

    if not args.url and not args.sitemap_file:
        parser.error("one of --url or --sitemap-file is required")

    if args.sitemap_file:
        sitemap_text = Path(args.sitemap_file).read_text(encoding="utf-8", errors="replace")
        urls = collect_sitemap_urls(sitemap_text)
    else:
        target = base_url(args.url)
        sitemap_text, status = fetch_text(target + "/sitemap.xml")
        urls = collect_sitemap_urls(sitemap_text or "") if status == "present" else []
        if not urls:
            urls = fallback_nav_footer_urls(target)

    result = sample_pages(urls, budget=args.budget)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
