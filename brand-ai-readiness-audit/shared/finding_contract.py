"""Normalised finding contract (INF-05).

Every skill in this marketplace emits findings in this shape. The entrypoint
skill merges them and serialises down to the competition's required report
schema with `to_floor_schema`.

The contract is a strict superset of the required schema: a finding carries the
five required fields plus the metadata the orchestrator needs to dedupe, order,
suppress, and explain findings. Nothing here reaches the network, imports a
third-party package, or reads a file.

Design decisions this file encodes, with the reason each was taken:

- `unknown` is a separate result type, not a severity. A check that could not
  run emits an `UnknownCheck` and never a finding, because a fabricated `pass`
  is a silent false negative and a fabricated `fail` is a false positive.
- `track` separates defects (a problem was observed) from proactive
  suggestions (no defect, but the change would still help). Both serialise to
  the same finding shape, so proactive items stay actionable without being
  dressed up as problems.
- `mechanism` is mandatory in practice for every emitted finding: severity has
  to be arguable from the report itself rather than asserted.
- `capability_id` names the single capability that owns the finding, so a
  duplicate id across two skills is a detectable composition bug.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low")
CATEGORIES = ("discoverability", "engagement")
TRACKS = ("defect", "proactive")
CONFIDENCES = ("high", "medium", "low")

_SEVERITY_ORDER = {name: index for index, name in enumerate(SEVERITIES)}
_CONFIDENCE_ORDER = {name: index for index, name in enumerate(("low", "medium", "high"))}


@dataclasses.dataclass
class SuggestedAction:
    """What to change and how. `summary` must name the concrete change."""

    summary: str
    priority: str
    details: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.summary or not self.summary.strip():
            errors.append("suggested_action.summary is empty")
        if self.priority not in SEVERITIES:
            errors.append(f"suggested_action.priority not in {SEVERITIES}: {self.priority!r}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"summary": self.summary, "priority": self.priority}
        if self.details:
            payload["details"] = self.details
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SuggestedAction":
        return cls(
            summary=data.get("summary", ""),
            priority=data.get("priority", ""),
            details=data.get("details"),
        )


@dataclasses.dataclass
class Finding:
    id: str
    title: str
    severity: str
    evidence: str
    suggested_action: SuggestedAction
    category: str
    capability_id: str
    owner_skill: str
    mechanism: str
    track: str = "defect"
    gate: int | None = None
    confidence: str = "high"
    structured_evidence: dict[str, Any] | None = None
    check_id: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id:
            errors.append("id is empty")
        if not self.title or not self.title.strip():
            errors.append("title is empty")
        if self.severity not in SEVERITIES:
            errors.append(f"severity not in {SEVERITIES}: {self.severity!r}")
        if not self.evidence or not self.evidence.strip():
            errors.append("evidence is empty")
        if not self.mechanism or not self.mechanism.strip():
            errors.append("mechanism is empty: severity must be arguable from the report")
        if self.category not in CATEGORIES:
            errors.append(f"category not in {CATEGORIES}: {self.category!r}")
        if self.track not in TRACKS:
            errors.append(f"track not in {TRACKS}: {self.track!r}")
        if self.confidence not in CONFIDENCES:
            errors.append(f"confidence not in {CONFIDENCES}: {self.confidence!r}")
        if not self.capability_id:
            errors.append("capability_id is empty")
        if not self.owner_skill:
            errors.append("owner_skill is empty")
        if self.gate is not None and self.gate not in (1, 2, 3):
            errors.append(f"gate must be 1, 2, 3 or None: {self.gate!r}")
        errors.extend(self.suggested_action.validate())
        return errors

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action.to_dict(),
            "category": self.category,
            "capability_id": self.capability_id,
            "owner_skill": self.owner_skill,
            "mechanism": self.mechanism,
            "track": self.track,
            "gate": self.gate,
            "confidence": self.confidence,
        }
        if self.structured_evidence is not None:
            payload["structured_evidence"] = self.structured_evidence
        if self.check_id:
            payload["check_id"] = self.check_id
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            severity=data.get("severity", ""),
            evidence=data.get("evidence", ""),
            suggested_action=SuggestedAction.from_dict(data.get("suggested_action", {})),
            category=data.get("category", ""),
            capability_id=data.get("capability_id", ""),
            owner_skill=data.get("owner_skill", ""),
            mechanism=data.get("mechanism", ""),
            track=data.get("track", "defect"),
            gate=data.get("gate"),
            confidence=data.get("confidence", "high"),
            structured_evidence=data.get("structured_evidence"),
            check_id=data.get("check_id"),
        )


@dataclasses.dataclass
class UnknownCheck:
    """A check that could not run. Reported, never silently dropped.

    `capability_id` is `"*"` when a whole skill failed and the orchestrator
    could not attribute the failure to one capability.
    """

    capability_id: str
    owner_skill: str
    reason: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.capability_id:
            errors.append("capability_id is empty")
        if not self.owner_skill:
            errors.append("owner_skill is empty")
        if not self.reason or not self.reason.strip():
            errors.append("reason is empty")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "owner_skill": self.owner_skill,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnknownCheck":
        return cls(
            capability_id=data.get("capability_id", ""),
            owner_skill=data.get("owner_skill", ""),
            reason=data.get("reason", ""),
        )


def validate_findings(findings: list[Finding]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for finding in findings:
        label = finding.id or "<no-id>"
        errors.extend(f"{label}: {message}" for message in finding.validate())
        seen[finding.id] = seen.get(finding.id, 0) + 1
    for finding_id, count in seen.items():
        if count > 1:
            errors.append(f"duplicate finding id emitted {count} times: {finding_id}")
    return errors


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Defects before proactive suggestions, then by severity, then by id.

    Deterministic: the same set of findings always orders identically.
    """
    return sorted(
        findings,
        key=lambda f: (
            0 if f.track == "defect" else 1,
            _SEVERITY_ORDER.get(f.severity, len(SEVERITIES)),
            f.id,
        ),
    )


def assign_sequential_ids(findings: list[Finding]) -> list[Finding]:
    """Renumber findings F-001, F-002, ... in report order.

    Skills emit a stable semantic id (`PER-01-ai-search-crawlers-blocked`) so a
    finding is traceable to its owning check across runs and across versions.
    The report needs short, ordered, non-expert-readable handles, so the
    semantic id moves to `check_id` and the report id becomes sequential. Same
    input set, same numbering.
    """
    renumbered: list[Finding] = []
    for index, finding in enumerate(sort_findings(findings), start=1):
        copy = dataclasses.replace(finding)
        copy.check_id = finding.check_id or finding.id
        copy.id = f"F-{index:03d}"
        renumbered.append(copy)
    return renumbered


def merge_paginated_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse same-id findings from different pages into one finding.

    A per-page check (e.g. EN-07 "unsized images") emits one `Finding` per
    page it runs on, all sharing the same semantic `id`. Left alone, that
    turns into N separate report findings for what is really one issue
    observed on N pages. This groups by `id` and merges each group of size
    > 1 into a single finding.

    Identity fields (title, severity, category, track, owner_skill,
    capability_id, mechanism, gate, suggested_action.priority) must match
    exactly across a group — a mismatch means the id was reused for
    genuinely different content, an authoring bug, and raises `ValueError`
    rather than silently picking one. Every finding in a group of size > 1
    must carry `structured_evidence["page_url"]` (i.e. went through
    `report_shape.stamp_page`) with no two members sharing a `page_url`;
    either violation also raises, since it means the duplicate isn't a
    legitimate multi-page case.

    Instance fields vary per page and are resolved deterministically:
    - `confidence` takes the weakest value present across the group.
    - `suggested_action` (summary/details) is taken from the group member
      with the lexicographically smallest `page_url`. Full per-page detail
      stays visible in `evidence` and `structured_evidence` regardless.

    Findings with a unique id pass through unchanged.
    """
    groups: dict[str, list[Finding]] = {}
    order: list[str] = []
    for finding in findings:
        if finding.id not in groups:
            groups[finding.id] = []
            order.append(finding.id)
        groups[finding.id].append(finding)

    merged: list[Finding] = []
    for finding_id in order:
        group = groups[finding_id]
        if len(group) == 1:
            merged.append(group[0])
            continue

        identity_fields = (
            "title",
            "severity",
            "category",
            "track",
            "owner_skill",
            "capability_id",
            "mechanism",
            "gate",
        )
        first = group[0]
        for field in identity_fields:
            values = {getattr(f, field) for f in group}
            if len(values) > 1:
                raise ValueError(
                    f"cannot merge findings sharing id {finding_id!r}: "
                    f"{field} differs across pages: {sorted(map(repr, values))}"
                )
        priorities = {f.suggested_action.priority for f in group}
        if len(priorities) > 1:
            raise ValueError(
                f"cannot merge findings sharing id {finding_id!r}: "
                f"suggested_action.priority differs across pages: {sorted(priorities)}"
            )

        page_urls: list[str] = []
        for f in group:
            page_url = (f.structured_evidence or {}).get("page_url")
            if not page_url:
                raise ValueError(
                    f"cannot merge findings sharing id {finding_id!r}: "
                    "a finding in the group has no structured_evidence['page_url']"
                )
            page_urls.append(page_url)
        if len(set(page_urls)) != len(page_urls):
            raise ValueError(
                f"cannot merge findings sharing id {finding_id!r}: "
                f"duplicate page_url within the group: {sorted(page_urls)}"
            )

        group_sorted = sorted(group, key=lambda f: f.structured_evidence["page_url"])
        lead_in = f"Found on {len(group_sorted)} pages:"
        merged_evidence = lead_in + "\n" + "\n".join(f"- {f.evidence}" for f in group_sorted)
        merged_structured_evidence = {
            "pages": [dict(f.structured_evidence) for f in group_sorted],
            "affected_page_count": len(group_sorted),
        }
        weakest_confidence = min(
            (f.confidence for f in group), key=lambda c: _CONFIDENCE_ORDER.get(c, len(_CONFIDENCE_ORDER))
        )
        chosen_action = group_sorted[0].suggested_action

        copy = dataclasses.replace(
            first,
            evidence=merged_evidence,
            structured_evidence=merged_structured_evidence,
            confidence=weakest_confidence,
            suggested_action=chosen_action,
        )
        merged.append(copy)
    return merged


def build_report(
    site: str,
    findings: list[Finding],
    unknown_checks: list[UnknownCheck] | None = None,
    audited_at: str | None = None,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge validated findings into the internal (superset) report.

    Raises ValueError on an invalid finding rather than emitting a malformed
    report: a broken finding is an authoring bug in the owning skill, not a
    runtime condition to paper over.

    `coverage`, when given (see shared/budget.py's `coverage_manifest`), is
    attached verbatim as `report["coverage"]` — an additive field the floor
    schema (`to_floor_schema`) does not project, so passing it never affects
    required-shape compliance.
    """
    errors = validate_findings(findings)
    for unknown in unknown_checks or []:
        errors.extend(f"unknown_check {unknown.capability_id}: {m}" for m in unknown.validate())
    if errors:
        raise ValueError("refusing to build a report from invalid findings:\n  " + "\n  ".join(errors))

    counts = {severity: 0 for severity in SEVERITIES}
    for finding in findings:
        counts[finding.severity] += 1

    ordered = sort_findings(findings)
    report: dict[str, Any] = {
        "site": site,
        "audited_at": audited_at or _utc_now(),
        "summary": {
            "total_findings": len(ordered),
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
            "defects": sum(1 for f in ordered if f.track == "defect"),
            "proactive_suggestions": sum(1 for f in ordered if f.track == "proactive"),
            "checks_unknown": len(unknown_checks or []),
        },
        "findings": [f.to_dict() for f in ordered],
        "unknown_checks": [u.to_dict() for u in (unknown_checks or [])],
    }
    if coverage is not None:
        report["coverage"] = coverage
    return report


def to_floor_schema(report: dict[str, Any]) -> dict[str, Any]:
    """Project the internal report down to exactly the required shape.

    Used to prove compliance: whatever else the report carries, this projection
    must always contain the required fields and nothing that depends on them.
    """
    return {
        "site": report["site"],
        "audited_at": report["audited_at"],
        "summary": {
            "total_findings": report["summary"]["total_findings"],
            "critical": report["summary"]["critical"],
            "high": report["summary"]["high"],
            "medium": report["summary"]["medium"],
        },
        "findings": [
            {
                "id": finding["id"],
                "title": finding["title"],
                "severity": finding["severity"],
                "evidence": finding["evidence"],
                "suggested_action": {
                    "summary": finding["suggested_action"]["summary"],
                    "priority": finding["suggested_action"]["priority"],
                },
            }
            for finding in report["findings"]
        ],
    }


def validate_floor_shape(report: dict[str, Any]) -> list[str]:
    """Structural check against the required report schema. Pure stdlib."""
    errors: list[str] = []

    for key in ("site", "audited_at", "summary", "findings"):
        if key not in report:
            errors.append(f"report is missing required key: {key}")
    if errors:
        return errors

    if not isinstance(report["site"], str) or not report["site"]:
        errors.append("site must be a non-empty string")
    if not _is_utc_timestamp(report["audited_at"]):
        errors.append(f"audited_at must be ISO-8601 UTC, e.g. 2026-09-20T14:32:00Z: {report['audited_at']!r}")

    summary = report["summary"]
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        for key in ("total_findings", "critical", "high", "medium"):
            if key not in summary:
                errors.append(f"summary is missing required key: {key}")
            elif not isinstance(summary[key], int):
                errors.append(f"summary.{key} must be an integer")

    findings = report["findings"]
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        return errors

    if isinstance(summary, dict) and summary.get("total_findings") != len(findings):
        errors.append(
            f"summary.total_findings ({summary.get('total_findings')}) "
            f"disagrees with len(findings) ({len(findings)})"
        )

    seen_ids: set[str] = set()
    for index, finding in enumerate(findings):
        where = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{where} must be an object")
            continue
        for key in ("id", "title", "severity", "evidence", "suggested_action"):
            if key not in finding:
                errors.append(f"{where} is missing required key: {key}")
        if finding.get("severity") not in SEVERITIES:
            errors.append(f"{where}.severity not in {SEVERITIES}: {finding.get('severity')!r}")
        finding_id = finding.get("id")
        if finding_id in seen_ids:
            errors.append(f"{where}.id is a duplicate: {finding_id}")
        seen_ids.add(finding_id)
        action = finding.get("suggested_action")
        if not isinstance(action, dict):
            errors.append(f"{where}.suggested_action must be an object")
        else:
            for key in ("summary", "priority"):
                if not action.get(key):
                    errors.append(f"{where}.suggested_action.{key} is missing or empty")

    if isinstance(summary, dict):
        for severity in ("critical", "high", "medium"):
            counted = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == severity)
            if summary.get(severity) != counted:
                errors.append(
                    f"summary.{severity} ({summary.get(severity)}) disagrees with the findings ({counted})"
                )

    return errors


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        _dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True
