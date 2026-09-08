"""Small-graph metrics over string-keyed nodes (shared infrastructure).

Replaces `networkx` for this project's purposes — networkx was rejected over
a hard `Requires-Python` floor and a 505ms cost to import it, to buy roughly
45 lines of union-find plus power-iteration PageRank on graphs of at most a
few dozen nodes. Every graph here is a
single page's JSON-LD entity graph or a bounded page-sample's link graph —
never more than a few dozen nodes — so an O(n) union-find and a fixed
20-iteration power-iteration PageRank are not approximations of the real
algorithm's behavior, they converge exactly at this scale.

Pure stdlib, pure functions over caller-supplied node-id/edge lists: no
network, no file I/O, no third-party imports. Callers are responsible for
building the (node_ids, edges) representation from whatever domain graph
they have (a JSON-LD @id graph, a page-to-page link graph); this module
knows nothing about JSON-LD or HTML.

An edge whose endpoint is not in `node_ids` is silently ignored everywhere
in this module, rather than raising — a caller building edges from a wider
reference set than its own vertex set (e.g. a reference to something outside
the page) is a normal, expected case, not a caller bug.
"""

from __future__ import annotations


def connected_components(node_ids: list[str], edges: list[tuple[str, str]]) -> list[set[str]]:
    """Undirected connected components via union-find (path-halving,
    union-by-rank-free — these graphs are far too small for the extra
    bookkeeping to matter).

    Every id in `node_ids` appears in exactly one returned component, even
    one with no edges at all (a singleton set of just itself).
    """
    parent: dict[str, str] = {node: node for node in node_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if a not in parent or b not in parent:
            continue
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    groups: dict[str, set[str]] = {}
    for node in node_ids:
        groups.setdefault(find(node), set()).add(node)
    return list(groups.values())


def degree(node_ids: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Undirected degree: how many edges touch each node, counting an edge
    once for each of its two endpoints (a self-loop counts twice, matching
    the standard undirected-degree convention)."""
    counts = {node: 0 for node in node_ids}
    for a, b in edges:
        if a in counts:
            counts[a] += 1
        if b in counts:
            counts[b] += 1
    return counts


def pagerank(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    damping: float = 0.85,
    iterations: int = 20,
) -> dict[str, float]:
    """Directed PageRank by power iteration. `edges` are (source, target)
    pairs — rank flows from source to target, same direction as a hyperlink.

    A dangling node (no outgoing edges among `node_ids`) redistributes its
    rank evenly across every node rather than losing it, which is what
    keeps total rank conserved at 1.0 across iterations — the standard
    fix for dangling nodes in power-iteration PageRank.

    Fixed iteration count rather than a convergence-tolerance loop: at this
    project's graph sizes (bounded page samples, at most a few dozen nodes)
    20 iterations converges to well past float precision's useful range, so
    a tolerance check would only add complexity without changing the result.
    """
    n = len(node_ids)
    if n == 0:
        return {}

    outgoing: dict[str, list[str]] = {node: [] for node in node_ids}
    for source, target in edges:
        if source in outgoing and target in outgoing:
            outgoing[source].append(target)

    rank = {node: 1.0 / n for node in node_ids}
    base = (1.0 - damping) / n
    for _ in range(iterations):
        new_rank = {node: base for node in node_ids}
        for node in node_ids:
            out_links = outgoing[node]
            if not out_links:
                share = damping * rank[node] / n
                for target in node_ids:
                    new_rank[target] += share
                continue
            share = damping * rank[node] / len(out_links)
            for target in out_links:
                new_rank[target] += share
        rank = new_rank
    return rank
