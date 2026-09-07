#!/usr/bin/env python3
"""Measure content-quality-audit detection accuracy against the labelled corpus.

Same reporting shape as measure_detection.py, applied to a single-input check
family (page text) instead of a (robots, llms) pair. See that file for the
report's field meanings.

Usage:
    measure_content_quality.py            # markdown summary
    measure_content_quality.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime
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


content_quality = _load("check_content_quality", "skills/content-quality-audit/scripts/check_content_quality.py")
orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"


def _match_by_prefix(expected: set[str], emitted: set[str]) -> tuple[set[str], set[str], set[str]]:
    """CQ-10's freshness finding id ends in a content-derived hash slug, so
    an `expected_findings` entry names its stable prefix instead of the full
    id — same convention as measure_entity.py/measure_engagement.py for
    their own hash-suffixed finding ids."""
    true_positives, matched_emitted = set(), set()
    for prefix in expected:
        hit = next((e for e in emitted if e.startswith(prefix) and e not in matched_emitted), None)
        if hit:
            true_positives.add(prefix)
            matched_emitted.add(hit)
    false_negatives = expected - true_positives
    false_positives = emitted - matched_emitted
    return true_positives, false_positives, false_negatives


def load_case_text(filename: str) -> str:
    path = CORPUS / "content" / filename
    raw = path.read_text(encoding="utf-8")
    return content_quality.extract_visible_text(raw) if path.suffix == ".html" else raw


def run_case(case: dict) -> dict:
    text = load_case_text(case["file"])
    headers = case.get("headers")
    fetched_at = datetime.fromisoformat(case["fetched_at"].replace("Z", "+00:00")) if case.get("fetched_at") else None

    start = time.perf_counter()
    output = content_quality.audit_text("example.com", text, headers=headers, fetched_at=fetched_at)
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

    with tempfile.TemporaryDirectory() as workdir:
        path = Path(workdir) / "skill.json"
        path.write_text(json.dumps(result["skill_output"]), encoding="utf-8")
        report = orchestrator.compose(
            "example.com", [("content-quality-audit", str(path))], audited_at=FIXED_TIMESTAMP
        )
    errors = validate_floor_shape(report)
    if report["summary"]["total_findings"] != len(result["emitted"]):
        errors.append("composition changed the finding count")
    return errors


def measure() -> dict:
    corpus = json.loads((CORPUS / "content_cases.json").read_text(encoding="utf-8"))
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
