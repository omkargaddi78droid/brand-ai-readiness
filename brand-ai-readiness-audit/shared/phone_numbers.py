"""Vendored `phonenumbers` (Google's libphonenumber port, pure Python, no
compiled extension, no pre-trained model — see third_party/VENDORED.md) for
international phone-number detection. Replaces a NANP-only 3-3-4 regex
(`_PHONE_PATTERN` in static-extraction-audit's REN-10 check) that cannot
match `+44 20 7946 0958`-style numbers outside North America.

sys.path is extended here, once, before importing it, so it always resolves
to the vendored copy under third_party/, never an ambient pip install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "third_party"))

import phonenumbers  # noqa: E402


def find_phone_number_matches(text: str, default_region: str | None = None) -> list[dict]:
    """Like `find_phone_numbers`, but returns each match's position alongside
    its formatted number: `{"formatted": <E.164 str>, "start": <int>,
    "raw_string": <str as it appears in `text`>}`, in first-seen order,
    deduplicated by formatted number (keeping the first occurrence's
    position — same convention as RET-09's `extract_load_bearing_values`).

    Added for REN-10's tracking-context filter, which needs a match's offset
    in the *script* text to check the characters immediately preceding it —
    `find_phone_numbers`'s plain string list has nowhere to hang that."""
    seen: set[str] = set()
    ordered: list[dict] = []
    for match in phonenumbers.PhoneNumberMatcher(text, default_region or "ZZ"):
        if not phonenumbers.is_valid_number(match.number):
            continue
        # `is_valid_number` still accepts a bare local-format match (e.g. a
        # 7-digit NANP number with no area code) for backward compatibility
        # with pre-area-code dialing. Out of context that is indistinguishable
        # from an arbitrary short numeric literal (a config id, a timestamp
        # fragment) — real-world false positive: "helpCenterId":3107781 in an
        # embedded app-config JSON blob matched as a "valid" local number.
        # `is_possible_number_with_reason` names this case explicitly; reject it.
        if (
            phonenumbers.is_possible_number_with_reason(match.number)
            == phonenumbers.ValidationResult.IS_POSSIBLE_LOCAL_ONLY
        ):
            continue
        formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
        if formatted in seen:
            continue
        seen.add(formatted)
        ordered.append({"formatted": formatted, "start": match.start, "raw_string": match.raw_string})
    return ordered


def find_phone_numbers(text: str, default_region: str | None = None) -> list[str]:
    """Return each distinct valid phone number found in `text`, formatted
    E.164, in first-seen order. `default_region` (an ISO 3166-1 alpha-2 code,
    e.g. "US") lets a national-format number with no country code resolve —
    without it, only numbers already carrying a `+country_code` are found,
    which is the safer default for a page whose country is unknown."""
    return [entry["formatted"] for entry in find_phone_number_matches(text, default_region)]
