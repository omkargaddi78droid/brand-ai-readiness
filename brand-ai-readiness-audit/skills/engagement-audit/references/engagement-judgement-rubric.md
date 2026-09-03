# Engagement judgement rubric: EN-01 and EN-03

Reference for `engagement-audit`. EN-01 and EN-03 are judgement calls — the
capability matrix names EN-01 explicitly as one, and EN-03's own test
criterion ("3 steps vs 8 steps") needs multi-page navigation a script cannot
do from one page. This document is what makes the judgement repeatable
instead of arbitrary: read it before scoring either capability, per
SKILL.md's procedure.

If you find yourself unsure whether something qualifies, the calibration
examples below are the standard to match against — not your own instinct
about what "feels" disoriented or frictionful. When still unsure after
checking the examples, say nothing rather than force a verdict: precision
beats recall in this project's rubric, and a wrong judgement call costs more
than a missed one.

---

## EN-01 — Visitor orientation

### The question

Within the headline and the first ~100 words, can a first-time visitor
answer three things: **what is this, who is it for, and what should I do
next?** Not eventually, after reading the whole page — within seconds, the
way an actual visitor decides whether to keep reading or leave.

### When this capability does not apply — say so, emit nothing

- The page is not a landing/orientation page at all — a documentation page,
  an API reference, a blog post the visitor already chose to read, a
  logged-in dashboard. These pages have a different job; judging them by
  "does it orient a cold visitor" is the wrong question, not a defect.
- `h1_text` is `null` and the page is clearly not meant to orient anyone
  (e.g. a utility page). Missing H1 on an actual landing page is itself
  evidence for a finding, not a reason to skip judging it.

### Calibration: oriented (no finding)

> **H1:** "Invoicing software for freelance designers"
> **First words:** "Send professional invoices in minutes, track payments,
> and get paid faster. No credit card required."
> **CTA:** "Start free trial"

Answers all three: what (invoicing software), who (freelance designers),
next (start free trial, framed as low-risk). No finding.

> **H1:** "Find a dentist near you, today"
> **First words:** "Compare ratings, book same-day appointments, and see
> real patient reviews — all in one place."
> **CTA:** "Search dentists"

What (a dentist-finding service), who (implied: anyone needing a dentist
soon), next (search). No finding, even though "who" is only implied — the
category itself makes the audience obvious, and demanding an explicit
audience statement here would be over-fitting the rubric rather than serving
its purpose.

### Calibration: disoriented (finding warranted)

> **H1:** "Welcome"
> **First words:** "We are passionate about excellence and innovation,
> delivering value-driven solutions for tomorrow's challenges, today."
> **CTA:** "Learn more"

Answers none of the three concretely. "Value-driven solutions" names no
product, no audience, no action with any specific meaning — this is the
generic-corporate-copy failure mode almost verbatim. `severity: medium`,
`confidence: high` (the vagueness itself is the evidence, quotable directly).

> **H1:** "Platform"
> **First words:** "Our platform enables seamless integration across your
> entire stack, empowering teams to move faster."
> **CTA:** "Get in touch"

Slightly more concrete than the previous example but still names no specific
product category, no specific audience, and "get in touch" is a weak,
open-ended next step for a visitor who doesn't yet know what they'd be
getting in touch about. `severity: medium`, `confidence: medium` — closer
to the line than the first example, worth flagging but with an honest hedge.

### Writing the finding

- `id`: `EN-01-unclear-orientation`
- `evidence`: quote the actual `h1_text` and enough of `first_150_words` to
  show the vagueness — the reader should be able to see the problem in the
  quote itself, not take your word for it.
- `severity`: `medium` in essentially all real cases — this is a real,
  measurable engagement cost (a Baymard-style category of finding), not a
  gate-breaking discoverability failure. Do not use `critical` or `high` for
  this capability.
- `mechanism`: state the cost plainly — a visitor who cannot tell what a
  page is within seconds leaves rather than reads further to find out; this
  is a behavioural fact about how people scan pages, not a stylistic
  preference.
- `category`: `"engagement"`, `gate`: `null`.

---

## EN-03 — Conversion-path friction

### The two sub-questions this capability actually answers

The capability matrix names three symptoms (step count, forced account
creation, hidden costs). Step count needs navigating the real flow across
pages, which this single-page audit cannot do — **never claim a step count**
from one page's observations. The two sub-questions this skill's
observations can actually support:

1. **Is account creation forced with no guest option?**
   `forms_with_password_field >= 1` and `guest_checkout_language_present`
   is `false`.
2. **Are fees present but never disclosed anywhere on the page?**
   The page clearly shows a price (check the live page or visible text) and
   `fee_or_tax_disclosure_snippets` is empty.

### When this capability does not apply — say so, emit nothing

- `forms_with_password_field == 0` and there is no visible price anywhere
  on the page. This is not a conversion page; judging it for conversion
  friction is the wrong question.
- The page is a login page for an *existing* account (not a new signup) —
  requiring a password there is the entire point, not friction.

### Calibration: forced account creation (finding warranted)

> `form_count: 1`, `forms_with_password_field: 1`,
> `guest_checkout_language_present: false`
> Page context: a checkout form asking for shipping address, card details,
> **and** "create a password" with no alternative offered anywhere.

A password field embedded directly in what is otherwise a one-time purchase
flow, with no "continue as guest" text anywhere on the page, is the forced-
account-creation pattern. `severity: medium`, `confidence: medium` — medium
confidence because the observations alone cannot fully rule out a legitimate
reason (e.g. a subscription service where an account is inherently required,
not checkout friction) — check the live page context before finalising, and
if it's genuinely a subscription/membership product rather than a one-time
purchase, do not flag this.

### Calibration: not forced (no finding)

> `forms_with_password_field: 1`, `guest_checkout_language_present: true`

The guest-checkout language being present at all is the signal that the
account creation is offered, not forced. No finding, even without reading
further — this is exactly what the deterministic signal is for.

> `forms_with_password_field: 1`, page context: an account-required SaaS
> signup page, not a purchase flow.

Requiring a password to create the only kind of account the product has is
not friction — it's the product. No finding.

### Calibration: undisclosed fees (finding warranted)

> Page context: prominently displays "$49" as "the price" with no other
> qualifying text anywhere on the page. `fee_or_tax_disclosure_snippets: []`.

A single, prominent, unqualified price with zero mention of tax, shipping or
fees anywhere on the page is worth flagging — not because shipping cost is
always disclosable up front (it frequently isn't, legitimately, before an
address is known), but because *total silence* on the topic, combined with a
price presented as final, is the pattern that produces sticker shock later.
`severity: medium`, `confidence: medium` — this is the softer of the two
EN-03 sub-checks; a single page's silence on fees is suggestive, not proof
that the real checkout flow hides them.

### Calibration: not undisclosed (no finding)

> `fee_or_tax_disclosure_snippets: ["price shown excludes shipping and
> applicable taxes"]`

The disclosure exists, even without a number attached — the visitor is told
to expect more, which is the transparency this check is actually about, not
a demand that every fee be pre-computed on this exact page.

### Writing the finding

- `id`: `EN-03-forced-account-creation` or `EN-03-undisclosed-fees` —
  whichever sub-question fired (both may fire independently; write two
  findings if both apply).
- `evidence`: state the concrete signal (`forms_with_password_field: 1, no
  guest-checkout language found` or the price context plus the empty
  disclosure list) — a counted observation, not an adjective, same standard
  as every other finding in this marketplace.
- `severity`: `medium` for both sub-cases in essentially all real
  applications of this rubric.
- Never write a finding whose evidence is a claimed step count. If you find
  yourself wanting to say "requires N steps to check out," you have gone
  beyond what a single page can support — stop and either drop the finding
  or reframe it around the specific signal you actually observed (the
  password field, the missing disclosure).
