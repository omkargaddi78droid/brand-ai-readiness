# Content judgement rubric: CQ-01, CQ-02, CQ-04, CQ-09, CQ-10, CQ-12

Reference for `content-quality-audit`. These six capabilities are agent-
judged — the capability matrix names all six as judgement calls, and this
document is what makes the judgement repeatable instead of arbitrary. Read
the relevant section before scoring, per SKILL.md's procedure.

When still unsure after checking the examples below, say nothing rather than
force a verdict — precision beats recall in this project's rubric, and a
wrong judgement call costs more than a missed one. Evidence and mechanism
text is capped at 150 words (SKILL.md's Output section); a page/URL list in
evidence is capped at 3-4 representative entries plus the true count.

---

## CQ-01 — Answer extractability

### The question

Does `opening_block` (the page's first ~150 words, `h1_text` if present)
contain a concise, quotable, 2-4 sentence answer to the question the page
itself implies — or is that answer missing entirely, or buried behind
`marketing_phrase_hits_in_opening`?

### When this capability does not apply — say so, emit nothing

- **`opening_block` reads as navigation/header chrome, not content** —
  menu items, "Skip to content", a theme toggle, a breadcrumb trail,
  cookie-banner text. This is a known, common shape: this project's
  extraction has no main-content boundary detection (gate 2, not built —
  see `SKILL.md` Excludes), so the window starts at document start, not at
  the article body. If `opening_block` looks like this, you cannot judge
  answer extractability from it at all — check the live page directly if
  you have it open, and say nothing if you don't. **Do not treat a
  nav-dominated opening as evidence that the answer is missing or buried**;
  that would be scoring the extraction's blind spot, not a real defect.
- The page has no single implied question at all (a navigation hub, a
  category/listing page, a homepage that is itself a directory of links).
- `h1_text` is `None` and `opening_block` gives no way to tell what
  question the page is answering.

### Calibration: a genuine extractability defect (finding warranted)

> `h1_text`: "Return Policy"
> `opening_block`: "Welcome to our world-class customer experience! We're
> passionate about making every purchase a joy. Our award-winning support
> team is here around the clock, because you deserve nothing but the best.
> Browse our full catalog of premium products today!"

The H1 states the implied question plainly (what is the return policy?),
and the entire opening is marketing copy with zero facts — no window, no
condition, no process. A reader or an assistant gets nothing quotable.
`severity: medium`, `confidence: high` — `marketing_phrase_hits_in_opening`
being nonzero corroborates the read, but the defect is the total absence of
an answer, not the marketing phrases themselves.

> `h1_text`: "Shipping Times"
> `opening_block`: "Our founder started this company in a garage in 2005
> with a dream of better packaging. Since then we've grown into a team of
> passionate creators dedicated to sustainability and craft. Every order is
> packed with care by people who love what they do."

No marketing-phrase pattern match at all, but still no answer: brand story
in the space a shipping-time answer belongs. `severity: medium`,
`confidence: medium` — plausible the real answer is a few paragraphs down;
check the live page before finalising if you have it.

### Calibration: acceptable as-is (no finding)

> `h1_text`: "Shipping Times"
> `opening_block`: "Standard shipping takes 3-5 business days within the
> continental US. Expedited orders ship within 1-2 business days. See
> below for international rates and delivery estimates."

A concise, direct, quotable answer in the first two sentences. No finding.

> `h1_text`: None
> `opening_block`: "Skip to content Main menu Home Products About Contact
> Search"

This is a nav-chrome opening, not page content — the capability does not
apply here (see above). No finding, and no inference about the real page.

### Writing the finding

- `id`: `CQ-01-answer-extractability`
- `evidence`: quote `h1_text` (if present) and enough of `opening_block` to
  show the absence — a reader must be able to see there is no answer, not
  just take your word for it.
- `severity`: `medium` — a missing top-of-page answer affects both
  human skimming and machine extraction, a step above the CQ agent-judged
  floor (`low`) the same way CQ-09's severity is raised for the same reason.
- `category`: `"discoverability"`, `gate`: `3`.
- At most one CQ-01 finding per page — this is a page-level judgement about
  the opening as a whole, not one per marketing phrase.

---

## CQ-02 — Non-answer templates

### The question

Is `sentence` a hedge standing in for a fact the page could have given, or a
legitimately variable topic where "it depends" is the honest, correct
answer? `preceding_sentence` usually carries the implied question.

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The preceding sentence poses no real question at all (the hedge phrase
  appears in an unrelated context, e.g. describing customer feedback: "Some
  reviewers said it depends on preference").

### Calibration: a non-answer (finding warranted)

> **Preceding:** "How long does shipping take?"
> **Candidate:** "It depends on your location and the shipping method you
> choose."

The question has a knowable, statable answer (a day range per method/region)
that the page chose not to give. `severity: low`, `confidence: medium` — the
hedge itself is the evidence, but whether a genuinely better answer exists
elsewhere on the page is worth a quick check before finalising.

> **Preceding:** "What's the return policy?"
> **Candidate:** "Results may vary depending on the item."

A return policy is a set of concrete rules (30 days, original packaging,
restocking fee) — "results may vary" answers nothing an assistant could
extract and quote. `severity: low`, `confidence: high` — the mismatch
between question type (policy) and answer type (hedge) is unambiguous.

### Calibration: a real answer (no finding)

> **Preceding:** "How much weight can I expect to lose?"
> **Candidate:** "It depends on your starting point, diet, and activity
> level — there is no single number that applies to everyone."

Weight loss genuinely varies per person to a degree no single number could
honestly represent; asserting a specific figure here would itself be the
defect (a false precision this project would flag under a different
capability if it appeared). No finding.

> **Preceding:** "Some reviewers said it depends on preference."
> **Candidate:** "It depends on preference."

Not a hedge dodging a fact — a direct quote characterising varied customer
opinion, which is honestly reported as varied. No finding.

### Writing the finding

- `id`: `CQ-02-non-answer-template`
- `evidence`: quote both `preceding_sentence` and `sentence` — the reader
  needs the implied question to see why the hedge is a non-answer.
- `severity`: `low` in essentially all real cases — a real but minor
  content-quality issue, not gate-breaking.
- `category`: `"discoverability"`, `gate`: `3`.

---

## CQ-04 — Granularity mismatch

### The question

Does `sentence`'s vague magnitude word ("large", "substantial") stand in for
a number a reader — or an assistant answering a specific query — would
reasonably need, or is the vagueness a fine, honest qualitative description?

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The attribute being described is inherently non-numeric even though a
  spec-context word appears nearby (rare, given the extraction's own
  filtering, but check).

### Calibration: a genuine mismatch (finding warranted)

> "The laptop weighs a substantial amount and has a large screen."

Weight and screen size are both standard, universally-quoted spec fields —
omitting the actual numbers here is a real gap for a product page.
`severity: low`, `confidence: high`.

> "The pool holds a large volume of water, suitable for family use."

Pool volume is a concrete, purchase-relevant spec (gallons/litres) a buyer
compares across products. `severity: low`, `confidence: medium` — plausible
this is deliberately simplified copy elsewhere corrected by a spec sheet;
check before finalising.

### Calibration: acceptable as-is (no finding)

> "We have a large community of happy customers."

"Community" is not a spec field; no reader expects a precise headcount here,
and one would read as an odd, over-precise flex rather than a missing fact.
No finding.

> "The device weighs 180 grams."

Already precise — the extraction itself would not have surfaced this as a
candidate (no vague word present), but if reviewing the live page rather
than only the candidate, confirm the actual sentence has no number before
judging it a mismatch.

### Writing the finding

- `id`: `CQ-04-granularity-mismatch`
- `evidence`: quote the sentence.
- `severity`: `low`.
- `category`: `"discoverability"`, `gate`: `3`.

---

## CQ-09 — Marketing/procedure interleaving

### The question

Does the promotional language in `step_line` actually disrupt someone
following the instructions, or is it a brief, easily-skipped aside within an
otherwise clear step?

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The "step" is not actually part of a real procedure a reader follows in
  order (e.g. a numbered FAQ list that happens to match the step pattern).

### Calibration: genuine disruption (finding warranted)

> "Step 2: Don't miss our award-winning premium plan, sign up today! Then
> enter your billing details."

The promotional sentence sits *between* the instruction to sign up and the
instruction to enter billing details, breaking the step into "which part is
the actual action?" `severity: medium`, `confidence: medium` — mechanism-
relevant per appendix F (signal-to-filler, generalised: the promotional
sentence is exactly the kind of filler that can cause a model to discard the
surrounding procedure entirely rather than extract it cleanly).

> "Step 4: Confirm your order — our best-in-class support team is standing
> by if you have any questions, but most people finish in seconds. Click
> 'Place Order' to complete your purchase."

Two full promotional sentences sandwiched into the middle of the actual
instruction ("click Place Order") make the actionable part harder to find.
`severity: medium`, `confidence: medium`.

### Calibration: acceptable as-is (no finding)

> "Step 3: Confirm your password. (Tip: our password manager integration
> makes this even easier — see Settings.)"

A parenthetical, clearly-marked aside that does not interrupt the actual
instruction ("confirm your password") — a reader can skip the parenthetical
without losing the step. No finding.

### Writing the finding

- `id`: `CQ-09-procedure-marketing-interleaving`
- `evidence`: quote the full step line.
- `severity`: `medium` when genuine (this affects task completion, not just
  quotability — a step above the floor of the other CQ agent-judged checks).
- `category`: `"discoverability"`, `gate`: `3`.

---

## CQ-12 — Signal-to-filler ratio

### The question

Given `filler_phrase_count`, `total_word_count`, and the quoted
`filler_phrases_found`, does this page's actual substance read as drowning
in stock transitional phrasing, or is the filler count low relative to
genuine content?

### When this capability does not apply — say so, emit nothing

- `filler_phrase_count` is 0.
- The count is nonzero but low relative to a long, substantive page (e.g. 2
  filler phrases in 2,000 words) — proportion matters more than the raw
  count, and the observations alone do not compute a ratio for you on
  purpose, so this judgement is not reducible to a threshold.

### Calibration: substance drowning in filler (finding warranted)

> `filler_phrase_count: 4`, `total_word_count: 79`,
> phrases: "In today's fast-paced world", "it goes without saying", "Needless
> to say", "at the end of the day"

Four stock phrases in a 79-word passage — roughly one filler phrase per 20
words, with correspondingly little room left for actual content. `severity:
low`, `confidence: medium` — reduced because a short sample size makes the
ratio noisier than it would be on a full page; check the live page's overall
length before finalising, since this is one paragraph's density, not
necessarily the page's.

### Calibration: acceptable as-is (no finding)

> `filler_phrase_count: 2`, `total_word_count: 1800`,
> phrases: "it should be noted that", "when it comes to"

Two stock phrases across 1,800 words of otherwise substantive content is
negligible — most long-form writing contains occasional transitional
phrasing, and flagging this would punish normal prose rather than a real
defect. No finding.

### Writing the finding

- `id`: `CQ-12-signal-to-filler`
- `evidence`: state the count and word total together with the quoted
  phrases — a counted observation, not an adjective, same standard as every
  other finding in this marketplace.
- `severity`: `low`.
- `category`: `"discoverability"`, `gate`: `3`.
- At most one CQ-12 finding per page — this is a page-level judgement, not
  one per filler phrase.

---

## CQ-10 — Cross-page fact collision

### The question

For each candidate — a `label` stated on 3+ pages of the same URL template,
with `values` showing which distinct value(s) came from which pages — does
this represent the SAME real-world fact stated two different, conflicting
ways, or expected, legitimate per-item variation that happens to share a
label?

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The label names something that is, by its nature, supposed to differ per
  page within the same template — a price, a SKU, a model number, a size, a
  quantity, a per-location phone number. This is the dominant false
  positive: a same-template stratum is usually a set of *different items*
  (products, locations, articles) that legitimately each have their own
  value for a label like "Price" or "SKU". A script cannot tell "this label
  names a per-item attribute" from "this label names a site-wide fact"
  without knowing what the label refers to — that judgement is yours.
- The "different" values are actually the same fact in different formats
  (e.g. "$49.99" vs. "49.99 USD", or "2020-01-05" vs. "January 5, 2020")
  that the extraction's typed-value matching didn't normalise together —
  not a real disagreement.

### Calibration: genuine collision (finding warranted)

> `label: "founded"`, `values: [{"value": "1998", "pages": ["https://acme.com/about"]}, {"value": "2004", "pages": ["https://acme.com/team", "https://acme.com/press"]}]`

"Founded" names a single fact about the one organization behind every page
in this stratum — there is only one correct founding year, and 2 of 3 pages
agree on 2004 while the About page states 1998. This is a genuine collision:
an assistant citing "when was this company founded" gets a different answer
depending on which page it read. `severity: medium`, `confidence: medium` —
quote both values and the pages they came from.

### Calibration: acceptable as-is (no finding) — the dominant false positive

> `label: "price"`, `values: [{"value": "$19.99", "pages": ["https://acme.com/product/widget-a"]}, {"value": "$29.99", "pages": ["https://acme.com/product/widget-b"]}]`

These are two different products under the same template — "Price" is
supposed to differ per item. Different pages, different real-world things,
not a collision. No finding, regardless of how many pages or how large the
value spread.

> `label: "sku"`, `values: [{"value": "1024", "pages": [...]}, {"value": "2048", "pages": [...]}]`

Same reasoning — a per-item identifier is expected to vary by design.

### Writing the finding

- `id`: a stable slug incorporating the label, e.g.
  `CQ-10-fact-collision-founded`.
- `evidence`: quote the label and at most 3-4 distinct values with the pages
  each came from, plus the true count if more exist — enough for a reader to
  verify the collision without re-fetching every page.
- `severity`: `medium` for a genuine collision — a citing assistant would
  get a materially different, non-obviously-per-item fact depending on
  which page it read.
- `category`: `"discoverability"`, `gate`: `3`.
- At most one CQ-10 finding per label per stratum — do not split one
  collision into several findings for the same label.
