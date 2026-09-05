#!/usr/bin/env python3
"""Template-stratified sitemap sampling — the orchestrator's own CLI over
shared/page_sample.py (INF-01/D1).

Replaces the orchestrator's former prose instruction ("pick a small,
representative sample of pages") with a deterministic algorithm: fetch (or
read) a sitemap, cluster its URLs by template shape, and allocate a fixed
page budget across clusters proportionally. See shared/page_sample.py's own
module docstring for why interest-biased picking (by a human or an LLM)
under-samples near-duplicate content specifically.

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

from page_fetch import fetch_text  # noqa: E402
from page_sample import parse_sitemap_urls, sample_pages  # noqa: E402


def base_url(url: str) -> str:
    value = url.strip()
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    return value.rstrip("/")


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
    else:
        sitemap_text, status = fetch_text(base_url(args.url) + "/sitemap.xml")
        if status != "present":
            json.dump(
                {"total_urls": 0, "budget": args.budget, "strata": [], "sample_urls": [], "forced_included": []},
                sys.stdout,
                indent=2,
            )
            sys.stdout.write("\n")
            return 0

    urls = parse_sitemap_urls(sitemap_text or "")
    result = sample_pages(urls, budget=args.budget)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
