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
default) is recursed via `collect_sitemap_urls` below — fetching each
sub-sitemap it lists and concatenating their pages, bounded by a total fetch
budget rather than a fixed depth (see `collect_sitemap_urls`'s own docstring
for why: pw.live, live-tested, nests four levels deep and uses a `<urlset>`
at one level whose `<loc>` entries are themselves further sitemap files, not
pages — a depth-1, tag-only recursion silently returned zero real pages
against it). A site with no sitemap.xml at all (missing, 403, or empty after
recursion) falls back to `fallback_nav_footer_urls`: the homepage's own
`<nav>`/`<footer>` links, best-effort rather than a guarantee (a
JS-only-navigation SPA can still yield nothing).

Usage:
    sample_pages.py --url https://example.com [--budget 30]
    sample_pages.py --sitemap-file sitemap.xml [--budget 30]

Emits one JSON object on stdout: {"total_urls": ..., "budget": ...,
"strata": [...], "sample_urls": [...], "forced_included": [...]}.
"sample_urls" is priority-ordered (highest first) via
shared/page_sample.py's rank_sample_urls — a deadline-gated caller (see
audit-orchestrator/SKILL.md) can stop partway through the list and still
have audited the highest-priority pages first. Judgement-resolution
capping happens later, per skill and by severity, via
select_judgement_items.py — not here.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from html_extract import extract_nav_footer_links  # noqa: E402
from page_fetch import fetch_page_html, fetch_text  # noqa: E402
from page_sample import (  # noqa: E402
    parse_sitemap_index_locs,
    parse_sitemap_urls,
    rank_sample_urls,
    sample_pages,
    sitemap_root_kind,
)

# Total sub-sitemap fetch budget for the WHOLE recursive walk (any depth),
# not a per-level count. A site that needs more sub-sitemap fetches than
# this to resolve is either unusually large or misbehaving/malicious;
# bounding the total keeps this script's own runtime predictable either
# way, while still resolving a real multi-level tree like pw.live's (a
# <sitemapindex> whose one sub-sitemap is a <urlset> of ~160 further
# per-category sitemap.xml files, each itself a <sitemapindex> pointing at
# one more <urlset> of real pages — four levels, mixed tags).
#
# Raised from 30 to 80 (live-tested against cleartrip.com): the depth-first
# walk fully resolves one top-level vertical's own nested index structure
# (trains alone needed 7 fetches, tourism/routes another 9) before ever
# returning to pop the NEXT top-level sibling off the stack, so a real
# multi-vertical site (flights, hotels, trains, tourism, each with its own
# sub-index) can exhaust a small total budget on just the first two or three
# verticals depth-first happens to reach first, never even attempting the
# rest — a real coverage gap, not just a per-leaf page-count one (see
# _MAX_URLS_PER_LEAF_SITEMAP below for that half of the fix). Each fetch is
# a small XML file already bounded by shared/page_fetch.py's own timeout and
# retry, so raising this trades a modest amount of wall-clock time (well
# inside the orchestrator's step budget, since sampling runs once per site
# before any per-page skill's own 280s deadline starts counting) for
# actually reaching every vertical a real e-commerce/travel site has.
_MAX_SUB_SITEMAPS = 80

# A single fetched sitemap document can list far more <loc> page entries than
# any real budget will sample (a pathological or malicious sitemap could list
# millions) — this bounds one collect_sitemap_urls() call's memory/CPU
# independently of _MAX_SUB_SITEMAPS, which only bounds sub-sitemap fetches.
# sample_pages()'s own --budget still governs the final sample size.
_MAX_URLS_PER_SITEMAP = 5000

# Bounds how many page URLs a SINGLE leaf <urlset> fetch may contribute to
# `pages`, independent of the _MAX_URLS_PER_SITEMAP total above. Without
# this, a depth-first walk that happens to reach one huge leaf sitemap
# first fills the entire total cap before the walk ever gets to pop a
# sibling sitemapindex entry off the stack — live-tested against
# cleartrip.com, whose sitemapindex lists separate flight/hotel/train
# sitemaps but whose /trains/* leaf alone lists 4993 pages: the walk
# resolved that one branch to the cap and stopped, so `total_urls` came
# back as a single template with zero flights/hotels representation,
# defeating the point of template-stratified sampling. 500 is generous
# enough that an ordinary single-urlset site (a few hundred pages, the
# common case) is unaffected, while still preventing one oversized leaf
# from starving every sibling vertical of the shared budget.
_MAX_URLS_PER_LEAF_SITEMAP = 500


def base_url(url: str) -> str:
    value = url.strip()
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    return value.rstrip("/")


def _looks_like_sitemap_file(url: str) -> bool:
    """A `<urlset>`'s `<loc>` value that is itself another sitemap document
    rather than a real page — live-tested against pw.live, whose
    `sitemap_1.xml` is tagged `<urlset>` (not `<sitemapindex>`) even though
    every one of its ~160 `<loc>` entries is a further per-category
    `sitemap.xml`, not a page. A root-tag-only check treats that as a leaf
    and returns sitemap file URLs as if they were content pages; matching
    the `<loc>` value's own shape instead catches this regardless of which
    tag wraps it."""
    path = urllib.parse.urlsplit(url).path.lower()
    return path.endswith(".xml") or path.endswith(".xml.gz")


def collect_sitemap_urls(sitemap_text: str) -> list[str]:
    """Every page URL reachable from a fetched sitemap.xml, walking as many
    levels of nesting as the site actually has (WordPress, Shopify, and
    Next.js all generate at least a `<sitemapindex>` by default; pw.live's
    live sitemap tree is four levels deep with a `<urlset>`-tagged level in
    the middle whose entries are themselves sitemap files — see
    `_looks_like_sitemap_file`). A `<sitemapindex>` contributes its
    `<sitemap><loc>` entries as more sitemaps to fetch; a `<urlset>`
    contributes any `<loc>` that looks like a sitemap file the same way, and
    every other `<loc>` as a real page.

    Bounded by a TOTAL fetch budget (`_MAX_SUB_SITEMAPS`) across the whole
    walk, not a depth limit — an attacker-controlled site (or a cyclic
    sitemap graph) still can't trap this script in an unbounded fetch loop,
    since each sub-sitemap URL is fetched at most once and the budget
    decrements on every fetch regardless of how deep it is.

    Walked depth-first (a stack, not a queue): live-tested against pw.live,
    whose ~160 top-level category branches each need 2 more fetches to
    reach that category's own page(s), a breadth-first walk spends the
    entire budget fetching every branch's first hop and never reaches a
    second hop in any of them — zero real pages found. Depth-first instead
    finishes resolving one branch all the way down before starting the
    next, so a limited budget still comes back with several fully-resolved
    branches instead of many half-resolved ones."""
    pages: list[str] = []
    seen: set[str] = set()

    def expand(text: str) -> list[str]:
        if sitemap_root_kind(text) == "sitemapindex":
            return parse_sitemap_index_locs(text)
        if len(pages) >= _MAX_URLS_PER_SITEMAP:
            return []
        leaf_urls = parse_sitemap_urls(text)
        new_pages = [u for u in leaf_urls if not _looks_like_sitemap_file(u)]
        pages.extend(new_pages[:_MAX_URLS_PER_LEAF_SITEMAP])
        del pages[_MAX_URLS_PER_SITEMAP:]
        return [u for u in leaf_urls if _looks_like_sitemap_file(u)]

    stack = expand(sitemap_text)
    fetch_budget = _MAX_SUB_SITEMAPS
    while stack and fetch_budget > 0 and len(pages) < _MAX_URLS_PER_SITEMAP:
        sub_url = stack.pop()
        if sub_url in seen:
            continue
        seen.add(sub_url)
        fetch_budget -= 1
        sub_text, status = fetch_text(sub_url)
        if status != "present" or not sub_text:
            continue
        stack.extend(expand(sub_text))
    return pages


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


_FORCE_INCLUDE_SUFFIXES = ("", "/contact", "/checkout", "/search", "/pricing")


def probe_forced_pages(target: str, existing_urls: list[str]) -> list[str]:
    """Directly fetches each standard process-page path (homepage,
    `/contact`, `/checkout`, `/search`, `/pricing`) against the live site
    and returns whichever ones exist (HTTP 200) and aren't already covered
    by `existing_urls` — matched by normalized path, not exact string, so
    `https://example.com` and `https://example.com/` count as the same
    homepage.

    `shared/page_sample.py`'s own `_FORCE_INCLUDE_PATHS` only forces a page
    that is already present in the sitemap's own URL list, which silently
    drops the homepage on any site whose sitemap simply doesn't list it —
    live-tested against cleartrip.com, whose ~4900-URL sitemap never
    mentions "/" itself even though the homepage obviously exists and its
    URL is already known from the `--url` argument. This makes forced
    inclusion unconditional instead: try the path directly rather than
    hoping the sitemap happened to list it."""
    existing_paths = {
        (urllib.parse.urlsplit(u).path.rstrip("/") or "/") for u in existing_urls
    }
    found: list[str] = []
    for suffix in _FORCE_INCLUDE_SUFFIXES:
        normalized_path = suffix or "/"
        if normalized_path in existing_paths:
            continue
        candidate = target + suffix
        html, status = fetch_page_html(candidate)
        if status == "present" and html:
            found.append(candidate)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Target site; fetches /sitemap.xml over the network")
    parser.add_argument("--sitemap-file", help="Read sitemap.xml from a local file instead of fetching")
    parser.add_argument(
        "--budget", type=int, default=30, help="Maximum sampled pages before forced inclusions (default 30)"
    )
    args = parser.parse_args(argv)

    if not args.url and not args.sitemap_file:
        parser.error("one of --url or --sitemap-file is required")

    target: str | None = None
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

    if target is not None:
        # sample_pages()'s own forced-inclusion only fires for a path
        # already present in `urls`; probe the live site directly for
        # whichever standard process pages the sitemap didn't happen to
        # list (see probe_forced_pages's own docstring).
        probed = probe_forced_pages(target, result["sample_urls"])
        if probed:
            result["forced_included"] = sorted(set(result["forced_included"]) | set(probed))
            result["sample_urls"] = rank_sample_urls(
                list(dict.fromkeys(result["sample_urls"] + probed))
            )

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
