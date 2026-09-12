# Retrieval-readiness checks: detection rules and why each is scoped the way it is

Reference for `retrieval-readiness-audit`. The machine-readable rules live in
`scripts/check_retrieval_readiness.py`; this file explains what each check
catches, why it is scoped the way it is, and what was deliberately left out.

RET-08 operates on `extract_headings()`'s output: every `<h1>`-`<h6>`
element's level and flattened text, in document order. RET-01 operates on
`extract_json_ld_and_text()`'s output: the page's JSON-LD nodes and a
lightly-scoped visible-text string. Both are narrow, single-purpose
extractions — not the render/extraction pipeline (REN-06/07 in the
capability matrix): no boilerplate-ratio scoring, no main/article boundary
detection.

---

## RET-08 — Heading hierarchy integrity

**What it catches, as two distinct findings because each needs a different fix:**

1. **A skipped heading level.** A heading whose level is more than one
   deeper than the heading immediately before it — `h2` followed directly by
   `h4`, with no `h3` anywhere in between. This breaks the document outline a
   retrieval system uses to segment a page into chunks and weight them by
   their position in the hierarchy: the missing level reads either as a
   section with no heading of its own, or as two genuinely separate sections
   merged into one chunk.
2. **An empty heading.** A heading element with no text content at all —
   often a template artifact (a heading wrapper left in place after its
   content was removed, or a spacer element). An empty heading contributes
   an outline entry with nothing to anchor it to.

**Why "skipped between two consecutive headings," not "must start at h1."**
Two rules were considered for this capability; only one shipped. Requiring
every page to start at `h1` is contested in practice — modern component-
based layouts frequently put the visual masthead or logo outside the
document's real content, so the first genuinely structural heading is
legitimately an `h2`; the HTML5 spec also permits more than one `h1` per
sectioning root, which some SEO folklore treats as an error and some
accessibility guidance does not. Firing on the starting level would raise
this check's false-positive rate on real, correctly-built pages for a rule
that is not actually settled. The skip check only ever compares two
headings that are *both present* on the page — it says nothing about
whichever heading came first.

**Why "more than one level deeper," not "any level change."** A heading
going *shallower* (h3 → h2, closing a subsection and starting a new section
at a higher level) is completely normal document structure, not a defect —
the check only compares in one direction. A heading at the *same* level as
the one before it is likewise never flagged. Only `current_level >
previous_level + 1` fires, which is exactly and only the shape of a genuine
gap in the outline.

**Guard: multiple independent skips on one page aggregate into one
finding**, the same design as `content-quality-audit`'s CQ-05/CQ-07 — a
reader sees every instance in one place rather than one finding per
occurrence, and the report stays proportional to the number of distinct
defect *classes* on a page, not the number of headings on it.

**What was left out, and why — the "decorative heading" half of this
capability's own wording in the matrix.** RET-08's capability-matrix
description also names "decorative heading levels" as part of what it
should detect — a heading tag used purely for visual styling (making text
bold and large) with no real structural role. This is deliberately not
built here: distinguishing a decorative heading from a terse-but-real one
needs to know how it actually renders (font size and visual weight relative
to the surrounding text), which this project has consistently drawn as the
render/extraction gate-2 boundary elsewhere (`content-quality-audit`'s CQ-01
opening-window limitation is the same class of boundary). A future
render-aware cycle is where this half belongs, not a static-markup check.

**Live validation, not just fixtures.** Checked against six real pages
(python.org, docs.python.org, en.wikipedia.org, apple.com/contact,
peps.python.org, stripe.com/pricing) before this was frozen: zero crashes,
zero false positives, and one genuine positive hit — stripe.com/pricing's
FAQ section jumps directly from its `h1` ("FAQs") to `h3` question headings
with no `h2` section heading in between, exactly the structural gap this
check exists to catch.

---

---

## RET-01 — Technical-identifier survival (BM25 exact-match retention, narrowed)

**What it catches.** A page's own JSON-LD declares a `Product` node with a
technical identifier field (`sku`, `mpn`, `gtin`, `gtin8`, `gtin12`,
`gtin13`, `gtin14`) whose value does not appear anywhere in the page's
extracted visible text — the identifier exists only inside a
`<script type="application/ld+json">` block, an `<img alt="...">`, or
nowhere a text-based (sparse/exact-match) retrieval system will ever see it,
even though the page's own structured data confirms the page is genuinely
about that exact identifier.

**Why this is the whole capability, not real BM25 ranking.** The capability
matrix names `bm25s` as RET-01's resource and describes a broad "Detects"
column: product SKUs, model numbers, statute names, technical terms lost
during extraction. Re-reading that column for its actual failure mode shows
the defect is binary presence/absence, not a relevance score — a real BM25
ranker computes term-frequency-weighted relevance across a whole corpus,
which is a different (and much larger) capability than "does this specific
identifier survive extraction at all." This check answers exactly the
narrower, still-genuinely-useful question with no ranking math and no
third-party dependency (`bm25s`/`rank_bm25`), matching this project's
consistent disposition toward every matrix-named third-party resource
(`seoscoreapi`, `crawl4ai`, `advertools`): reimplement the actual defect in
stdlib, narrower if needed, rather than add a dependency.

**Why JSON-LD `Product` identifiers specifically, not "model numbers in
`<title>`" or "statute names."** Both of those need a free-text pattern-
matching heuristic — what does a model number or a statute citation *look
like* in ordinary prose — which carries real false-positive risk (a lot of
ordinary text is alphanumeric-with-digits) this project's discipline says
should not ship without a fixture built specifically to break the heuristic
first (the same bar CQ-11's Flesch-threshold FP-guard claim failed to clear
in cycle 8, and was corrected rather than shipped overstated). A JSON-LD
`sku`/`mpn`/`gtin*` value needs no heuristic at all: the page's own
structured data already told us, unambiguously, that this exact string
matters — there is nothing to infer. Scoped to `@type` containing `Product`
specifically, not any node carrying one of these field names, for the same
reason: an unrelated node type reusing a field name is not this capability's
concern, and widening the type check raises false-positive surface for no
demonstrated benefit.

**Matching rule.** A token survives if it appears anywhere in the visible
text, case-insensitively, with a word-boundary guard on both ends
(`(?<![A-Za-z0-9])token(?![A-Za-z0-9])`) so a token is never satisfied by
being a substring of a longer alphanumeric run — `"WID-123"` inside
`"WID-1234"` does not count as surviving. Case-insensitive on purpose: the
identifier's exact casing is not the thing being tested, its presence is.

**Guard: multiple missing identifiers on one page aggregate into one
finding**, matching RET-08's own aggregation shape and this project's
general "one finding per defect class, not per occurrence" convention.

**Live validation, not just fixtures.** Checked against real product pages
before this was frozen. lego.com's product pages (`millennium-falcon-75192`,
`orchid-10311`) both fire: the JSON-LD `sku` value never appears outside a
`<script>`/`<style>` block anywhere on the page — confirmed by an
independent script-stripped substring check outside this skill's own code,
not just the skill's own report. Notably, the JSON-LD `sku` (e.g.
`"6175771"`) is a different value entirely from the LEGO set number shown
959 times in real visible text (`"75192"`) — LEGO's structured data and
its customer-facing text use two different identifiers for the same
product, and only the customer-facing one is ever retrievable by exact
match. No live "survives" (silent) case was found — every real product page
tested during this cycle happened to exhibit the same gap — so the silent
path's correctness rests on the synthetic fixture pair
(`test_a_token_present_in_visible_text_does_not_fire`) rather than a live
confirmation; flagged here rather than left implicit.

---

## RET-04 — Keyword stuffing

**What it catches.** A 4-word phrase — not composed entirely of stopwords —
that repeats at least 5 times anywhere across the page's prose, at a
density of at least 8% of the page's prose word count
(`occurrences * 4 / total_prose_words`), with `<table>`, `<dl>`, `<ul>`,
`<ol>` and `<select>` regions excluded from the corpus before counting
starts. Both thresholds must be met together: density alone would flag a
short but genuinely on-topic phrase on a brief page; occurrence-count alone
would flag long pages that simply mention a real topic often. Counting is
over overlapping windows across the whole prose corpus, not just adjacent
repeats, so a phrase spread throughout a page — the realistic shape of
actual keyword stuffing, not one repeated directly after itself — is still
caught.

**Why exclude structured regions, and why those five tags specifically.**
The capability matrix's own risk note for RET-04 names the false-positive
case directly: "fires on legitimately repetitive pages (spec tables,
glossaries); exclude structured regions before counting." `table`, `dl`
(the standard glossary/definition-list element), `ul`, `ol` and `select`
are the HTML elements whose entire purpose is repeated, parallel-structure
content — a spec table's column values, a glossary's term/definition pairs,
a navigation or filter list. Excluding them at the extraction step (in
`extract_prose_text()`) rather than filtering matches after the fact means
their inherent repetition is structurally invisible to the counter, not a
pattern that has to be recognized and suppressed.

**Why a 4-word n-gram, not 2 or 3.** A 2- or 3-word phrase repeats
constantly in ordinary prose for entirely innocent reasons ("the same
product," "our new feature," any common noun phrase used more than a
handful of times across a page of any real length). A 4-word window is
long enough that repeating it exactly, many times, stops looking like
normal topical focus and starts looking like a copy-pasted phrase —
the actual mechanical signature of keyword stuffing.

**Why stopword-only n-grams are excluded.** Purely grammatical 4-word
sequences ("in the of the," "of the on the") repeat at very high frequency
in any text of reasonable length and carry no topical signal at all —
counting them would either need a much higher, awkward threshold to avoid
false positives, or would flag ordinary prose's own grammar. Requiring at
least one non-stopword token in the n-gram keeps the check meaningful
without a separate, harder-to-justify threshold just for function words.

**Why a minimum prose-word floor (80 words).** Density is not a stable
signal on a very short page — five occurrences of a three-or-four-word
phrase inside forty words of prose is a different, much noisier
statistical claim than the same five occurrences inside a normal-length
page. Below the floor, RET-04 stays silent rather than guess; a genuinely
stuffed short page could go undetected as a result, a known, stated
limitation rather than a silently accepted gap.

**Live validation, not just fixtures.** Checked against seven real pages
before this was frozen: `docs.python.org/3/library/re.html` (dense,
naturally repetitive regex terminology), `en.wikipedia.org/wiki/
Glossary_of_chess` (a literal glossary page, `<dl>`-heavy), `peps.python.org/
pep-0008/` (code examples with repeated syntax), lego.com's and gymshark.com's
product pages, and two finance-content pages (nerdwallet.com,
investopedia.com — one 404'd, harmlessly reported `unknown`). **Zero
crashes, zero false positives** — the glossary and regex-docs pages in
particular are exactly the "legitimately repetitive" risk case the
capability matrix warned about, and both stayed silent. **No live true
positive was found**: reputable, well-indexed sites generally avoid
keyword stuffing because search/AI ranking already penalizes it, which is
the same mechanism this check exists to flag — so the absence of a live hit
is consistent with, not contrary to, the capability's own premise. The
detection path's correctness rests on the synthetic fixture pair
(`KeywordStuffingTests.test_a_repeated_phrase_at_high_density_fires` and
its structured-region-exclusion counterpart) rather than a live positive;
stated here rather than left implicit, the same disposition RET-01's
reference section took for its own missing live "survives" case.

---

## RET-07 — Retrieval-oriented structure

**What it catches.** A substantial page (≥300 words of visible text) that
has *none* of three named structural aids at all: zero heading elements,
no heading whose text ends in `?` and no `FAQPage`/`QAPage` JSON-LD (the
two ways this project detects Q&A framing), and no `<dt>`/`<dd>`
definition-list markup anywhere. Any single one of the three present is
enough to stay silent — this only fires on the genuine "none of the above"
case, the actual chunking failure the capability matrix names.

**Why "none of the three," not "no headings" alone.** The matrix's own
wording names three separate, independently-sufficient aids, not a single
required one: "Absent headings, Q&A framing, or definition blocks that
make chunks self-contained." A page built entirely around an FAQ pattern
(`<dl>`-based Q&A, or a schema.org `FAQPage`) with no traditional headings
is well-structured for chunking, not a defect — flagging it would punish a
legitimate alternative pattern for not using the more conventional one.

**Why the semantic half is out of scope.** The matrix's phrase "that make
chunks self-contained" implies a judgement this script does not attempt:
having a heading does not guarantee the text under it stands alone without
context from earlier in the page ("As mentioned above, the fee is..." under
a heading called "Pricing" is still not self-contained). Distinguishing
that needs reading comprehension across a chunk and its surrounding
context, not a structural pattern match — the same class of exclusion this
project has drawn for RET-02/03/05's semantic-judgement scope elsewhere in
this cluster. What ships here is the fully deterministic, near-zero-FP
structural half only.

**Why a 300-word floor.** A short page (a contact page, a single-product
landing page with a photo and a price) legitimately has no headings and no
Q&A framing without that being any kind of defect — there is not enough
content for a document outline to matter. The floor is intentionally the
same shape as RET-04's word-count floor, applied for the analogous reason:
below it, the absence of structure is not a meaningful signal.

**A real bug caught by live validation, not a fixture: which word count to
use.** The first implementation used the same `extract_prose_text()`
corpus RET-04 uses (structured regions excluded) for RET-07's word-count
floor too. Live testing against `paulgraham.com`'s essays — genuinely
headingless, long-form prose, the exact page shape RET-07 exists to catch
— found the bug: Paul Graham's pages are laid out entirely inside
`<table>` elements (old-school HTML, tables used for visual layout, not
data), so RET-04's table exclusion — correct for that capability's own FP
guard — silently reduced the page's word count to near zero, suppressing
RET-07 entirely on exactly the pages it should have caught. Fixed by
switching RET-07 to `extract_json_ld_and_text()`'s visible-text corpus
(RET-01's, which excludes nothing but script/style/code), which has no
reason to inherit RET-04's own FP guard. A capability sharing another
capability's extraction corpus is only safe when their false-positive
guards actually agree — they did not here, and the fix is to give each
capability the corpus its own logic actually needs.

**Live validation, five real pages, two genuine positives.**
`paulgraham.com/simply.html` and `/read.html` (headingless, table-laid-out
essay pages — fires, confirming the bug fix above), `en.wikipedia.org/
wiki/Glossary_of_chess` and `docs.python.org/3/library/re.html` (both
well-headed, stay silent), and `python.org/about/` — an unexpected second
genuine positive on a major, reputable site: 1445 words of visible text
with **zero** `<h1>`-`<h6>` tags anywhere in the raw markup, independently
confirmed with a plain `grep -oE "<h[1-6][ >]"` outside this skill's own
code, returning nothing. python.org's own About page uses styled `<div>`
elements rather than real heading markup for its visual section titles —
exactly the retrieval-structure gap this capability exists to name, on a
site that is otherwise a model of good markup elsewhere in this project's
own validation history (its `docs.python.org` subdomain, PEP pages, etc.).

---

## RET-09 — Positional fact interment

**What it catches.** A page with 800+ words of prose whose load-bearing
values — currency amounts, unit-bearing numbers (`%`, weights, distances,
durations, data sizes), explicit dates, and dimension/spec patterns
(`52x38x12`) — sit only in the document's middle band (normalized position
`0.25 < p < 0.75`) and are never restated anywhere a reader or a
retrieval/attention mechanism is likely to land first: the `<title>`, any
`h1`/`h2`, the opening or closing 15% of prose, a `<dt>`/`<dd>` definition,
a `<td>`/`<th>` table cell, or the page's own JSON-LD. Fires when at least
3 distinct such values are found and at least 40% of all extracted values
meet that "interred" condition.

**Why this mechanism, and why it is scored `confidence: medium` rather than
`high`.** Liu et al. ("Lost in the Middle", TACL 2024) demonstrate a
U-shaped accuracy curve for LLMs retrieving facts from long contexts —
information in the middle is measurably more likely to be dropped from a
synthesized answer than the same information at either end, independent of
whether retrieval itself succeeds. Hsieh et al. (2024) give the
architectural explanation (positional attention bias, RoPE long-term
decay), and Chroma's 2025 "Context Rot" study replicates the degradation
across 18 frontier models including GPT-4.1, Claude 4 and Gemini 2.5 — this
is not a solved problem, but it is also a *probabilistic* mechanism, not a
guarantee of omission on any single page. `confidence: medium` says so
directly in the finding's own field rather than burying the hedge in
evidence wording, the same convention this project already uses for other
genuinely contested mechanisms.

**Why an 800-word gate.** Below 800 words there is no meaningful "middle"
for a value to be lost in — a short page's values are inherently close to
both margins regardless of where they sit. The gate is intentionally high
relative to RET-04's (80 words) and RET-07's (300 words): this capability's
entire premise depends on there being enough distance between a value's
position and either margin for "buried in the middle" to mean anything.

**Why these value patterns, and why a fresh extractor.** Currency, unit-
bearing numbers, dates, and dimension/spec patterns are the load-bearing
figure shapes the plan's own worked example names (`$1,299`, `40%`, `18
months`, `2.4 GB`). This is a deliberately fresh, narrow regex extractor —
not reused from `extract_prose_text` (RET-04's structured-region exclusion
is the wrong corpus here: a value inside a spec table is exactly the kind
of anchor RET-09 wants to credit, not exclude) or `extract_json_ld_and_text`
(RET-09 reuses that function's already-flattened `json_ld_nodes` output
directly rather than re-parsing JSON-LD a third way). The unit list is
broader than the plan's own worked example implies is required (currency,
`%`, weight/distance/time/data units, degrees, a bare multiplier like
`2.4x`) — narrow enough to keep false-positive risk low (a preceding digit
and a trailing word boundary are both required for every alphabetic unit),
wide enough to catch the plan's own "18 months" example, which is a time
unit outside its algorithm section's literal `hrs`-only list.

**Why a value is deduplicated to one representative position.** The same
figure can appear more than once in a document; the margin-restatement test
below is a *global* presence check (is this value present anywhere among
the anchor sites), not tied to a specific occurrence, so tracking more than
one offset per distinct value adds no information the check would use.

**The margin-restatement test is global, not proximity-based.** A value
counts as anchored if it appears *anywhere* in the combined text of the
title, h1/h2 headings, the opening 15% of prose, the closing 15% of prose,
every `<dt>`/`<dd>`, every `<td>`/`<th>`, or any JSON-LD leaf value —
regardless of where in the document the anchor site itself sits relative to
the buried occurrence. This is deliberate: a spec table placed in the
document's own middle still functions as an anchor (the reader or model
encounters the value structurally, not just positionally), which is exactly
why the plan's own adversarial test case requires a mid-document spec table
to suppress the finding.

**The three required false-positive guards:**

1. **Chronology guard.** If 70%+ of a page's extracted values are bare
   4-digit years appearing in non-decreasing document order, the page is a
   timeline (a history page, a changelog, a "company milestones" section),
   not a page burying facts — silent regardless of the other thresholds.
   This directly answers the mechanism research's own named false-positive
   risk.
2. **Summary-block guard.** A heading matching `summary`, `tl;dr`, `key
   takeaways`, `at a glance`, or `overview` anchors every value in the
   block under it, even if that block itself sits in the document's middle
   third — a summary section is functionally a second opening, not buried
   text.
3. **The 800-word gate itself** (see above) is the third required guard per
   the plan — restated here because it is load-bearing, not merely a
   performance floor.

**Why the overlap with CQ-01 (`content-quality-audit`) is intentional, not
a duplicate.** CQ-01 asks whether a *canonical answer* sits near the top of
the page. RET-09 asks a narrower, deterministic question over the *whole*
document: are load-bearing *values* anchored at either margin, a heading, a
table, a definition, or JSON-LD — never whether the opening reads well.
Different trigger, different remedy, different capability id — both can
fire on the same page; `OverlapControlTests` in
`tests/test_retrieval_readiness.py` proves neither trips the duplicate-
finding-id guard.

**What was left out, and why.** Abbreviated month names ("Jan 15, 2024")
are not matched — only full month names, ISO dates, and slash-form dates —
narrower than it could be, to avoid the false-positive surface a 3-letter
abbreviation pattern would open against ordinary capitalized words. Ranges
("$50-$100", "10-20%") are matched as their component values, not as a
single range value — a deliberate simplification, not a bug: each endpoint
is independently load-bearing and independently checked for restatement.
Numeric equality (matching "$1,299" against a JSON-LD `"1299.00"`) is not
attempted — the margin-restatement test is literal substring containment,
case-insensitive, mirroring RET-01's own exact-token-survival philosophy
rather than adding a normalization layer with its own false-positive
surface.

---

## RET-10 — Chunk self-containment

**What it catches.** A content block (per `shared.text_spans.extract_blocks`)
of 25+ words whose first sentence opens with an unresolved reference — a
leading personal/possessive pronoun (`it/they/he/she/them/its/their`), a
leading demonstrative (`this/that/these/those`) not immediately followed by
a proper-noun-like capitalized word, or a generic definite description
(`the company/product/platform/service/tool/team`) — and which never names
its own subject anywhere inside itself (no proper noun, no word shared with
the page's `<title>`/`<h1>`, no topic term repeated from its own nearest
heading). Fires once per page, not once per block, when at least 25% of
judged blocks (across at least 4 of them) are context-dependent this way.

**Why this mechanism.** A RAG pipeline retrieves chunks, not whole pages,
and the block is the smallest unit every real chunker respects. A chunk's
dense-retrieval embedding is computed only from the text inside it — if the
entity is never named there, the embedding drifts away from queries that
name the entity explicitly, hurting recall; and if the chunk is retrieved
anyway, the model has to guess or invent the antecedent. Three independent
2025 papers converge on this from different methodologies: CoRAG
(coreference preprocessing before chunking), CLAP ("semantic chunking
inevitably breaks cross-chunk context ... leading to degraded expansion
quality and suboptimal retrieval performance"), and an ACL SRW study
measuring gains in both retrieval relevance and downstream QA accuracy from
coreference resolution in RAG. This also absorbs the defensible core of a
deferred "chunk fracture" idea from this project's own capability-selection
process: a block whose value sits far from its own subject is exactly a
block that fails the anchor test below, captured here without an arbitrary
window-offset heuristic.

**Why a 25-word floor, distinct from every other floor in this file.** A
short block naturally retrieves alongside its neighbors in most real
chunking strategies (which merge short adjacent blocks up to a target
token count), so a short block opening with "It..." is not the same risk
as a long, substantial block standing entirely on an unresolved reference.
25 words is deliberately lower than RET-04's 80-word floor or RET-07's
300-word floor — those decide whether a *page* has enough content for a
signal to mean anything; this decides whether a single *block* is
substantial enough to plausibly be retrieved and read alone.

**The anaphor test, worked through.** "It cut onboarding time by 40%." —
leading pronoun, anaphoric. "This approach scales better than the last
one." — leading demonstrative not immediately followed by a capitalized
word (`approach` is lowercase), anaphoric: "this approach" does not say
*which* approach. "This Widget Pro ships with a longer battery." — leading
demonstrative immediately followed by a capitalized word (`Widget`), *not*
anaphoric: the block names its own subject in the same breath. "The
company reported strong earnings." — generic definite description,
anaphoric: "the company" could be any company. "Acme Corp reported strong
earnings." — an ordinary named subject, not anaphoric at all, since the
first word is neither a pronoun, demonstrative, nor "the".

**Why "not immediately followed by a capitalized word" for demonstratives,
specifically.** This is the resolution to an apparent contradiction between
the plan's own worked example ("This approach scales better" is cited as
unresolved) and its own required exemption (self-referential deixis, "This
guide explains ..." must never fire). Both "This approach" and "This
guide" are demonstrative-plus-lowercase-noun — the anaphor test alone
cannot distinguish them by capitalization, because neither is capitalized.
The self-deixis exemption (below) is what actually separates them: "This
guide/article/page/post/section/table/chapter" is checked *before* the
general anaphor test and, when it matches, always wins — the block is
never counted as context-dependent regardless of what the general anaphor
test would have said. "This Widget Pro" is a *third*, distinct case: a
demonstrative followed by an actual capitalized entity name, which the
anaphor test itself declines to flag (no exemption needed — the block
already names its subject in its own first sentence).

**The three anchor sources, and why each is needed.** (1) A proper-noun
token anywhere in the block (`shared.text_spans.proper_noun_tokens`) — the
strongest, most direct anchor: the block names an actual entity. (2) A
content word (non-stopword, 4+ characters) shared with the page's own
`<title>`/`<h1>` — a block that repeats the page's own subject, even
without a capitalized proper noun (e.g. "the setup process" on a page
titled "Setup Documentation"), is anchored to the page's topic. (3) A
content word repeated from the block's own nearest preceding heading — the
same logic, scoped to the block's local section rather than the whole
page. All three are checked as simple word-set intersections, deliberately
without any semantic/embedding comparison — the same "reimplement the
narrow, deterministic slice, not the general NLP task" discipline this
project has applied everywhere else in this cluster (RET-01's exact-token
survival, RET-09's literal substring restatement check).

**Required exemption: self-referential deixis.** "This guide/article/
page/post/section/table/chapter explains ..." names *itself*, not an
external antecedent — checked first, on the first sentence, and always
wins over the general anaphor test. This is the research's own stated
false-positive risk, addressed directly.

**Required, but not suppressed: the heading-anchor confidence signal.**
When a context-dependent block's own nearest preceding heading carries a
proper noun or a real content word, a heading-aware chunker (one that
carries the preceding heading forward into each chunk) could still resolve
the reference — but *most* naive chunkers do not carry headings forward,
so this is not grounds to suppress the finding. Instead: `nearest_heading`
is recorded in each example, and the page-level `confidence` is `high`
only when *none* of the page's context-dependent blocks have any heading
anchor at all (most commonly, a page with no headings above the flagged
blocks whatsoever); otherwise it stays at `medium`, per the plan.

**Why RET-10 fires once per page, not once per block.** The same "report
proportional to defect classes, not occurrence count" discipline RET-08
and RET-01 already established in this file — a page with a systemic
anaphora problem would otherwise flood the report with one finding per
paragraph. `structured_evidence.examples` carries up to 5 verbatim
examples (`text`, `first_sentence`, `nearest_heading`) so a reader still
sees concrete instances, not just a count.

**Overlap with RET-06, and why it is intentional.** RET-06 (agent-judged,
this same file) triggers on a paragraph's *length* (≥80 words and ≥5
sentences) and asks whether it blends several distinct ideas — a semantic
judgement about content variety. RET-10 is fully deterministic, triggers on
*anaphora*, and asks only whether a block names its own subject — it never
reads the block's ideas at all. A single long paragraph can legitimately
trip both: opening with an unresolved "it" *and* wandering across several
unrelated topics are independent defects with independent fixes (name the
subject vs. split the paragraph). `tests/test_retrieval_readiness.py::
Ret10Ret06OverlapControlTests` proves both surface distinctly from
`audit_html()` (one as a script `Finding`, one as an
`agent_judgement_required` candidate) and, once the agent has authored its
own RET-06 finding, compose cleanly through `compose_report.py` with no
duplicate-id collision — the same shape RET-09's own overlap-control test
against CQ-01 already established, but intra-skill here rather than
cross-skill.

**What was left out, and why.** The anaphor test only inspects a block's
*first* sentence — a mid-block anaphoric reference ("The pricing changed
last quarter. It affected every region.") is not evaluated, since the
plan's own detection algorithm scopes the test to the opening sentence
specifically (the sentence most likely to be a chunk's own lead-in, and
the one a chunker's embedding weighs most heavily). This is a documented,
accepted narrowing, not an oversight — broadening it to every sentence in
a block would need a real coreference-resolution pass, well beyond what a
regex-based anaphor test can safely claim.

---

## What extraction does not handle (known, accepted limits)

- **Malformed HTML with mismatched or improperly nested heading tags** can
  cause a second, invalid nested heading to be folded into its parent's text
  buffer rather than recorded as its own heading. No HTML-repair dependency
  is used; this is a documented limitation, not silently corrected, the same
  disposition every other HTML-parsing script in this project already
  states for its own extraction step.
- **Content assembled by JavaScript after load** is invisible to `--url`
  mode, which fetches raw HTML only. A page whose real heading structure
  depends on client-side rendering is gate 2's problem, not this skill's.
- **Visually-hidden headings** (e.g. a screen-reader-only `<h2>` used purely
  for accessibility structure) are evaluated the same as any other heading.
  This is intentional, not an oversight: a hidden heading still participates
  in the document outline a retrieval system reads, so a skip involving one
  is still a real structural gap.
- **Malformed JSON-LD is silently skipped for RET-01's purposes**, not
  reported — `entity-audit`'s ENT-01 already owns malformed-JSON-LD
  detection as its own finding; RET-01 only needs whatever identifiers
  successfully parsed elsewhere on the page, and reporting the same
  malformed block twice under two different capability IDs would be
  duplicate noise, not two independent findings.
- **JSON-LD injected by client-side JavaScript after load** is invisible to
  `--url` mode, same as RET-08's heading limitation above — gate 2's
  concern, not this skill's.
- **A styled `<div>`/`<strong>` used as a visual section title, with no
  real heading element, is never counted as a heading for RET-07's
  purposes.** This is intentional, not an oversight — it is in fact the
  exact defect this capability exists to flag (as `python.org/about/`'s
  live positive shows). Distinguishing a genuine visual-only label from
  incidental bold text would need render/CSS inspection, the same gate-2
  boundary this project draws everywhere else.
- **RET-09's value extractor does not attempt every conceivable
  load-bearing-value shape.** Abbreviated month names, numeric ranges
  collapsed to a single value, and any value expressed only in prose
  without a currency symbol/unit/date pattern (e.g. a number spelled out
  as a word) are all outside this extractor's scope — a fresh, narrow
  regex set per the plan, not the general-purpose numeric-entity extraction
  a full NLP pipeline would attempt.
- **RET-09's margin-restatement test is literal substring containment,
  not numeric equivalence.** `"$1,299"` in prose is not credited as
  restated by a JSON-LD value of `"1299.00"` or `"1299"` — the two strings
  differ. This mirrors RET-01's own exact-token-survival design rather than
  adding a normalization layer with its own false-positive surface, at the
  cost of occasionally under-crediting a genuinely present but
  differently-formatted restatement.
- **RET-10's anaphor test only inspects a block's first sentence.** A
  mid-block anaphoric reference is not evaluated — a documented narrowing
  matching the plan's own detection algorithm, not an oversight. Broadening
  it to every sentence in a block would need real coreference resolution,
  not a regex-based opening-sentence check.
- **RET-10's in-block anchor test is word-set intersection, not semantic
  matching.** A block that refers to its subject only via a synonym never
  present in the title/h1/heading text (e.g. "the firm" for a company
  named only "Acme Corp" elsewhere) is not credited as anchored. This
  mirrors the same "reimplement the narrow, deterministic slice" design
  RET-01 and RET-09 already use in this file.
