"""Public Suffix List lookups (shared infrastructure, cycle 23 Part 1/2).

Replaces the `tldextract` package rejected in docs/02-project-plan.md Part 1:
tldextract's own dependency chain pulls in `requests` (which drags in a
compiled `charset-normalizer` transitively) and fetches a live copy of the
PSL on first use, which fails outright in a sandboxed grading environment.
The actual capability need — registrable-domain grouping for ENT-07's
cross-domain service attribution (B2) — only needs the PSL *data*, not a
package: this module is under 90 lines against the vendored snapshot at
vendor/public_suffix_list.dat (see vendor/VENDORED.md for provenance).

Algorithm (the standard PSL matching rule, https://publicsuffix.org/list/):
for a hostname's labels, the public suffix is the longest matching rule,
where a `!exception` rule wins over the wildcard it exists specifically to
carve an exception out of (e.g. "!www.ck" means "ck" — not "www.ck" — is the
suffix, despite the general "*.ck" wildcard rule). Implemented by checking
candidate suffixes from longest to shortest and returning the first match,
which is exactly the longest-match rule without needing a trie.

Degrades, never raises: if the vendored .dat is missing or unreadable, falls
back to a naive last-two-labels heuristic with `confidence: "low"` — wrong
for multi-label suffixes like "co.uk", but a defensible, documented
approximation rather than a crash over a missing data file.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

_DEFAULT_PSL_PATH = Path(__file__).resolve().parent.parent / "vendor" / "public_suffix_list.dat"


@dataclasses.dataclass(frozen=True)
class _Rules:
    normal: frozenset[str]
    wildcard: frozenset[str]
    exception: frozenset[str]


@dataclasses.dataclass(frozen=True)
class SuffixResult:
    """registrable_domain is None only when `host` IS exactly a public
    suffix with no label registrable beneath it (e.g. "co.uk" itself) — an
    edge case the caller should treat as "not a real registrable site"."""

    host: str
    public_suffix: str
    registrable_domain: str | None
    confidence: str  # "high" (PSL-backed) or "low" (heuristic fallback)


_rules_cache: dict[Path, _Rules | None] = {}


def _parse_rules(text: str) -> _Rules:
    normal: set[str] = set()
    wildcard: set[str] = set()
    exception: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("//"):
            continue
        if line.startswith("!"):
            exception.add(line[1:])
        elif line.startswith("*."):
            wildcard.add(line[2:])
        else:
            normal.add(line)
    return _Rules(normal=frozenset(normal), wildcard=frozenset(wildcard), exception=frozenset(exception))


def _load_rules(psl_path: Path) -> _Rules | None:
    if psl_path in _rules_cache:
        return _rules_cache[psl_path]
    try:
        text = psl_path.read_text(encoding="utf-8")
        rules = _parse_rules(text)
    except OSError:
        rules = None
    _rules_cache[psl_path] = rules
    return rules


def clear_cache() -> None:
    """Reset the in-process parsed-rules cache. Tests call this between
    cases that use a custom `psl_path` so one test's parse can't leak into
    another's."""
    _rules_cache.clear()


def _public_suffix_labels(labels: list[str], rules: _Rules) -> list[str]:
    n = len(labels)
    for i in range(n):
        candidate = ".".join(labels[i:])
        if candidate in rules.exception:
            return labels[i + 1 :]
        if candidate in rules.normal:
            return labels[i:]
        if ".".join(labels[i + 1 :]) in rules.wildcard:
            return labels[i:]
    return labels[-1:] if labels else []


def registrable_domain(host: str, *, psl_path: Path | None = None) -> SuffixResult:
    """The registrable domain (public suffix plus one label) for `host`.

    `psl_path` overrides the vendored default — tests use this to exercise
    the missing-file fallback without touching the real vendor/ asset.
    """
    normalized = host.strip().lower().rstrip(".")
    labels = [label for label in normalized.split(".") if label]
    if not labels:
        return SuffixResult(host=host, public_suffix="", registrable_domain=None, confidence="low")

    rules = _load_rules(psl_path or _DEFAULT_PSL_PATH)
    if rules is None:
        # Naive heuristic: only the final label is treated as the suffix, so
        # the registrable domain comes out as "last two labels" — wrong for
        # a real multi-label suffix like "co.uk" (see the module docstring),
        # an accepted approximation rather than a crash over a missing file.
        suffix_labels = labels[-1:]
        confidence = "low"
    else:
        suffix_labels = _public_suffix_labels(labels, rules)
        confidence = "high"

    suffix = ".".join(suffix_labels)
    extra_labels = len(labels) - len(suffix_labels)
    registrable = ".".join(labels[extra_labels - 1 :]) if extra_labels >= 1 else None
    return SuffixResult(host=normalized, public_suffix=suffix, registrable_domain=registrable, confidence=confidence)


def same_entity(host_a: str, host_b: str, *, psl_path: Path | None = None) -> bool:
    """Whether `host_a` and `host_b` share a registrable domain — the same
    site's subdomains, not merely the same top-level suffix. "status.acme.com"
    and "acme.com" are the same entity; "acme.com" and "acme.co.uk" are not."""
    a = registrable_domain(host_a, psl_path=psl_path)
    b = registrable_domain(host_b, psl_path=psl_path)
    return a.registrable_domain is not None and a.registrable_domain == b.registrable_domain
