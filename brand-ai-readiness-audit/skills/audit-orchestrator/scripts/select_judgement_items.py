#!/usr/bin/env python3
"""Per-skill top-N agent-judged candidate selection by rubric-declared
severity — replaces the page-based `judgement_urls`/`--judgement-cap`
mechanism formerly in sample_pages.py.

Orchestrator-only tooling: no skill's own check_*.py imports this, matching
sample_pages.py/compose_report.py's own placement. A skill run standalone
(outside the orchestrator) has no cap and must resolve every
`agent_judgement_required` candidate it produces (skill-engineering-
principles.md §5.3, "independently runnable").

Why item-based, not page-based: the old mechanism picked a fixed slice of
highest-priority PAGES and resolved every judged item on them, regardless of
how trivial those items were, while dropping every item on lower-priority
pages regardless of how severe. This picks the highest-severity ITEMS
instead, per skill, wherever they were found.

Usage:
    select_judgement_items.py --skill content-quality-audit \
        --input /tmp/audit/content-pricing.json \
        --input /tmp/audit/content-checkout.json \
        --input /tmp/audit/content-near-dup.json \
        > /tmp/audit/content-judgement-selection.json

Reads each `--input` file's own "agent_judgement_required" array (a missing
key means no candidates from that file — e.g. a page skipped past the 280s
deadline — not an error), concatenates them in argument order, and emits:

{"skill": ..., "items_total": N, "items_resolved": min(N, limit),
 "capped": items_resolved < items_total,
 "selected": [ {..raw candidate.., "_source_file": ..., "_source_index": ...} ]}

Selection is a stable sort by each candidate's capability_id severity (see
CAPABILITY_SEVERITY below), so ties keep their original --input order. Pass
--input files in the same page-priority order as sample_urls so ties break
by page priority, same as before.

"selected" candidates are tagged with _source_file/_source_index so the
calling procedure knows which of a skill's several output files each
winning candidate came from — resolve it per that skill's own SKILL.md step
3, then strip agent_judgement_required from that file afterward (via
shared/judgement_merge.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# One entry per agent-judged capability id, across the five judging skills
# (content-quality-audit, entity-audit, engagement-audit, citability-audit,
# retrieval-readiness-audit). Values are each rubric's stated severity.
#
# ENT-06, EN-08, and EN-11 are CEILINGS, not exact values — their rubrics
# cap the agent's eventual choice ("high when the page claims official
# status, medium when weaker"; "cap at medium") but don't fix one value the
# way the other 13 ids do. The actual instance severity is only known once
# an agent judges it, which is exactly what this ranking has to happen
# *before* — so the ceiling is the best available proxy. Do not "fix" these
# to look up a per-instance value; none exists pre-judgement.
CAPABILITY_SEVERITY: dict[str, str] = {
    # content-quality-audit
    "CQ-01": "medium",
    "CQ-02": "low",
    "CQ-04": "low",
    "CQ-09": "medium",
    "CQ-10": "medium",
    "CQ-12": "low",
    # entity-audit
    "ENT-05": "medium",
    "ENT-06": "high",  # ceiling
    "ENT-09": "medium",
    # engagement-audit
    "EN-01": "medium",
    "EN-03": "medium",
    "EN-08": "medium",  # ceiling
    "EN-11": "medium",  # ceiling
    # citability-audit
    "CIT-04": "medium",
    "CIT-13": "medium",
    # retrieval-readiness-audit
    "RET-02": "low",
    "RET-03": "low",
    "RET-05": "low",
    "RET-06": "low",
}

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

DEFAULT_LIMIT = 5


def candidate_severity(candidate: dict[str, Any]) -> str:
    """An unknown capability_id defaults to "low" rather than raising, so a
    newly added judged capability that forgets to update this map just sinks
    to the bottom of the ranking (visible as a lopsided `selected` list)
    instead of crashing the run."""
    return CAPABILITY_SEVERITY.get(candidate.get("capability_id", ""), "low")


def select_top_candidates(candidates: list[dict], limit: int = DEFAULT_LIMIT) -> tuple[list[dict], int]:
    """Stable sort by severity rank, then truncate. Stability means ties
    (same severity) keep the order they arrived in `candidates` — see
    gather_candidates for why that's page-priority order."""
    ranked = sorted(
        candidates,
        key=lambda c: _SEVERITY_RANK.get(candidate_severity(c), len(_SEVERITY_RANK)),
    )
    return ranked[:limit], len(candidates)


def gather_candidates(paths: list[str]) -> list[dict]:
    candidates: list[dict] = []
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for index, raw in enumerate(data.get("agent_judgement_required", [])):
            tagged = dict(raw)
            tagged["_source_file"] = path
            tagged["_source_index"] = index
            candidates.append(tagged)
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill", required=True, help="Skill name, e.g. content-quality-audit")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        dest="inputs",
        help="One of this skill's own JSON output files from this run. Repeatable; pass in "
        "sample_urls priority order so severity ties break by page priority.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Max items to resolve (default 5)")
    args = parser.parse_args(argv)

    candidates = gather_candidates(args.inputs)
    selected, total = select_top_candidates(candidates, args.limit)
    json.dump(
        {
            "skill": args.skill,
            "items_total": total,
            "items_resolved": len(selected),
            "capped": len(selected) < total,
            "selected": selected,
        },
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
