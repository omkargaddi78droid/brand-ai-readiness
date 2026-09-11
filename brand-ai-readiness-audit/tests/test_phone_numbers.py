"""Coverage for shared/phone_numbers.py (cycle 24 item 9): the vendored-
phonenumbers wrapper wired into static-extraction-audit's REN-10 check."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "shared"))

from phone_numbers import find_phone_numbers


class FindPhoneNumbersTests(unittest.TestCase):
    def test_an_international_e164_number_is_found(self):
        self.assertEqual(
            find_phone_numbers("Call +44 20 7946 0958 for support."),
            ["+442079460958"],
        )

    def test_no_default_region_and_no_plus_finds_nothing(self):
        """The conservative default: with no
        `default_region`, a bare national-format number carries no signal
        about which country it belongs to, so it is not matched."""
        self.assertEqual(find_phone_numbers("Call 202-555-0173 for support."), [])

    def test_a_default_region_resolves_a_national_format_number(self):
        self.assertEqual(
            find_phone_numbers("Call 202-555-0173 for support.", default_region="US"),
            ["+12025550173"],
        )

    def test_duplicates_are_deduplicated_first_seen_order(self):
        text = "Call +44 20 7946 0958, or +44 20 7946 0958 again."
        self.assertEqual(find_phone_numbers(text), ["+442079460958"])

    def test_two_distinct_numbers_are_both_found_in_document_order(self):
        text = "UK: +44 20 7946 0958. US: +1 202-555-0173."
        self.assertEqual(
            find_phone_numbers(text), ["+442079460958", "+12025550173"]
        )

    def test_an_invalid_looking_number_is_rejected(self):
        """'555-123-4567' has an invalid NANP exchange (123 is not a real
        exchange code) — a permissive regex would match it; the real
        validator correctly does not."""
        self.assertEqual(find_phone_numbers("Call 555-123-4567.", default_region="US"), [])

    def test_a_bare_local_only_number_with_no_area_code_is_rejected(self):
        """Live regression (tryhackme.com help center, 2026-09-11):
        '"helpCenterId":3107781' — a plain numeric config id with no phone
        context, no separators, and no area code — was matched as a "valid"
        NANP local-only number by libphonenumber's backward-compatibility
        allowance. Out of context that is indistinguishable from arbitrary
        short numeric literals, so it must not be reported as a found phone
        number."""
        self.assertEqual(
            find_phone_numbers('"helpCenterId":3107781,"url":"https://x"', default_region="US"),
            [],
        )

    def test_no_phone_number_in_text_returns_empty(self):
        self.assertEqual(find_phone_numbers("There is no phone number here."), [])

    def test_empty_text_returns_empty(self):
        self.assertEqual(find_phone_numbers(""), [])


if __name__ == "__main__":
    unittest.main()
