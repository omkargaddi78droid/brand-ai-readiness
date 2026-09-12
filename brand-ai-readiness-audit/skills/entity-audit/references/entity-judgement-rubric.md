# Entity judgement rubric: ENT-05, ENT-06, ENT-09

Reference for `entity-audit`. ENT-05, ENT-06 and ENT-09 are agent-judged —
three of this skill's seven capabilities. Read the relevant section before
scoring, per `SKILL.md`'s procedure.

When still unsure after checking the examples below, say nothing rather
than force a verdict — precision beats recall in this project's rubric, and
a wrong judgement call costs more than a missed one. This is especially
sharp for ENT-05/ENT-06: a false accusation of brand collision or domain
impersonation is a serious, reputationally-loaded false positive that no
amount of recall justifies.

---

## ENT-05 — Brand-name entity collision

### The question

Does `snippet` (a window of text around the brand-name mention on an
off-site page) refer to *this* brand, or to a different, unrelated entity
that happens to share the name closely enough that an assistant could
plausibly merge their attributes (location, rating, offerings, reviews)?
Only the second case is a defect worth reporting — a genuine collision that
puts the brand at risk of attribute-merging hallucinations, per Round-2
appendix D.

The script has already confirmed the brand name appears in the snippet
(word-boundary, case-insensitive) — that alone proves nothing about whether
it is the same entity. Read the snippet, and the live page at `url` if the
snippet alone is not enough context, before judging.

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The mention plainly refers to the same brand this audit is about (a
  customer review, a support thread, a news mention) — the overwhelming
  majority of real candidates.
- The snippet is too short or ambiguous to tell whether it is the same
  entity or not — do not guess from insufficient context.

### Calibration: a genuine collision (finding warranted)

> `url`: `https://forum.example/t/acme-plumbing-reviews`
> `snippet`: "Called Acme Plumbing in Denver last week for a leak, they were
> fantastic, five stars, highly recommend this small family-owned shop."

The audited site is `acmeplumbing.com`, a plumbing supply *manufacturer*
based in Ohio with no service branches, no Denver presence, and no
customer-facing reviews of its own. This snippet describes a completely
different, unrelated local service business that happens to share the
name — exactly the collision risk that could cause an assistant to merge
this Denver shop's five-star service reviews onto the manufacturer's own
entity. `severity: medium`, `confidence: medium` — a script cannot rule
out a franchise/subsidiary relationship the agent should also check for
plausibility before concluding collision, hence not `high`.

### Calibration: acceptable as-is (no finding)

> `url`: `https://forum.example/t/acme-plumbing-supply-order`
> `snippet`: "Ordered a case of Acme Plumbing brass fittings for a
> commercial job, arrived on time, good quality, will order again."

This describes the audited manufacturer's own actual product line. Same
entity. No finding.

### Writing the finding

- `id`: `ENT-05-brand-name-collision`
- `evidence`: quote the snippet and name the off-site URL; state plainly
  why it is a different entity (location, business type, or offering that
  contradicts the audited brand's own identity).
- `severity`: `medium` in essentially all real cases.
- `category`: `"discoverability"`, `gate`: `3`.
- `confidence`: `medium` unless the two entities are unambiguously
  distinct (different industries entirely, e.g. a bakery vs. a software
  company sharing a name) — then `high`.

---

## ENT-06 — Lookalike domain impersonation

### The question

Given `domain` (already flagged as string-similar to the audited site's
own domain — see `similarity`) and `content_excerpt` (the fetched page's
own visible text), does this domain plausibly impersonate the brand —
present itself as, or risk being mistaken for, the official site — rather
than being a legitimately different, unrelated business that happens to
have picked a similar name?

`similarity` alone is never sufficient: it is a string-distance score, not
a judgement about intent. A domain one character off from the brand's own
(`acme-w1dgets.com` vs. `acmewidgets.com`) that also brands itself as
"Official Acme Widgets Store" is a strong impersonation signal; the same
similarity score on a page that plainly identifies itself as a different,
unrelated company is not.

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- `content_excerpt` plainly identifies itself as a distinct, legitimately
  different business — a naming coincidence, not impersonation.
- The excerpt is too thin (a parked domain, a placeholder page) to tell
  intent either way — do not guess.

### Calibration: plausible impersonation (finding warranted)

> `domain`: `acme-w1dgets.com`, `similarity`: 0.91
> `content_excerpt`: "Welcome to Acme Widgets official store. Shop the full
> catalog with free shipping. 100% authentic, guaranteed lowest prices."

A near-identical domain (digit substituted for a letter — a classic
typosquat pattern) presenting itself as the "official store" with no
disclosure of being unaffiliated. `severity: high`, `confidence: medium` —
the pattern is a textbook impersonation shape, but confirming actual
customer harm (real transactions happening there) is beyond what a single
fetched page can prove, so this stops short of `critical`.

### Calibration: acceptable as-is (no finding)

> `domain`: `acmewidgetsreview.com`, `similarity`: 0.78
> `content_excerpt`: "Independent reviews and comparisons of Acme Widgets
> and competing brands. This site is not affiliated with Acme Widgets."

A review/comparison site that explicitly discloses it is unaffiliated —
legitimate, not impersonation, even with high string similarity. No
finding.

> `domain`: `meta.discourse.org` (a subdomain of the audited site's own
> `discourse.org`, live-found scoring 0.839 similarity)

Already excluded by the script before reaching this rubric — subdomains of
the audited site's own domain are never candidates. Included here as a
reminder of why: this is exactly the false-candidate shape the subdomain
guard exists to prevent from ever needing your judgement at all.

### Writing the finding

- `id`: `ENT-06-lookalike-domain-impersonation`
- `evidence`: quote `content_excerpt` and name the domain and its
  similarity score; state plainly what makes this impersonation rather
  than a coincidental name (no disclosure, "official" claims, brand
  imagery, character-substitution pattern).
- `severity`: `high` when the page actively claims official status or
  omits any disclosure; `medium` when the signal is present but weaker.
- `category`: `"discoverability"`, `gate`: `3`.
- `confidence`: `medium` — a single fetched page is real but partial
  evidence of intent; never `high` for this capability, since confirming
  genuine deceptive intent needs more than one page can show.

---

## ENT-09 — Taxonomy consistency

### The question

Does `category_label` genuinely describe what `visible_text_excerpt` is
about? A synonym, a paraphrase, a broader or narrower term in the same
family (e.g. "Laptops" and body text about "notebook computers"; "Politics"
and body text about an election) all count as agreement. Only a real,
unrelated mismatch — the label naming one topic while the text is
demonstrably about something else — is a defect.

Every candidate you see has already passed the script's own filter: it
shares *zero* keywords (after stopword and singular/plural folding) with
the page's visible text. That is why this needs your judgement rather than
a script verdict — zero keyword overlap is consistent with both a real
mismatch and a same-topic synonym pair the keyword match cannot see.

### When this capability does not apply — say so, emit nothing

- `candidates` is empty.
- The excerpt reads as a synonym, a narrower/broader term, or a natural
  variant of the label, even with no shared keyword literally.
- The excerpt is too short, too generic, or too boilerplate (a cookie
  notice, a navigation stub) to tell what the page is actually about —
  judge from what you can see, not from an inference the excerpt does not
  support.

### Calibration: a genuine mismatch (finding warranted)

> `category_label`: "Bicycles"
> `source`: "product_category"
> `visible_text_excerpt`: "This wireless noise-cancelling headset delivers
> up to 30 hours of battery life, Bluetooth 5.3 pairing, and a padded
> over-ear design for all-day comfort. Available in three colours..."

The declared category and the actual product description describe
completely unrelated things — an audio product marked up as a bicycle. No
synonym or broader-term relationship explains this. `severity: medium`,
`confidence: medium` — the mismatch is clear from the excerpt alone, but a
script cannot rule out a data-entry error elsewhere on the page that
resolves it, so this stops short of `high`.

> `category_label`: "Travel"
> `source`: "breadcrumb"
> `visible_text_excerpt`: "Our quarterly earnings report shows revenue grew
> 12% year over year, driven by strong performance in the enterprise
> software segment. Operating margin improved to 18%..."

A breadcrumb trail ending in "Travel" on a page that is plainly an
investor-relations earnings report — a real taxonomy error, likely from a
templated breadcrumb component that inherited the wrong category.
`severity: medium`, `confidence: high` — no plausible synonym relationship
exists between "travel" and financial reporting.

### Calibration: acceptable as-is (no finding)

> `category_label`: "Laptops"
> `source`: "product_category"
> `visible_text_excerpt`: "This lightweight notebook computer features a
> 14-inch display, all-day battery, and a backlit keyboard. Ideal for work
> or study on the go..."

Zero literal keyword overlap ("laptop" vs. "notebook computer"), but this
is exactly the synonym case ENT-09 exists to catch correctly rather than
false-positive on. No finding.

> `category_label`: "Accessibility"
> `source`: "article_section"
> `visible_text_excerpt`: "Screen readers rely on properly structured
> headings and alt text to convey meaning to users who cannot see the
> page..."

"Accessibility" as a section label and body text about screen readers and
alt text are the same topic in different words. No finding.

> `category_label`: "Electronics"
> `source`: "breadcrumb"
> `visible_text_excerpt`: "Compare our full lineup of laptops, tablets,
> headphones and smart home devices..."

A broader category term over text spanning several of its narrower members
is a normal, correct taxonomy relationship, not a mismatch. No finding.

### Writing the finding

- `id`: `ENT-09-taxonomy-mismatch`
- `evidence`: quote both `category_label` and enough of the excerpt to show
  the mismatch — a reader must be able to see the disagreement, not just
  take your word for it.
- `severity`: `medium` in essentially all real cases — a real but
  bounded discoverability defect, not gate-breaking.
- `category`: `"discoverability"`, `gate`: `3`.
- `confidence`: `high` only when no synonym/broader-term relationship is
  even plausible (see the "Travel" vs. earnings-report example); `medium`
  otherwise.
- At most one ENT-09 finding per distinct `category_label` — several
  candidates sharing the same label are one taxonomy claim to judge, not
  several.
