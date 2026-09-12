"""Unit tests for skills/audit-orchestrator/scripts/select_judgement_items.py
— the per-skill, severity-ranked judgement cap that replaced the old
page-based judgement_urls/--judgement-cap mechanism (sample_pages.py)."""

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


select_judgement_items = _load(
    "select_judgement_items", "skills/audit-orchestrator/scripts/select_judgement_items.py"
)


def _candidate(capability_id: str) -> dict:
    return {"capability_id": capability_id, "instructions": "judge me", "observations": {}}


class CandidateSeverityTests(unittest.TestCase):
    def test_uses_the_fixed_map_for_known_ids(self):
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("CQ-01")), "medium")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("CQ-02")), "low")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("EN-01")), "medium")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("CIT-04")), "medium")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("RET-02")), "low")

    def test_uses_the_ceiling_for_capped_ids(self):
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("ENT-06")), "high")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("EN-08")), "medium")
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("EN-11")), "medium")

    def test_defaults_unknown_capability_id_to_low(self):
        self.assertEqual(select_judgement_items.candidate_severity(_candidate("ZZ-99")), "low")
        self.assertEqual(select_judgement_items.candidate_severity({}), "low")


class SelectTopCandidatesTests(unittest.TestCase):
    def test_returns_top_n_and_true_total(self):
        candidates = [_candidate(cid) for cid in ["CQ-02", "ENT-06", "CQ-01", "RET-02", "CQ-12", "CQ-09", "CQ-04"]]
        selected, total = select_judgement_items.select_top_candidates(candidates, limit=5)
        self.assertEqual(len(selected), 5)
        self.assertEqual(total, 7)

    def test_orders_by_severity_high_to_low(self):
        candidates = [_candidate("CQ-02"), _candidate("ENT-06"), _candidate("CQ-01")]
        selected, _ = select_judgement_items.select_top_candidates(candidates, limit=3)
        self.assertEqual([c["capability_id"] for c in selected], ["ENT-06", "CQ-01", "CQ-02"])

    def test_stable_tie_break_preserves_input_order(self):
        candidates = [_candidate("CQ-01"), _candidate("CQ-09"), _candidate("CQ-10")]
        selected, _ = select_judgement_items.select_top_candidates(candidates, limit=3)
        self.assertEqual([c["capability_id"] for c in selected], ["CQ-01", "CQ-09", "CQ-10"])

    def test_returns_all_when_under_limit(self):
        candidates = [_candidate("CQ-01"), _candidate("CQ-02")]
        selected, total = select_judgement_items.select_top_candidates(candidates, limit=5)
        self.assertEqual(len(selected), 2)
        self.assertEqual(total, 2)


class GatherCandidatesTests(unittest.TestCase):
    def test_concatenates_files_in_argument_order_and_tags_source(self):
        with tempfile.TemporaryDirectory() as workdir:
            path_a = Path(workdir) / "a.json"
            path_b = Path(workdir) / "b.json"
            path_a.write_text(json.dumps({"agent_judgement_required": [_candidate("CQ-01"), _candidate("CQ-02")]}))
            path_b.write_text(json.dumps({"agent_judgement_required": [_candidate("CQ-04")]}))

            candidates = select_judgement_items.gather_candidates([str(path_a), str(path_b)])

        self.assertEqual(len(candidates), 3)
        self.assertEqual(candidates[0]["_source_file"], str(path_a))
        self.assertEqual(candidates[0]["_source_index"], 0)
        self.assertEqual(candidates[1]["_source_index"], 1)
        self.assertEqual(candidates[2]["_source_file"], str(path_b))
        self.assertEqual(candidates[2]["_source_index"], 0)

    def test_treats_missing_agent_judgement_required_key_as_empty(self):
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "no-candidates.json"
            path.write_text(json.dumps({"findings": []}))

            candidates = select_judgement_items.gather_candidates([str(path)])

        self.assertEqual(candidates, [])


class CliEndToEndTests(unittest.TestCase):
    def test_writes_expected_json_shape(self):
        with tempfile.TemporaryDirectory() as workdir:
            path_a = Path(workdir) / "a.json"
            path_b = Path(workdir) / "b.json"
            path_a.write_text(
                json.dumps({"agent_judgement_required": [_candidate("CQ-02"), _candidate("ENT-06")]})
            )
            path_b.write_text(json.dumps({"agent_judgement_required": [_candidate("CQ-01")]}))

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exit_code = select_judgement_items.main(
                    [
                        "--skill",
                        "content-quality-audit",
                        "--input",
                        str(path_a),
                        "--input",
                        str(path_b),
                        "--limit",
                        "2",
                    ]
                )

        self.assertEqual(exit_code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["skill"], "content-quality-audit")
        self.assertEqual(result["items_total"], 3)
        self.assertEqual(result["items_resolved"], 2)
        self.assertTrue(result["capped"])
        self.assertEqual([c["capability_id"] for c in result["selected"]], ["ENT-06", "CQ-01"])
        self.assertEqual(result["selected"][0]["_source_file"], str(path_a))
        self.assertEqual(result["selected"][1]["_source_file"], str(path_b))


if __name__ == "__main__":
    unittest.main()
