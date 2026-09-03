# Phase 4 (capability cycle 2 of N) — CQ-03, CQ-05, CQ-07, CQ-08

Phase 4 output, second capability cycle. New skill: `content-quality-audit`.
Gate A–H for all four capabilities together, since they share one script, one
text-extraction step, and one design review.

---

## A — Gap confirmation

Not baseline-covered — the baseline has no equivalent (baseline-capabilities.md
marks the deterministic four as entirely build-from-scratch). `BUILD_REQUIRED`,
resolved by building.

## B — Resource evaluation

stdlib only: `re`, `collections.defaultdict`, `html.parser.HTMLParser`,
`ipaddress`, `socket`, `urllib`. No new dependency.

## C — Design

**A new skill, not an extension of `perimeter-access-audit`.** Gate 3
(content) is a different concern from gate 1 (reachability) — different
input (page text vs. well-known files), different failure model, different
capability owner in the matrix. One skill per cluster, per project convention.

**A narrow, purpose-built text extractor, not the render/extraction
pipeline.** `extract_visible_text()` strips `<script>/<style>/<code>/<pre>`
and normalises whitespace — exactly what these four checks need, explicitly
documented as *not* REN-06/07 (boilerplate ratio, main/article boundaries),
which remain build-required and belong to a different skill.

**Every detector scoped down from its most general form, on purpose:**

- **CQ-03** matches three templating syntaxes (`{{ }}`, `{% %}`, `<% %>`)
  chosen because they essentially never occur in ordinary prose. Two riskier
  patterns (CMS shortcodes, `${VAR}` env-var syntax) were considered and
  explicitly dropped — see the reference doc's "What was left out" — rather
  than shipped at a worse false-positive rate to inflate the pattern count.
- **CQ-05** requires a claim verb *and* a relative-time phrase in the *same
  sentence*, with no absolute date. Flagging every relative-time mention
  would fire on nearly every news or blog page and mean nothing.
- **CQ-07** is scoped to colon-labeled key:value lines (spec-sheet style),
  not general prose — a fully general version needs part-of-speech tagging
  this project does not have, and would not clear the near-zero-FP bar the
  capability matrix sets for this cluster.
- **CQ-08** requires keyword overlap between a labeled number list's label
  and an average-claim sentence, plus a suppression list for
  weighted/filtered/adjusted averages — the matrix's own explicit warning for
  this check.

Each of these is a documented tradeoff (recall for precision), not a hidden
limitation — stated in `references/content-anti-patterns.md` so a future
cycle can revisit any one of them behind its own fixture pair.

**Multi-page attribution, designed in before it became a bug.** This skill
runs once per page (per its own SKILL.md), so two pages with the same defect
class produce findings sharing an identical `check_id`. `audit_text()` takes
an optional `page_url` and stamps it into both the evidence string and
`structured_evidence`, so a composed multi-page report stays attributable —
caught by tracing the design through to composition before shipping, not
after a report came back unreadable.

## D — Implement

`extract_visible_text`, `find_template_leakage`, `find_relative_date_anchors`,
`find_scope_ambiguous_numbers`, `find_computed_stat_mismatches`, the four
finding builders, `audit_text`, `_stamp_page`, `is_public_host`,
`fetch_page_html`, CLI. Only this cycle's four capabilities.

## E — Test

**36 unit tests** (pure functions, no network) + **8-case measured corpus**
(precision 1.000, recall 1.000, 4.7 ms) + the existing 92-test perimeter suite,
unaffected. **136 tests total project-wide.**

Every clean fixture in the corpus was chosen because it resembles a defect
closely enough to have tripped an earlier version of a detector during
development (see §F) — not written in advance, but *promoted from a bug found
while building*, which is a stronger provenance than an imagined edge case.

## F — Review

**Four real bugs found before a single formal test was written**, by running
the detectors against realistic fixtures first and reading the output —
the same discipline that found PER-03's bugs in cycle 1, now confirmed twice:

1. **Singular/plural keyword mismatch (CQ-08).** `"Customer ratings"` (list
   label) never matched `"average rating"` (claim sentence) because keyword
   comparison required exact string equality — `"ratings" != "rating"`. The
   very first synthetic positive fixture silently produced zero findings.
   Fixed with a crude singularization fold (strip a trailing `s`) applied to
   both sides of the comparison.
2. **Parenthesised labels unparseable (CQ-07/CQ-08).** `"Delivery times
   (days): 2, 3, 2, 4, 3"` did not match the label regex at all — the
   character class excluded `(` and `)`, a common, legitimate real-world
   label format. Found while testing a second CQ-08 pair in the same fixture
   as bug 1; fixed by widening the label character class, which fixed both
   CQ-07 and CQ-08 in one change since they share the pattern shape.
3. **Substring match on the qualifier word "per" (CQ-07).** `"Warranty
   period: 1 year"` / `"Warranty period: 2 years"` was silently suppressed
   because `"per" in line.lower()` matches inside `"period"`. The exact
   failure mode this project's own principles doc already named — "regexes
   are exactly where the silent false positives live" — recurring through a
   different, naive `in` check rather than a regex, and now the second
   instance of substring-matching causing a wrong result in this project
   (the first was `urllib.robotparser` matching `Fetch` inside
   `Meta-ExternalFetcher`, cycle 1). Fixed with `\bper\b`.
4. **The same substring class in CQ-05.** Found by inspection once bug 3's
   pattern was recognised, before it shipped: `"this week"` is a literal
   prefix of `"this weekend"`, so `"We updated the schedule this weekend"`
   would have wrongly matched the phrase. Fixed the same way, pre-emptively,
   with a regression test (`test_this_weekend_is_not_matched_as_this_week`)
   added before any fixture exposed it live.
5. **A fifth, structural bug, caught by the test suite itself:**
   `extract_visible_text` was splitting a single sentence into two "lines"
   whenever the HTML source happened to wrap it across a literal newline —
   unrelated to any real block-tag boundary. This would have fragmented
   CQ-05's same-sentence AND-check across the wrap point on ordinary
   pretty-printed HTML. Fixed by collapsing all whitespace *within* a text
   node (including embedded newlines) to a single space at collection time,
   so only the deliberately-inserted block-boundary markers produce a line
   break in the extracted text.

**Substring matching is now a named, tracked failure class in this project**,
not a one-off. Every phrase/word list added from here on (`_QUALIFIER_WORDS`,
`_RELATIVE_TIME_PHRASES`, `_SUPPRESSION_WORDS`, `CLAIM_VERBS`) is matched with
`\b...\b`, and this is stated as a standing rule in the reference doc rather
than left implicit in the code.

**Duplication:** none — the skill introduces no logic that overlaps
`perimeter-access-audit`; the finding contract is the only shared code, as
designed.

**Runtime:** 4.7 ms for the 8-case corpus; a live single-page run is one GET
(≤10 s timeout) plus regex work on the extracted text, negligible against the
5-minute budget. Ten real pages fetched live took under a few seconds each.

## G — Document

This file; `SKILL.md`, `references/content-anti-patterns.md`, README,
`marketplace.json` (0.4.0 → 0.6.0), `docs/capability-matrix.md` (CQ-03/05/07/08
→ IMPLEMENTED), entrypoint `SKILL.md` (registry updated with per-page vs.
per-site run semantics), `docs/00-project-plan.md`.

## H — Freeze

Frozen at this design. Re-open only if: a documented false-positive case
survives against real content (none found in field validation, §Field
validation below), or one of the deliberately-dropped patterns (CMS
shortcodes, `${VAR}` syntax, general-prose CQ-07) gets its own fixture pair
and a case for inclusion.

---

## Field validation

Ten live pages, read-only, single GET each, via `--url`: a Wikipedia article,
Python's `re` module docs (deliberately chosen — full of `{n,m}` quantifier
syntax, a stress test for CQ-03's code-block-stripping guard), python.org's
about page, BBC News, Nike's help center, Stripe's pricing page, an Apple
product page, GSMArena's iPhone review, RTINGS' review index, and Consumer
Reports' electronics section.

**Result: zero crashes, zero findings, on all ten.** No false positives —
including on the regex-documentation page, which is exactly the kind of
"legitimate curly-brace-heavy technical content" CQ-03's design worries
about, and which stayed clean because the quantifier syntax lives inside
`<code>` blocks that `extract_visible_text` already strips.

**Recorded honestly, not glossed over:** none of the ten pages exhibited a
genuine positive case in this sample. That is a *precision* result (these are
well-maintained, professionally produced pages, and the checks correctly
found nothing to complain about) rather than a *recall* result — the recall
evidence comes from the synthetic corpus and the five bugs in §F, each of
which was caught precisely because a realistic fixture was run and read
before being trusted. The next capability cycle that touches page content
should keep watching for a genuine live positive, the same open item left for
PER-03 in cycle 1.

## Next

Continue Phase 4 with `ENT-01…ENT-04` (schema.org/JSON-LD presence, knowledge-
graph grounding, canonicalisation, brand-entity coherence) — the identity
multiplier, well-supported by the baseline's documented JSON-LD and
knowledge-graph checks per `docs/baseline-capabilities.md` §1, and a useful
contrast after two cycles built entirely from scratch.
