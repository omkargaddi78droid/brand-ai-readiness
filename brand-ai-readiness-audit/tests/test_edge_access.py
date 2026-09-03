"""PER-03 (CDN/edge blocking) tests.

Everything upstream of the actual HTTP GET is pure: `classify_response`,
`plan_edge_probes`, `interpret_edge_results`. Those are tested here with fixed
inputs, no network. Only `probe_with_user_agent` and
`fetch_and_evaluate_edge_access` touch the network, and they are exercised
live in Phase 4's field validation, not in this suite.

The compliance rule under test throughout: PER-03 must never plan a probe for
an agent robots.txt already disallows.
"""

import http.server
import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_perimeter", REPO_ROOT / "skills/perimeter-access-audit/scripts/check_perimeter.py"
)
perimeter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perimeter)


class ClassifyResponseTests(unittest.TestCase):
    def test_403_is_blocked(self):
        self.assertEqual(perimeter.classify_response(403, "Forbidden"), "blocked")

    def test_429_is_blocked(self):
        self.assertEqual(perimeter.classify_response(429, "Too Many Requests"), "blocked")

    def test_200_with_ordinary_body_is_ok(self):
        self.assertEqual(perimeter.classify_response(200, "<html>Welcome</html>"), "ok")

    def test_200_with_a_challenge_page_is_challenge_not_ok(self):
        body = "<html><body>Checking your browser before accessing example.com...</body></html>"
        self.assertEqual(perimeter.classify_response(200, body), "challenge")

    def test_403_with_a_challenge_body_is_still_reported_as_challenge(self):
        # The stronger, more specific signal wins when both are present.
        body = "Access Denied - captcha-delivery.com"
        self.assertEqual(perimeter.classify_response(403, body), "challenge")

    def test_a_server_error_is_ambiguous_not_blocked(self):
        """A 500 could be a bot-specific block or an unrelated origin fault.
        Asserting a block from an ambiguous status is exactly the
        false-positive-of-severity failure this project tests against."""
        self.assertEqual(perimeter.classify_response(500, "Internal Server Error"), "ambiguous")

    def test_an_unexpected_4xx_like_402_is_ambiguous_not_blocked(self):
        """Field case (forbes.com): GPTBot got HTTP 402. Not one of the two
        codes that name a deliberate access decision, so it must not be
        asserted as a block."""
        self.assertEqual(perimeter.classify_response(402, "Payment Required"), "ambiguous")

    def test_a_redirect_is_ambiguous(self):
        self.assertEqual(perimeter.classify_response(301, ""), "ambiguous")

    def test_no_status_at_all_is_ambiguous(self):
        self.assertEqual(perimeter.classify_response(None, ""), "ambiguous")


class PlanEdgeProbesComplianceTests(unittest.TestCase):
    """The hard rule: never plan a probe for an agent robots.txt disallows."""

    def test_a_clean_site_plans_to_probe_every_tier(self):
        groups = perimeter.parse_groups("User-agent: *\nDisallow:\n")
        plan = perimeter.plan_edge_probes(groups)
        self.assertTrue(plan["probe_baseline"])
        self.assertEqual(set(plan["tiers_to_probe"]), {"training", "ai_search", "on_demand"})
        self.assertEqual(plan["tiers_skipped_by_robots"], [])

    def test_a_tier_already_blocked_by_robots_is_never_probed(self):
        groups = perimeter.parse_groups("User-agent: *\nDisallow:\n\nUser-agent: GPTBot\nDisallow: /\n")
        plan = perimeter.plan_edge_probes(groups)
        self.assertNotIn("training", plan["tiers_to_probe"])
        self.assertEqual(plan["tiers_skipped_by_robots"], ["training"])
        self.assertEqual(set(plan["tiers_to_probe"]), {"ai_search", "on_demand"})

    def test_every_tier_blocked_by_robots_plans_no_probes_at_all(self):
        blocked = "\n".join(f"User-agent: {a}\nDisallow: /" for a in perimeter.REPRESENTATIVE_AGENTS.values())
        groups = perimeter.parse_groups(f"User-agent: *\nDisallow:\n\n{blocked}\n")
        plan = perimeter.plan_edge_probes(groups)
        self.assertEqual(plan["tiers_to_probe"], {})
        self.assertEqual(set(plan["tiers_skipped_by_robots"]), set(perimeter.REPRESENTATIVE_AGENTS))

    def test_a_wildcard_root_block_skips_the_baseline_control_too(self):
        """If robots.txt disallows / for everyone, not even the reachability
        control request can be made compliantly."""
        groups = perimeter.parse_groups("User-agent: *\nDisallow: /\n")
        plan = perimeter.plan_edge_probes(groups)
        self.assertFalse(plan["probe_baseline"])
        self.assertEqual(plan["tiers_to_probe"], {})

    def test_a_scoped_disallow_does_not_suppress_probing(self):
        groups = perimeter.parse_groups("User-agent: *\nDisallow: /staging/\n")
        plan = perimeter.plan_edge_probes(groups)
        self.assertTrue(plan["probe_baseline"])
        self.assertEqual(set(plan["tiers_to_probe"]), {"training", "ai_search", "on_demand"})

    def test_no_robots_txt_at_all_plans_to_probe_everything(self):
        plan = perimeter.plan_edge_probes(perimeter.parse_groups(""))
        self.assertTrue(plan["probe_baseline"])
        self.assertEqual(len(plan["tiers_to_probe"]), 3)


class InterpretEdgeResultsTests(unittest.TestCase):
    def _plan(self, tiers=("training", "ai_search", "on_demand")):
        return {
            "probe_baseline": True,
            "tiers_to_probe": {t: perimeter.REPRESENTATIVE_AGENTS[t] for t in tiers},
            "tiers_skipped_by_robots": [],
        }

    def test_all_ok_produces_nothing(self):
        results = {"ai_search": ("ok", 200), "on_demand": ("ok", 200), "training": ("ok", 200)}
        findings, unknowns = perimeter.interpret_edge_results(self._plan(), "ok", results)
        self.assertEqual(findings, [])
        self.assertEqual(unknowns, [])

    def test_ai_search_blocked_at_the_edge_is_critical_with_high_confidence(self):
        results = {"ai_search": ("blocked", 403)}
        findings, _ = perimeter.interpret_edge_results(self._plan(["ai_search"]), "ok", results)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.capability_id, "PER-03")
        self.assertEqual(finding.severity, "critical")
        self.assertEqual(finding.confidence, "high")
        self.assertIn("OAI-SearchBot", finding.evidence)
        self.assertIn("robots.txt permits", finding.evidence)

    def test_a_challenge_page_is_reported_at_reduced_confidence(self):
        results = {"training": ("challenge", 200)}
        findings, _ = perimeter.interpret_edge_results(self._plan(["training"]), "ok", results)
        self.assertEqual(findings[0].confidence, "medium")
        self.assertEqual(findings[0].severity, "medium")  # training tier severity, unchanged by detection layer

    def test_an_ambiguous_status_is_unknown_not_a_finding(self):
        results = {"on_demand": ("ambiguous", 503)}
        findings, unknowns = perimeter.interpret_edge_results(self._plan(["on_demand"]), "ok", results)
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)
        self.assertEqual(unknowns[0].capability_id, "PER-03")

    def test_a_failed_baseline_control_yields_one_unknown_and_no_findings(self):
        """If the control itself did not succeed, an AI-bot-specific block
        cannot be distinguished from the origin being down. No finding may be
        asserted, even though agent_results below would otherwise imply one."""
        results = {"ai_search": ("blocked", 403)}
        findings, unknowns = perimeter.interpret_edge_results(self._plan(["ai_search"]), "unreachable", results)
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)

    def test_a_challenged_baseline_control_also_suppresses_findings(self):
        """Field case (two live sites, both aggressive bot-management CDNs):
        the ordinary-browser control itself gets a JS challenge, meaning
        *everyone* without a real browser is challenged, not AI bots
        specifically. Asserting an AI-bot block here would be a guaranteed
        false positive; the correct result is one unknown."""
        results = {"ai_search": ("challenge", 200), "training": ("challenge", 200)}
        findings, unknowns = perimeter.interpret_edge_results(
            self._plan(["ai_search", "training"]), "challenge", results
        )
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)

    def test_probe_baseline_false_yields_exactly_one_unknown(self):
        plan = {"probe_baseline": False, "tiers_to_probe": {}, "tiers_skipped_by_robots": []}
        findings, unknowns = perimeter.interpret_edge_results(plan, None, {})
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)
        self.assertIn("wildcard", unknowns[0].reason)

    def test_a_missing_result_for_a_planned_tier_is_unknown(self):
        findings, unknowns = perimeter.interpret_edge_results(self._plan(["training"]), "ok", {})
        self.assertEqual(findings, [])
        self.assertEqual(len(unknowns), 1)
        self.assertIn("GPTBot", unknowns[0].reason)

    def test_every_emitted_finding_satisfies_the_contract(self):
        results = {
            "ai_search": ("blocked", 403),
            "on_demand": ("challenge", 200),
        }
        findings, _ = perimeter.interpret_edge_results(self._plan(["ai_search", "on_demand"]), "ok", results)
        self.assertEqual(len(findings), 2)
        for finding in findings:
            self.assertEqual(finding.validate(), [], f"{finding.id} violates the contract")
            self.assertEqual(finding.gate, 1)
            self.assertEqual(finding.owner_skill, "perimeter-access-audit")


class _ScriptedHandler(http.server.BaseHTTPRequestHandler):
    """Serves one fixed (status, body) response per test server. Local only,
    127.0.0.1, no external network — exercises the real HTTP round trip
    without depending on any live site."""

    status = 200
    body = b"ok"

    def do_GET(self):  # noqa: N802 (stdlib method name)
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass  # silence per-request stderr logging


class _LocalServer:
    def __init__(self, status: int, body: bytes):
        handler = type("Handler", (_ScriptedHandler,), {"status": status, "body": body})
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


class ProbeWithUserAgentReturnShapeTests(unittest.TestCase):
    """Regression: a field run against nytimes.com found that the success and
    HTTPError branches returned a bare classification string instead of the
    documented `(classification, status)` tuple, so
    `baseline_classification, _ = probe_with_user_agent(...)` silently
    unpacked the string "ok" into a one-character "o". Every unit test above
    calls `interpret_edge_results` directly and could not have caught this —
    it is specific to the one impure function that touches the network. A
    local HTTP server exercises that function for real without needing the
    internet.
    """

    def test_a_200_response_returns_ok_and_the_real_status_code(self):
        with _LocalServer(200, b"hello") as server:
            result = perimeter.probe_with_user_agent(server.url, "GPTBot", timeout=5)
        self.assertEqual(result, ("ok", 200))

    def test_a_403_response_returns_blocked_and_403(self):
        with _LocalServer(403, b"Forbidden") as server:
            result = perimeter.probe_with_user_agent(server.url, "GPTBot", timeout=5)
        self.assertEqual(result, ("blocked", 403))

    def test_a_403_challenge_body_returns_challenge_and_403(self):
        with _LocalServer(403, b"Access Denied - captcha-delivery.com") as server:
            result = perimeter.probe_with_user_agent(server.url, "GPTBot", timeout=5)
        self.assertEqual(result, ("challenge", 403))

    def test_a_500_response_returns_ambiguous_and_500(self):
        with _LocalServer(500, b"boom") as server:
            result = perimeter.probe_with_user_agent(server.url, "GPTBot", timeout=5)
        self.assertEqual(result, ("ambiguous", 500))

    def test_every_branch_returns_a_two_tuple(self):
        """The precise shape bug: assert the type, not just the value, so a
        future regression to a bare string fails loudly instead of silently
        unpacking."""
        for status in (200, 403, 500):
            with _LocalServer(status, b"x") as server:
                result = perimeter.probe_with_user_agent(server.url, "GPTBot", timeout=5)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)

    def test_an_unreachable_host_returns_unreachable_and_none(self):
        result = perimeter.probe_with_user_agent("http://127.0.0.1:1/", "GPTBot", timeout=2)
        self.assertEqual(result, ("unreachable", None))


class CliWiringTests(unittest.TestCase):
    """PER-03 only ever runs in --url mode. These exercise `main()` itself,
    not the pure functions, to catch a regression in how the two are wired
    together (e.g. the flag being read but never checked)."""

    def _run(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = perimeter.main(argv)
        return exit_code, json.loads(buffer.getvalue())

    def test_offline_file_mode_reports_per_03_as_unknown(self):
        with tempfile.TemporaryDirectory() as workdir:
            robots_path = Path(workdir) / "robots.txt"
            robots_path.write_text("User-agent: *\nDisallow:\n", encoding="utf-8")
            exit_code, output = self._run(
                ["--site", "example.com", "--robots-file", str(robots_path), "--llms-absent"]
            )
        self.assertEqual(exit_code, 0)
        per03 = [u for u in output["unknown_checks"] if u["capability_id"] == "PER-03"]
        self.assertEqual(len(per03), 1)
        self.assertIn("no --url given", per03[0]["reason"])
        self.assertIn("PER-03", output["capability_ids"])

    def test_no_edge_probe_flag_reports_per_03_as_unknown_with_its_own_reason(self):
        exit_code, output = self._run(["--url", "http://127.0.0.1:1", "--no-edge-probe"])
        self.assertEqual(exit_code, 0)
        per03 = [u for u in output["unknown_checks"] if u["capability_id"] == "PER-03"]
        self.assertEqual(len(per03), 1)
        self.assertIn("--no-edge-probe", per03[0]["reason"])


class RepresentativeAgentSanityTests(unittest.TestCase):
    def test_every_representative_agent_belongs_to_its_named_tier(self):
        for tier, agent in perimeter.REPRESENTATIVE_AGENTS.items():
            self.assertIn(agent, perimeter.BOT_TIERS[tier])

    def test_the_control_user_agent_is_not_one_of_the_tracked_bots(self):
        tracked = {bot.lower() for bots in perimeter.BOT_TIERS.values() for bot in bots}
        self.assertNotIn(perimeter.CONTROL_USER_AGENT.lower(), tracked)


if __name__ == "__main__":
    unittest.main()
