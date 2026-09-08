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

    def test_third_party_contains_only_declared_packages_no_compiled_binaries(self):
        """Cycle 24: pure-Python, no-model-weights third-party packages are
        vendored (not pip-installed, not fetched at runtime) under
        third_party/. No compiled extension may sneak in, and no package
        outside the ones this project actually vendors and documents in
        third_party/VENDORED.md may appear here."""
        third_party_dir = REPO_ROOT / "third_party"
        self.assertTrue(third_party_dir.is_dir(), "third_party/ must exist")
        forbidden_suffixes = (".so", ".pyd", ".dylib")
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in third_party_dir.rglob("*")
            if path.is_file() and path.suffix in forbidden_suffixes
        ]
        self.assertEqual(offenders, [], f"third_party/ must contain no compiled binaries, found: {offenders}")

        declared_top_level = {"bs4", "soupsieve", "typing_extensions.py", "phonenumbers", "licenses", "VENDORED.md"}
        actual_top_level = {
            path.name
            for path in third_party_dir.iterdir()
            if not path.name.startswith(".") and path.name != "__pycache__"
        }
        self.assertEqual(actual_top_level, declared_top_level)

    def test_vendored_payload_stays_under_the_50mb_budget(self):
        """Cycle 24: vendoring is allowed (packages under third_party/, data
        under vendor/) provided the total payload stays well inside the
        submission's 50MB zip cap (M6) alongside everything else in the zip."""
        total_bytes = sum(
            path.stat().st_size
            for directory in (REPO_ROOT / "vendor", REPO_ROOT / "third_party")
            for path in directory.rglob("*")
            if path.is_file()
        )
        self.assertLess(total_bytes, 50 * 1024 * 1024, f"vendor/+third_party/ payload is {total_bytes} bytes")

    def test_scripts_import_no_third_party_packages(self):
        """'No third-party packages' now means 'no package that isn't
        vendored under third_party/ and declared here' — bs4/soupsieve/
        typing_extensions/phonenumbers are allowed specifically because every
        module that imports them first inserts third_party/ onto sys.path
        (see shared/html_extract.py, shared/phone_numbers.py), so they always
        resolve to the vendored copy, never an ambient pip install."""
        allowed_roots = {
            "argparse", "asyncio", "collections", "dataclasses", "datetime", "difflib", "email", "hashlib", "html",
            "importlib", "ipaddress", "json", "pathlib", "re", "socket", "sys", "tempfile",
            "time", "typing", "unittest", "urllib", "zlib", "finding_contract", "text_spans",
            "jsonld_graph", "page_fetch", "graph_metrics", "page_sample", "xml", "budget",
            "public_suffix", "fuzzy_match", "shingles", "links", "__future__", "judgement_merge",
            "html_extract", "phone_numbers",
            # Vendored under third_party/, never pip-installed — see third_party/VENDORED.md.
            "bs4", "soupsieve", "typing_extensions", "phonenumbers",
        }
        for script in list(REPO_ROOT.glob("skills/*/scripts/*.py")) + list(REPO_ROOT.glob("shared/*.py")):
            with self.subTest(script=script.name):
                for line in script.read_text(encoding="utf-8").splitlines():
                    match = re.match(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
                    if match:
                        self.assertIn(match.group(1).split(".")[0], allowed_roots, line.strip())

    def test_html_extract_and_phone_numbers_put_third_party_on_sys_path_before_importing_vendored_packages(self):
        """Guards against silently falling back to an ambient pip install of
        bs4/phonenumbers if one happens to exist in the grading environment —
        the whole point of vendoring is that the audit works identically with
        nothing installed."""
        for module_name, vendored_import in (("html_extract", "bs4"), ("phone_numbers", "phonenumbers")):
            source = (REPO_ROOT / "shared" / f"{module_name}.py").read_text(encoding="utf-8")
            path_insert_line = next(
                (i for i, line in enumerate(source.splitlines()) if '"third_party"' in line), None
            )
            import_line = next(
                (i for i, line in enumerate(source.splitlines()) if re.match(rf"^\s*(?:from|import)\s+{vendored_import}\b", line)),
                None,
            )
            self.assertIsNotNone(path_insert_line, f"{module_name}.py must insert third_party/ onto sys.path")
            self.assertIsNotNone(import_line, f"{module_name}.py must import {vendored_import}")
            self.assertLess(path_insert_line, import_line, f"{module_name}.py imports {vendored_import} before sys.path is set up")


if __name__ == "__main__":
    unittest.main()
