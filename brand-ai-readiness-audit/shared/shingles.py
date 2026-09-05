"""K-shingle near-duplicate detection (shared infrastructure, cycle 23 Part
1/2).

Replaces the `datasketch` package rejected in docs/02-project-plan.md Part 1:
MinHash/LSH's sub-linear advantage over exact Jaccard only matters at a
document count datasketch is built for (thousands+); this project's largest
comparison set is a bounded page sample of ~30 pages (~450 pairs), where
exact shingle-set Jaccard is fast enough outright and needs no compiled
`numpy`/`scipy` transitive dependencies.

Serves B6 (near-duplicate / template-dilution detection, Phase 4): compare
main-content text — not raw page text, which is dominated by shared template
chrome (nav, footer, boilerplate) that would make every page in a site look
like a near-duplicate of every other.
"""

from __future__ import annotations

import re

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _WORD_PATTERN.findall(text.lower())


def shingle_set(text: str, k: int = 5) -> frozenset[tuple[str, ...]]:
    """The set of overlapping k-word shingles in `text`.

    Word-level, not character-level: two pages sharing a distinctive phrase
    ("30-day money-back guarantee") are a near-duplicate signal even if
    surrounding wording differs slightly, which word shingles capture and
    character shingles would dilute with mostly-identical byte runs.

    Fewer than `k` words yields a single shingle covering all of them rather
    than an empty set — a short page is still comparable, just at reduced
    resolution.
    """
    words = _tokenize(text)
    if not words:
        return frozenset()
    if len(words) < k:
        return frozenset({tuple(words)})
    return frozenset(tuple(words[i : i + k]) for i in range(len(words) - k + 1))


def jaccard_similarity(a: frozenset, b: frozenset) -> float:
    """0.0-1.0 Jaccard similarity between two shingle sets. Two empty sets
    are defined as identical (1.0) — both pages had no comparable content,
    which is a data-quality signal handled elsewhere, not a similarity of 0
    that would suggest they're maximally different."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def near_duplicate_groups(texts: list[str], *, k: int = 5, threshold: float = 0.7) -> list[list[int]]:
    """Group `texts` (by index) into near-duplicate clusters — single-linkage
    over pairwise Jaccard similarity at or above `threshold`.

    Returns clusters as lists of indices, including singleton clusters for
    texts that matched nothing. An empty-string text never joins a
    near-duplicate cluster with anything else — see `jaccard_similarity`'s
    both-empty special case, which is deliberately *not* invoked here: two
    blank pages aren't a meaningful "duplicate content" finding.
    """
    n = len(texts)
    shingles = [shingle_set(text, k=k) for text in texts]
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[max(root_i, root_j)] = min(root_i, root_j)

    for i in range(n):
        if not shingles[i]:
            continue
        for j in range(i + 1, n):
            if not shingles[j]:
                continue
            if jaccard_similarity(shingles[i], shingles[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [groups[root] for root in sorted(groups)]
