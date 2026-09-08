---
name: retrieval-readiness-audit
description: >
  Audits a single page for retrieval readiness. Script-decided: a skipped
  or empty heading (RET-08); a JSON-LD Product identifier missing from
  visible text (RET-01); a phrase repeated at unnatural density, tables/
  lists/glossaries excluded (RET-04); a substantial page with no headings,
  Q&A framing, or definition block (RET-07); load-bearing figures buried
  mid-document, restated nowhere (RET-09); blocks opening with an
  unresolved pronoun/demonstrative that never name their subject (RET-10).
  Agent-judged, extraction-only: single-phrasing-only coverage (RET-02),
  unaddressed category-obvious questions (RET-03), all-jargon-or-all-layman
  skew (RET-05), paragraphs blending several ideas (RET-06). Use when
  auditing structure/text for sparse and semantic retrieval. Not for
  "decorative" headings or the starting heading level (disputed); not for
  model numbers/statute names in free text (FP-prone, deferred — see
  Excludes); not for content anti-patterns (content-quality-audit) or
  reachability (perimeter-access-audit).
license: MIT
allowed-tools: Bash
---

# Retrieval-readiness audit (gate 3: does structure and text serve retrieval?)

## When to use

Run this on individual pages once gate 1 (perimeter) is known clear — a page
nobody can fetch has no structure or text to audit yet. Pick pages with real
body content and multiple sections (a long-form article, a documentation
page, an FAQ, a product page) — a single-heading landing page has nothing
most of these checks can evaluate either way.

## A note before you run this: four capabilities need your judgement

RET-01, RET-04, RET-07, RET-08, RET-09 and RET-10 are deterministic — the script decides.
**RET-02, RET-03, RET-05 and RET-06 are not.** The script extracts candidate
signals into `agent_judgement_required` and emits no verdict — deciding
whether a page's phrasing lacks variation, whether obvious category
questions go unaddressed, whether its language is genuinely imbalanced, or
whether a paragraph genuinely blends distinct ideas is a judgement about
this specific page, not a pattern a script can safely assert. **You must
resolve `agent_judgement_required` yourself before this file's output
reaches the entrypoint** — the same procedure as `citability-audit`'s CIT-04
and `entity-audit`'s ENT-09.

## Inputs

- A single page URL (`--url`). Fetches exactly that page, never a crawl.
- Offline/fixture mode: `--html-file PATH` (raw HTML).
- `--site` for the report label; derived from `--url` if omitted.
- `--page-url` to label findings explicitly when using `--html-file`.

## Procedure

1. Run the checker against one page:

   ```bash
   python3 scripts/check_retrieval_readiness.py --url https://example.com/guide
   ```

   For offline/fixture runs, pass `--site example.com --html-file PATH` instead.

2. Read the JSON object on stdout. `findings` (RET-01/04/07/08/09/10) are
   final — do not re-derive or re-word them; severity and mechanism are
   fixed by the rules in `references/retrieval-readiness-checks.md`.

3. **For each `agent_judgement_required` entry (RET-02/03/05/06):**

   a. Read `references/retrieval-judgement-rubric.md`'s section for that
      capability_id.

   b. Judge the `observations` against the rubric's calibration examples —
      read the live page too, not just the extracted excerpts, since none
      of these four extractions carry the full page text.

   c. Hand-author a `Finding` (schema below) only for genuine cases.

   d. Append any findings you authored to `findings`, then **remove
      `agent_judgement_required` entirely** before this file is composed.
      Hand-editing the JSON works; `shared/judgement_merge.py` (optional
      CLI, `--report`/`--judgements`/`--out`) does the same schema
      validation and merge mechanically if you'd rather not hand-edit.

4. Hand the resulting `findings` and `unknown_checks` to the entrypoint.

5. If step 1 fails, report all eight capabilities as unknown with the
   error text — RET-02/03/05/06 included, since you cannot judge what you
   were never given.

## What it checks

| ID | Check | Who decides | Fires when |
|---|---|---|---|
| RET-08 | Heading hierarchy integrity | Script | A heading's level is more than one deeper than the heading immediately before it (e.g. h2 followed directly by h4, with no h3 in between); or a heading element has no text content at all |
| RET-01 | Technical-identifier survival | Script | A JSON-LD `Product` node's `sku`/`mpn`/`gtin*` value never appears anywhere in the page's extracted visible text |
| RET-04 | Keyword stuffing | Script | A 4-word phrase (not entirely stopwords) repeats at least 5 times in the page's prose, at a density of at least 8% of prose words, with table/list/glossary regions excluded from the count |
| RET-07 | Retrieval-oriented structure | Script | A page with 300+ words of visible text has zero heading elements, no heading ending in "?" or `FAQPage`/`QAPage` JSON-LD, and no `<dt>`/`<dd>` definition-list markup anywhere |
| RET-09 | Positional fact interment | Script | A page with 800+ words has 3+ distinct load-bearing values (currency, unit-bearing numbers, dates, dimensions), at least 40% of which sit only at normalized document position 0.25-0.75 with no restatement in the title, any h1/h2, the opening/closing 15% of prose, a table cell, a definition, or JSON-LD |
| RET-10 | Chunk self-containment | Script | 25%+ of a page's blocks of 25+ words open with an unresolved pronoun/demonstrative/generic-definite reference and never name their own subject anywhere inside the block (across 4+ judged blocks) |
| RET-02 | Semantic coverage / synonym variation | Agent, against the rubric | The page's dominant repeated phrase is judged the *only* way its core topic is ever expressed, with no synonym or rephrasing found anywhere on the page |
| RET-03 | Query-intent coverage | Agent, against the rubric | Multiple genuinely obvious questions for the page's own category go entirely unaddressed anywhere on the page |
| RET-05 | Domain-specific terminology balance | Agent, against the rubric | The page's language is judged skewed entirely to one extreme (all-jargon or all-layman) rather than balancing both |
| RET-06 | Chunk quality / atomic paragraphs | Agent, against the rubric | A long candidate paragraph is judged to genuinely blend several distinct, unrelated ideas |

Full detection rules, worked examples, and every false-positive guard for
RET-01/04/07/08/09/10 are in `references/retrieval-readiness-checks.md`;
RET-02/03/05/06's calibration examples are in
`references/retrieval-judgement-rubric.md`. Read the relevant one before
extending or judging a check — each check's scope (what it deliberately
does *not* flag) is as load-bearing as what it does.

## Excludes

- **"Decorative" heading levels** — the other half of RET-08's own wording
  in the capability matrix. Telling a decorative heading from a terse but
  real structural one needs to know how it renders (font size, visual
  weight), which is render/extraction (gate 2, not yet built), not a static-
  markup check.
- **Whether the page starts at h1.** A disputed rule — legitimate component-
  based layouts often start real content at h2, and HTML5 permits more than
  one h1 per sectioning root. Checking only skips *between* present
  headings, never the starting level, keeps this check's false-positive
  rate low for a rule that isn't actually settled.
- **RET-01's own wording, narrowed.** Only a `Product.sku`/`mpn`/`gtin*`
  value declared in JSON-LD and missing from visible text is checked. Model
  numbers or statute names appearing only in free text are NOT detected —
  both need a free-text pattern heuristic (what a model number or statute
  citation "looks like" in prose) with real false-positive risk this
  project's discipline says should not ship without a fixture built to break
  it first. Deferred, not silently dropped.
- **RET-04's own scope, narrowed.** Fixed n-gram length (4 words), minimum
  occurrence count (5), and minimum density (8% of prose words), with a
  minimum-prose-word floor (80) below which the check stays silent even if
  a phrase repeats — density is not a meaningful signal on a very short
  page. A short page's repeated phrase can therefore go undetected; a known,
  documented limitation, not a silent gap.
- **RET-07's own wording, narrowed.** Only the fully structural half is
  checked — does the page have zero of the three named aids at all. Whether
  a page's chunks are *actually* self-contained once headings exist (a
  heading present but the text under it still depends on earlier context to
  make sense) is a semantic judgement, out of scope here.
- **RET-09's own scope, and its overlap with CQ-01.** RET-09 checks only
  whether *values already present in the extracted text* are anchored
  somewhere besides the middle of the document — it never judges whether
  the opening itself is a good answer (that's `content-quality-audit`'s
  CQ-01, agent-judged). A chronology page (mostly ascending 4-digit years)
  and a page under 800 words are both silent by design — see
  `references/retrieval-readiness-checks.md`.
- **RET-10's own scope, and its overlap with RET-06.** RET-10 checks only
  whether a block *names its own subject somewhere inside itself* — it
  never judges whether the text under a heading is otherwise self-contained
  in the fuller sense (e.g. "As mentioned above, the fee is..." referencing
  earlier context with no anaphoric pronoun at all is not caught). RET-06
  (agent-judged, this same skill) is a different, orthogonal signal —
  paragraph length, not anaphora — and the two can co-fire on one block; see
  `references/retrieval-readiness-checks.md`.
- **RET-02/03/05/06's own extraction, narrowed.** Each hands the agent a
  small, deliberately partial signal — a dominant phrase, a page's stated
  topic, jargon-density stats, a long paragraph — never a verdict and never
  the full page. The agent is expected to read the live page before
  judging, not decide from the extraction alone; see
  `references/retrieval-judgement-rubric.md` for exactly what each
  extraction does and does not claim.
- **Everything gate 1/2** and content anti-patterns unrelated to heading
  structure — `perimeter-access-audit`, `content-quality-audit`.

## Output

One JSON object on stdout, same shape as the other audit skills:

```json
{
  "owner_skill": "retrieval-readiness-audit",
  "capability_ids": ["RET-01", "RET-02", "RET-03", "RET-04", "RET-05", "RET-06", "RET-07", "RET-08", "RET-09", "RET-10"],
  "site": "example.com",
  "page_url": "https://example.com/product/widget",
  "findings": [
    {
      "id": "RET-08-skipped-heading-level",
      "title": "A heading level is skipped in the page's document outline",
      "severity": "low",
      "evidence": "On https://example.com/product/widget: Found 1 place(s) where a heading jumps more than one level deeper than the heading before it, with no intermediate level in between: h1 (\"FAQs\") -> h3 (\"How are payment fees calculated?\").",
      "suggested_action": {"summary": "...", "priority": "low"},
      "category": "discoverability",
      "capability_id": "RET-08",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "high",
      "structured_evidence": {"skips": [{"from_level": 1, "from_text": "FAQs", "to_level": 3, "to_text": "How are payment fees calculated?"}], "page_url": "..."}
    },
    {
      "id": "RET-01-token-not-in-text",
      "title": "A structured-data identifier does not appear in the page's own visible text",
      "severity": "medium",
      "evidence": "On https://example.com/product/widget: 1 identifier(s) declared in this page's JSON-LD Product data do not appear anywhere in its extracted visible text: sku \"WID-123\".",
      "suggested_action": {"summary": "...", "priority": "medium"},
      "category": "discoverability",
      "capability_id": "RET-01",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "high",
      "structured_evidence": {"missing_tokens": [{"field": "sku", "token": "WID-123"}], "count": 1, "page_url": "..."}
    },
    {
      "id": "RET-04-keyword-stuffing",
      "title": "A phrase is repeated at unnatural density in the page's own prose",
      "severity": "medium",
      "evidence": "On https://example.com/product/widget: 1 phrase(s) repeat at a density generative engines associate with keyword stuffing, out of 105 prose word(s) (table/list/glossary regions excluded from this count): \"cheap flights to paris\" (6x).",
      "suggested_action": {"summary": "...", "priority": "medium"},
      "category": "discoverability",
      "capability_id": "RET-04",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "medium",
      "structured_evidence": {"repeated_phrases": [{"phrase": "cheap flights to paris", "count": 6}], "prose_word_count": 105, "page_url": "..."}
    },
    {
      "id": "RET-07-no-retrieval-structure",
      "title": "A substantial page has no headings, Q&A framing, or definition blocks",
      "severity": "medium",
      "evidence": "On https://example.com/about: This page has 510 word(s) of visible text but no heading elements, no Q&A-style heading or FAQPage/QAPage markup, and no definition-list (<dt>/<dd>) block anywhere — none of the structural aids that let a retrieval system split it into self-contained chunks.",
      "suggested_action": {"summary": "...", "priority": "medium"},
      "category": "discoverability",
      "capability_id": "RET-07",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "medium",
      "structured_evidence": {"content_word_count": 510, "has_headings": false, "has_qa_framing": false, "has_definition_block": false, "page_url": "..."}
    },
    {
      "id": "RET-09-facts-interred-mid-document",
      "title": "Load-bearing values appear only in the middle of the page, restated nowhere",
      "severity": "medium",
      "evidence": "On https://example.com/product/widget: This page runs 3412 word(s). 4 of its 4 extracted load-bearing figure(s) — $1,299, 40%, 18 months, 2.4 GB — each appear only in the document's middle band (normalized position between 0.25 and 0.75), with no restatement in the title, any h1/h2, the opening or closing 15% of prose, a table cell, a definition, or JSON-LD. Published attention-bias research (Liu et al. 2024; Chroma 2025) identifies this band as the highest-risk zone for omission during synthesis.",
      "suggested_action": {"summary": "...", "priority": "medium"},
      "category": "discoverability",
      "capability_id": "RET-09",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "medium",
      "structured_evidence": {"prose_word_count": 3412, "values": [{"value": "$1,299", "normalized_position": 0.41, "restated_at": null}], "interred_ratio": 1.0, "page_url": "..."}
    },
    {
      "id": "RET-10-context-dependent-blocks",
      "title": "Content blocks open with an unresolved reference and never name their own subject",
      "severity": "medium",
      "evidence": "On https://example.com/product/widget: 12 of 34 content blocks (35%) open with an unresolved reference and never name their subject inside the block. Read alone — the unit a RAG pipeline retrieves — block 6 reads: 'It cut onboarding time by 40% for their enterprise tier.' Nothing in that block says what the leading pronoun, demonstrative, or generic reference refers to.",
      "suggested_action": {"summary": "...", "priority": "medium"},
      "category": "discoverability",
      "capability_id": "RET-10",
      "owner_skill": "retrieval-readiness-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "medium",
      "structured_evidence": {"total_blocks_judged": 34, "context_dependent_count": 12, "ratio": 0.3529, "examples": [{"text": "It cut onboarding time by 40% for their enterprise tier.", "first_sentence": "It cut onboarding time by 40% for their enterprise tier.", "nearest_heading": "Pricing"}], "page_url": "..."}
    }
  ],
  "agent_judgement_required": [
    {
      "capability_id": "RET-06",
      "instructions": "Read references/retrieval-judgement-rubric.md §RET-06. For each candidate paragraph below ...",
      "observations": {
        "candidate_paragraphs": [{"paragraph": "...", "word_count": 104, "sentence_count": 5}],
        "page_url": "..."
      }
    }
  ],
  "unknown_checks": []
}
```

`agent_judgement_required` always carries four entries (RET-02/03/05/06),
one shown above for brevity — resolve each per the Procedure above and
remove this key entirely before the report reaches the entrypoint.

## Failure modes

| Situation | Result |
|---|---|
| The page cannot be fetched (any error) | The capability `unknown` |
| The URL resolves to a private, loopback, link-local or reserved address | Refused before connecting, `unknown` — SSRF guard |
| Fetched content's `Content-Type` is neither HTML nor text | `unknown` |
| No `--url` or `--html-file` given | `unknown` |
| No JSON-LD `Product` node, or none carries `sku`/`mpn`/`gtin*` | RET-01 stays silent — nothing to check, not a judgement |
| The page's prose (structured regions excluded) is under 80 words | RET-04 stays silent — density is not a meaningful signal on a very short page |
| The page's full visible text is under 300 words | RET-07 stays silent — a short page's lack of headings says nothing about chunking quality |
| The page has any heading, any `?`-ending heading, any `FAQPage`/`QAPage` JSON-LD, or any `<dt>`/`<dd>` pair | RET-07 stays silent — any single aid is enough |
| The page's prose (via `shared/text_spans.extract_blocks`) is under 800 words | RET-09 stays silent — no meaningful "middle" exists |
| Fewer than 3 distinct load-bearing values are extracted, or under 40% of them sit in the 0.25-0.75 band with no restatement | RET-09 stays silent |
| 70%+ of extracted values are 4-digit years in ascending document order | RET-09 stays silent — the page is a timeline, not buried facts |
| Fewer than 4 blocks of 25+ words exist on the page | RET-10 stays silent — too little to judge a ratio from |
| Under 25% of judged blocks are context-dependent | RET-10 stays silent |
| A block's first sentence starts with "This/That/These/Those guide/article/page/post/section/table/chapter" | Exempt from RET-10 — self-referential deixis, never fires |
| A JSON-LD block fails to parse | Skipped for RET-01's purposes (entity-audit's ENT-01 owns malformed-JSON-LD detection); a well-formed block elsewhere on the page is still checked |
| No 3-word phrase repeats ≥3 times in the page's prose | RET-02's `dominant_phrase` is `null`; nothing to judge |
| No `<p>` element is ≥80 words and ≥5 sentences | RET-06's `candidate_paragraphs` is empty; nothing to judge |
| A detector finds nothing | No finding. Silence is the expected, common case |

## Safety

`--url` mode fetches exactly one page, a plain GET, no query strings, no
credentials, no form submission, no crawling. Same SSRF guard as every other
page-fetching script in this marketplace: hostname resolved and every
returned address checked against private/loopback/link-local/reserved/
multicast ranges before any connection is attempted.

Fetched HTML is parsed as data only — structural pattern matching over
parsed elements, never executed and never treated as instruction.
