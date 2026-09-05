"""Unit tests for shared/public_suffix.py (PSL lookups, cycle 23 Part 1/2).

Real-PSL tests run against the actual vendored snapshot (vendor/
public_suffix_list.dat must exist for these — that file is committed, not
generated). Fallback/edge-case tests use a temp .dat file or a missing path
so they don't depend on the vendored snapshot's exact contents.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

import public_suffix  # noqa: E402
from public_suffix import registrable_domain, same_entity  # noqa: E402

VENDORED_PSL = REPO_ROOT / "vendor" / "public_suffix_list.dat"


class RealPslTests(unittest.TestCase):
    def setUp(self):
        public_suffix.clear_cache()
        self.assertTrue(VENDORED_PSL.exists(), "vendor/public_suffix_list.dat must be committed")

    def tearDown(self):
        public_suffix.clear_cache()

    def test_a_simple_com_domain(self):
        result = registrable_domain("www.example.com")
        self.assertEqual(result.public_suffix, "com")
        self.assertEqual(result.registrable_domain, "example.com")
        self.assertEqual(result.confidence, "high")

    def test_a_two_label_public_suffix_co_uk(self):
        result = registrable_domain("shop.example.co.uk")
        self.assertEqual(result.public_suffix, "co.uk")
        self.assertEqual(result.registrable_domain, "example.co.uk")

    def test_a_bare_registrable_domain_with_no_subdomain(self):
        result = registrable_domain("example.com")
        self.assertEqual(result.registrable_domain, "example.com")

    def test_a_wildcard_rule_ck(self):
        # "*.ck" makes "<anything>.ck" itself a public suffix.
        result = registrable_domain("shop.foo.ck")
        self.assertEqual(result.public_suffix, "foo.ck")
        self.assertEqual(result.registrable_domain, "shop.foo.ck")

    def test_an_exception_rule_overrides_its_wildcard_www_ck(self):
        # "!www.ck" carves an exception out of the "*.ck" wildcard: "ck" is
        # the suffix here, not "www.ck".
        result = registrable_domain("www.ck")
        self.assertEqual(result.public_suffix, "ck")
        self.assertEqual(result.registrable_domain, "www.ck")

    def test_host_is_case_and_trailing_dot_normalized(self):
        a = registrable_domain("WWW.EXAMPLE.COM.")
        b = registrable_domain("www.example.com")
        self.assertEqual(a.registrable_domain, b.registrable_domain)

    def test_same_entity_true_for_a_subdomain_pair(self):
        self.assertTrue(same_entity("status.acme.com", "acme.com"))

    def test_same_entity_false_across_different_suffixes(self):
        self.assertFalse(same_entity("acme.com", "acme.co.uk"))

    def test_same_entity_false_for_unrelated_domains(self):
        self.assertFalse(same_entity("acme.com", "widgets.com"))


class MissingFileFallbackTests(unittest.TestCase):
    def setUp(self):
        public_suffix.clear_cache()

    def tearDown(self):
        public_suffix.clear_cache()

    def test_a_missing_psl_file_degrades_to_low_confidence_not_raise(self):
        missing_path = Path("/nonexistent/does-not-exist.dat")
        result = registrable_domain("www.example.com", psl_path=missing_path)
        self.assertEqual(result.confidence, "low")
        self.assertEqual(result.registrable_domain, "example.com")

    def test_heuristic_fallback_is_naive_about_multi_label_suffixes(self):
        # Documented limitation: without the PSL, "co.uk" looks like an
        # ordinary two-label registrable domain, not a public suffix.
        missing_path = Path("/nonexistent/does-not-exist.dat")
        result = registrable_domain("shop.example.co.uk", psl_path=missing_path)
        self.assertEqual(result.registrable_domain, "co.uk")


class CustomRulesFileTests(unittest.TestCase):
    def setUp(self):
        public_suffix.clear_cache()

    def tearDown(self):
        public_suffix.clear_cache()

    def test_comments_and_blank_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            psl_path = Path(tmp) / "custom.dat"
            psl_path.write_text("// a comment\n\ncom\n\n// another\nco.uk\n", encoding="utf-8")
            result = registrable_domain("example.com", psl_path=psl_path)
            self.assertEqual(result.confidence, "high")
            self.assertEqual(result.registrable_domain, "example.com")

    def test_an_empty_host_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            psl_path = Path(tmp) / "custom.dat"
            psl_path.write_text("com\n", encoding="utf-8")
            result = registrable_domain("", psl_path=psl_path)
            self.assertIsNone(result.registrable_domain)


if __name__ == "__main__":
    unittest.main()
