"""Report-shape helpers shared by every skill script (shared infrastructure).

`site_label`, page-stamping, and unknown-output assembly were each an
identical or near-identical private copy inside every one of the 7
`skills/*/scripts/check_*.py` files. This module is the single source of
truth; each script imports from here instead of defining its own copy.

Pure stdlib, pure data-structure processing: no network, no file I/O.
"""

from __future__ import annotations

from finding_contract import Finding, UnknownCheck


def site_label(url_or_domain: str) -> str:
    """Normalizes a `--url`/`--site` value to a bare, lowercased host: strips
    a leading scheme and any path, matching what every skill's report
    expects in its `"site"` field."""
    value = url_or_domain.strip()
    for scheme in ("https://", "http://"):
        if value.lower().startswith(scheme):
            value = value[len(scheme):]
            break
    return value.split("/")[0].strip().lower()


def stamp_page(findings: list[Finding], page_url: str | None) -> list[Finding]:
    """Prefixes each finding's evidence with its source page and records the
    page URL in structured_evidence. Every per-page skill runs once per
    page, so a report composed from several pages needs each finding
    attributable to its source page (the output-design rubric's "a
    non-expert could act on it") once the entrypoint composes findings from
    more than one page. A no-op when `page_url` is falsy."""
    if not page_url:
        return findings
    stamped = []
    for finding in findings:
        finding.evidence = f"On {page_url}: {finding.evidence}"
        finding.structured_evidence = {**(finding.structured_evidence or {}), "page_url": page_url}
        stamped.append(finding)
    return stamped


def unknown_output(
    owner_skill: str,
    capability_ids: list[str],
    site: str,
    reason: str,
    *,
    page_url: str | None = None,
    include_page_url: bool = True,
) -> dict:
    """The floor-schema report shape for "could not check anything" —
    every capability this skill owns reported as a single `unknown_checks`
    entry. `include_page_url=False` for a skill whose CLI has no per-page
    concept in this code path."""
    output: dict = {
        "owner_skill": owner_skill,
        "capability_ids": capability_ids,
        "site": site,
    }
    if include_page_url:
        output["page_url"] = page_url
    output["findings"] = []
    output["agent_judgement_required"] = []
    output["unknown_checks"] = [UnknownCheck("*", owner_skill, reason).to_dict()]
    return output
