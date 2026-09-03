# Content anti-patterns: detection rules, guards, and why each guard exists

Reference for `content-quality-audit`. The machine-readable rules live in
`scripts/check_content_quality.py`; this file explains what each check
catches, why it is scoped the way it is, and — for every false-positive
guard — the specific real case that guard exists to stop, because most of
them were only found by running the detectors against realistic text, not
by reasoning about them in advance.

Every check here operates on `extract_visible_text()`'s output: HTML with
`<script>`/`<style>`/`<code>`/`<pre>` stripped, entities decoded, block-level
tag boundaries turned into line breaks, everything else collapsed to single
spaces. This is a narrow text-extraction step for these four checks, not the
render/extraction pipeline (REN-06/07 in the capability matrix) — no
boilerplate-ratio scoring, no main/article boundary detection.

---

## CQ-03 — Template leakage

**What it catches.** A templating engine's placeholder syntax appearing
verbatim in the rendered page — `{{first_name}}` instead of the customer's
actual name. This is not a cosmetic bug: appendix C of the Round-2 model says
explicit, plain-text facts are what a machine extracts correctly, and a
placeholder is not the fact, it is the *absence* of the fact wearing the
fact's position on the page. An assistant reading the page has no way to know
`{{price}}` isn't a real price.

**Patterns matched:** Mustache/Handlebars/Liquid variables (`{{ ... }}`),
Liquid/Jinja tags (`{% ... %}`), ERB/ASP.NET tags (`<% ... %>`). These three
were chosen deliberately over a broader set (see "What was left out" below):
double curly braces and `<%...%>` essentially never occur in ordinary English
prose, so the false-positive floor is very low without needing a semantic
judgement.

**Guard: code/pre stripping.** The single largest false-positive source for
this check is documentation that teaches templating syntax — a tutorial page
showing `{{ product.title }}` as an example is not a defect. `extract_visible_text`
strips `<code>`/`<pre>` before this check ever sees the text, which removes
the overwhelming majority of legitimate examples (most sites that show syntax
examples put them in a code block; that is what the tag is for).

**What was left out, and why.** Two patterns were considered and dropped from
this version: CMS shortcode brackets (`[gallery ids="1,2"]`) — too easily
confused with citation markers (`[1]`), wiki edit links (`[edit]`), or
`[sponsored]`/`[ad]` labels, none of which is a defect; and shell/env-style
`${VAR}` syntax — legitimately discussed in prose on technical documentation
sites ("set the `${API_KEY}` environment variable") even outside a code
block often enough that the false-positive rate did not clear this project's
bar. Both are candidates for a future cycle behind their own fixture pair, not
silently folded into this one's confidence.

---

## CQ-05 — Relative-date anchors

**What it catches.** A sentence that describes a change — "updated",
"increased", "launched" — using only relative time ("last month",
"recently") with no absolute date anywhere in the sentence. This is the
appendix-C mechanism generalised: a relative anchor is only meaningful at the
moment a human reads it. Once an assistant extracts and stores the sentence,
the anchor is gone and the claim reads as permanently current, however old
the page actually gets.

**The two-list-AND design, and why it is not "flag every relative phrase".**
Flagging any occurrence of "this week" or "currently" would fire on nearly
every blog or news page and say nothing useful. A finding only fires when a
relative-time phrase and a change-describing verb appear in the **same
sentence**, with no absolute date also in that sentence. "This week's
newsletter covers three topics" has the phrase but no claim verb, and stays
silent. "We updated our return policy last month" has both, and no date, and
fires.

**Absolute-date recognition** accepts a bare four-digit year (1900–2099), a
month name with a day, or a numeric date — deliberately permissive, because
the goal is to catch the *absence* of any anchor, not to demand a specific
date format.

**Guard: word-boundary phrase matching, not substring.** Regression case:
"We updated the schedule this weekend for everyone" contains the literal
characters "this week" as a prefix of "weekend", and a naive substring check
(`"this week" in text`) matches it — reporting a phrase that isn't actually
there. Every phrase and claim verb is matched with `\b...\b` word boundaries
for exactly this reason. This is the same failure mode already found once in
this project, in `perimeter-access-audit`'s robots.txt user-agent group
matching — substring matching is where silent false positives live, stated as
a general rule in the project's engineering principles and now confirmed
twice in two different detectors.

---

## CQ-07 — Scope-ambiguous numeric claims

**What it catches.** A colon-labeled metric — the spec-sheet, FAQ, or
pricing-table pattern (`Battery life: 10 hours`) — stated twice on the same
page with two different values and nothing nearby explaining why they
differ. An assistant asked "what's the battery life" has no principled way to
pick one of two contradicting numbers, and no way to know they are not simply
an error.

**Why colon-labeled pairs, not general prose.** A fully general version of
this check — finding any two numeric claims in prose that plausibly describe
"the same metric" — needs part-of-speech tagging or an entity model this
project does not have, and a naive keyword-adjacency version would have an
unacceptable false-positive rate. Colon-labeled key:value lines are a strong,
structural, low-ambiguity signal instead: if the label text matches exactly
(after whitespace normalisation and singular/plural folding), it is very
likely the same metric.

**Guard: a qualifier anywhere in the group suppresses the finding.**
`"Battery life: 10 hours"` next to `"Battery life: up to 14 hours"` is not
ambiguous — "up to" is doing the explaining. The qualifier list
(`up to`, `starting at`, `depending on`, `per`, `minimum`, `maximum`, ...) is
checked with word-boundary matching against every line in the group; presence
in *any* line suppresses the whole finding, favoring fewer false positives
over completeness.

**Guard: `per` is not a substring of `period`.** Regression case:
`"Warranty period: 1 year"` / `"Warranty period: 2 years"` was being silently
suppressed, because a naive `"per" in line.lower()` check matched inside the
word "period". Fixed by requiring `\bper\b` — the same substring-matching
lesson as CQ-05, found independently while building this check.

**Guard: unit singular/plural folding.** `"1 year"` and `"2 years"` must be
recognised as the same unit or the pair never groups together at all. Units
captured after the number are folded by stripping a trailing `s` (`years` →
`year`) before grouping — deliberately simple rather than a real stemmer,
sufficient for the common units this check sees (hours, days, years, weeks,
months, minutes).

**Guard: a single-word label is too generic.** `"Price: 10"` / `"Price:
20"` is not flagged — a one-word label is too likely to mean different
things in different places on the page (list price vs. sale price vs.
shipping) to compare on structurally. The label must be at least two words.

**Guard: identical repeated values are not ambiguous.** `"Storage: 128GB"`
appearing twice with the same value is confirmation, not contradiction.

---

## CQ-08 — Computed-stat integrity

**What it catches.** A stated summary statistic — an average, mean — that
contradicts the arithmetic of a labeled list of numbers elsewhere on the same
page. This is the highest-evidence-quality check in the cluster: the finding
literally shows the arithmetic (`5, 4, 3, 5, 2` → mean `3.80`) next to the
page's own claim (`4.8`), so the reader does not have to trust a judgement —
they can check the subtraction themselves.

**Matching a list to a claim.** A labeled list (`Customer ratings: 5, 4, 3, 5,
2`, 3+ comma-separated numbers) is compared against every "average"/"avg"/
"mean" claim on the page whose sentence shares at least one significant
keyword with the list's label. `"ratings"` (list label) and `"rating"`
(claim sentence, singular) are folded to the same keyword the same way CQ-07
folds units — without that, the two are different strings and never compared,
which is exactly the bug this project found while building the check: the
positive fixture did not fire until the singular/plural fold was added.

**Tolerance.** `max(0.15, 5% of the computed mean)` — wide enough to absorb
ordinary rounding in the page's own stated average, narrow enough that a
real, page-breaking contradiction (`3.8` claimed as `4.8`) still fires.

**Guard: suppression words for legitimately non-simple averages.** `weighted`,
`excluding`, `filtered`, `verified only`, `adjusted`, `normalized` near the
claim sentence suppress the comparison — a weighted or filtered average is
not expected to equal the simple mean of every listed number, and asserting a
mismatch there would be the false positive the capability matrix explicitly
warned about for this check.

**Guard: unrelated lists are never compared.** `"Page views: 100, 200, 300"`
next to `"Average price: $45"` shares no keyword and is never evaluated — the
keyword-overlap requirement is what keeps this check from comparing arbitrary
unrelated numbers on a busy page.

**Guard: parenthesised labels parse.** Regression case: `"Delivery times
(days): 2, 3, 2, 4, 3"` originally failed to match the labeled-list pattern
at all, because the label character class excluded `(` and `)` — a common,
legitimate real-world label format (units or clarifications in parentheses).
Fixed by widening the label character class; this fix applies to CQ-07's
label matching too, since both share the same pattern shape.

---

## CQ-11 — Fluency / readability

**What it catches.** A page whose visible text scores in the Flesch Reading
Ease formula's "very difficult, college-graduate" band (0-30) — long
sentences built from high-syllable words, the pattern that raises both a
human reader's and an assistant's parse cost when extracting a clean,
quotable claim.

**Why a formula, not agent judgement, for this one.** Unlike CQ-01/02/04/09/
12, readability has a standard, decades-old, purely arithmetic definition
(`206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word`).
Computing it is exactly the kind of "the script decides" case CQ-03/05/07/08
already establish: the evidence is the arithmetic itself, not a pattern
match standing in for a judgement.

**Guard: minimum sample size (300 words).** Below this, a handful of
one-word nav-menu "sentences" (this project's `_split_sentences` is
line/punctuation-based, not a real sentence boundary detector) can swing the
average wildly in either direction. This is the primary false-positive
guard: a short excerpt does not get scored at all, avoiding a noisy verdict
on too little data — same "short sample is noise" principle CQ-12's rubric
already applies by hand.

**Guard: the strictest published band, not merely "difficult" — partial,
not complete.** Firing only at "very difficult" (<30), not "difficult"
(30-50), is conservative: checked live against GNU's GPL v3 full text
(dense legalese, historically used as a canonical "hard to read" example),
and it did not cross this threshold. But building this corpus's fixtures
found the guard is *not* a full defence against Flesch's well-known
jargon-density limitation. A fixture of short, simple, clinically ordinary
sentences built from dense medical vocabulary
(`defect_dense_jargon_short_sentences.txt`: avg. 6.9 words/sentence, still
scored 9.9) still crosses the threshold — the formula's syllable-per-word
term (`84.6 ×`) dominates its sentence-length term (`1.015 ×`) heavily
enough that short sentences do not protect against high syllable density
the way an intuitive reading of "sentence length AND syllable density both
have to be extreme" would suggest. This is now a known, accepted, honestly-
documented limitation, not a solved guard: a page written in dense domain
jargon (medical, legal, scientific) can fire even when a domain expert
would call it perfectly clear, which is why every CQ-11 finding is capped
at `confidence: medium`, never `high` — see the corpus's own
`content_cases.json` note for both the confirmed-firing jargon case and
the confirmed-silent plain-prose case (`clean_plain_prose.txt`) this
distinction is calibrated against.

**Guard: `confidence: medium`, never `high`.** The formula's known
limitation (jargon vs. genuine difficulty) is not fully solved by the
threshold alone, so every CQ-11 finding is capped at medium confidence —
honest about what a syllable-counting heuristic can and cannot assert.

**What was tried and reverted for a sibling capability (CQ-01), and why it
matters here too.** An early version of CQ-01 tried to window its opening-
text signal from just after the page's first `<h1>` rather than document
start, specifically to skip nav/header chrome. Live validation before
freeze found two independent real bugs (a `<title>`-derived substring
collision, and — even after fixing that — en.wikipedia.org's language-
switcher panel and stripe.com's logo-as-`<h1>` both producing a false or
wrong anchor, confirmed by fetching and reading the raw HTML). It was
reverted to a simple, honestly-limited document-start window rather than
chasing per-site DOM shapes. CQ-11 deliberately never attempted anything
h1-anchored or position-sensitive at all — it scores the whole page's text,
so this class of bug has no foothold here, which is itself part of why a
formula over the whole page was the safer design than a positional window.

---

## What extraction does not handle (known, accepted limits)

- **CQ-01's `opening_block` has no main-content boundary detection.** It is
  the first ~150 words of `extract_visible_text`'s output, document start —
  on a real page with a conventional nav bar this is frequently nav/header
  chrome rather than article prose (confirmed live: python.org,
  docs.python.org, Wikipedia, PEP 8, Stripe). This is gate 2's job (render/
  extraction, not yet built), not this skill's; `content-judgement-
  rubric.md`'s §CQ-01 explicitly instructs the agent to recognise a
  nav-dominated opening and say nothing rather than score it as a missing
  answer.
- **Malformed HTML with mismatched tags** can confuse the skip-depth counter
  in `extract_visible_text` (e.g. an unclosed `<pre>`). No HTML-repair
  dependency is used; this is a documented limitation, not silently corrected.
- **Content assembled by JavaScript after load** is invisible to `--url`
  mode, which fetches raw HTML only. A page whose real content depends on
  client-side rendering is gate 2's problem (render/extraction, not yet
  built), not this skill's.
- **Cross-page contradictions** (the same stat stated differently on two
  different pages) are out of scope for a single-page check; see CQ-10 in the
  capability matrix.
