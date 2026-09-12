# Retrieval-readiness judgement rubric: RET-02, RET-03, RET-05, RET-06

Reference for `retrieval-readiness-audit`. RET-01/04/07/08's deterministic
rules live in `retrieval-readiness-checks.md`; this file is the calibration
guide for the four capabilities the script cannot verdict on its own — read
the relevant section before resolving any `agent_judgement_required` entry,
in the same style as `citability-audit`'s and `engagement-audit`'s own
rubric files.

**Every entry not resolved into a hand-authored Finding must be removed
from `agent_judgement_required` before this skill's output is composed** —
an unresolved entry becomes a visible `unknown_checks` item, never a silent
drop, per this project's standing contract.

---

## RET-02 — Dense/semantic coverage & synonym variation (agent-judged)

### The question

`find_semantic_coverage_candidates` extracts the page's single most-
repeated 3-word phrase (`dominant_phrase`, ≥3 occurrences) plus up to three
sentences using it (`example_sentences`). The judgement layered on top:
**does the page ever express this same underlying concept a genuinely
different way anywhere else** — a synonym, a conversational rephrasing, a
question form — **or does it only ever state it this one way?** Repetition
of a phrase is not itself the defect (that is RET-04's job, at a much
higher density); the defect is the *absence of any alternative phrasing*
for the page's core topic, which narrows what queries the page can match.

### When this capability does not apply — say so, emit nothing

- `dominant_phrase` is `null` — no phrase repeats often enough to judge.
- The full page (read it, not just `example_sentences`) does show real
  variation elsewhere — different section headings, a summary that
  paraphrases, a synonym used even once in a meaningfully different way.

### Calibration: single phrasing only (finding warranted)

> `dominant_phrase`: "24/7 customer support" (5 occurrences). Every mention
> across the page — hero copy, features list, FAQ, footer — uses this exact
> phrase, never "round-the-clock help," "always-on support," "help
> whenever you need it," or a question form like "can I get help at night?"

A real synonym/conversational-breadth gap: a visitor searching in different
words for the same benefit has no matching phrasing anywhere on the page.
`severity: low`, `confidence: medium` (a script-extracted signal, not a
full-page read — verify against the live page before finalising).

### Calibration: real variation exists (no finding)

> `dominant_phrase`: "email marketing platform" (4 occurrences), but the
> page also says "send newsletters," "automate your campaigns," and has an
> FAQ heading "What is email marketing software?" — different phrasings of
> the same core concept appear throughout.

Genuine breadth. No finding, even though the raw phrase count triggered
extraction.

### Writing the finding

- `id`: `RET-02-single-phrasing-only`.
- `evidence`: quote `dominant_phrase`, its occurrence count, and note that a
  full read of the page found no alternative phrasing for the concept.
- `severity`: `low` (a real but modest retrieval-breadth gap, not a hard
  block). `category`: `"discoverability"`, `gate`: `3`.
- `mechanism`: state that dense/semantic retrieval matches conceptually
  similar queries via varied phrasing, and a single fixed phrasing narrows
  which query forms can match at all.
- Never author a finding from `dominant_phrase` alone without actually
  checking the rest of the page for variation — the extraction only ever
  proves repetition, never absence.

---

## RET-03 — Query-intent coverage (agent-judged)

### The question

`find_query_intent_candidates` extracts `primary_heading`,
`existing_qa_headings`, `has_qa_schema`, and `opening_excerpt`. **Using
your own knowledge of the page's category** (inferred from the heading and
excerpt), name the 3-5 most obvious questions a real visitor to a page like
this would ask — then check whether the page's existing Q&A content or
general body copy already addresses each one. This is the one capability in
this rubric that leans most heavily on the agent's own world knowledge
rather than anything extractable from the page itself; the script cannot
know what questions are "obvious" for an arbitrary category.

### When this capability does not apply — say so, emit nothing

- The page's category/purpose is genuinely unclear from `primary_heading`
  and `opening_excerpt` — do not guess at questions for a page you cannot
  categorize with reasonable confidence.
- The obvious questions you named are already covered somewhere in the
  page's body content, even without a dedicated Q&A heading.

### Calibration: obvious questions unaddressed (finding warranted)

> `primary_heading`: "Wireless Noise-Cancelling Headphones — Model X200".
> `existing_qa_headings`: []. `has_qa_schema`: false. Reading the rest of
> the page: specs, price, and a buy button, but nothing about battery life,
> whether it works with both iOS and Android, or the warranty length —
> three of the most obvious questions any shopper for this category asks.

A real category-appropriate gap. `severity: low`, `confidence: medium`
(the "obvious questions" judgement is inherently softer than a structural
check — say which questions you picked and why).

### Calibration: obvious questions covered without a Q&A heading (no finding)

> `primary_heading`: "Wireless Noise-Cancelling Headphones — Model X200".
> `existing_qa_headings`: [], but the product description prose states
> "up to 30 hours of battery life," "compatible with iOS and Android via
> Bluetooth 5.2," and "backed by a 2-year warranty."

The obvious questions are answered in ordinary prose, just not framed as a
Q&A. No finding — RET-07 (structural Q&A framing) is a different, already-
built capability; RET-03 cares about coverage of content, not its framing.

### Writing the finding

- `id`: `RET-03-unaddressed-category-questions`.
- `evidence`: list the 3-5 questions you judged obvious for this category
  and state plainly that the page's content (quote what you checked) does
  not address them.
- `severity`: `low`. `category`: `"discoverability"`, `gate`: `3`.
- `mechanism`: a retrieval/generative system answering a category-typical
  query about this brand has no content on the page to draw from for that
  question, even though the page is squarely about the right topic.
- Never invent questions that are not genuinely obvious for the category —
  a niche or unusual question going unanswered is not this capability's
  concern, and manufacturing one to justify a finding is exactly the
  overreach this rubric exists to prevent.

---

## RET-05 — Domain-specific terminology balance (agent-judged)

### The question

`find_terminology_balance_candidates` extracts `long_word_ratio`,
`acronym_count`, and three `sample_sentences` (opening, middle, closing).
**Does the page's language skew entirely to one extreme** — all
unexplained jargon with no plain-language framing anywhere, or so
simplified it never names the actual technical terms a domain expert or
precise query would use — **rather than genuinely balancing both?** The
matrix's own framing is explicit that a page needs *both* registers to
serve technical retrieval and simplified generation at once; a page
skewed to either extreme is the defect, not a page that is simply
technical or simply simple in isolation.

### When this capability does not apply — say so, emit nothing

- The three sample sentences (and the full page, if you have it open) read
  as reasonably balanced — some technical terms, with enough surrounding
  plain language to follow them.
- `long_word_ratio` and `acronym_count` are elevated but the surrounding
  prose already explains the terms in context (a glossary, an inline
  definition, a "in other words" clause) — that is balance working
  correctly, not a defect.

### Calibration: all-jargon, no plain-language framing (finding warranted)

> `long_word_ratio`: 0.41, `acronym_count`: 9. Sample sentences: "The API
> leverages OAuth2 PKCE flows with JWT-based RBAC enforcement across
> multi-tenant namespace isolation boundaries." No sentence anywhere on the
> page explains what any of this means in plain terms.

A real all-jargon skew: a non-expert query or a simplified-generation
context has nothing to work with. `severity: low`, `confidence: medium`.

### Calibration: all-layman, missing the real technical terms (finding warranted)

> `long_word_ratio`: 0.04, `acronym_count`: 0. The page describes a
> database product entirely as "it keeps your stuff safe and organized"
> across every section, never once naming what kind of database it is,
> what protocol it speaks, or any term a technical buyer would search for.

The opposite skew — a technical/exact-match query has no matching
vocabulary anywhere on the page. Also a finding, same severity.

### Calibration: balanced (no finding)

> `long_word_ratio`: 0.15, `acronym_count`: 2. Sample sentences show
> technical terms ("end-to-end encryption," "zero-knowledge architecture")
> each followed by a plain-language gloss in the same or next sentence.

Balance working as intended. No finding.

### Writing the finding

- `id`: `RET-05-jargon-imbalance` (or `-oversimplified` for the opposite
  skew — pick the one that matches the direction found).
- `evidence`: quote the ratio/count and 1-2 representative sentences.
- `severity`: `low`. `category`: `"discoverability"`, `gate`: `3`.
- `mechanism`: state which side of retrieval/generation the imbalance
  fails — all-jargon fails simplified generation and non-expert queries;
  all-layman fails exact-match technical retrieval.
- A single dense or single simple sentence is never enough on its own —
  the finding must reflect a genuine, page-wide skew, not an isolated line.

---

## RET-06 — Chunk quality / atomic paragraphs (agent-judged)

### The question

`find_chunk_quality_candidates` flags paragraphs long enough (≥80 words,
≥5 sentences) to plausibly blend more than one idea — length alone is a
filter, not the defect. **Does this specific candidate paragraph actually
address more than one distinct idea**, such that a retrieval system
chunking by paragraph would return a muddied, low-relevance result for a
query about either idea? A long paragraph that stays on one coherent idea
throughout is not a defect, however long it runs.

### When this capability does not apply — say so, emit nothing

- `candidate_paragraphs` is empty — nothing long enough to plausibly blend.
- Every candidate, on reading, is long but stays on a single coherent idea
  (an extended explanation, a detailed walkthrough of one process).

### Calibration: genuinely blended ideas (finding warranted)

> "Our return policy allows exchanges within 30 days of purchase, no
> questions asked. Founded in 2015, our company has grown from a two-person
> garage operation to a team of 200 across three countries. Shipping
> typically takes 3-5 business days within the continental US, longer for
> international orders. Our customer support team is available 24/7 via
> chat, email, or phone for any questions you might have."

Four unrelated ideas (returns, company history, shipping, support contact)
in one paragraph — a retrieval chunk built from this cannot cleanly answer
a query about any single one of them. `severity: low`, `confidence: medium`.

### Calibration: long but atomic (no finding)

> A 120-word paragraph walking through a single multi-step configuration
> process end to end, one continuous idea from start to finish.

Long, but every sentence serves the same single idea. No finding — length
was the extraction filter, not the standard being judged.

### Writing the finding

- `id`: `RET-06-blended-paragraph` (append a short slug if more than one
  candidate qualifies on the same page).
- `evidence`: quote the paragraph, capped at 150 words (truncate with "..."
  past that) — the reader should be able to see the blend themselves, not
  take a summary on faith.
- `severity`: `low`. `category`: `"discoverability"`, `gate`: `3`.
- `mechanism`: state plainly which distinct ideas are blended and why a
  retrieval chunk built from this paragraph would serve neither well.
- Never flag a candidate for length alone — every finding must name the
  specific distinct ideas found blended.
