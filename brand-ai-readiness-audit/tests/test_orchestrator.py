"""End-to-end tests for the audit-orchestrator entrypoint.

Every prior cycle's test suite exercises exactly one real skill's output
through `compose_report.py` (confirmed by grep across all nine prior call
sites before this file was written). This file is the first to compose more
than one real skill's output together, across more than one page, the way
the entrypoint's own documented Procedure actually runs in production —
closing a gap identified in an earlier orchestrator end-to-end validation
pass.

Offline and deterministic throughout: every skill function is called
in-process with inline fixture text, never over the network, matching this
project's `README.md` no-network-in-tests guarantee.
"""

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import validate_floor_shape  # noqa: E402


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")
perimeter = _load("check_perimeter", "skills/perimeter-access-audit/scripts/check_perimeter.py")
content_quality = _load(
    "check_content_quality", "skills/content-quality-audit/scripts/check_content_quality.py"
)
entity = _load("check_entity", "skills/entity-audit/scripts/check_entity.py")
engagement = _load("check_engagement", "skills/engagement-audit/scripts/check_engagement.py")

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"

# A robots.txt that blocks every known AI user agent while leaving the
# wildcard group open to conventional crawlers — PER-02, one real,
# unambiguous critical finding (same shape as
# tests/fixtures/robots/blanket_block_ai.txt).
_BLOCKING_ROBOTS = "\n".join(
    [
        "User-agent: *",
        "Disallow: /admin/",
        "",
        "User-agent: GPTBot",
        "User-agent: ClaudeBot",
        "User-agent: Google-Extended",
        "User-agent: CCBot",
        "User-agent: Applebot-Extended",
        "User-agent: meta-externalagent",
        "User-agent: Bytespider",
        "User-agent: OAI-SearchBot",
        "User-agent: PerplexityBot",
        "User-agent: Claude-SearchBot",
        "User-agent: DuckAssistBot",
        "User-agent: ChatGPT-User",
        "User-agent: Claude-User",
        "User-agent: Perplexity-User",
        "User-agent: Meta-ExternalFetcher",
        "Disallow: /",
    ]
)

# Two distinct sampled pages for content-quality-audit, which runs once per
# page rather than once per site. Page 1 carries a real CQ-05 relative-date
# defect; page 2 is clean prose with no defect at all.
_PAGE_1_TEXT = (
    "Pricing — Example Inc. We recently updated our pricing to better reflect "
    "the value we deliver to customers across every plan we offer today."
)
_PAGE_2_TEXT = (
    "Shipping Times — Example Inc. Standard shipping takes 3-5 business days "
    "within the continental US. Expedited orders ship within 1-2 business days."
)

# Minimal HTML for entity-audit: no canonical link at all, a real ENT-04
# medium finding, on a third distinct real skill.
_ENTITY_HTML = "<html><head><title>Example Inc.</title></head><body><p>Hi.</p></body></html>"


def _write(workdir: str, name: str, data: dict) -> str:
    path = Path(workdir) / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


class MultiSkillMultiPageCompositionTests(unittest.TestCase):
    """A real compose across 3 skills and 2 sampled pages for one of them —
    the shape the entrypoint's own Procedure runs in production, never
    exercised by any test before this file."""

    def _compose(self):
        perimeter_out = perimeter.audit(
            "example.com",
            _BLOCKING_ROBOTS,
            "present",
            None,
            "absent",
            llms_full_status="absent",
            sitemap_status="absent",
            md_status="absent",
            api_catalog_status="absent",
        )
        page1_out = content_quality.audit_text(
            "example.com", _PAGE_1_TEXT, page_url="https://example.com/pricing"
        )
        page2_out = content_quality.audit_text(
            "example.com", _PAGE_2_TEXT, page_url="https://example.com/shipping"
        )
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")

        # The calling Procedure resolves every agent_judgement_required entry
        # before composition; content-quality-audit always emits 5 (one per
        # agent-judged capability) and entity-audit 1 (ENT-09), regardless of
        # whether any candidate fired. Every candidate list here is empty, so
        # the correct resolution is to remove the key entirely without
        # authoring a finding.
        for out in (page1_out, page2_out, entity_out):
            for pending in out["agent_judgement_required"]:
                caps_with_candidates = pending["observations"].get("candidates")
                if caps_with_candidates:
                    raise AssertionError("fixture text unexpectedly produced a judgement candidate")
            del out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("perimeter-access-audit", _write(workdir, "perimeter.json", perimeter_out)),
                ("content-quality-audit", _write(workdir, "cq-pricing.json", page1_out)),
                ("content-quality-audit", _write(workdir, "cq-shipping.json", page2_out)),
                ("entity-audit", _write(workdir, "entity-home.json", entity_out)),
            ]
            return orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

    def test_multi_skill_multi_page_compose_is_a_valid_floor_report(self):
        report = self._compose()
        self.assertEqual(validate_floor_shape(report), [])
        self.assertEqual(report["site"], "example.com")
        self.assertEqual(report["audited_at"], FIXED_TIMESTAMP)

    def test_findings_from_every_skill_and_both_pages_are_present(self):
        report = self._compose()
        owner_skills = {f["owner_skill"] for f in report["findings"]}
        self.assertEqual(
            owner_skills, {"perimeter-access-audit", "content-quality-audit", "entity-audit"}
        )
        cq_pages = {
            f["structured_evidence"]["page_url"]
            for f in report["findings"]
            if f["owner_skill"] == "content-quality-audit"
        }
        self.assertEqual(cq_pages, {"https://example.com/pricing"})
        self.assertEqual(report["summary"]["checks_unknown"], 0)

    def test_severity_and_ordering_are_correct_across_skills_not_just_within_one(self):
        """Extends sort_findings's existing per-skill coverage: defects before
        proactive suggestions, then severity, then id — verified here on a set
        assembled from three different skills, not one skill's own findings."""
        report = self._compose()
        findings = report["findings"]

        # PER-02 (critical, defect) must lead: it is more severe than every
        # other finding in this set regardless of which skill produced it.
        self.assertEqual(findings[0]["owner_skill"], "perimeter-access-audit")
        self.assertEqual(findings[0]["severity"], "critical")

        # Ids are sequential in the same order as the sort.
        self.assertEqual([f["id"] for f in findings], [f"F-{i:03d}" for i in range(1, len(findings) + 1)])

        # Every defect sorts before every proactive suggestion, and within
        # each track severity is non-increasing — checked across the whole
        # mixed-skill list, not one skill's slice of it.
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        seen_proactive = False
        last_rank = -1
        for f in findings:
            if f["track"] == "proactive":
                seen_proactive = True
            else:
                self.assertFalse(seen_proactive, "a defect sorted after a proactive suggestion")
            rank = severity_rank[f["severity"]]
            if not seen_proactive:
                self.assertGreaterEqual(rank, last_rank)
                last_rank = rank

        self.assertGreaterEqual(len(findings), 2)


class UnresolvedJudgementAlongsideCleanSkillsTests(unittest.TestCase):
    """One skill's agent_judgement_required entry is left unresolved; several
    other skills' clean output composes alongside it without disruption."""

    def test_one_unresolved_entry_becomes_exactly_one_unknown_check(self):
        skill_with_pending_judgement = {
            "owner_skill": "engagement-audit",
            "capability_ids": ["EN-01"],
            "site": "example.com",
            "findings": [],
            "agent_judgement_required": [
                {
                    "capability_id": "EN-01",
                    "instructions": "Read the rubric and judge orientation.",
                    "observations": {"h1_text": "Welcome", "first_150_words": "..."},
                }
            ],
            "unknown_checks": [],
        }

        perimeter_out = perimeter.audit(
            "example.com",
            "User-agent: *\nAllow: /",
            "present",
            None,
            "absent",
            llms_full_status="absent",
            sitemap_status="absent",
            md_status="absent",
            api_catalog_status="absent",
        )
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        page_out = content_quality.audit_text(
            "example.com", _PAGE_2_TEXT, page_url="https://example.com/shipping"
        )
        del page_out["agent_judgement_required"]
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("perimeter-access-audit", _write(workdir, "perimeter.json", perimeter_out)),
                ("entity-audit", _write(workdir, "entity.json", entity_out)),
                ("content-quality-audit", _write(workdir, "cq.json", page_out)),
                (
                    "engagement-audit",
                    _write(workdir, "engagement.json", skill_with_pending_judgement),
                ),
            ]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertEqual(validate_floor_shape(report), [])
        self.assertEqual(report["summary"]["checks_unknown"], 1)
        self.assertEqual(len(report["unknown_checks"]), 1)
        unknown = report["unknown_checks"][0]
        self.assertEqual(unknown["capability_id"], "EN-01")
        self.assertEqual(unknown["owner_skill"], "engagement-audit")

        # The rest of composition is unaffected: entity-audit's real
        # ENT-04-missing-canonical finding still comes through untouched.
        other_owners = {f["owner_skill"] for f in report["findings"]}
        self.assertIn("entity-audit", other_owners)


class Inf08NotBuiltTests(unittest.TestCase):
    """INF-08 (cross-skill dedup) stays NOT_STARTED per this pass's own
    checked negative result: no genuine cross-skill redundancy was found in
    either of the two real composed reports produced during Part 1. This
    test documents
    that two distinct skills' findings about unrelated defects on the same
    page are never merged or suppressed — the current, correct behaviour in
    the absence of INF-08."""

    def test_two_distinct_skills_findings_on_the_same_page_both_survive(self):
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        page_out = content_quality.audit_text(
            "example.com", _PAGE_1_TEXT, page_url="https://example.com/"
        )
        del page_out["agent_judgement_required"]
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("entity-audit", _write(workdir, "entity.json", entity_out)),
                ("content-quality-audit", _write(workdir, "cq.json", page_out)),
            ]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertEqual(validate_floor_shape(report), [])
        owner_skills = [f["owner_skill"] for f in report["findings"]]
        self.assertIn("entity-audit", owner_skills)
        self.assertIn("content-quality-audit", owner_skills)
        self.assertEqual(len(report["findings"]), len(entity_out["findings"]) + len(page_out["findings"]))


class CoverageManifestMergeTests(unittest.TestCase):
    """INF-10 (cycle 23 Phase 4 follow-up): each `--sample-file` skill's own
    `coverage.stages` entry (from `shared/budget.StageBudget`) must survive
    composition into the final report, so a budget-limited stage stays
    visible in the report itself rather than only inferrable from a
    shorter-than-expected findings list."""

    def test_a_single_skills_coverage_stage_is_merged_into_the_report(self):
        service_out = entity.audit_service_domains("example.com", [])
        del service_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [("entity-audit", _write(workdir, "entity-service.json", service_out))]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertEqual(validate_floor_shape(report), [])
        self.assertEqual(len(report["coverage"]["stages"]), 1)
        self.assertEqual(report["coverage"]["stages"][0]["stage"], "entity-audit-sample-fetch")

    def test_coverage_stages_from_several_skills_are_all_present(self):
        service_out = entity.audit_service_domains("example.com", [])
        near_dup_out = content_quality.audit_near_duplicates("example.com", [])
        del service_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("entity-audit", _write(workdir, "entity-service.json", service_out)),
                ("content-quality-audit", _write(workdir, "cq-dup.json", near_dup_out)),
            ]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        stage_names = {stage["stage"] for stage in report["coverage"]["stages"]}
        self.assertEqual(stage_names, {"entity-audit-sample-fetch", "content-quality-audit-sample-fetch"})

    def test_no_coverage_anywhere_means_no_coverage_key_at_all(self):
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [("entity-audit", _write(workdir, "entity.json", entity_out))]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertNotIn("coverage", report)


class TotalElapsedSecondsTests(unittest.TestCase):
    """`--start-epoch-file` / `compose()`'s `start_epoch_file` param: the run's
    true wall-clock duration, distinct from any skill's own coverage stages."""

    def test_a_known_past_epoch_produces_the_expected_total_elapsed_seconds(self):
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [("entity-audit", _write(workdir, "entity.json", entity_out))]
            epoch_file = Path(workdir) / "start_epoch"
            epoch_file.write_text(str(int(time.time()) - 30))
            report = orchestrator.compose(
                "example.com", skills, audited_at=FIXED_TIMESTAMP, start_epoch_file=str(epoch_file)
            )

        self.assertIn("total_elapsed_seconds", report)
        self.assertAlmostEqual(report["total_elapsed_seconds"], 30.0, delta=2.0)

    def test_missing_epoch_file_omits_the_field_without_crashing(self):
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [("entity-audit", _write(workdir, "entity.json", entity_out))]
            report = orchestrator.compose(
                "example.com",
                skills,
                audited_at=FIXED_TIMESTAMP,
                start_epoch_file=str(Path(workdir) / "does-not-exist"),
            )

        self.assertNotIn("total_elapsed_seconds", report)

    def test_no_start_epoch_file_argument_omits_the_field(self):
        entity_out = entity.audit_html("example.com", _ENTITY_HTML, page_url="https://example.com/")
        del entity_out["agent_judgement_required"]

        with tempfile.TemporaryDirectory() as workdir:
            skills = [("entity-audit", _write(workdir, "entity.json", entity_out))]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertNotIn("total_elapsed_seconds", report)


_UNSIZED_IMAGES_HTML = (
    '<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
    "<body><img src=\"a.jpg\"><img src=\"b.jpg\"><img src=\"c.jpg\"><p>Hello world.</p></body></html>"
)


def _resolve_judgement(out: dict) -> None:
    for pending in out["agent_judgement_required"]:
        caps_with_candidates = pending["observations"].get("candidates")
        if caps_with_candidates:
            raise AssertionError("fixture text unexpectedly produced a judgement candidate")
    del out["agent_judgement_required"]


class PaginatedFindingMergeTests(unittest.TestCase):
    """merge_paginated_findings, exercised end-to-end through compose(): the
    real reproduction of the F-018..F-021 bug report, where the same
    engagement-audit EN-07 unsized-images check fires on several sampled
    pages of one site and used to become one report finding per page."""

    def test_the_same_check_firing_on_two_pages_becomes_one_merged_finding(self):
        page1_out = engagement.audit_html(
            "example.com", _UNSIZED_IMAGES_HTML, page_url="https://example.com/a"
        )
        page2_out = engagement.audit_html(
            "example.com", _UNSIZED_IMAGES_HTML, page_url="https://example.com/b"
        )
        _resolve_judgement(page1_out)
        _resolve_judgement(page2_out)

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("engagement-audit", _write(workdir, "en-a.json", page1_out)),
                ("engagement-audit", _write(workdir, "en-b.json", page2_out)),
            ]
            report = orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

        self.assertEqual(validate_floor_shape(report), [])
        en07 = [f for f in report["findings"] if f["check_id"] == "EN-07-unsized-images"]
        self.assertEqual(len(en07), 1)
        finding = en07[0]
        pages_mentioned = {p["page_url"] for p in finding["structured_evidence"]["pages"]}
        self.assertEqual(pages_mentioned, {"https://example.com/a", "https://example.com/b"})
        self.assertIn("Found on 2 pages:", finding["evidence"])

    def test_a_genuine_severity_mismatch_under_the_same_id_aborts_composition(self):
        page1_out = engagement.audit_html(
            "example.com", _UNSIZED_IMAGES_HTML, page_url="https://example.com/a"
        )
        page2_out = engagement.audit_html(
            "example.com", _UNSIZED_IMAGES_HTML, page_url="https://example.com/b"
        )
        _resolve_judgement(page1_out)
        _resolve_judgement(page2_out)
        # Corrupt one page's EN-07 finding to simulate an authoring bug: same
        # semantic id, genuinely different severity.
        for finding in page2_out["findings"]:
            if finding["id"] == "EN-07-unsized-images":
                finding["severity"] = "high"

        with tempfile.TemporaryDirectory() as workdir:
            skills = [
                ("engagement-audit", _write(workdir, "en-a.json", page1_out)),
                ("engagement-audit", _write(workdir, "en-b.json", page2_out)),
            ]
            with self.assertRaises(ValueError):
                orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)


if __name__ == "__main__":
    unittest.main()
