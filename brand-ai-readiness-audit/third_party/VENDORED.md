# Vendored package code

Package **code**, not data — see `vendor/VENDORED.md` for the data-only
sibling directory. `tests/test_marketplace_manifest.py`'s `SafetyTests.
test_third_party_contains_only_declared_packages_no_compiled_binaries`
enforces this directory's exact top-level contents and that it contains zero
`.so`/`.pyd`/`.dylib` files; `test_vendored_payload_stays_under_the_50mb_
budget` sums this directory plus `vendor/` against the project's 50MB
vendoring limit.

All four packages below are `py3-none-any` / `py2.py3-none-any` pure-Python
wheels — confirmed by inspecting the actual downloaded wheel contents, not
assumed from reputation. None depends on a compiled extension anywhere in
its own import chain, and none requires a pre-trained model or a runtime
network call.

## bs4 (BeautifulSoup) 4.15.0

- **Source:** PyPI, `beautifulsoup4==4.15.0`
- **License:** MIT (text: `third_party/licenses/`)
- **Why:** canonical HTML parser for `shared/html_extract.py` — `<th>`/`<td>`
  and `<dt>`/`<dd>` structural pairing (CQ-07/CQ-08) and `<main>`/`<article>`
  boundary extraction (CQ-01), replacing ad hoc regex/state-machine parsing
  for those two needs. Runs on the stdlib `html.parser` backend only — no
  `lxml`, no `html5lib` — a fixed decision independent of vendor-budget size.
- **Size:** ~820KB.

## soupsieve 2.9.2

- **Source:** PyPI, `soupsieve==2.9.2`
- **License:** MIT (text: `third_party/licenses/`)
- **Why:** bs4's own CSS-selector engine dependency (`.select()`/
  `.select_one()`); not called directly by this project's code, but required
  for bs4 to import at all.
- **Size:** ~328KB.

## typing_extensions 4.16.0

- **Source:** PyPI, `typing_extensions==4.16.0`
- **License:** PSF-2.0 (text: `third_party/licenses/`)
- **Why:** an unconditional, non-type-checking-only runtime import inside
  bs4 4.15's own `formatter.py`, `_typing.py`, `element.py`, and `dammit.py`
  — bs4 fails to import without it on any Python version, so it had to be
  vendored alongside bs4 rather than treated as a dev-only extra.
- **Size:** ~165KB. Single-file module (`typing_extensions.py`), not a
  package directory.

## phonenumbers 9.0.38

- **Source:** PyPI, `phonenumbers==9.0.38`
- **License:** Apache-2.0 (text: `third_party/licenses/`)
- **Why:** international phone-number detection/validation/E.164 formatting
  for `shared/phone_numbers.py`, wired into `static-extraction-audit`'s
  REN-10 check — replaces a NANP-only 3-3-4 regex that could never match a
  `+44 20 7946 0958`-style number.
- **Size:** ~1.4MB, trimmed down from the untrimmed wheel's 23MB. Deleted
  `geodata/` (reverse geocoding), `carrierdata/` (carrier-name lookup), and
  `.pyi` type-stub files — none of `parse()`/`is_valid_number()`/
  `format_number()` (the only three functions this project calls) touch any
  of those. Kept `data/` and `shortdata/` because `phonenumbers/__init__.py`
  eagerly imports `shortnumberinfo`, which reads from `shortdata/` at import
  time. `parse`/`is_valid_number`/`format_number` were re-run against known
  test numbers after the trim to confirm nothing needed from the deleted
  directories.

## Update process

There is no automated re-vendor script. To bump a version: download the
wheel from PyPI (`pip download --no-deps <package>==<version>`), extract it,
diff the extracted package directory against what's here, copy the new
version's files over, re-copy its `LICENSE`/`LICENSE.txt` into
`third_party/licenses/` if the license text itself changed, update the
version number and size in this file, and run the full test suite —
especially `tests/test_marketplace_manifest.py`'s `SafetyTests` (compiled-
binary and size-budget guards) and the module's own dedicated test file
(`tests/test_html_extract.py`, `tests/test_phone_numbers.py`,
`tests/test_static_extraction_audit.py`'s `NapScriptOnlyPhoneTests`,
`tests/test_content_quality.py`'s bs4-dependent tests) before committing.
