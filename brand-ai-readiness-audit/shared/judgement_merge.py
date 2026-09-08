"""Merge agent-authored judgements into a skill's report, safely.

Every agent-judged capability (ENT-05/06/09, CQ-01/02/04/09/10/12, CIT-03,
RET-02, EN-01/11, ...) follows the same convention: the script emits
candidates under `agent_judgement_required` and never a verdict; the calling
agent judges each one against its skill's `references/*-rubric.md` and
hand-authors a `Finding` for any real defect it finds. Until now that meant
directly hand-editing the report JSON — appending to `findings`, deleting
`agent_judgement_required` — with nothing catching a malformed finding before
it corrupted the file. This module does that merge instead: every authored
judgement is validated against the `Finding` schema (INF-05) before it is
accepted, and a bad one is rejected with a precise error naming which
judgement and which field, rather than a silent bad write or a downstream
JSON parse crash.

This does not change *who* judges — the agent still reads the rubric and
decides whether a candidate is a real defect. It only makes the mechanical
step of recording that decision safe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402


class JudgementMergeError(ValueError):
    """Raised when one or more authored judgements fail Finding validation.
    Carries every error found, not just the first, so a single re-author
    pass can fix them all."""


def merge_judgements(report: dict[str, Any], judgements: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a new report dict with `judgements` (each a Finding-shaped
    dict) appended to `findings` and `agent_judgement_required` removed.
    Raises `JudgementMergeError` — naming every offending judgement and
    field — if any judgement does not validate; the input report and
    judgements are never partially applied.

    Does not mutate `report` or `judgements`.
    """
    existing_ids = {f.get("id") for f in report.get("findings", [])}
    errors: list[str] = []
    authored: list[Finding] = []

    for index, raw in enumerate(judgements):
        label = raw.get("id") or f"judgement[{index}]"
        try:
            finding = Finding.from_dict(raw)
        except Exception as exc:  # a raw dict this malformed is itself the finding
            errors.append(f"{label}: could not read as a Finding: {exc}")
            continue
        field_errors = finding.validate()
        if field_errors:
            errors.extend(f"{label}: {message}" for message in field_errors)
            continue
        if finding.id in existing_ids:
            errors.append(f"{label}: id already present in report.findings — ids must be unique")
            continue
        existing_ids.add(finding.id)
        authored.append(finding)

    if errors:
        raise JudgementMergeError(
            f"{len(errors)} judgement(s) failed validation, nothing merged:\n  " + "\n  ".join(errors)
        )

    merged = dict(report)
    merged["findings"] = [*report.get("findings", []), *(f.to_dict() for f in authored)]
    merged.pop("agent_judgement_required", None)
    return merged


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="Path to the script's JSON report")
    parser.add_argument(
        "--judgements", required=True, type=Path,
        help="Path to a JSON array of agent-authored Finding-shaped objects",
    )
    parser.add_argument("--out", type=Path, help="Write merged report here (default: stdout)")
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    judgements = json.loads(args.judgements.read_text(encoding="utf-8"))
    if not isinstance(judgements, list):
        print("--judgements must be a JSON array of Finding-shaped objects", file=sys.stderr)
        return 2

    try:
        merged = merge_judgements(report, judgements)
    except JudgementMergeError as error:
        print(str(error), file=sys.stderr)
        return 1

    output = json.dumps(merged, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
