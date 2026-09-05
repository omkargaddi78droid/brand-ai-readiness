# Vendored assets

Data only — no code. `tests/test_marketplace_manifest.py`'s `SafetyTests`
enforces this: `vendor/` may contain no `.py`, `.so`, or `.pyd` file.

## public_suffix_list.dat

- **Upstream:** https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat
  (mirrors https://publicsuffix.org/list/public_suffix_list.dat, the canonical
  source; the GitHub raw URL was used only because it was reachable from this
  environment)
- **Snapshot date:** 2026-09-05
- **License:** MPL-2.0 (text: `vendor/LICENSE-public-suffix-list.txt`)
- **SHA-256:** `00dda6fa84060cca59415b5ba30bbe9d6700deb78d177f59fc83673531e30099`
- **Consumed by:** `shared/public_suffix.py`
- **Depended on by capability rows:** ENT-07 (cross-domain service
  attribution, B2, Phase 4)

`shared/public_suffix.py` loads this file lazily at first use and degrades to
a documented two-label heuristic with `confidence: low` if the file is
missing — it never raises on a missing or unreadable vendor asset.
