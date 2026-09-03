# Citability detection rules and the CIT-04/CIT-13 judgement rubrics

Reference for `citability-audit`. CIT-01/02/06/07's rules and guards are
documented first; CIT-04's and CIT-13's judgement rubrics (read before
scoring, per SKILL.md's procedure) follow, in the same style as
`engagement-audit`'s `engagement-judgement-rubric.md`.

---

## CIT-01 — Trust-signal authority (About-page discoverability)

**What it catches.** No link on the page resolves to a conventional
About/company URL path. Scoped to this single, low-FP sub-case of the
matrix's broader "trust-signal authority" description (which also mentions
bylines and author bios — deliberately excluded, see below).

**Matching is segment-based, not a path-anchored regex.** A link's path is
split on `/` and each segment compared against a fixed set
(`about`, `about-us`, `our-story`, `company`, `our-team`, `who-we-are`,
`meet-the-team`, `team`). This was not the first implementation: a regex
requiring a literal leading `/` before the matched word missed
`href="about-us"` — an entirely ordinary same-directory relative link with
no leading slash — because `urlparse("about-us").path` is `"about-us"`, not
`"/about-us"`. Found by sweeping realistic link forms against the code before
writing a single formal test. Segment-based matching handles every href form
(leading slash, none, `./`, `../`, trailing slash, query string) uniformly,
and whole-segment membership is naturally immune to the substring false
positives a looser pattern would risk: `/roundabout-tour`,
`/company-news/2026`, and `/team-building-tips` all correctly do not match,
because none of their path *segments* equals `about`, `company`, or `team`
exactly.

**Why byline/author detection is excluded.** The matrix's fuller description
("missing bylines, thin author bios") is genuinely page-type-dependent — a
byline is expected on an article and nonsensical on a product page — and
reliably distinguishing the two from markup alone risks a false-positive
rate this project's bar does not accept. Left out as a stated scope
narrowing, not silently dropped.

---

## CIT-02 — Explicit source attribution

**What it catches.** A substantial page (500+ words) linking to zero other
domains. Appendix D: a claim repeated only on the brand's own site, with
nothing pointing outward to corroborate it, is fragile — and a page of any
real length making claims with no outbound attribution at all is the
extreme case of that fragility.

**Why 500 words.** Below that, a page is more likely a pricing table, a
contact page, or a short landing section — genuinely fine with zero external
links, and flagging it would be exactly the false positive this check must
avoid. The threshold is a stated tradeoff (recall for precision), not a
principled boundary; `MIN_SUBSTANTIAL_WORD_COUNT` in the script if it needs
revisiting.

**`www.` is not a different domain.** `www.example.com` and `example.com`
are the same site; a link between them is not a citation. Both the page's
`site` label and every candidate link's hostname are compared with a leading
`www.` stripped, so a page that only links to its own `www.`-prefixed
subdomain still correctly fires — confirmed by a dedicated test, since it is
exactly the kind of case that would otherwise silently under-count how
self-referential a page is.

---

## CIT-06 — Statistics density / numeric verifiability

**What it catches.** An unqualified superlative ("the best", "industry-
leading", "unmatched") in a sentence with no digit anywhere in it. An
assistant cannot verify or quote a superlative as a fact — a sourced number
is quotable, "industry-leading" on its own is marketing language.

**Guard: sentence-length bounds.** Fragments under 20 characters (nav labels
like "Best Sellers") and anything over 400 characters (likely a parsing
artifact, not a real sentence) are excluded — the same bound
`content-quality-audit`'s CQ-05 uses, for the same reason: short fragments
outside real prose are the primary false-positive source for phrase-based
checks.

**Guard: the number can be anywhere in the sentence**, not necessarily
adjacent to the superlative — "The fastest plan processes 940 requests per
second" is clean, because the qualifying number is present in the same
sentence even though it isn't directly beside "fastest." Requiring adjacency
would under-detect legitimately supported claims.

---

## CIT-04 — Citation recall (agent-judged)

### The question

A candidate is a sentence containing a number with no link anywhere in that
same sentence (`find_citation_recall_candidates`, deterministic and pure).
The judgement layered on top: **is this specific number load-bearing** —
central enough to the page's claim that a reader would reasonably expect it
sourced — or incidental, where no reasonable reader would expect a citation?

### When this capability does not apply — say so, emit nothing

- `candidate_unsourced_claims` is empty. Nothing to judge.
- Every candidate is incidental (a price, a model number, a date, a page
  count) — do not manufacture a finding to justify having read the list.

### Calibration: load-bearing (finding warranted)

> "Our servers handle 10 million requests per second with no downtime
> reported."

A specific, striking performance claim, presented as a fact a reader would
weigh when evaluating the product — exactly the kind of number that gets
challenged and exactly the kind that should carry a source.
`severity: medium`, `confidence: medium` (the observations alone cannot
fully rule out the number being defined/sourced elsewhere on a page you
haven't fully read — check the live page before finalising).

> "Studies show that 73% of buyers abandon carts due to unexpected shipping
> costs."

A statistic attributed to unnamed "studies" with no link — the classic
uncited-statistic pattern. `severity: medium`, `confidence: high` — the
vague attribution ("studies show") without a source is itself corroborating
evidence that this number needs one.

### Calibration: not load-bearing (no finding)

> "This plan starts at $49 per month."

A price is not a claim that needs external sourcing — it's the seller's own
stated price. No finding, even though it is a bare, unlinked number.

> "Founded in 2019, we've grown to a team of 40."

Company facts about the page's own organisation (founding year, headcount)
are self-reported by nature — a reader does not expect or need a citation
for a company's claims about itself, unlike a claim about the external world
(market size, competitor performance, industry statistics).

> "The device weighs 180 grams and measures 146mm tall."

Product specifications are the manufacturer's own stated facts — the same
category as the price example. No finding.

### Writing the finding

- `id`: `CIT-04-unsourced-load-bearing-claim` (append a short slug if more
  than one fires on the same page, e.g. `-servers`, `-cart-abandonment`).
- `evidence`: quote the exact candidate sentence — do not paraphrase.
- `severity`: `medium` in essentially all real applications of this rubric.
- `mechanism`: state plainly why *this specific* claim is load-bearing —
  the reader should be able to see the reasoning, not just the verdict.
- `category`: `"discoverability"`, `gate`: `3`.
- Never invent a claim that is not one of the listed candidates, and never
  judge a candidate you would classify as self-reported (price, spec, company
  fact about itself) as load-bearing just because it contains a number.

---

## CIT-13 — Off-site corroboration (agent-judged, cycle 19)

### The question

A candidate is a claim from this page (the same CIT-04 extraction, reused)
whose own significant number was not found on any of the agent-supplied
off-site pages that were fetched (`find_offsite_corroboration_candidates`,
deterministic numeric survival check). The judgement layered on top: is
this claim **genuinely fragile for being single-sourced** — a
decision-critical fact appendix D says a reader would want independently
corroborated — or an obviously fine unsourced detail that off-site
corroboration was never going to exist for anyway (a price, an internal
metric, a model number)? This is the same self-reported-vs-external
distinction CIT-04 already draws, applied to a different signal.

An unmatched number is a much weaker signal than CIT-04's "no link at all"
— it only means *this project's own bounded set of fetched off-site pages*
didn't happen to mention it, which says nothing definitive about whether
the claim is corroborated somewhere the agent didn't check. Treat every
candidate as "worth a second look," never as "proven uncorroborated."

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The claim is self-reported by nature (price, spec, headcount, internal
  metric) — the same category CIT-04's rubric already excludes. Off-site
  corroboration was never going to exist for these; their absence off-site
  is expected, not a defect.
- Too few off-site pages were checked (`offsite_pages_checked` is 1 or 2)
  to treat "not found" as meaningful — a thin check proves little either
  way.

### Calibration: genuinely fragile (finding warranted)

> `claim`: "Independent lab tests confirmed our device reduces allergens by
> 94% compared to leading competitors."
> `number`: "94%"
> (checked against 4 off-site pages, none mention this figure)

A specific, competitively significant claim attributed to "independent lab
tests" with no named lab, no link, and — per this check — no off-site
mention anywhere the agent looked either. This is exactly the single-source
fragility appendix D describes: a claim invoking outside authority that
cannot actually be found outside the brand's own site. `severity: medium`,
`confidence: medium` — the off-site check is bounded (only the pages the
agent supplied), so this cannot rule out corroboration existing elsewhere.

### Calibration: acceptable as-is (no finding)

> `claim`: "Our starter plan is priced at $29 per month."
> `number`: "29"

A price is self-reported by nature — the same reasoning CIT-04's rubric
already gives. Off-site corroboration was never expected to exist for a
seller's own price. No finding, regardless of what the numeric-survival
check found.

> `claim`: "Founded in 2019, we now employ over 400 people."
> `number`: "400"

Company facts about the page's own organisation — self-reported, not the
kind appendix D worries about single-sourcing. No finding.

### Writing the finding

- `id`: `CIT-13-unsourced-offsite-claim` (append a short slug if more than
  one fires on the same page).
- `evidence`: quote the exact candidate claim, name how many off-site pages
  were checked (`offsite_pages_checked`), and state plainly why this claim
  is decision-critical enough to want independent corroboration.
- `severity`: `medium` in essentially all real applications of this rubric.
- `confidence`: `medium` at most — the off-site check is inherently bounded
  to whatever pages were supplied, never proof of universal absence.
- `category`: `"discoverability"`, `gate`: `3`.
- Never judge a self-reported claim (price, spec, headcount) as fragile
  just because the numeric-survival check flagged it — the same discipline
  CIT-04's rubric already establishes.
