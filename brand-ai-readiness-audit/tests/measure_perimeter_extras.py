#!/usr/bin/env python3
"""Measure PER-05/06/07/08/09 detection accuracy against their labelled corpus.

Kept separate from measure_detection.py (PER-01/02/04): that corpus's
fixtures were designed before these four capabilities existed and were never
meant to also carry llms-full.txt/sitemap.xml/.md inputs.

Usage:
    measure_perimeter_extras.py            # markdown summary
    measure_perimeter_extras.py --json     # machine-readable
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
DEFAULT_STATUS = {
    "robots_status": "present",
    "llms_full_status": "unavailable",
    "sitemap_status": "unavailable",
    "md_status": "unavailable",
}


_DEFAULT_ROBOTS_TEXT = "User-agent: *\nDisallow:\n"  # plain allow-all, so PER-01/02 never interfere
_DEFAULT_LLMS_TEXT = (  # a conforming llms.txt, so PER-04 never interferes either
    "# Example Corp\n\n> One-line summary.\n\n## Docs\n\n- [Start](https://example.com/a): begin here.\n"
)


def _load_input(inputs: dict, file_key: str, status_key: str, default_text: str | None = None) -> tuple[str | None, str]:
    status = inputs.get(status_key, DEFAULT_STATUS[status_key])
    if status == "absent" or status == "unavailable":
        return None, status
    if file_key not in inputs:
        return default_text, status
    filename = inputs[file_key]
    return (CORPUS / "perimeter_extras" / filename).read_text(encoding="utf-8"), status


def _load_page_results(inputs: dict) -> list[dict]:
    """PER-09's page_results: a JSON array of {"url", "headers", "meta"}
    fixtures. `meta.robots_tokens` is stored as a JSON list (JSON has no set
    type) and converted back to a set here, matching what
    `parse_meta_directives` returns live."""
    filename = inputs.get("page_results_file")
    if not filename:
        return []
    raw = json.loads((CORPUS / "perimeter_extras" / filename).read_text(encoding="utf-8"))
    pages = []
    for page in raw:
        meta = dict(page.get("meta") or {})
        if "robots_tokens" in meta:
            meta["robots_tokens"] = set(meta["robots_tokens"])
        pages.append({"url": page["url"], "headers": page.get("headers") or {}, "meta": meta})
    return pages


def _load_tdmrep(inputs: dict) -> tuple[dict | None, str]:
    status = inputs.get("tdmrep_status", "unavailable")
    if status != "present":
        return None, status
    filename = inputs["tdmrep_file"]
    return json.loads((CORPUS / "perimeter_extras" / filename).read_text(encoding="utf-8")), status


def run_case(case: dict) -> dict:
    inputs = case["inputs"]
    robots_text, robots_status = _load_input(inputs, "robots_file", "robots_status", _DEFAULT_ROBOTS_TEXT)
    llms_full_text, llms_full_status = _load_input(inputs, "llms_full_file", "llms_full_status")
    sitemap_text, sitemap_status = _load_input(inputs, "sitemap_file", "sitemap_status")
    md_text, md_status = _load_input(inputs, "md_file", "md_status")
    page_results = _load_page_results(inputs)
    tdmrep_data, tdmrep_status = _load_tdmrep(inputs)

    start = time.perf_counter()
    output = perimeter.audit(
        "example.com",
        robots_text,
        robots_status,
        _DEFAULT_LLMS_TEXT,
        "present",
        llms_full_text,
        llms_full_status,
        sitemap_text,
        sitemap_status,
        md_text,
        md_status,
        page_results,
        tdmrep_data,
        tdmrep_status,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    expected = set(case["expected_findings"])
    emitted = {finding["id"] for finding in output["findings"]}

    return {
        "id": case["id"],
        "label": case["label"],
        "note": case["note"],
        "expected": sorted(expected),
        "emitted": sorted(emitted),
        "true_positives": sorted(expected & emitted),
        "false_positives": sorted(emitted - expected),
        "false_negatives": sorted(expected - emitted),
        "elapsed_ms": elapsed_ms,
        "skill_output": output,
    }


def compose_case(result: dict) -> list[str]:
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
    corpus = json.loads((CORPUS / "perimeter_extras_cases.json").read_text(encoding="utf-8"))
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
