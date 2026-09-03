# Static-extraction checks: detection rules and why each is scoped the way it is

Reference for `static-extraction-audit`. The machine-readable rules live in
`scripts/check_static_extraction.py`; this file explains what each check
catches, why it is scoped the way it is, and what was deliberately left out.

All nine capabilities operate on `_PageParser`'s single-pass output: JSON-LD
blocks, hydration-state JSON blocks (any `<script type="application/json">`,
or a script tagged with a known hydration id like `__NEXT_DATA__`/
`__NUXT_DATA__`), whole-page visible text, `<main>`/`<article>`-scoped text,
image alt-attribute state, video/audio track-child state, PDF link hrefs,
and inline `<script>` text. None of it comes from a rendered page — every
row below is a static approximation of what Cluster B originally described
against a headless-browser render, before hard constraint 1 (no headless
browser, anywhere, cycle 19) made that permanently unavailable.

---

## REN-02 — Hydration-state coverage diff

**What it catches.** A string value inside an embedded hydration-state JSON
blob that looks like real prose — at least 20 characters, at least 3 words —
and never appears (case-insensitive, whitespace-normalized) anywhere in the
page's extracted visible text.

**Why the length/word-count filter.** Hydration JSON is mostly not prose: it
carries ids, slugs, URLs, flags, numbers. A filter requiring real internal
whitespace and enough length screens those out; a value with no space in it
is far more likely an identifier than content. This is a narrowed,
documented scope, the same discipline RET-01 applies to its own field list:
short hydrated facts (a price, a single-word status) are NOT this
capability's concern — REN-04/REN-05 own JSON-LD-declared facts
specifically; this row is about hydrated *prose* going missing, not every
hydrated value.

**Why `unknown`-by-silence when no hydration blob exists.** Most static
(non-framework, or server-only-rendered) pages have no `__NEXT_DATA__`/
`__NUXT_DATA__`/`application/json` script at all. That is the honest,
common, and entirely fine case — this check finds nothing to compare, not a
defect to report.

**What was left out.** `window.__NEXT_DATA__ = {...}` or
`window.__NUXT__ = {...}` assigned as a raw JavaScript object literal
(rather than a `<script type="application/json">` block) is NOT parsed —
that needs a JS parser to extract safely, which this project's stdlib-only
dependency set does not have; regex-scraping a JS object literal was
considered and rejected as unsafe/fragile. Only the JSON-block form is
read. **Found live, worth stating plainly:** Next.js's App Router (the
current default, as of this cycle) streams its payload as RSC "flight
data" (`self.__next_f.push([...])` calls, not a `<script
type="application/json">` block or a `__NEXT_DATA__` id) — this check
reports `unknown`-by-silence on those pages, the same honest "no
hydration blob found" case as a purely static site. Live-checked against
nextjs.org itself (no `__NEXT_DATA__`, no `application/json` script
present at all). Only the Pages Router's `__NEXT_DATA__` convention and
Nuxt 3's `__NUXT_DATA__` convention are covered; parsing RSC flight data
is a materially different, streaming format and out of scope here.

---

## REN-04 — Price-render gating

**What it catches.** A `price` value on a JSON-LD `Offer`/`AggregateOffer`
node, or on a `Product` node's `offers` field (dict or list of dicts, both
permitted by schema.org), that does not appear anywhere in the page's
visible text under a currency-symbol- and comma-tolerant numeric match
(`29.99`, `$29.99`, `29,99`, and `"29.99 USD"` all match `29.99`).

**FP guard: numeric-tolerant, not string-exact.** A price restated with a
currency symbol, a thousands separator, or trailing units is still the same
fact — string-exact matching would flag every one of those as missing. The
check parses every number-shaped substring in visible text and compares by
value (within a 0.005 tolerance for floating-point noise), not by string
equality.

**What was left out.** No currency-conversion awareness — a price declared
in one currency and restated (correctly) in a different one after
conversion will not match; documented, not solved. `priceValidUntil`,
`lowPrice`/`highPrice` ranges, and multi-offer price comparisons are not
checked — only the single `price`/`priceSpecification.price` field.

---

## REN-05 — Real-time availability exposure

**What it catches.** A JSON-LD offer declares an `availability` field (a
volatile, time-sensitive fact — in-stock/out-of-stock/pre-order), and the
page carries no freshness signal anywhere: no `dateModified` field on any
JSON-LD node, and no textual phrase ("as of", "last updated", "updated on",
"checked on", "in stock as of") anywhere in visible text.

**Why page-level, not proximity-scoped.** The ideal check would confirm a
freshness signal sits *near* the specific availability claim it qualifies.
This static text stream does not preserve reliable DOM proximity between an
inline script's JSON-LD position and the surrounding visible text, so this
check is coarser than that: it asks only whether a freshness signal exists
*anywhere* on the page. A page with a freshness statement far from the
actual stock claim is a false negative this row accepts rather than risking
a false positive from guessing proximity.

---

## REN-06 — Semantic HTML5 extraction compatibility

**What it catches.** A page with 150+ words of visible text and no `<main>`
or `<article>` element anywhere in its markup.

**Why the word-count floor.** A trivial page (an error page, a redirect
stub, a single-line contact card) legitimately has no reason to declare a
content boundary — flagging it would be noise, not signal. 150 words is a
low bar deliberately: this check should catch genuinely substantial pages
built without semantic structure, not argue about borderline cases.

**Why this never needed a browser.** `<main>`/`<article>` presence is a
static markup fact; this check was mis-scoped into the original
browser-dependent Cluster B by inheriting its framing, not by its own
detection logic.

---

## REN-07 — Boilerplate / content separation quality

**What it catches.** When a `<main>`/`<article>` boundary exists on a
substantial page (150+ words), the ratio of visible-text words found inside
that boundary to the page's total visible-text words. Fires when that ratio
falls under 30%.

**Why silent when no boundary exists at all.** REN-06 owns that case; a
ratio has nothing to divide by without a boundary to measure. The two
checks are deliberately mutually exclusive on any one page.

**What was left out.** This measures the *declared* boundary's share of
text, not whether the boundary's own content is itself free of chrome (a
`<main>` that still contains a nav block would read as high-ratio and
correct here) — a real but narrower signal than "is the page's content
cleanly separated," documented as a known limitation, not solved.

---

## REN-08 — Multimodal accessibility

**What it catches, as two distinct findings.**

1. **Missing alt text.** An `<img>` with no `alt` attribute, or an
   empty/whitespace-only one, that is not marked decorative
   (`role="presentation"` or `aria-hidden="true"`).
2. **Missing media captions.** A `<video>` or `<audio>` element with no
   `<track>` child at all (captions, transcript, or descriptions).

**FP guard: decorative images excluded.** A purely decorative image
correctly has no `alt` text per accessibility guidance (an empty `alt=""`
or an ARIA-hidden marker is the *correct* pattern, not a defect) — flagging
those would punish sites that already did this right.

**What was left out.** No check on `alt` text *quality* (a vague "image" or
"photo" alt is not distinguished from a genuinely descriptive one) — that
is a semantic judgement this static check does not attempt.

---

## REN-10 — NAP render asymmetry (phone numbers only)

**What it catches.** A US-shaped phone number pattern found inside inline
`<script>` text, normalized to digits-only, that does not also appear
(digits-only) anywhere in the page's visible text — the signature of a
number assembled client-side (e.g. a "click to reveal" pattern) rather than
present as real text.

**Why phone numbers only, not addresses.** Free-form street-address
pattern matching needs a real address parser to keep false positives low —
"123 Main St" is a much fuzzier pattern than a phone number's fixed digit
shape, and this project's discipline (front-load only near-zero-FP checks)
says it should not ship without a fixture built specifically to break it
first. Deferred, not silently dropped; matrix REN-10 stays partially
covered.

---

## REN-11 — PDF-only fact lock (proactive only)

**What it catches.** The presence of any `<a href="*.pdf">` link on the
page. That's it — this check never inspects the PDF's own content.

**Why this can never be a confirmed defect.** Verifying whether a PDF's
key facts are restated in HTML needs to read the PDF's text layer. This
project has no PDF-parsing library in its stdlib-only dependency set (per
the project's own no-third-party-package rule), so there is no way to
confirm or refute restatement — only to note the PDF exists. Every finding
this check emits is `track: "proactive"`, `confidence: "low"`: a
suggestion to check manually, never an assertion that facts are actually
missing.
