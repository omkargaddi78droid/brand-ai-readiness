"""Shared CLI scaffolding for the single-page skill scripts (shared
infrastructure).

`--url`/`--site`/`--html-file`/`--page-url` and the html-resolution dispatch
that follows them were an identical block copy-pasted into 5 of the 6
single-page `skills/*/scripts/check_*.py` main() functions (content-quality-
audit's own `--text-file`/`--url`/`--html-file` dispatch differs enough — it
also needs live HTTP headers for its freshness check — that it keeps its
own, separate resolution code, though it still uses `add_page_arguments`
for the 4 flags it shares with the other five).

Pure stdlib except the one runtime fetch call: no network of its own beyond
what `page_fetch.fetch_page_html` already does.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from page_fetch import fetch_page_html


def add_page_arguments(parser: argparse.ArgumentParser, *, page_url_help: str | None = None) -> None:
    """Adds the 4 flags every single-page skill script's CLI shares.
    `page_url_help` overrides the default `--page-url` help text for a
    script whose extra input modes (e.g. content-quality-audit's
    `--text-file`) need a longer explanation."""
    parser.add_argument("--url", help="A single page URL to fetch and audit")
    parser.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser.add_argument("--html-file", help="Read page HTML from a local file instead of fetching")
    parser.add_argument(
        "--page-url",
        help=page_url_help or "Label findings with this page URL (default: --url)",
    )


def resolve_page_html(
    args: argparse.Namespace,
    site: str,
    page_url: str | None,
    unknown_output_fn: Callable[[str, str, str | None], dict],
) -> tuple[str | None, int | None]:
    """Resolves `html` from `--html-file` or a live `--url` fetch — the same
    3-way dispatch every single-page skill script performs. Returns
    `(html, None)` on success, or `(None, exit_code)` once
    `unknown_output_fn(site, reason, page_url)`'s JSON has already been
    written to stdout — the caller should `return exit_code` immediately."""
    if args.html_file:
        return Path(args.html_file).read_text(encoding="utf-8", errors="replace"), None
    if args.url:
        html_or_error, status = fetch_page_html(args.url)
        if status != "present":
            _emit(unknown_output_fn(site, html_or_error or "fetch failed", page_url))
            return None, 0
        return html_or_error, None
    _emit(unknown_output_fn(site, "no --url or --html-file given", page_url))
    return None, 0


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
