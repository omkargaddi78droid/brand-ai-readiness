#!/usr/bin/env python3
"""Measure detection accuracy against the labelled corpus.

Reports true positives, false positives, false negatives, severity errors,
precision, recall and runtime — the numbers the rubric asks for, measured
rather than asserted. Exits non-zero if anything is wrong, so it doubles as a
regression gate.

Usage:
    measure_detection.py            # markdown summary
    measure_detection.py --json     # machine-readable
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


perimeter = _load("check_perimeter", "skills/perimeter-access-audit/scripts/check_perimeter.py")
orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"


def resolve_input(kind: str, value: str) -> tuple[str | None, str]:
    """Turn a corpus field into the (text, status) pair the checker takes."""
    if value == "absent":
        return None, "absent"
    if value == "unavailable":
        return f"{kind} could not be fetched: simulated transport failure", "unavailable"
    return (CORPUS / kind / value).read_text(encoding="utf-8"), "present"


def run_case(case: dict) -> dict:
    robots_text, robots_status = resolve_input("robots", case["robots"])
    llms_text, llms_status = resolve_input("llms", case["llms"])

    start = time.perf_counter()
    output = perimeter.audit("example.com", robots_text, robots_status, llms_text, llms_status)
    elapsed_ms = (time.perf_counter() - start) * 1000

    expected = {item["check_id"]: item["severity"] for item in case["expected_findings"]}
    emitted = {finding["id"]: finding["severity"] for finding in output["findings"]}

    true_positives = sorted(set(expected) & set(emitted))
    false_positives = sorted(set(emitted) - set(expected))
    false_negatives = sorted(set(expected) - set(emitted))
    severity_errors = sorted(
        f"{check_id}: expected {expected[check_id]}, got {emitted[check_id]}"
        for check_id in true_positives
        if expected[check_id] != emitted[check_id]
    )

    expected_unknown = sorted(case["expected_unknown"])
    # This corpus predates PER-05/06/07/08/10 and supplies no llms-full.txt/
    # sitemap.xml/.md/api-catalog inputs at all, so `audit()` correctly
    # reports those as `unknown` on every case via its documented default —
    # see `audit()`'s docstring. That is accurate, not a regression in what
    # this corpus was built to measure (robots.txt/llms.txt behaviour), so
    # it is filtered out here rather than forcing 23 unrelated fixture cases
    # to grow inputs for capabilities they were never designed to exercise.
    UNMEASURED_BY_THIS_CORPUS = {"PER-05", "PER-06", "PER-07", "PER-08", "PER-10"}
    emitted_unknown = sorted(
        {
            entry["capability_id"]
            for entry in output["unknown_checks"]
            if entry["capability_id"] not in UNMEASURED_BY_THIS_CORPUS
        }
    )
    unknown_errors = []
    if expected_unknown != emitted_unknown:
        unknown_errors.append(f"expected unknown {expected_unknown}, got {emitted_unknown}")

    return {
        "id": case["id"],
        "label": case["label"],
        "note": case["note"],
        "expected": expected,
        "emitted": emitted,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "severity_errors": severity_errors,
        "unknown_errors": unknown_errors,
        "elapsed_ms": elapsed_ms,
        "skill_output": output,
    }


def compose_case(result: dict) -> list[str]:
    """Every case must also survive composition into a schema-valid report."""
    import tempfile

    with tempfile.TemporaryDirectory() as workdir:
        path = Path(workdir) / "skill.json"
        path.write_text(json.dumps(result["skill_output"]), encoding="utf-8")
        report = orchestrator.compose(
            "example.com", [("perimeter-access-audit", str(path))], audited_at=FIXED_TIMESTAMP
        )
    errors = validate_floor_shape(report)
    if report["summary"]["total_findings"] != len(result["emitted"]):
        errors.append("composition changed the finding count")
    return errors


def measure() -> dict:
    corpus = json.loads((CORPUS / "cases.json").read_text(encoding="utf-8"))
    results = []
    for case in corpus["cases"]:
        result = run_case(case)
        result["report_errors"] = compose_case(result)
        results.append(result)

    totals = {
        "cases": len(results),
        "clean_cases": sum(1 for r in results if r["label"] == "clean"),
        "defect_cases": sum(1 for r in results if r["label"] == "defect"),
        "unknown_cases": sum(1 for r in results if r["label"] == "unknown"),
        "true_positives": sum(len(r["true_positives"]) for r in results),
        "false_positives": sum(len(r["false_positives"]) for r in results),
        "false_negatives": sum(len(r["false_negatives"]) for r in results),
        "severity_errors": sum(len(r["severity_errors"]) for r in results),
        "unknown_errors": sum(len(r["unknown_errors"]) for r in results),
        "report_errors": sum(len(r["report_errors"]) for r in results),
        "total_ms": sum(r["elapsed_ms"] for r in results),
        "slowest_ms": max(r["elapsed_ms"] for r in results),
    }
    tp, fp, fn = totals["true_positives"], totals["false_positives"], totals["false_negatives"]
    totals["precision"] = tp / (tp + fp) if tp + fp else 1.0
    totals["recall"] = tp / (tp + fn) if tp + fn else 1.0
    totals["clean_case_false_positives"] = sum(
        len(r["false_positives"]) for r in results if r["label"] == "clean"
    )
    return {"results": results, "totals": totals}


def render_markdown(measurement: dict) -> str:
    totals = measurement["totals"]
    lines = [
        "| Case | Label | Expected | Emitted | TP | FP | FN | ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
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
        f"Cases: {totals['cases']} "
        f"({totals['defect_cases']} defect, {totals['clean_cases']} clean, "
        f"{totals['unknown_cases']} unknown)",
        f"TP {totals['true_positives']} · FP {totals['false_positives']} · "
        f"FN {totals['false_negatives']} · severity errors {totals['severity_errors']} · "
        f"unknown errors {totals['unknown_errors']} · report errors {totals['report_errors']}",
        f"Precision {totals['precision']:.3f} · Recall {totals['recall']:.3f}",
        f"Evaluation time: {totals['total_ms']:.1f} ms for {totals['cases']} cases "
        f"(slowest case {totals['slowest_ms']:.2f} ms)",
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
    failed = (
        totals["false_positives"]
        + totals["false_negatives"]
        + totals["severity_errors"]
        + totals["unknown_errors"]
        + totals["report_errors"]
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
