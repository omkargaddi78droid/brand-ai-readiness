#!/usr/bin/env python3
"""Merge audit-skill outputs into the single audit report.

This script composes; it never detects. Every finding in the report was
produced by an audit skill and passes through with its evidence, mechanism and
severity intact. The orchestrator's only jobs are: collect, validate, renumber,
order, count, and emit.

Failure handling: a skill whose output is missing or unparseable becomes one
`unknown_checks` entry attributed to that skill, and the report is still
produced from the skills that did run. One broken skill degrades coverage; it
does not destroy the audit. A *malformed finding*, by contrast, aborts the run
loudly — that is an authoring bug in the owning skill, and hiding it would ship
a report whose evidence cannot be trusted.

An unresolved `agent_judgement_required` entry (from a skill with agent-judged
capabilities, e.g. engagement-audit's EN-01/EN-03) becomes one `unknown_checks`
entry per capability, not a silent drop and not an error — the calling
procedure is supposed to resolve these into findings before this script ever
runs, but nothing here should crash or lose data if that step was skipped.
"Reduced coverage is reported, never hidden" applies to a judgement nobody
rendered exactly as it applies to a check that failed to run.

Usage:
    compose_report.py --site example.com \
        --skill perimeter-access-audit out/perimeter.json \
        [--skill other-skill out/other.json ...] \
        [--audited-at 2026-09-20T14:32:00Z] [--floor-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import (  # noqa: E402
    Finding,
    UnknownCheck,
    assign_sequential_ids,
    build_report,
    to_floor_schema,
    validate_floor_shape,
)


def load_skill_output(skill_name: str, path: str) -> tuple[list[Finding], list[UnknownCheck], list[dict]]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as error:
        return (
            [],
            [
                UnknownCheck(
                    capability_id="*",
                    owner_skill=skill_name,
                    reason=(
                        f"{skill_name} produced no usable output "
                        f"({type(error).__name__}: {error}); its checks were not evaluated"
                    ),
                )
            ],
            [],
        )

    findings = [Finding.from_dict(item) for item in data.get("findings", [])]
    unknowns = [UnknownCheck.from_dict(item) for item in data.get("unknown_checks", [])]
    stages = data.get("coverage", {}).get("stages", [])

    for pending in data.get("agent_judgement_required", []):
        capability_id = pending.get("capability_id", "*")
        unknowns.append(
            UnknownCheck(
                capability_id=capability_id,
                owner_skill=skill_name,
                reason=(
                    f"{capability_id} requires agent judgement and was not resolved into a "
                    "finding before composition — the calling procedure should have read "
                    "the skill's rubric and either authored a finding or dropped this entry"
                ),
            )
        )

    return findings, unknowns, stages


def compose(
    site: str,
    skill_outputs: list[tuple[str, str]],
    audited_at: str | None = None,
) -> dict:
    findings: list[Finding] = []
    unknowns: list[UnknownCheck] = []
    stages: list[dict] = []
    for skill_name, path in skill_outputs:
        skill_findings, skill_unknowns, skill_stages = load_skill_output(skill_name, path)
        findings.extend(skill_findings)
        unknowns.extend(skill_unknowns)
        stages.extend(skill_stages)

    coverage = {"stages": stages} if stages else None
    return build_report(site, assign_sequential_ids(findings), unknowns, audited_at=audited_at, coverage=coverage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, help="Site label, e.g. example.com")
    parser.add_argument(
        "--skill",
        nargs=2,
        action="append",
        metavar=("NAME", "PATH"),
        required=True,
        help="Skill name and the path to its JSON output. Repeatable.",
    )
    parser.add_argument("--audited-at", help="ISO-8601 UTC timestamp; defaults to now")
    parser.add_argument(
        "--floor-only",
        action="store_true",
        help="Emit the strict required schema instead of the full report",
    )
    args = parser.parse_args(argv)

    report = compose(args.site, [(name, path) for name, path in args.skill], args.audited_at)

    errors = validate_floor_shape(report)
    if errors:
        for error in errors:
            print(f"report validation failed: {error}", file=sys.stderr)
        return 1

    json.dump(to_floor_schema(report) if args.floor_only else report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
