#!/usr/bin/env bash
# Builds the actual submission zip as a reproducible artifact that gets
# inspected, not guessed at.
#
# Submission shape per problem-statement.txt: "a zip of the marketplace
# root directory (containing marketplace.json and every skill folder),
# with a short README.md at the root". `shared/` is included too — it is a
# real runtime dependency every skill script and the entrypoint import via
# `sys.path.insert(0, ... / "shared")`, not optional tooling. `vendor/` is
# included for the same reason (shared/public_suffix.py's PSL data asset —
# see vendor/VENDORED.md); it is a runtime dependency, not tooling, but
# ships data only, never code (tests/test_marketplace_manifest.py enforces
# this). `third_party/` is included for the same reason — shared/html_extract.py
# and shared/phone_numbers.py import vendored bs4/phonenumbers from it at
# runtime (see third_party/VENDORED.md). `tests/` is deliberately excluded:
# it is this project's own development-time verification, not part of what
# a grader runs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO_ROOT/brand-ai-readiness-audit-submission.zip}"

cd "$REPO_ROOT"
rm -f "$OUT"

zip -r -q "$OUT" \
    marketplace.json \
    README.md \
    LICENSE \
    shared \
    skills \
    vendor \
    third_party \
    -x '*__pycache__*' -x '*.pyc' -x '*.pyo'

echo "Built: $OUT"
du -h "$OUT"
