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


def find_phone_numbers(text: str, default_region: str | None = None) -> list[str]:
    """Return each distinct valid phone number found in `text`, formatted
    E.164, in first-seen order. `default_region` (an ISO 3166-1 alpha-2 code,
    e.g. "US") lets a national-format number with no country code resolve —
    without it, only numbers already carrying a `+country_code` are found,
    which is the safer default for a page whose country is unknown."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in phonenumbers.PhoneNumberMatcher(text, default_region or "ZZ"):
        if not phonenumbers.is_valid_number(match.number):
            continue
        formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
        if formatted not in seen:
            seen.add(formatted)
            ordered.append(formatted)
    return ordered
