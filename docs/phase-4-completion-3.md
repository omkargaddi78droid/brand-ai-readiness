# Phase 4 (capability cycle 3 of N) — ENT-01, ENT-02, ENT-03, ENT-04

Phase 4 output, third capability cycle. New skill: `entity-audit`. Gate A–H
for all four capabilities together — one script, one page-parsing pass, one
design review.

---

## A — Gap confirmation

Not baseline-covered by anything testable: baseline-capabilities.md marks
ENT-01/ENT-02 as baseline "Full"/"Partial" coverage, but Phase 3 already
established the baseline is untestable offline (SSRF guard rejects loopback)
and its `.recommendations` strings carry no location or rule identity we can
normalise (baseline-selection §5c, binding: do not use). Built locally, same
disposition as PER-03 and the CQ cluster. `BUILD_REQUIRED`, resolved by
building.

## B — Resource evaluation

stdlib only: `json`, `re`, `html.parser.HTMLParser`, `ipaddress`, `socket`,
`urllib`. No new dependency.

## C — Design

**A new skill, not folded into `content-quality-audit`.** Cluster C (entity)
is the matrix's own "cross-cutting multiplier" — a distinct concern from
Cluster F (content anti-patterns), with its own owner-per-capability
boundary. One skill per cluster, third time this convention has held.

**One parsing pass serves all four checks.** `parse_page()` returns
JSON-LD nodes, JSON-LD parse errors, canonical hrefs, and visible text in a
single `HTMLParser` traversal — cheaper than four separate parses of the
same page, and the natural shape given all four checks read different parts
of the same document.

**Scope narrowed in three places, stated rather than hidden** (full reasoning
in `references/entity-checks.md`):

- **ENT-01** checks a curated four-type table (Organization, LocalBusiness,
  WebSite, Product), not the full schema.org vocabulary — Article/FAQPage
  markup varies enough in legitimate practice that a rigid required-field
  table would raise the false-positive rate.
- **ENT-02** only evaluates when an identity node already exists. A page
  with no Organization node at all gets `ENT-01-no-structured-data`, not
  also a second "no sameAs either" finding for the same root cause — the
  same one-root-cause-one-finding discipline as `perimeter-access-audit`'s
  PER-02.
- **ENT-03** compares only `aggregateRating` against text, not price — a
  general markup-vs-text price comparison needs to know which of several
  prices on a page the markup describes, an ambiguity this cycle does not
  try to resolve.

**Multi-page attribution, carried over from cycle 2's design.** Same
`page_url` stamping into evidence and `structured_evidence`, for the same
reason: this skill runs once per page, so a composed multi-page report needs
every finding attributable to its source.

## D — Implement

`parse_page`, `_flatten_json_ld`, `find_schema_issues` (+3 finding builders),
`find_knowledge_graph_gaps`, `find_markup_text_disagreement`,
`find_canonical_issues` (+4 finding builders), `audit_html`, `_stamp_page`,
`is_public_host`, `fetch_page_html`, CLI. Only this cycle's four
capabilities.

## E — Test

**40 unit tests** (pure functions except the two SSRF-guard tests, no
network) + **9-case measured corpus** (precision 1.000, recall 1.000, 3.9 ms)
+ the existing 136-test suite from cycles 1–2, unaffected. **176 tests
total project-wide.**

## F — Review

**One real bug, found on the very first live run, more consequential than
either single bug in cycles 1–2 because it silently dropped an entire
category of markup:**

`_PageParser` overrode `handle_startendtag` to insert a paragraph break for
self-closed block tags, but did not delegate to `handle_starttag` first —
unlike `HTMLParser`'s own documented default, which runs `handle_starttag`
then `handle_endtag` for a self-closed tag. Every attribute-based extraction
that lives in `handle_starttag` (canonical-link capture, JSON-LD
`<script>`-tag detection) was silently skipped for **any self-closed tag**,
including the extremely common XHTML-style `<link rel="canonical" href="..."
/>`.

**Caught immediately**, on the first of five live pages: `apple.com`'s iPhone
page has a canonical tag, confirmed by inspecting the raw response, and the
tool reported it missing. Verified with the raw JSON-LD too — Apple's page
has genuine `Product`/`BreadcrumbList`/`FAQPage` markup and correctly no
Organization/WebSite node, so the parallel `ENT-01-no-identity-type` finding
on the same page was a true positive throughout; only the canonical
extraction was broken.

**Fixed** by having `handle_startendtag` call `self.handle_starttag(tag,
attrs)` then `self.handle_endtag(tag)` — restoring `HTMLParser`'s documented
default behaviour that the override had silently replaced. Regression
coverage added for both the specific canonical case and a synthetic
self-closed-`<script>` case (invalid HTML, never emitted by real pages, but
checked so the parser cannot get stuck mid-skip if one appears).

**Checked whether the same pattern existed in `content-quality-audit`**
(cycle 2's `_VisibleTextExtractor` has the identical
`handle_startendtag`-without-delegation shape). Confirmed safe: that
extractor never reads tag *attributes*, only tracks block/skip category
membership, and its `handle_startendtag` already inline-replicates the one
behaviour (`BLOCK_TAGS` → newline) that would otherwise be lost. No fix
needed there, and the reasoning is recorded here rather than left as an
unstated assumption.

**Duplication:** `_PageParser` reimplements the same narrow
"strip script/style/code/pre, collapse whitespace" pattern as
`content-quality-audit`'s extractor, deliberately not shared — see
`references/entity-checks.md`'s closing note on why importing across skill
folders was rejected again, same reasoning as cycle 2.

**Runtime:** 3.9 ms for the 9-case corpus; a live single-page run is one GET
plus one parse pass, negligible against the budget.

## G — Document

This file; `SKILL.md`, `references/entity-checks.md`, README, `marketplace.json`
(0.6.0 → 0.7.0), `docs/capability-matrix.md` (ENT-01/02/03 → IMPLEMENTED,
ENT-04 → PARTIALLY_COVERED — the crawl-wide half is explicitly still
build-required), entrypoint `SKILL.md` (registry), `docs/00-project-plan.md`.

## H — Freeze

Frozen at this design. Re-open only if: ENT-01's four-type table proves too
narrow against a documented real case, ENT-03 gets a price-comparison
extension behind its own fixture pair, or ENT-04's crawl-wide half is built
(needs a sitemap and multi-page canonical map, out of scope for a
single-page script).

---

## Correction (added during the Phase 4 engagement-audit cycle)

**The `python.org` row below was wrong**, and the "hand-verified" claim
next to it was too: both this skill's fetch and the `curl` command used to
check it were silently reading raw gzip bytes as text, because
`python.org`'s CDN sends `Content-Encoding: gzip` and neither `curl` without
`--compressed` nor this project's `urllib`-based fetchers decompress
automatically. The bug was found live during `engagement-audit`'s field
validation (docs/phase-4-completion-4.md §F) and fixed retroactively across
all four fetch functions in this marketplace, this skill's included. Re-run
after the fix, `python.org` genuinely has a `WebSite` JSON-LD node (missing
`name`) and genuinely has no canonical — half of the original claim was
right by coincidence, half was not. The corrected row is below; the struck
claim is kept struck rather than deleted, because the point of this section
is that the earlier verification step wasn't as independent as it looked —
"I checked it with curl" is not a defense against a bug that also fools curl.

## Field validation

Seven live pages, read-only, single GET each: python.org, a Wikipedia
article, Apple's iPhone product page, Stripe's pricing page, BBC News,
GitHub's homepage, and nytimes.com.

**Result: zero crashes; one real bug found and fixed (§F); every remaining
finding independently hand-verified against the raw HTTP response, not just
trusted — except python.org, corrected above:**

| Site | Finding | Verified against |
|---|---|---|
| ~~`python.org`~~ `python.org` | ~~No structured data, no canonical~~ **`WebSite` node missing `name`; no canonical** | ~~`curl` confirms no `ld+json` script...~~ **See Correction above — original claim was wrong, `curl` was fooled by the same gzip issue** |
| `github.com` | No structured data | `curl` confirms no `ld+json` in the raw response; canonical *is* present and correctly not flagged |
| `apple.com` (iPhone page) | No Organization/WebSite identity type | Raw JSON-LD inspected directly: genuine `Product`/`BreadcrumbList`/`FAQPage` nodes, no `Organization` or `WebSite` anywhere |
| `en.wikipedia.org` | No Organization/WebSite identity type | Consistent with Wikipedia's own JSON-LD, which is article/`WebPage`-shaped, not Organization-shaped |
| `stripe.com/pricing` | No Organization/WebSite identity type | Page carries `FAQPage` markup only |
| `bbc.com/news` | No Organization/WebSite identity type | Page carries `WebPage` markup only |
| `nytimes.com` | Clean | Genuinely has canonical, Organization markup, and no rating disagreement |

This is a stronger field-validation result than either of the first two
cycles: those found zero genuine positives across their live samples and had
to document that honestly. This cycle found six genuine, hand-verified
positives across seven sites, plus the self-closing-tag bug — evidence that
ENT-01's scope (identity-type presence, not just schema presence at all) is
catching a real, common gap: pages with rich Product/FAQ/Article markup that
never actually identify the organization behind them.

## Next

Continue Phase 4 with the engagement beachhead — `EN-01, EN-03, EN-06,
EN-09` — per the front-loading order. Half the rubric weight and still
entirely unbuilt; three cycles have now been spent entirely on
discoverability.
