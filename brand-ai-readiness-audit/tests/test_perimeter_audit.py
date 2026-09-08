"""Fixture tests for the perimeter-access-audit skill.

Every detector is tested as a pair: a fixture that exhibits the defect, and a
fixture that looks similar but is clean. The clean fixtures are the false-
positive control, and false positives are named in the rubric, so they are not
optional garnish.
"""

import http.server
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding, validate_floor_shape  # noqa: E402


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perimeter = _load("check_perimeter", "skills/perimeter-access-audit/scripts/check_perimeter.py")
orchestrator = _load("compose_report", "skills/audit-orchestrator/scripts/compose_report.py")

FIXED_TIMESTAMP = "2026-09-20T14:32:00Z"


def robots(fixture: str) -> str:
    return (FIXTURES / "robots" / fixture).read_text(encoding="utf-8")


def llms(fixture: str) -> str:
    return (FIXTURES / "llms_txt" / fixture).read_text(encoding="utf-8")


class RobotsCleanFixtureTests(unittest.TestCase):
    """The false-positive control. None of these may produce a finding."""

    def test_allow_all_produces_nothing(self):
        findings, unknowns = perimeter.evaluate_robots(robots("allow_all.txt"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_scoped_disallow_is_not_a_site_wide_block(self):
        findings, _ = perimeter.evaluate_robots(robots("staging_path_only.txt"), "present")
        self.assertEqual(findings, [], "a Disallow on /staging/ must not read as a root block")

    def test_an_html_error_page_served_at_robots_txt_does_not_crash_or_fire(self):
        findings, unknowns = perimeter.evaluate_robots(robots("malformed.txt"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_missing_robots_txt_permits_everything(self):
        findings, unknowns = perimeter.evaluate_robots(None, "absent")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])


class RobotsDetectionTests(unittest.TestCase):
    def test_all_ai_agents_blocked_is_one_finding_not_three(self):
        findings, _ = perimeter.evaluate_robots(robots("blanket_block_ai.txt"), "present")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.capability_id, "PER-02")
        self.assertEqual(finding.severity, "critical")
        self.assertFalse(finding.structured_evidence["wildcard_blocks_root"])
        self.assertIn("while allowing conventional crawlers", finding.title)

    def test_a_site_wide_block_is_described_as_a_site_wide_block(self):
        findings, _ = perimeter.evaluate_robots(robots("site_wide_block.txt"), "present")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "PER-02")
        self.assertTrue(findings[0].structured_evidence["wildcard_blocks_root"])
        self.assertIn("every crawler", findings[0].title)

    def test_ai_search_tier_block_is_critical_and_counts_the_agents(self):
        findings, _ = perimeter.evaluate_robots(robots("ai_search_partial_block.txt"), "present")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.capability_id, "PER-01")
        self.assertEqual(finding.severity, "critical")
        self.assertEqual(finding.confidence, "high")
        self.assertEqual(sorted(finding.structured_evidence["blocked"]), ["OAI-SearchBot", "PerplexityBot"])
        self.assertIn("2/4", finding.evidence)
        self.assertIn("Still allowed in this tier", finding.evidence)

    def test_on_demand_tier_block_is_high_with_reduced_confidence(self):
        findings, _ = perimeter.evaluate_robots(robots("on_demand_block.txt"), "present")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.severity, "high")
        self.assertEqual(
            finding.confidence,
            "medium",
            "user-directed fetches are a documented grey zone; the finding must say so",
        )

    def test_training_tier_block_is_medium_not_critical(self):
        findings, _ = perimeter.evaluate_robots(robots("training_tier_block.txt"), "present")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.structured_evidence["tier"], "training")
        self.assertEqual(
            finding.severity,
            "medium",
            "blocking training crawlers is often a deliberate licensing choice, "
            "and it does not stop today's cited answers",
        )

    def test_an_unfetchable_robots_txt_is_unknown_not_pass_or_fail(self):
        findings, unknowns = perimeter.evaluate_robots("connection timed out", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual({u.capability_id for u in unknowns}, {"PER-01", "PER-02"})
        self.assertIn("connection timed out", unknowns[0].reason)


class LlmsTxtTests(unittest.TestCase):
    def test_a_valid_file_produces_nothing(self):
        findings, unknowns = perimeter.evaluate_llms_txt(llms("valid.txt"), "present")
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_a_missing_file_is_a_low_severity_proactive_suggestion(self):
        findings, _ = perimeter.evaluate_llms_txt(None, "absent")
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.capability_id, "PER-04")
        self.assertEqual(
            finding.severity,
            "low",
            "measured crawler traffic does not support calling this a defect",
        )
        self.assertEqual(finding.track, "proactive")

    def test_a_file_without_an_h1_is_flagged_with_the_specific_gap(self):
        findings, _ = perimeter.evaluate_llms_txt(llms("no_h1.txt"), "present")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["problems"], ["no H1 title line (`# Name`)"])

    def test_bare_urls_without_structure_are_flagged(self):
        findings, _ = perimeter.evaluate_llms_txt(llms("bare_links.txt"), "present")
        problems = findings[0].structured_evidence["problems"]
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("blockquote" in p for p in problems))
        self.assertTrue(any("section headings" in p for p in problems))
        self.assertTrue(any("markdown link list" in p for p in problems))

    def test_an_unfetchable_file_is_unknown(self):
        findings, unknowns = perimeter.evaluate_llms_txt("HTTP 503", "unavailable")
        self.assertEqual(findings, [])
        self.assertEqual([u.capability_id for u in unknowns], ["PER-04"])


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        cases = [
            ("blanket_block_ai.txt", "site_wide_block.txt"),
            ("ai_search_partial_block.txt", "on_demand_block.txt"),
            ("training_tier_block.txt", "allow_all.txt"),
        ]
        emitted = []
        for left, right in cases:
            for fixture in (left, right):
                emitted.extend(perimeter.evaluate_robots(robots(fixture), "present")[0])
        emitted.extend(perimeter.evaluate_llms_txt(None, "absent")[0])
        emitted.extend(perimeter.evaluate_llms_txt(llms("bare_links.txt"), "present")[0])

        self.assertTrue(emitted)
        for finding in emitted:
            self.assertEqual(finding.validate(), [], f"{finding.id} violates the contract")
            self.assertTrue(finding.evidence.rstrip().endswith(".") or "." in finding.evidence)
            self.assertEqual(finding.owner_skill, "perimeter-access-audit")
            self.assertEqual(finding.gate, 1)

    def test_evaluation_is_deterministic(self):
        first = perimeter.audit("example.com", robots("blanket_block_ai.txt"), "present", None, "absent")
        second = perimeter.audit("example.com", robots("blanket_block_ai.txt"), "present", None, "absent")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))


class EndToEndCompositionTests(unittest.TestCase):
    """Phase 2 gate: a skill runs through our interface and the entrypoint
    composes its output into a schema-valid report."""

    def _compose(self, skill_output: dict, extra_skills=()) -> dict:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "perimeter.json"
            path.write_text(json.dumps(skill_output), encoding="utf-8")
            skills = [("perimeter-access-audit", str(path))] + list(extra_skills)
            return orchestrator.compose("example.com", skills, audited_at=FIXED_TIMESTAMP)

    def test_a_blocked_site_produces_a_valid_report(self):
        skill_output = perimeter.audit(
            "example.com", robots("blanket_block_ai.txt"), "present", None, "absent"
        )
        report = self._compose(skill_output)

        self.assertEqual(validate_floor_shape(report), [])
        self.assertEqual(report["site"], "example.com")
        self.assertEqual(report["audited_at"], FIXED_TIMESTAMP)
        self.assertEqual([f["id"] for f in report["findings"]], ["F-001", "F-002"])
        self.assertEqual(report["findings"][0]["check_id"], "PER-02-all-ai-agents-blocked")
        self.assertEqual(report["summary"]["critical"], 1)
        self.assertEqual(report["summary"]["proactive_suggestions"], 1)

    def test_a_clean_site_produces_a_valid_empty_report(self):
        skill_output = perimeter.audit(
            "example.com", robots("allow_all.txt"), "present", llms("valid.txt"), "present"
        )
        report = self._compose(skill_output)
        self.assertEqual(validate_floor_shape(report), [])
        self.assertEqual(report["summary"]["total_findings"], 0)
        self.assertEqual(report["findings"], [])

    def test_a_skill_that_produced_no_output_degrades_to_unknown(self):
        skill_output = perimeter.audit(
            "example.com", robots("allow_all.txt"), "present", llms("valid.txt"), "present"
        )
        report = self._compose(skill_output, extra_skills=[("future-skill", "/nonexistent/out.json")])

        self.assertEqual(validate_floor_shape(report), [])
        unknown = [u for u in report["unknown_checks"] if u["owner_skill"] == "future-skill"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["capability_id"], "*")

    def test_a_malformed_finding_aborts_rather_than_shipping_bad_evidence(self):
        skill_output = perimeter.audit(
            "example.com", robots("blanket_block_ai.txt"), "present", None, "absent"
        )
        skill_output["findings"][0]["evidence"] = ""
        with self.assertRaises(ValueError):
            self._compose(skill_output)

    def test_the_report_carries_every_required_field_per_finding(self):
        skill_output = perimeter.audit(
            "example.com", robots("ai_search_partial_block.txt"), "present", None, "absent"
        )
        report = self._compose(skill_output)
        for finding in report["findings"]:
            for key in ("id", "title", "severity", "evidence", "suggested_action"):
                self.assertIn(key, finding)
            self.assertIn("mechanism", finding)
            restored = Finding.from_dict(finding)
            self.assertEqual(restored.validate(), [])


class _HeaderScriptedHandler(http.server.BaseHTTPRequestHandler):
    """Serves one fixed (status, headers, body) response. Local only,
    127.0.0.1, no external network — same pattern as test_edge_access.py's
    `_ScriptedHandler`, extended to send extra response headers so
    `fetch_page_with_headers` has something real to capture."""

    status = 200
    body = b"ok"
    extra_headers: dict[str, str] = {}

    def do_GET(self):  # noqa: N802 (stdlib method name)
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        for name, value in self.extra_headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass  # silence per-request stderr logging


class _HeaderLocalServer:
    def __init__(self, status: int, body: bytes, extra_headers: dict[str, str] | None = None):
        handler = type(
            "Handler",
            (_HeaderScriptedHandler,),
            {"status": status, "body": body, "extra_headers": extra_headers or {}},
        )
        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class FetchPageWithHeadersTests(unittest.TestCase):
    """PER-09's future data source. A real local HTTP server, not a mock, so
    these exercise the actual urllib round trip — same convention as
    test_edge_access.py's ProbeWithUserAgentReturnShapeTests."""

    def test_a_present_page_returns_headers_with_case_insensitive_lookup(self):
        with _HeaderLocalServer(200, b"hello", {"X-Robots-Tag": "noai"}) as server:
            text, headers, status = perimeter.fetch_page_with_headers(server.url)
        self.assertEqual(status, "present")
        self.assertEqual(text, "hello")
        # The header was sent on the wire as "X-Robots-Tag"; lookup must not
        # depend on the caller matching that exact casing.
        self.assertEqual(headers.get("x-robots-tag"), "noai")
        self.assertNotIn("X-Robots-Tag", headers, "keys must be normalized to lowercase")

    def test_404_is_absent_with_empty_headers(self):
        with _HeaderLocalServer(404, b"not found", {"X-Robots-Tag": "noai"}) as server:
            text, headers, status = perimeter.fetch_page_with_headers(server.url)
        self.assertEqual(status, "absent")
        self.assertIsNone(text)
        self.assertEqual(headers, {})

    def test_410_is_absent_with_empty_headers(self):
        with _HeaderLocalServer(410, b"gone", {"X-Robots-Tag": "noai"}) as server:
            text, headers, status = perimeter.fetch_page_with_headers(server.url)
        self.assertEqual(status, "absent")
        self.assertIsNone(text)
        self.assertEqual(headers, {})

    def test_a_non_404_http_error_is_unavailable_with_headers_populated(self):
        """The one behavior that diverges from fetch_text's pattern: a 403's
        response headers are still available on the error object and carry
        real signal (e.g. X-Robots-Tag), so they must not be discarded."""
        with _HeaderLocalServer(403, b"Forbidden", {"X-Robots-Tag": "noai"}) as server:
            text, headers, status = perimeter.fetch_page_with_headers(server.url)
        self.assertEqual(status, "unavailable")
        self.assertIsNotNone(text)
        self.assertIn("403", text)
        self.assertEqual(headers.get("x-robots-tag"), "noai")
        self.assertNotEqual(headers, {})

    def test_a_generic_fetch_failure_is_unavailable_with_empty_headers(self):
        """Connection refused (nothing listening on this port) exercises the
        generic exception branch — same unreachable-host pattern as
        test_edge_access.py's probe_with_user_agent test."""
        text, headers, status = perimeter.fetch_page_with_headers("http://127.0.0.1:1/")
        self.assertEqual(status, "unavailable")
        self.assertIsNotNone(text)
        self.assertEqual(headers, {})


class BotTaxonomyAccelerationTests(unittest.TestCase):
    """`_baseline_bot_taxonomy()` / `resolve_bot_tiers()`: the vendored
    snapshot only adds coverage, it never overrides the 15 hand-curated
    BOT_TIERS assignments, and a missing/malformed snapshot degrades to
    BOT_TIERS alone rather than raising."""

    def test_the_real_vendored_snapshot_loads(self):
        loaded = perimeter._baseline_bot_taxonomy()
        self.assertIsNotNone(loaded)
        self.assertIn("training", loaded)
        self.assertIn("ai_search", loaded)
        self.assertIn("on_demand", loaded)

    def test_a_missing_file_degrades_to_none(self):
        missing = FIXTURES / "does_not_exist.json"
        self.assertIsNone(perimeter._baseline_bot_taxonomy(path=missing))

    def test_a_malformed_file_degrades_to_none(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{not valid json")
            bad_path = Path(fh.name)
        try:
            self.assertIsNone(perimeter._baseline_bot_taxonomy(path=bad_path))
        finally:
            bad_path.unlink()

    def test_a_file_missing_the_tiers_key_degrades_to_none(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"_meta": {}}, fh)
            bad_path = Path(fh.name)
        try:
            self.assertIsNone(perimeter._baseline_bot_taxonomy(path=bad_path))
        finally:
            bad_path.unlink()

    def test_resolve_bot_tiers_falls_back_to_builtin_when_snapshot_missing(self):
        original = perimeter._baseline_bot_taxonomy
        perimeter._baseline_bot_taxonomy = lambda: None
        try:
            self.assertEqual(perimeter.resolve_bot_tiers(), perimeter.BOT_TIERS)
        finally:
            perimeter._baseline_bot_taxonomy = original

    def test_resolve_bot_tiers_preserves_original_15_curated_assignments(self):
        """Cross-check the original 15 hand-curated BOT_TIERS entries keep
        their exact tier after merging with the real vendored snapshot —
        the snapshot is additive-only, never an override, including for the
        one known divergence (DuckAssistBot: snapshot says on_demand, the
        curated baseline says ai_search, and the curated baseline must win)."""
        resolved = perimeter.resolve_bot_tiers()
        for tier, bots in perimeter.BOT_TIERS.items():
            for bot in bots:
                self.assertIn(bot, resolved[tier], f"{bot} must remain in {tier}")
        self.assertIn("DuckAssistBot", perimeter.BOT_TIERS["ai_search"])
        self.assertIn("DuckAssistBot", resolved["ai_search"])
        self.assertNotIn("DuckAssistBot", resolved["on_demand"])

    def test_resolve_bot_tiers_never_puts_the_same_bot_in_two_tiers(self):
        """Regression test for a real cross-tier duplicate found in the raw
        snapshot: "meta-externalagent" (training) and "Meta-ExternalAgent"
        (on_demand) are the same robots.txt product token under RFC 9309's
        case-insensitive matching, so they must never both survive the merge
        under two different tiers."""
        resolved = perimeter.resolve_bot_tiers()
        seen: dict[str, str] = {}
        for tier, bots in resolved.items():
            for bot in bots:
                key = bot.lower()
                self.assertNotIn(
                    key, seen, f"{bot!r} appears in both {seen.get(key)!r} and {tier!r}"
                )
                seen[key] = tier

    def test_resolve_bot_tiers_adds_new_coverage_from_the_snapshot(self):
        """The snapshot has bots the curated baseline doesn't (e.g.
        PerplexityBot is curated in ai_search already, but the snapshot adds
        many more names to each tier) — confirm the merge actually widens
        coverage rather than being a no-op."""
        resolved = perimeter.resolve_bot_tiers()
        for tier in perimeter.BOT_TIERS:
            self.assertGreater(len(resolved[tier]), len(perimeter.BOT_TIERS[tier]))


if __name__ == "__main__":
    unittest.main()
