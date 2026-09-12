"""Coverage for shared/phone_numbers.py (cycle 24 item 9): the vendored-
phonenumbers wrapper wired into static-extraction-audit's REN-10 check."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "shared"))

from phone_numbers import find_phone_numbers, find_phone_number_matches


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


class FindPhoneNumberMatchesTests(unittest.TestCase):
    """`find_phone_number_matches` is the additive wrapper REN-10's
    tracking-context filter needs; `find_phone_numbers` becomes a thin
    wrapper over it, so its own contract must stay byte-identical (covered
    above) while this class covers the new `start`/`raw_string` fields."""

    def test_returns_formatted_start_and_raw_string(self):
        text = "Call +44 20 7946 0958 for support."
        matches = find_phone_number_matches(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["formatted"], "+442079460958")
        self.assertEqual(matches[0]["raw_string"], "+44 20 7946 0958")
        self.assertEqual(text[matches[0]["start"] : matches[0]["start"] + len(matches[0]["raw_string"])], "+44 20 7946 0958")

    def test_two_distinct_numbers_are_both_found_with_increasing_offsets(self):
        text = "UK: +44 20 7946 0958. US: +1 202-555-0173."
        matches = find_phone_number_matches(text)
        self.assertEqual([m["formatted"] for m in matches], ["+442079460958", "+12025550173"])
        self.assertLess(matches[0]["start"], matches[1]["start"])

    def test_duplicate_numbers_keep_only_the_first_offset(self):
        text = "Call +44 20 7946 0958, or +44 20 7946 0958 again."
        matches = find_phone_number_matches(text)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["start"], text.index("+44"))

    def test_rejected_matches_are_absent_same_as_find_phone_numbers(self):
        self.assertEqual(
            find_phone_number_matches('"helpCenterId":3107781,"url":"https://x"', default_region="US"),
            [],
        )

    def test_no_match_returns_empty_list(self):
        self.assertEqual(find_phone_number_matches("There is no phone number here."), [])

    def test_find_phone_numbers_is_a_thin_wrapper_over_the_matches(self):
        text = "UK: +44 20 7946 0958. US: +1 202-555-0173."
        self.assertEqual(
            find_phone_numbers(text),
            [m["formatted"] for m in find_phone_number_matches(text)],
        )


if __name__ == "__main__":
    unittest.main()
