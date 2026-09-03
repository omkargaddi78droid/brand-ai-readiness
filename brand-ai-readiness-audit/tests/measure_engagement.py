#!/usr/bin/env python3
"""Measure engagement-audit's two deterministic checks (EN-06, EN-09) against
the labelled corpus. EN-01/EN-03 are agent-judged and have no script verdict
to measure here.

Same reporting shape as the other measure_*.py scripts, except matching is by
ID PREFIX, not exact equality: EN-06's finding id carries a content-hash
suffix, so "EN-06-interstitial-wall-" is compared as a prefix.

Usage:
    measure_engagement.py            # markdown summary
    measure_engagement.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path(__file__).resolve().parent / "corpus"
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import validate_floor_shape  # noqa: E402


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engagement_audit = _load("check_engagement", "skills/engagement-audit/scripts/check_engagement.py")
orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"


def _match_by_prefix(expected: set[str], emitted: set[str]) -> tuple[set[str], set[str], set[str]]:
    true_positives, matched_emitted = set(), set()
    for prefix in expected:
        hit = next((e for e in emitted if e.startswith(prefix) and e not in matched_emitted), None)
        if hit:
            true_positives.add(prefix)
            matched_emitted.add(hit)
    false_negatives = expected - true_positives
    false_positives = emitted - matched_emitted
    return true_positives, false_positives, false_negatives


def run_case(case: dict) -> dict:
    html = (CORPUS / "engagement" / case["file"]).read_text(encoding="utf-8")

    start = time.perf_counter()
    output = engagement_audit.audit_html("example.com", html, page_url="https://example.com/page")
    elapsed_ms = (time.perf_counter() - start) * 1000

    expected = set(case["expected_findings"])
    emitted = {finding["id"] for finding in output["findings"]}
    true_positives, false_positives, false_negatives = _match_by_prefix(expected, emitted)

    return {
        "id": case["id"],
        "label": case["label"],
        "note": case["note"],
        "expected": sorted(expected),
        "emitted": sorted(emitted),
        "true_positives": sorted(true_positives),
        "false_positives": sorted(false_positives),
        "false_negatives": sorted(false_negatives),
        "elapsed_ms": elapsed_ms,
        "skill_output": output,
    }


def compose_case(result: dict) -> list[str]:
    import tempfile

    output = dict(result["skill_output"])
    output.pop("agent_judgement_required", None)  # intermediate; never reaches the composer

    with tempfile.TemporaryDirectory() as workdir:
        path = Path(workdir) / "skill.json"
        path.write_text(json.dumps(output), encoding="utf-8")
        report = orchestrator.compose("example.com", [("engagement-audit", str(path))], audited_at=FIXED_TIMESTAMP)
    errors = validate_floor_shape(report)
    if report["summary"]["total_findings"] != len(result["emitted"]):
        errors.append("composition changed the finding count")
    return errors


def measure() -> dict:
    corpus = json.loads((CORPUS / "engagement_cases.json").read_text(encoding="utf-8"))
    results = []
    for case in corpus["cases"]:
        result = run_case(case)
        result["report_errors"] = compose_case(result)
        results.append(result)

    totals = {
        "cases": len(results),
        "clean_cases": sum(1 for r in results if r["label"] == "clean"),
        "defect_cases": sum(1 for r in results if r["label"] == "defect"),
        "true_positives": sum(len(r["true_positives"]) for r in results),
        "false_positives": sum(len(r["false_positives"]) for r in results),
        "false_negatives": sum(len(r["false_negatives"]) for r in results),
        "report_errors": sum(len(r["report_errors"]) for r in results),
        "total_ms": sum(r["elapsed_ms"] for r in results),
        "slowest_ms": max(r["elapsed_ms"] for r in results),
    }
    tp, fp, fn = totals["true_positives"], totals["false_positives"], totals["false_negatives"]
    totals["precision"] = tp / (tp + fp) if tp + fp else 1.0
    totals["recall"] = tp / (tp + fn) if tp + fn else 1.0
    return {"results": results, "totals": totals}


def render_markdown(measurement: dict) -> str:
    totals = measurement["totals"]
    lines = ["| Case | Label | Expected | Emitted | TP | FP | FN | ms |", "|---|---|---|---|---|---|---|---|"]
    for result in measurement["results"]:
        lines.append(
            "| `{id}` | {label} | {expected} | {emitted} | {tp} | {fp} | {fn} | {ms:.2f} |".format(
                id=result["id"],
                label=result["label"],
                expected=len(result["expected"]) or "—",
                emitted=len(result["emitted"]) or "—",
                tp=len(result["true_positives"]),
                fp=len(result["false_positives"]) or "—",
                fn=len(result["false_negatives"]) or "—",
                ms=result["elapsed_ms"],
            )
        )
    lines += [
        "",
        f"Cases: {totals['cases']} ({totals['defect_cases']} defect, {totals['clean_cases']} clean)",
        f"TP {totals['true_positives']} · FP {totals['false_positives']} · "
        f"FN {totals['false_negatives']} · report errors {totals['report_errors']}",
        f"Precision {totals['precision']:.3f} · Recall {totals['recall']:.3f}",
        f"Evaluation time: {totals['total_ms']:.1f} ms for {totals['cases']} cases "
        f"(slowest case {totals['slowest_ms']:.2f} ms)",
        "",
        "EN-01/EN-03 are agent-judged and not measured by this script.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Emit measurements as JSON")
    args = parser.parse_args(argv)

    measurement = measure()
    if args.json:
        for result in measurement["results"]:
            result.pop("skill_output", None)
        json.dump(measurement, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_markdown(measurement))

    totals = measurement["totals"]
    failed = totals["false_positives"] + totals["false_negatives"] + totals["report_errors"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
