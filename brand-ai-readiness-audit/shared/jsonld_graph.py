"""JSON-LD graph flattening, indexing, and reference classification (shared
infrastructure).

ENT-11 (JSON-LD graph referential integrity), a capability being built in a
separate task, consumes this module without seeing its implementation. The
contract below — the four public functions and the `Reference` dataclass —
is everything it relies on.

This module also absorbs a genuine triplication: three skills
(`entity-audit`, `retrieval-readiness-audit`, `static-extraction-audit`)
each contain an identical private `_flatten_json_ld` function plus an
identical parse-and-skip wrapper around it. `flatten` below replicates that
combined behavior exactly. The three existing skill scripts are left
untouched by this task; only `entity-audit`'s call sites are migrated to
this module, and only in a later, separate task.

Pure stdlib, pure data-structure processing on already-parsed JSON: no
network, no file I/O, no third-party imports, no browser/DOM/JS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator
from urllib.parse import urlsplit


@dataclass
class Reference:
    source_node_id: str | None
    property_path: str
    target_id: str
    is_bare_uri: bool


_ENTITY_VALUED_PROPERTIES = {
    "brand",
    "publisher",
    "author",
    "provider",
    "seller",
    "manufacturer",
    "parentOrganization",
    "isPartOf",
    "mainEntity",
    "itemReviewed",
}

_VOCABULARY_PREFIXES = (
    "https://schema.org",
    "http://schema.org",
    "https://www.w3.org",
    "http://www.w3.org",
    "https://purl.org",
    "http://purl.org",
    "https://www.wikidata.org",
    "http://www.wikidata.org",
)


def flatten(blocks: list[str]) -> list[dict]:
    """Parse each raw JSON-LD block string (the text content of a <script
    type="application/ld+json"> tag) and flatten into a single list of node
    dicts, walking @graph arrays and top-level arrays.

    Replicates the `_flatten_json_ld` function duplicated identically across
    entity-audit/scripts/check_entity.py, retrieval-readiness-audit/scripts/
    check_retrieval_readiness.py, and static-extraction-audit/scripts/
    check_static_extraction.py, together with the strip/parse/skip wrapper
    each of those modules builds around it before calling it. A block that
    is blank (after stripping) or fails to parse as JSON is silently
    skipped, matching all three implementations.
    """
    nodes: list[dict] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        nodes.extend(_flatten_value(value))
    return nodes


def _flatten_value(value) -> list[dict]:
    if isinstance(value, list):
        flattened = []
        for item in value:
            flattened.extend(_flatten_value(item))
        return flattened
    if isinstance(value, dict):
        if isinstance(value.get("@graph"), list):
            flattened = []
            for item in value["@graph"]:
                flattened.extend(_flatten_value(item))
            return flattened
        return [value]
    return []


def build_id_index(nodes: list[dict]) -> dict[str, dict]:
    """Map every node's "@id" value to the node dict itself. Nodes without
    an "@id" key (or whose "@id" isn't a string) are simply not indexed —
    that's not an error. When more than one node shares the same "@id", the
    last one encountered wins (ordinary dict-assignment behavior)."""
    index: dict[str, dict] = {}
    for node in nodes:
        node_id = node.get("@id")
        if isinstance(node_id, str):
            index[node_id] = node
    return index


def _type_name(node: dict) -> str:
    type_value = node.get("@type")
    if isinstance(type_value, str):
        return type_value
    if isinstance(type_value, list):
        for item in type_value:
            if isinstance(item, str):
                return item
    return "Unknown"


def _is_bare_uri_string(value: str) -> bool:
    return value.startswith("#") or "://" in value or value.startswith("http")


def _reference_for(value, property_name: str):
    """Returns (target_id, is_bare_uri, path_suffix) if `value` qualifies as
    a reference under case (a) or (b), else None."""
    if isinstance(value, dict) and set(value.keys()) == {"@id"} and isinstance(value["@id"], str):
        return value["@id"], False, ".@id"
    if (
        isinstance(value, str)
        and property_name in _ENTITY_VALUED_PROPERTIES
        and _is_bare_uri_string(value)
    ):
        return value, True, ""
    return None


def iter_references(nodes: list[dict]) -> Iterator[Reference]:
    """Walk every top-level property of every node and yield a `Reference`
    for each value that is either:
      (a) a dict of exactly {"@id": "..."} (no other keys), or
      (b) a bare URI/fragment string (starts with "#", or looks like a URL
          via "://" or a leading "http") whose property name is one of the
          entity-valued properties (brand, publisher, author, provider,
          seller, manufacturer, parentOrganization, isPartOf, mainEntity,
          itemReviewed).

    Array-valued properties are walked element-by-element, indexed by their
    actual position in the array ("author[0]", "author[1]", ...); each
    element is checked independently against (a)/(b).

    `property_path` is built as "<Type>[<node index>].<property>[<i>]" (the
    "[<i>]" segment only present for array elements), where <node index> is
    the node's position in the `nodes` list passed in and <Type> is the
    node's "@type" (its first string entry if "@type" is a list, else the
    literal string "Unknown" if "@type" is missing/non-string). A ".@id"
    suffix is appended for case (a) references only, since case (b) bare
    strings have no "@id" key to point at.
    """
    for node_index, node in enumerate(nodes):
        type_name = _type_name(node)
        raw_source_id = node.get("@id")
        source_node_id = raw_source_id if isinstance(raw_source_id, str) else None
        node_prefix = f"{type_name}[{node_index}]"
        for property_name, value in node.items():
            if isinstance(value, list):
                for item_index, item in enumerate(value):
                    resolved = _reference_for(item, property_name)
                    if resolved is None:
                        continue
                    target_id, is_bare_uri, suffix = resolved
                    yield Reference(
                        source_node_id=source_node_id,
                        property_path=f"{node_prefix}.{property_name}[{item_index}]{suffix}",
                        target_id=target_id,
                        is_bare_uri=is_bare_uri,
                    )
            else:
                resolved = _reference_for(value, property_name)
                if resolved is None:
                    continue
                target_id, is_bare_uri, suffix = resolved
                yield Reference(
                    source_node_id=source_node_id,
                    property_path=f"{node_prefix}.{property_name}{suffix}",
                    target_id=target_id,
                    is_bare_uri=is_bare_uri,
                )


def classify_target(target: str, index: dict[str, dict], page_url: str) -> str:
    """Classify a reference target against the page's own node index.

    - Exact match in `index` -> "resolved".
    - Fragment (starts with "#") that isn't an exact match: also resolved if
      any index key *ends with* that same fragment string (e.g. "#org"
      matches "https://site.com/page#org" as well as a bare "#org" key);
      otherwise -> "dangling_fragment" (a fragment is page-scoped by
      definition, so if it isn't defined by this page's own nodes it can't
      be defined anywhere else).
    - Starts with a known vocabulary URI prefix (schema.org, w3.org,
      purl.org, wikidata.org, any scheme) -> "vocabulary".
    - Same origin (scheme + host, via urllib.parse.urlsplit) as `page_url`
      but not resolved above -> "dangling_same_origin".
    - Anything else (a different-origin absolute URL) -> "external".
    """
    if target in index:
        return "resolved"

    if target.startswith("#"):
        for key in index:
            if key.endswith(target):
                return "resolved"
        return "dangling_fragment"

    for prefix in _VOCABULARY_PREFIXES:
        if target.startswith(prefix):
            return "vocabulary"

    page_parts = urlsplit(page_url)
    target_parts = urlsplit(target)
    if (target_parts.scheme, target_parts.netloc) == (page_parts.scheme, page_parts.netloc):
        return "dangling_same_origin"

    return "external"
