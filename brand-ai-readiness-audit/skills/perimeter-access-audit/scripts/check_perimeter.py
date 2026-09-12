#!/usr/bin/env python3
"""Gate-1 perimeter audit: can AI crawlers reach the site at all?

Owns four capabilities:
  PER-01  AI-crawler access across the three-tier bot taxonomy (robots.txt)
  PER-02  Blanket-block anti-pattern (every AI agent disallowed at the root)
  PER-03  CDN/WAF edge blocking — robots.txt allows, the edge answers 403 or a
          challenge. Live-only: it needs real requests under real bot user
          agents, so it runs from --url and never from --robots-file.
  PER-04  llms.txt presence and spec validity

Deliberately does NOT own: llms-full.txt payload depth, sitemap discovery,
`.md` content negotiation. Those need a crawl and belong to sibling skills.

PER-03's compliance rule, binding and enforced in code (`plan_edge_probes`):
never probe an agent robots.txt already disallows. Two reasons, both hard
requirements rather than politeness — sending that request would itself
violate "respect robots.txt", and it would write a hit from that agent's exact
UA string into the target's own bot-traffic logs under a name it explicitly
excluded. This is why PER-03 needs the same parsed robots.txt groups PER-01
computes: the two checks share the compliance boundary, not just the taxonomy.

Bot-taxonomy accelerator
------------------------
`_baseline_bot_taxonomy()` loads the vendored snapshot at
`vendor/bot_taxonomy.json` (175 bots, MIT, see vendor/VENDORED.md) and
`resolve_bot_tiers()` widens BOT_TIERS with it, case-insensitively
deduplicated so the same bot can never end up double-counted across two
tiers. It degrades to None — falling back to BOT_TIERS alone — if the file is
missing or unparseable, so a corrupted or absent snapshot never breaks an
audit run. The 15 original bot->tier assignments always win over the
snapshot's own classification for the same bot name: the snapshot can only
add bots BOT_TIERS doesn't already name, never override one.

`resolve_bot_tiers()` is deliberately NOT called by PER-01/PER-02/C1 (see
`evaluate_robots`, `_is_blanket_blocked`, `_c1_sitemap_url_ai_disallowed`,
which all use BOT_TIERS directly): widening those checks' bot list to all 175
makes "blocks every AI agent" require blocking every obscure one, so a
robots.txt that blocks the ~15 well-known bots — the realistic real-world
"block all AI" pattern — would silently stop tripping the critical PER-02
finding at all. Explicit user decision, cycle 24: keep PER-01/PER-02/C1's
threshold on the 15 curated bots; `resolve_bot_tiers()` stays available as a
tested, correct seam for a future capability that wants the wider list.

Determinism
-----------
Every evaluation is a pure function of the fetched text. No randomness, no
clock, no ordering by dict iteration. The same robots.txt always yields the
same findings in the same order.

Safety
------
Read-only. Two GETs (`/robots.txt`, `/llms.txt`) plus, in `--url` mode, at most
four more for PER-03 (one reachability control plus one per bot tier, fewer
whenever robots.txt already covers a tier) — six requests total, worst case, to
one path each. No query strings, no credentials, no form submission, no
redirect chasing past the standard urllib limit. A short delay separates the
PER-03 probes so they never burst. The fetched text is parsed as data only; it
is never executed and never forwarded anywhere that interprets instructions.
The PER-03 probes send real bot user-agent strings on purpose — that is the
only way to observe edge-layer behaviour that diverges from robots.txt — plus
an `X-Audit-Purpose` header naming this as a read-only accessibility check, so
the request is honest about what sent it even while it wears a bot's identity
to test how that bot would be treated.

Usage:
    check_perimeter.py --url https://example.com
    check_perimeter.py --site example.com --robots-file R.txt --llms-file L.txt
    check_perimeter.py --site example.com --robots-file R.txt --llms-absent

Emits one JSON object on stdout:
    {"owner_skill": ..., "capability_ids": [...],
     "findings": [...], "unknown_checks": [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from finding_contract import Finding, UnknownCheck  # noqa: E402
from report_shape import site_label  # noqa: E402
from _perimeter_constants import (  # noqa: E402
    OWNER_SKILL,
    CAPABILITY_IDS,
    USER_AGENT,
    FETCH_TIMEOUT_SECONDS,
    REPRESENTATIVE_AGENTS,
)
from _perimeter_encoding import decode_content_encoding, _best_effort_decode_content_encoding  # noqa: E402
from _perimeter_fetch import fetch_text  # noqa: E402
from _perimeter_access_rules import (  # noqa: E402
    BOT_TIERS,
    _baseline_bot_taxonomy,
    resolve_bot_tiers,
    parse_groups,
    can_fetch_root,
    can_fetch_path,
    evaluate_robots,
)
from _perimeter_edge_probe import (  # noqa: E402
    CONTROL_USER_AGENT,
    classify_response,
    plan_edge_probes,
    interpret_edge_results,
    probe_with_user_agent,
    fetch_and_evaluate_edge_access,
)
from _perimeter_content_parity import (  # noqa: E402
    evaluate_content_parity,
    fetch_full_body_with_user_agent,
    fetch_and_evaluate_content_parity,
    _visible_text_length,
    _json_ld_node_count,
)
from _perimeter_artifacts import (  # noqa: E402
    evaluate_llms_txt,
    evaluate_llms_full_txt,
    evaluate_sitemap,
    evaluate_md_negotiation,
    evaluate_api_catalog,
    evaluate_sitemap_discoverability,
    evaluate_llms_sitemap_agreement,
    extract_sitemap_url_from_robots,
    _SITEMAP_ROOT_PATTERN,
)
from _perimeter_contradictions import (  # noqa: E402
    TIER_SEVERITY,
    parse_meta_directives,
    fetch_tdmrep,
    _tdmrep_reserves,
    _degrade_severity,
    _c1_sitemap_url_ai_disallowed,
    _c2_noindex_on_declared_url,
    _c3_tdm_reservation_contradicts_robots,
    _c4_header_meta_robots_disagree,
    _c5_no_tdm_declaration,
    evaluate_access_contradictions,
)


def fetch_page_with_headers(url: str) -> tuple[str | None, dict[str, str], str]:
    """GET a page and capture its response headers alongside the body.

    Returns (text_or_error, headers, status). status is the same three-value
    contract as `fetch_text`: "present", "absent" (404/410) or "unavailable"
    (anything else, including network failure).

    `headers` is built as a plain dict with every header name lowercased —
    chosen over a dedicated case-insensitive mapping type because the only
    thing a caller needs is `.get("some-header")` lookups regardless of the
    casing seen on the wire, and a lowercased-key dict gives that directly
    without adding a new type to the module.

    On "absent" there is no page to have headers from, so headers is `{}`.
    On "unavailable" from a non-HTTPError failure (timeout, DNS, TLS), the
    fetch never completed enough to have any headers, so headers is also
    `{}`. The one case that diverges from `fetch_text`'s pattern: an
    HTTPError that isn't 404/410 still carries response headers on the error
    object (`error.headers`), and those are captured here — a 403 or 500
    response's headers can still carry `X-Robots-Tag` or similar signal a
    later capability needs.

    Same classification as `fetch_text` on that non-404/410 branch: the body
    is still read and run through `classify_response`, so a 429/403 or a
    challenge-interstitial 200 is named as a CDN/edge decision in the
    returned text instead of a bare HTTP code indistinguishable from a
    transient error.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            raw = response.read(2_000_000)
            content_encoding = response.headers.get("Content-Encoding", "")
            headers = {key.lower(): value for key, value in response.headers.items()}
        raw = decode_content_encoding(raw, content_encoding)
        return raw.decode("utf-8", errors="replace"), headers, "present"
    except urllib.error.HTTPError as error:
        code = error.code
        error_headers = {key.lower(): value for key, value in error.headers.items()} if error.headers else {}
        if code in (404, 410):
            error.close()
            return None, {}, "absent"
        try:
            raw = error.read(4096)
            raw = _best_effort_decode_content_encoding(raw, error_headers.get("content-encoding", ""))
            body = raw.decode("utf-8", errors="replace")
        except Exception:
            body = ""
        finally:
            error.close()
        classification = classify_response(code, body)
        if classification in ("blocked", "challenge"):
            how = "a bot-management challenge page" if classification == "challenge" else "a deliberate edge decision"
            server_note = f" (server: {error_headers['server']})" if error_headers.get("server") else ""
            text = (
                f"{url} returned HTTP {code}, classified as a CDN/edge {classification}{server_note}: "
                f"the edge answered with {how} rather than a generic error, so this is not confirmation "
                "the file is absent — see PER-03 for the same classification applied to root access"
            )
        else:
            text = f"{url} returned HTTP {code}"
        return text, error_headers, "unavailable"
    except Exception as error:  # timeout, DNS, TLS, redirect loop
        return f"{url} could not be fetched: {type(error).__name__}: {error}", {}, "unavailable"


def base_url(url_or_domain: str) -> str:
    value = url_or_domain.strip().rstrip("/")
    if value.lower().startswith(("https://", "http://")):
        return value
    return "https://" + value


def md_variant_url(url_or_domain: str) -> str:
    """PER-07's target: the same page with a `.md` suffix. A bare domain or
    root path has no page to suffix, so it falls back to the `index.md`
    convention rather than producing something like `https://example.com.md`."""
    parsed = urllib.parse.urlparse(base_url(url_or_domain))
    path = parsed.path or "/"
    candidate_path = f"{path}index.md" if path.endswith("/") else f"{path}.md"
    return urllib.parse.urlunparse(parsed._replace(path=candidate_path, query="", fragment=""))


def audit(
    site: str,
    robots_text: str | None,
    robots_status: str,
    llms_text: str | None,
    llms_status: str,
    llms_full_text: str | None = None,
    llms_full_status: str = "unavailable",
    sitemap_text: str | None = None,
    sitemap_status: str = "unavailable",
    md_text: str | None = None,
    md_status: str = "unavailable",
    page_results: list[dict] | None = None,
    tdmrep_data: dict | None = None,
    tdmrep_status: str = "unavailable",
    api_catalog_text: str | None = None,
    api_catalog_headers: dict[str, str] | None = None,
    api_catalog_status: str = "unavailable",
) -> dict:
    """PER-05/06/07/08/09 default to "unavailable" (or, for `page_results`,
    empty): a caller that only passes robots/llms (every test written before
    these cycles) correctly gets an honest `unknown_checks` entry for the
    newer capabilities rather than a silently fabricated result — "reduced
    coverage is reported, never hidden" applies to callers that predate a
    capability too."""
    robots_findings, robots_unknown = evaluate_robots(robots_text, robots_status)
    llms_findings, llms_unknown = evaluate_llms_txt(llms_text, llms_status)
    llms_full_findings, llms_full_unknown = evaluate_llms_full_txt(llms_full_text, llms_full_status)
    sitemap_findings, sitemap_unknown = evaluate_sitemap(sitemap_text, sitemap_status)
    md_findings, md_unknown = evaluate_md_negotiation(md_text, md_status)
    sitemap_disc_findings, sitemap_disc_unknown = evaluate_sitemap_discoverability(
        robots_text, robots_status, sitemap_status
    )
    llms_sitemap_findings, llms_sitemap_unknown = evaluate_llms_sitemap_agreement(
        llms_text, llms_status, sitemap_text, sitemap_status
    )
    contradiction_findings, contradiction_unknown = evaluate_access_contradictions(
        robots_text,
        robots_status,
        sitemap_text,
        sitemap_status,
        llms_text,
        llms_status,
        page_results or [],
        tdmrep_data,
        tdmrep_status,
    )
    api_catalog_findings, api_catalog_unknown = evaluate_api_catalog(
        api_catalog_text, api_catalog_headers, api_catalog_status
    )

    findings = (
        robots_findings
        + llms_findings
        + llms_full_findings
        + sitemap_findings
        + md_findings
        + sitemap_disc_findings
        + llms_sitemap_findings
        + contradiction_findings
        + api_catalog_findings
    )
    unknowns = (
        robots_unknown
        + llms_unknown
        + llms_full_unknown
        + sitemap_unknown
        + md_unknown
        + sitemap_disc_unknown
        + llms_sitemap_unknown
        + contradiction_unknown
        + api_catalog_unknown
    )
    return {
        "owner_skill": OWNER_SKILL,
        "capability_ids": CAPABILITY_IDS,
        "site": site,
        "findings": [f.to_dict() for f in findings],
        "unknown_checks": [u.to_dict() for u in unknowns],
    }


def _read_file(path: str) -> tuple[str, str]:
    return Path(path).read_text(encoding="utf-8", errors="replace"), "present"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="Target site; fetches /robots.txt and /llms.txt over the network")
    parser.add_argument("--site", help="Site label for the report, e.g. example.com")
    parser.add_argument("--robots-file", help="Read robots.txt from a local file instead of fetching")
    parser.add_argument("--llms-file", help="Read llms.txt from a local file instead of fetching")
    parser.add_argument("--robots-absent", action="store_true", help="Treat robots.txt as a 404")
    parser.add_argument("--llms-absent", action="store_true", help="Treat llms.txt as a 404")
    parser.add_argument("--llms-full-file", help="Read llms-full.txt from a local file instead of fetching")
    parser.add_argument("--llms-full-absent", action="store_true", help="Treat llms-full.txt as a 404")
    parser.add_argument("--sitemap-file", help="Read sitemap.xml from a local file instead of fetching")
    parser.add_argument("--sitemap-absent", action="store_true", help="Treat sitemap.xml as a 404")
    parser.add_argument("--md-file", help="Read the .md page variant from a local file instead of fetching")
    parser.add_argument("--md-absent", action="store_true", help="Treat the .md page variant as a 404")
    parser.add_argument(
        "--headers-file",
        help=(
            "PER-09 offline testing: read the root page's URL/headers/HTML from a local JSON "
            'file ({"url": ..., "headers": {...}, "html": "..."}) instead of fetching'
        ),
    )
    parser.add_argument(
        "--tdmrep-file", help="Read /.well-known/tdmrep.json from a local file instead of fetching"
    )
    parser.add_argument("--tdmrep-absent", action="store_true", help="Treat tdmrep.json as a 404")
    parser.add_argument(
        "--api-catalog-file", help="Read /.well-known/api-catalog's body from a local file instead of fetching"
    )
    parser.add_argument("--api-catalog-absent", action="store_true", help="Treat api-catalog as a 404")
    parser.add_argument(
        "--api-catalog-content-type",
        default="application/linkset+json",
        help="Content-Type to assume for --api-catalog-file (a live fetch reads the real header)",
    )
    parser.add_argument(
        "--page-url",
        action="append",
        default=[],
        help=(
            "Additional page URL to widen PER-09's X-Robots-Tag/meta-robots comparison beyond "
            "the root page (repeatable; live --url mode only)"
        ),
    )
    parser.add_argument(
        "--no-edge-probe",
        action="store_true",
        help="Skip PER-03 (CDN/edge access). PER-03 only ever runs in --url mode; this opts out of it there too.",
    )
    parser.add_argument(
        "--no-content-parity-probe",
        action="store_true",
        help="Skip PER-11 (AI-crawler content-parity diff). PER-11 only ever runs in --url mode.",
    )
    args = parser.parse_args(argv)

    if not args.url and not args.site:
        parser.error("one of --url or --site is required")

    site = site_label(args.site or args.url)

    if args.robots_file:
        robots_text, robots_status = _read_file(args.robots_file)
    elif args.robots_absent:
        robots_text, robots_status = None, "absent"
    elif args.url:
        robots_text, robots_status = fetch_text(base_url(args.url) + "/robots.txt")
    else:
        robots_text, robots_status = "robots.txt was not supplied and no --url was given", "unavailable"

    if args.llms_file:
        llms_text, llms_status = _read_file(args.llms_file)
    elif args.llms_absent:
        llms_text, llms_status = None, "absent"
    elif args.url:
        llms_text, llms_status = fetch_text(base_url(args.url) + "/llms.txt")
    else:
        llms_text, llms_status = "llms.txt was not supplied and no --url was given", "unavailable"

    if args.llms_full_file:
        llms_full_text, llms_full_status = _read_file(args.llms_full_file)
    elif args.llms_full_absent:
        llms_full_text, llms_full_status = None, "absent"
    elif args.url:
        llms_full_text, llms_full_status = fetch_text(base_url(args.url) + "/llms-full.txt")
    else:
        llms_full_text, llms_full_status = None, "unavailable"

    if args.sitemap_file:
        sitemap_text, sitemap_status = _read_file(args.sitemap_file)
        sitemap_source_url = None
    elif args.sitemap_absent:
        sitemap_text, sitemap_status = None, "absent"
        sitemap_source_url = None
    elif args.url:
        default_sitemap_url = base_url(args.url) + "/sitemap.xml"
        sitemap_text, sitemap_status = fetch_text(default_sitemap_url)
        sitemap_source_url = default_sitemap_url
        default_looks_valid = sitemap_status == "present" and _SITEMAP_ROOT_PATTERN.search(
            (sitemap_text or "")[:2000]
        )
        if sitemap_status == "absent" or (sitemap_status == "present" and not default_looks_valid):
            # scribd.com live-testing false positive: the default path is a
            # bogus/absent stub, but robots.txt names the real location.
            # One fallback fetch, only when the default path already failed
            # PER-06's own root-element check, and only if it succeeds and
            # is itself a valid sitemap — otherwise the original (failing)
            # fetch result stands and PER-06 reports it exactly as before.
            alt_url = extract_sitemap_url_from_robots(robots_text) if robots_status == "present" else None
            if alt_url:
                alt_text, alt_status = fetch_text(alt_url)
                if alt_status == "present" and _SITEMAP_ROOT_PATTERN.search((alt_text or "")[:2000]):
                    sitemap_text, sitemap_status, sitemap_source_url = alt_text, alt_status, alt_url
    else:
        sitemap_text, sitemap_status = None, "unavailable"
        sitemap_source_url = None

    if args.md_file:
        md_text, md_status = _read_file(args.md_file)
    elif args.md_absent:
        md_text, md_status = None, "absent"
    elif args.url:
        md_text, md_status = fetch_text(md_variant_url(args.url))
    else:
        md_text, md_status = None, "unavailable"

    page_results: list[dict] = []
    if args.headers_file:
        payload = json.loads(Path(args.headers_file).read_text(encoding="utf-8"))
        page_html = payload.get("html", "")
        page_results.append(
            {
                "url": payload.get("url", base_url(args.site or args.url or site)),
                "headers": {key.lower(): value for key, value in (payload.get("headers") or {}).items()},
                "meta": parse_meta_directives(page_html),
            }
        )
    elif args.url:
        root_url = base_url(args.url)
        root_text, root_headers, root_status = fetch_page_with_headers(root_url)
        if root_status in ("present", "unavailable"):
            page_results.append(
                {"url": root_url, "headers": root_headers, "meta": parse_meta_directives(root_text or "")}
            )
        for extra_url in args.page_url:
            extra_text, extra_headers, extra_status = fetch_page_with_headers(extra_url)
            if extra_status in ("present", "unavailable"):
                page_results.append(
                    {"url": extra_url, "headers": extra_headers, "meta": parse_meta_directives(extra_text or "")}
                )

    if args.tdmrep_file:
        try:
            tdmrep_data = json.loads(Path(args.tdmrep_file).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            tdmrep_data = None
        tdmrep_status = "present"
    elif args.tdmrep_absent:
        tdmrep_data, tdmrep_status = None, "absent"
    elif args.url:
        tdmrep_data, tdmrep_status = fetch_tdmrep(base_url(args.url) + "/.well-known/tdmrep.json")
    else:
        tdmrep_data, tdmrep_status = None, "unavailable"

    if args.api_catalog_file:
        api_catalog_text = Path(args.api_catalog_file).read_text(encoding="utf-8", errors="replace")
        api_catalog_headers = {"content-type": args.api_catalog_content_type}
        api_catalog_status = "present"
    elif args.api_catalog_absent:
        api_catalog_text, api_catalog_headers, api_catalog_status = None, {}, "absent"
    elif args.url:
        api_catalog_text, api_catalog_headers, api_catalog_status = fetch_page_with_headers(
            base_url(args.url) + "/.well-known/api-catalog"
        )
    else:
        api_catalog_text, api_catalog_headers, api_catalog_status = None, {}, "unavailable"

    output = audit(
        site,
        robots_text,
        robots_status,
        llms_text,
        llms_status,
        llms_full_text,
        llms_full_status,
        sitemap_text,
        sitemap_status,
        md_text,
        md_status,
        page_results,
        tdmrep_data,
        tdmrep_status,
        api_catalog_text,
        api_catalog_headers,
        api_catalog_status,
    )
    output["sitemap_source_url"] = sitemap_source_url

    if not args.url:
        output["unknown_checks"].append(
            UnknownCheck(
                "PER-03",
                OWNER_SKILL,
                "no --url given; PER-03 needs a live target and does not run against local files",
            ).to_dict()
        )
    elif args.no_edge_probe:
        output["unknown_checks"].append(
            UnknownCheck("PER-03", OWNER_SKILL, "skipped: --no-edge-probe was set").to_dict()
        )
    else:
        edge_findings, edge_unknowns, _ = fetch_and_evaluate_edge_access(base_url(args.url))
        output["findings"].extend(f.to_dict() for f in edge_findings)
        output["unknown_checks"].extend(u.to_dict() for u in edge_unknowns)

    if not args.url:
        output["unknown_checks"].append(
            UnknownCheck(
                "PER-11",
                OWNER_SKILL,
                "no --url given; PER-11 needs a live target and does not run against local files",
            ).to_dict()
        )
    elif args.no_content_parity_probe:
        output["unknown_checks"].append(
            UnknownCheck("PER-11", OWNER_SKILL, "skipped: --no-content-parity-probe was set").to_dict()
        )
    else:
        parity_findings, parity_unknowns = fetch_and_evaluate_content_parity(base_url(args.url))
        output["findings"].extend(f.to_dict() for f in parity_findings)
        output["unknown_checks"].extend(u.to_dict() for u in parity_unknowns)

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
