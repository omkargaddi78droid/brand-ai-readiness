"""Fuzzy string similarity (shared infrastructure, cycle 23 Part 1/2).

Replaces the `rapidfuzz` package rejected in docs/02-project-plan.md Part 1:
the wheel is platform/interpreter-locked (manylinux + a specific CPython ABI
tag), and its documented pure-Python fallback is not what `pip` actually
resolves — not a safe shipping mode for a submission graded on an unknown
machine. `difflib.SequenceMatcher` is already stdlib, already imported
elsewhere in this project (INF-08's dedup groundwork), and fast enough at
this project's scale: the largest comparison set is a bounded page sample of
~30 pages (~450 pairs), not a corpus needing rapidfuzz's C-level throughput.

`token_sort_ratio` and `partial_ratio` intentionally mirror rapidfuzz's own
naming and semantics (its docs are the closest thing to a spec these two
functions have) so a reader who already knows rapidfuzz needs no translation.
"""

from __future__ import annotations

from difflib import SequenceMatcher


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() * 100


def token_sort_ratio(a: str, b: str) -> float:
    """Similarity (0-100) after tokenizing both strings on whitespace,
    sorting the tokens, and rejoining — insensitive to word order, so
    "Acme Widgets Inc" and "Inc Acme Widgets" score 100 despite the reorder.
    """
    a_sorted = " ".join(sorted(a.lower().split()))
    b_sorted = " ".join(sorted(b.lower().split()))
    return _ratio(a_sorted, b_sorted)


def partial_ratio(a: str, b: str) -> float:
    """Similarity (0-100) of the best-matching substring of the longer
    string against the shorter one — for when one string is expected to be
    fully contained in (or a near-exact substring of) the other, e.g.
    matching a short address fragment against a longer formatted address.
    """
    if not a or not b:
        return 0.0 if (a or b) else 100.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    matcher = SequenceMatcher(None, longer, shorter)
    best = 0.0
    for block in matcher.get_matching_blocks():
        start = max(0, block.a - (len(shorter) - block.size))
        end = min(len(longer), block.a + len(shorter))
        window = longer[start:end]
        best = max(best, _ratio(window, shorter))
    return best


def single_linkage_clusters(items: list[str], threshold: float, *, scorer=token_sort_ratio) -> list[list[int]]:
    """Group `items` (by index) into clusters where every member scored at
    least `threshold` against at least one other member of the same cluster
    (single-linkage, i.e. a chain of pairwise matches — not every pair within
    a cluster need score above threshold against each other directly).

    Returns clusters as lists of indices into `items`, including singleton
    clusters for items that matched nothing. Order is deterministic: clusters
    are emitted in order of their lowest member index.
    """
    n = len(items)
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
        for j in range(i + 1, n):
            if scorer(items[i], items[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [groups[root] for root in sorted(groups)]
