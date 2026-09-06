"""Packaging hygiene: the manifest and every SKILL.md must stay spec-valid.

Stdlib only — no YAML dependency — because the marketplace must be resolvable
with nothing installed.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "marketplace.json"
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KEY_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
REQUIRED_SECTIONS = ("## When to use", "## Inputs", "## Procedure", "## Output")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Minimal YAML frontmatter reader: scalars and `>` folded blocks."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError("SKILL.md must open with a `---` frontmatter fence")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise AssertionError("frontmatter is not closed with `---`") from error

    fields: dict[str, str] = {}
    index = 1
    while index < end:
        match = KEY_PATTERN.match(lines[index])
        if not match:
            index += 1
            continue
        key, value = match.group(1), match.group(2).strip()
        index += 1
        if value in (">", "|", ">-", "|-"):
            folded: list[str] = []
            while index < end and (not lines[index].strip() or lines[index].startswith((" ", "\t"))):
                folded.append(lines[index].strip())
                index += 1
            value = " ".join(part for part in folded if part)
        fields[key] = value
    return fields


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_has_the_required_top_level_fields(self):
        for key in ("name", "version", "skills"):
            self.assertIn(key, self.manifest)

    def test_exactly_one_entrypoint(self):
        entrypoints = [s for s in self.manifest["skills"] if s.get("entrypoint")]
        self.assertEqual([s["id"] for s in entrypoints], ["audit-orchestrator"])

    def test_every_listed_skill_exists_and_has_a_skill_md(self):
        for skill in self.manifest["skills"]:
            folder = REPO_ROOT / skill["path"]
            self.assertTrue(folder.is_dir(), f"{skill['path']} is missing")
            self.assertTrue((folder / "SKILL.md").is_file(), f"{skill['path']}/SKILL.md is missing")
            self.assertEqual(folder.name, skill["id"], "skill id must match its folder name")

    def test_no_skill_folder_is_left_out_of_the_manifest(self):
        listed = {skill["id"] for skill in self.manifest["skills"]}
        on_disk = {path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir()}
        self.assertEqual(on_disk, listed)

    def test_the_marketplace_needs_no_external_service_to_resolve(self):
        raw = MANIFEST_PATH.read_text(encoding="utf-8")
        self.assertNotIn("http://", raw)
        self.assertNotIn("https://", raw)


class SkillFrontmatterTests(unittest.TestCase):
    def skill_dirs(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return [REPO_ROOT / skill["path"] for skill in manifest["skills"]]

    def test_frontmatter_is_valid_for_every_skill(self):
        for folder in self.skill_dirs():
            with self.subTest(skill=folder.name):
                fields = parse_frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))

                self.assertEqual(fields.get("name"), folder.name)
                self.assertLessEqual(len(fields["name"]), 64)
                self.assertRegex(fields["name"], NAME_PATTERN)

                description = fields.get("description", "")
                self.assertTrue(description, "description is required")
                self.assertLessEqual(len(description), 1024)

                self.assertTrue(fields.get("license"), "license is required")
                self.assertTrue(fields.get("allowed-tools"), "allowed-tools must be declared")

    def test_description_names_what_the_skill_does_not_own(self):
        """MECE boundary: a skill that cannot name its exclusions has an
        undefined boundary and should not exist separately."""
        for folder in self.skill_dirs():
            with self.subTest(skill=folder.name):
                description = parse_frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))["description"]
                self.assertTrue(
                    "Not for" in description or "owns no detection" in description,
                    "description must state what the skill does not own",
                )

    def test_body_has_the_required_sections_and_stays_lean(self):
        for folder in self.skill_dirs():
            with self.subTest(skill=folder.name):
                text = (folder / "SKILL.md").read_text(encoding="utf-8")
                for section in REQUIRED_SECTIONS:
                    self.assertIn(section, text)
                self.assertLess(len(text.splitlines()), 500, "SKILL.md body must stay under 500 lines")


class SafetyTests(unittest.TestCase):
    def test_no_script_can_write_to_an_audited_site(self):
        forbidden = ("method='POST'", 'method="POST"', "data=", "requests.post", "urlopen(req, data")
        for script in REPO_ROOT.glob("skills/*/scripts/*.py"):
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                for token in forbidden:
                    self.assertNotIn(token, source, f"{script.name} looks like it can send a request body")

    def test_vendor_contains_data_only_no_code(self):
        vendor_dir = REPO_ROOT / "vendor"
        self.assertTrue(vendor_dir.is_dir(), "vendor/ must exist")
        forbidden_suffixes = (".py", ".so", ".pyd")
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in vendor_dir.rglob("*")
            if path.is_file() and path.suffix in forbidden_suffixes
        ]
        self.assertEqual(offenders, [], f"vendor/ must contain no code, found: {offenders}")

    def test_scripts_import_no_third_party_packages(self):
        allowed_roots = {
            "argparse", "collections", "dataclasses", "datetime", "difflib", "hashlib", "html",
            "importlib", "ipaddress", "json", "pathlib", "re", "socket", "sys", "tempfile",
            "time", "typing", "unittest", "urllib", "zlib", "finding_contract", "text_spans",
            "jsonld_graph", "page_fetch", "graph_metrics", "page_sample", "xml", "budget",
            "public_suffix", "fuzzy_match", "shingles", "links", "__future__",
        }
        for script in list(REPO_ROOT.glob("skills/*/scripts/*.py")) + list(REPO_ROOT.glob("shared/*.py")):
            with self.subTest(script=script.name):
                for line in script.read_text(encoding="utf-8").splitlines():
                    match = re.match(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
                    if match:
                        self.assertIn(match.group(1).split(".")[0], allowed_roots, line.strip())


if __name__ == "__main__":
    unittest.main()
