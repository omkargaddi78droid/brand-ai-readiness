# Entity checks: detection rules and why each is scoped the way it is

Reference for `entity-audit`. The machine-readable rules live in
`scripts/check_entity.py`; this explains the reasoning and every
false-positive guard.

---

## ENT-01 — Schema.org / JSON-LD presence & validity

**What it catches.** Four distinct conditions, each a different finding
because each needs a different fix:

1. **No JSON-LD at all.** `medium` severity, framed for entity resolution and
   rich results — an Ahrefs test found roughly +2.4% AI-Mode citation lift
   from adding JSON-LD, within noise, so this is not sold as a citation lever
   the way a perimeter block is. Same calibration discipline as
   `perimeter-access-audit`'s llms.txt finding: the mechanism claimed matches
   the evidence available, not the alarming-sounding one.
2. **A block that fails to parse.** `high` severity — this is an unambiguous,
   objective defect (valid JSON or not, no interpretation required), and a
   broken block is worse than none: a strict consumer discards it entirely.
3. **Structured data present, but no Organization/WebSite/LocalBusiness
   node.** The page might have excellent Product or FAQ markup and still
   leave the *publisher* unidentified — a distinct problem from having no
   schema at all, so it gets its own finding rather than being folded into #1.
4. **An identity node missing a required core field** (`name`, `url`).

**Scope: four types, not the whole schema.org vocabulary.** The required-
field table covers `Organization`, `LocalBusiness`, `WebSite`, `Product`.
Article/BlogPosting/FAQPage were deliberately left out: real-world markup for
those varies more (a publisher might use `name` instead of `headline`, or
structure FAQ content differently), and checking them with the same rigid
required-field table would raise the false-positive rate on legitimate but
unusual markup. Extending coverage to those types is a candidate for a future
cycle, behind its own fixture pair — not folded into this one's confidence.

---

## ENT-02 — Knowledge-graph grounding

**What it catches.** An Organization or LocalBusiness node whose `sameAs` is
missing, empty, or points only to unrecognised domains. Appendix D: a name
shared by several things is disambiguated by something that clearly
distinguishes them, and `sameAs` to Wikidata or a verified profile is exactly
that signal.

**Authority domains checked:** wikidata.org, wikipedia.org, linkedin.com,
crunchbase.com, twitter.com/x.com, facebook.com, instagram.com, youtube.com,
github.com. Not exhaustive — a `sameAs` to a lesser-known but genuinely
authoritative registry would still be reported as ungrounded. Recorded as a
known limitation rather than attempting a longer, less-maintainable list.

**Guard: only evaluated when an identity node exists.** A page with no
Organization node at all gets `ENT-01-no-structured-data`, not also
`ENT-02-no-knowledge-graph-link` — the fix for both is the same first step
(add the node), and two findings for one root cause is exactly the report
noise this project's other skills already avoid (see `perimeter-access-audit`
§PER-02, one finding for a blanket block rather than three per-tier ones).

**Guard: `sameAs` as a bare string is accepted, not just an array.**
schema.org permits either shape; only checking the array form would produce
false negatives on perfectly valid markup.

---

## ENT-03 — Markup/text agreement

**What it catches.** `aggregateRating.ratingValue` in JSON-LD disagreeing
with an explicit rating number stated in the page's own visible text — the
same "show your work" evidence style as `content-quality-audit`'s CQ-08:
the finding states both numbers, so the reader checks the disagreement
directly rather than trusting a judgement call.

**Scope: rating only, not price.** A fully general version comparing every
markup number against every text number would need to know which of several
prices on a page (list price, sale price, member price) is the one the
markup claims to describe — exactly the ambiguity `content-quality-audit`'s
CQ-07 already handles for prose, and doing it well for markup-vs-text needs
more structure than this cycle scopes for. Rating is the safer first case:
pages rarely state more than one rating number in prose, and "N out of 5" /
"N/5" / "rated N" are specific, low-collision patterns.

**Guard: silence when there is nothing to compare against.** If the markup
has a rating but the visible text never states one in prose (common — many
sites render stars visually with no text restatement), this is not a
disagreement, it is an unverifiable fact. Firing here would assert a
judgement the check cannot support; REN-08/REN-09 (visual-only facts, not yet
built) is where that gap belongs.

**Tolerance:** `0.3`, wide enough to absorb a markup value carrying more
decimal precision than the prose restates ("4.8" vs "4.75" rounded down in
copy), narrow enough that a real, meaningfully different number still fires.

---

## ENT-04 — Canonicalisation

**What it catches, as four distinct findings because each needs a different
fix:**

1. **No `rel=canonical` at all.** `medium` — URL variants (tracking params,
   trailing slash, http/https) get indexed and cited separately instead of
   consolidating onto one URL.
2. **A canonical tag with an empty href.** `medium` — worth distinguishing
   from #1 because the fix is different (set the value, not add the tag) and
   because a site that has the tag but leaves it empty likely has a template
   bug worth finding, not a missing-feature gap.
3. **Two or more different canonical hrefs on one page.** `high`, `high`
   confidence — deterministic, zero interpretation: two conflicting
   declarations mean different consumers resolve the ambiguity differently,
   and the signal is unreliable exactly when it matters.
4. **A canonical resolving to a different hostname than the page itself.**
   `high` severity, **`medium` confidence** — the confidence is reduced on
   purpose. Off-domain canonicals are a legitimate, deliberate pattern for
   content syndication, and also an easy, costly accident (a staging URL or
   copy-paste artifact left in). The finding names both possibilities rather
   than asserting the accident.

**Guard: the empty-href capture bug.** Development found that a naive
`attr_dict.get("href")` truthiness check silently dropped a `href=""`
canonical tag from the collected list entirely, making it indistinguishable
from "no canonical tag at all" — folding finding #1 and #2 above into one.
Fixed by checking for the key's *presence*, not its truthiness, before the
first formal test was written; a regression test locks the distinction in.

**Guard: relative hrefs are resolved before the off-domain check.** A
canonical of `/product/widget` is not off-domain — it is resolved against the
page's own URL with `urljoin` before comparing hostnames, so a normal
relative canonical never false-positives as pointing elsewhere.

**Out of scope:** slug variants and trailing-slash forks *across many URLs*
on the same site — that needs a sitemap and a canonical map spanning the
whole crawl, which is ENT-04's other half per the capability matrix and
belongs to a future crawl-aware skill, not a single-page check.

---

## ENT-11 — JSON-LD graph referential integrity

**What it catches, that ENT-01/03 don't.** ENT-01 validates each node in
isolation (required fields present, type recognised). ENT-03 compares
markup to visible text. Neither follows an `@id` edge. A page's JSON-LD can
be entirely valid per-node and still be a broken graph: a `Product` whose
`brand` points at `{"@id": "#organization-1"}` when no node with that `@id`
exists anywhere on the page. Every per-node validator passes; the graph is
still broken, and the failure is silent until something actually walks the
edge — which is exactly what entity resolution and knowledge-graph
grounding do to assemble one coherent entity from a `Product`'s `brand`,
`publisher`, `author`, and similar links.

**Built on `shared/jsonld_graph.py`** (`flatten`, `build_id_index`,
`iter_references`, `classify_target`) — the same module `entity-audit`
migrated its own private `_flatten_json_ld` to. That migration is
behavior-preserving by construction: `flatten` replicates the exact
strip/parse/skip wrapper the three duplicated private copies (this skill,
`retrieval-readiness-audit`, `static-extraction-audit`) already had, so
ENT-01/02/03/04's own tests needed no changes when the migration landed —
they were the regression proof.

**Three findings, three different confidence levels, because they claim
different things:**

1. **Dangling fragment reference** (`ENT-11-dangling-id-reference-*`,
   `medium` severity, `high` confidence). A fragment `@id` (`#foo`) is
   page-scoped by definition — schema.org and JSON-LD both treat a bare
   fragment as resolvable only within the same document. If it isn't
   defined by this page's own nodes, it cannot be defined anywhere else.
   That is a literal fact, not an inference, hence high confidence.
2. **Cross-page reference** (`ENT-11-cross-page-id-reference-*`, `low`
   severity, `medium` confidence). A same-origin *absolute* URL reference
   (`https://site.com/other-page#org`) that doesn't resolve on *this* page
   may legitimately be defined on the page it points to — sites do
   structure shared entities this way. Confidence is reduced because this
   skill only ever sees one page at a time and has no way to check the
   other page without a second fetch, which this capability deliberately
   does not make (zero new fetches, per the plan this shipped against).
3. **Orphan identity node** (`ENT-11-orphan-identity-node`, `medium`
   severity, one finding per page, not per node). An
   Organization/Person/LocalBusiness node with an `@id` that nothing on the
   page references, *and* the page also carries a Product/Article/Review
   node with no `brand`/`publisher`/`author` link at all. Both conditions
   are required: an orphaned identity node on a page with no content to
   ground is not this defect (nothing needed the link in the first place),
   and a content node with *some* link — even a dangling one — is not "no
   link at all" for this rule's purposes; that is finding #1's territory,
   a different, more specific defect on the same underlying problem.

**No `sameAs` liveness fetching, anywhere in ENT-11.** Deliberate: it costs
a fetch to a third-party host per candidate, LinkedIn/Crunchbase-class
sites are known to bot-block this project's user agent, and a blocked
fetch would manufacture a false "dangling" verdict on a link that is
actually fine. ENT-02 already owns the "does `sameAs` point somewhere
authoritative" question at the string level; ENT-11 never re-derives it by
fetching.

**Overlap control with ENT-01.** ENT-11 runs only when `nodes` is
non-empty and carries zero JSON-LD parse errors — the caller (`audit_html`)
enforces this before calling `find_graph_integrity_issues` at all, rather
than re-deriving ENT-01's own no-structured-data/malformed-json-ld
conditions a second time inside ENT-11 itself. A page with no parseable
graph has nothing to walk; reporting a broken graph there would blame
ENT-11's own capability for a defect ENT-01 already names correctly.

**Deterministic finding ids on a content hash.** The two per-instance
finding types append `hashlib.sha256(f"{property_path}|{target_id}")[:8]`
to their id — the same pattern (and the same reason) `engagement-audit`'s
EN-06 uses: `id(object)` or dict-iteration order would make the same page
audited twice produce different ids, which is a stability regression this
project tests against. Capped at 5 findings per class (fragment,
cross-page) so a pathological page with dozens of broken references cannot
flood a report — the corpus/measure harness (`measure_entity.py`) matches
these ids by *prefix*, not exact equality, for the same reason
`measure_engagement.py` does for EN-06.

**Known gap, not fixed here.** `shared/jsonld_graph.classify_target`
classifies a relative-path `@id` target (e.g. `"/organization"`, no
scheme/host) as `"external"` rather than `"dangling_same_origin"`, because
`urlsplit` on a schemeless path yields an empty `(scheme, netloc)` that
never matches the page's own. This was flagged during the module's own
build and left as-is: `shared/jsonld_graph.py` is committed, shared
infrastructure another capability may also depend on, and this task's scope
is ENT-11's own detection logic, not revisiting a dependency's contract.
Documented with a regression test (`test_relative_path_id_target_does_not_crash`
in `tests/test_entity_audit.py`) that locks in the *current* behavior so a
future change to `classify_target` is a visible, deliberate decision rather
than a silent drift.

---

## ENT-09 — Taxonomy consistency (extraction only — see entity-judgement-rubric.md)

**What it catches.** A declared category signal — `Product.category`,
`articleSection`, or a `BreadcrumbList`'s deepest item — that shares no
vocabulary at all with the page's own visible text, surfaced for the agent
to judge whether it is a real mismatch or a synonym/paraphrase a keyword
match cannot see.

**Why this is agent-judged, not script-decided, unlike ENT-01–04.** Every
other capability in this skill compares two structured or pattern-matched
values (a rating number, a set of canonical hrefs) where agreement or
disagreement is unambiguous once extracted. "Does this category relate to
this text" is not — "Laptops" and "notebook computers" describe the same
thing with zero shared keywords. Asserting a mismatch from keyword absence
alone would be exactly the false-positive-of-severity failure
`content-quality-audit`'s CQ-02/04/09/12 already exist to avoid for prose;
ENT-09 applies the same discipline to structured-data-vs-text comparison.

**Three extraction sources, one dedup pass.** `Product.category` and
`articleSection` are read directly off any JSON-LD node that carries them.
A `BreadcrumbList` is walked to its deepest (`position`) `ListItem`,
handling both the common shapes real markup uses — `item` as a bare URL
string, or as a nested object carrying its own `name`. All three sources
feed one deduplicated label list (case-insensitive) — the same category
named twice (a breadcrumb *and* `Product.category` agreeing) is one thing
for the agent to judge, not two near-identical candidates.

**Guard: zero keyword overlap, not "low" overlap.** Only a label sharing
*no* keyword at all with the page's text becomes a candidate — any overlap
at all (even one shared word) is treated as agreement and never reaches the
agent. This is a deliberately conservative threshold: a partial-overlap
case is far more likely to be a legitimate related term than a real
mismatch, and the zero-overlap floor keeps the candidate set to the cases
most worth a second look, the same "the pattern match cannot say more than
this" discipline `content-quality-audit`'s extraction functions already use.

**Guard: generic labels are never candidates.** "Home", "Blog", "General",
"Uncategorized" and similar carry no specific claim to check agreement on —
excluded by an explicit list, the same category of guard as `content-
quality-audit`'s CQ-07 excluding single-word metric labels as too generic
to compare structurally.

**Guard: a 50-word minimum on visible text.** Below this, "zero keyword
overlap" is at least as likely to mean "not enough text was extracted" as
"the category is wrong" — the same "short sample is noise" principle
`content-quality-audit`'s CQ-11 applies to its own readability threshold.

**Keyword folding** reuses `content-quality-audit`'s CQ-08 approach
(stopword-stripped, trailing-`s` singularised) — reimplemented here per this
skill's own "independently runnable" convention (see Shared infrastructure
notes below), not imported.

---

## Shared infrastructure notes

`_PageParser` is a second, independent implementation of the same narrow
"strip script/style/code/pre, collapse whitespace, break at block
boundaries" pattern `content-quality-audit` uses, reimplemented here rather
than imported. Per `skill-engineering-principles.md` §5.3, a skill must be
independently runnable and testable; importing another skill folder's script
would create a cross-skill dependency this project's convention avoids (the
only shared code is `shared/finding_contract.py`, genuinely cross-cutting
infrastructure, not skill-specific logic). The small duplication cost is the
explicit tradeoff for that independence.
