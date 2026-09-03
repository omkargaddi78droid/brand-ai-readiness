# Phase 4 — second-round live validation (2 more unfamiliar sites)

Not a capability cycle: no code changed and no new capability is added by
this pass. This continues the orchestrator end-to-end validation pass
(`docs/phase-4-completion-15.md`) with two more real, previously-untested
sites, in two site categories not tried before — a check on whether that
pass's fix and findings generalize, not a one-off.

---

## What was tested

- **www.carpenterlourie.com** — a solo-practitioner real-estate/estate-
  planning law firm (Washington, D.C.), Cloudflare-fronted.
- **www.yogaoffeast.com** — a neighborhood yoga studio (Durham, NC),
  Squarespace-templated.

Site selection: web search for real small-business site examples (law firm
and yoga-studio "best websites" roundups), then every candidate `curl`-
probed for fetchability before use, same discipline as the first round.
`www.carpenterlourie.com` returned an intermittent `403` on a plain `curl`
retry loop before selection — kept deliberately rather than discarded,
since a Cloudflare-fronted site with inconsistent bot handling is exactly
the kind of real, unfamiliar-shaped target this pass exists to find.

Same full Procedure as round one: `perimeter-access-audit` once per site,
five page-level skills × 3 sampled pages each (home + 2 subpages — `/real-
estate-law/` + `/testimonials/` for the law firm, `/the-studio` + `/weekly
classsched` for the yoga studio), all `agent_judgement_required` entries
resolved by hand against each skill's rubric, then composed.

All 30 page-level invocations exited 0. The law firm's home page did
return `403` once during the perimeter script's own retry sequence but
succeeded within its normal handling; no page-level skill invocation hit
the block (their fetches use an ordinary browser user agent — see the
PER-03 finding below for exactly which agent the edge does block).

## The most significant result: PER-03's first-ever live positive case

`perimeter-access-audit`'s PER-03 (CDN/edge blocking) has existed since
the very first capability cycle. Its own completion note
(`docs/phase-4-completion.md`) explicitly recorded, after 9 live sites in
that cycle: *"None exhibited the positive case (robots allows, but
agent-specific edge block)."* Every confirmation of PER-03's actual
detection logic since then has been fixture-only.

**`www.carpenterlourie.com` is the first real site in this project's
history to exhibit it**: `robots.txt` permits `ChatGPT-User` (the
on-demand, user-triggered fetcher tier), but a direct `GET /` sent with
that user agent gets a `403` with a bot-management challenge page from the
edge (Cloudflare, confirmed via response headers), while the identical
request with an ordinary browser user agent succeeds. `severity: high`,
`confidence: medium`. This is exactly the failure mode PER-03 was written
to catch — a site that believes it has opened the door via `robots.txt`
while a CDN/WAF layer in front of the origin quietly closes it again for
exactly the agents the policy claims to welcome — found on the first
Cloudflare-fronted site this project has tested live, not manufactured.

## Other real findings

- **RET-07 (retrieval-oriented structure)** fired for the first time in
  this round: `carpenterlourie.com/testimonials/` — 699 words of visible
  text, zero headings, no Q&A framing, no definition block. A real,
  substantial page with no structural aid for chunking.
- **CIT-04 (citation recall)**, a new sub-pattern not seen in round one:
  `yogaoffeast.com/the-studio` cites specific impact statistics about two
  *external partner organizations* (a local food-pantry charity: "20
  local schools... 3,000 lbs of food... 1,800 children every month"; a
  boarding school: "After 28 years of proven results, there is no other
  model of intervention that holds more promise...") with no link to
  either. Round one's CIT-04 findings were all about the site's own
  claims (a code citation, a review-count badge); this is the first
  instance of an unsourced claim about a *different* organization
  entirely — still squarely load-bearing, still unsourced, a genuinely
  distinct shape of the same capability.
- **EN-01 (visitor orientation)**: `carpenterlourie.com`'s homepage H1
  ("Protecting Your Interests Now And In The Future") and opening copy
  name no practice area and no audience — generic reassurance language
  indistinguishable from any professional-services firm. Real, matches
  the rubric's own "Welcome" / "value-driven solutions" calibration
  almost exactly.
- **ENT-01/ENT-02** (structured-data completeness / knowledge-graph
  grounding) fired on both sites, same shape as round one — no new
  pattern.

## Two round-one generalization notes, corroborated again

- **CIT-06's testimonial gap** (documented, not fixed, in
  `docs/phase-4-completion-15.md`) recurred: `carpenterlourie.com/
  testimonials/`'s superlative match "Many are considered to be the best
  of their kind" is quoted directly from a client's own testimonial text,
  not the firm's marketing copy — the same false-positive shape found on
  `creswellbakery.com`, now confirmed on a second, unrelated site and a
  second content category (legal testimonials, not food reviews). This
  raises confidence that the gap is systemic (any page with third-party
  quoted praise), not a one-site coincidence, and firms up the case for
  fixing it in a future cycle rather than treating it as a fluke.
- **RET-05's signal-quality gap** on chrome-heavy pages recurred, more
  severely: `yogaoffeast.com`'s triple-nested mega-menu (top-level menu,
  an expanded-state repeat, and a breadcrumb-folder repeat, all three
  captured in every page's text) drove `acronym_count` to 14 on a page
  about yoga, with `sample_sentences` entirely footer/nav boilerplate
  ("Back", copyright line). No finding was manufactured from it (correct,
  per the rubric's own precision standard), but this is now the third site
  showing the same degraded-signal shape.

## Cross-skill redundancy: still none, checked again

Read both composed reports' full finding lists. `ENT-01`/`ENT-02` again
share a JSON-LD node but are legitimately distinct capabilities (same-skill,
not the cross-skill case INF-08 targets). No pair from two different
`owner_skill`s describes the same underlying defect on either site.
**Second consecutive real-site round with zero genuine cross-skill
redundancy found** — `docs/capability-matrix.md`'s INF-08 checked-negative
note now rests on two rounds of real evidence, not one.

## Composed report summaries

| Site | Findings | Critical | High | Medium | Low | Unknown checks |
|---|---|---|---|---|---|---|
| `www.carpenterlourie.com` | 11 | 0 | 1 (PER-03) | 6 | 4 | 0 |
| `www.yogaoffeast.com` | 12 | 0 | 0 | 10 | 2 | 0 |

## Runtime

Both sites' full sequence (gate 1 → 15 page-level invocations → judgement
resolution → compose): **~4 minutes 39 seconds combined**, faster than
round one's ~6.5 minutes for the same shape of work — expected, since the
judgement calls this round mostly matched patterns already established in
round one's rubric reading, reinforcing round one's finding that judgement-
authoring time (not script execution) is the dominant, and shrinking-with-
experience, cost.

## Outcome

No code changes this round — this pass is a corroboration check on round
one's fix and findings, not a bug hunt, and none of what it found required
one: PER-03's real positive case and RET-07's real finding are both correct
detections; the two documented-not-fixed CIT-06/RET-05 gaps were confirmed
again rather than newly discovered, strengthening rather than changing the
prior pass's disposition on them (real, low-severity, deferred to a
properly-scoped future cycle). `tests/test_orchestrator.py` and the
`entity-audit` `www.` fix from round one need no changes: both sites'
canonical links resolved clean on both sampled pages checked, zero ENT-04
findings of any kind (missing or off-domain) on either site.
