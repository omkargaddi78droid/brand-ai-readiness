# Phase 4 completion — cycle 20

## What changed

Second half of the cycle-19 policy reversal (see `docs/capability-matrix.md`'s
"Hard constraints" section, and `docs/phase-4-completion-19.md` for the first
half, Cluster B). Hard constraint 2 permits direct, bounded HTTP queries to
named public sites (Reddit, Quora, forums, review sites), robots.txt-
respecting, computing the verdict locally — no third-party scoring API. This
reopens ENT-05, ENT-06 (`entity-audit`) and CIT-13 (`citability-audit`),
previously `DEFERRED`/`NOT_STARTED` on the wrong reason (their old blocker
cited "external-API dependency," which does not describe a direct HTTP GET
to a public page).

Design, confirmed with the user before implementation: the script never
searches the web itself. It only fetches **agent-supplied** off-site URLs —
finding candidate pages (a forum thread mentioning the brand, a
suspiciously-similar domain) is the calling agent's own search step. This
avoids hardcoding fragile, often-bot-blocked search-JSON endpoints
(confirmed live: Reddit's own robots.txt disallows `/` entirely for all
agents; Quora and Stack Overflow similarly block broad crawling) into a
script this project also has to fixture-test.

## `entity-audit` — ENT-05, ENT-06 (off-site mode)

New `--offsite-url URL` (repeatable) + `--brand-name NAME` CLI mode,
separate from the existing per-page/`--sitemap-file` modes:

- **ENT-05 (brand-name entity collision):** for every fetched off-site page
  mentioning the brand name (word-boundary, case-insensitive), a text
  snippet around the mention — the agent judges same-entity vs. genuine
  collision.
- **ENT-06 (lookalike-domain impersonation):** the domain-string-similarity
  half is scriptable (stdlib `difflib.SequenceMatcher`, ≥0.75 threshold
  against the audited site's own domain); the agent judges the fetched
  page's content for plausible impersonation intent.

New per-third-party-host robots.txt check
(`robots_allows_offsite_fetch`) before any off-site fetch: an unreachable
robots.txt defaults to allow (RFC 9309 convention), a reachable one that
disallows is always honoured. A disallowed or unreachable URL becomes one
`unknown_checks` entry, never a silent drop.

**Live-found bug, fixed before shipping:** `find_lookalike_domain_candidates`
initially had no subdomain guard. Live-tested against a real forum thread
(`meta.discourse.org`, audited site `discourse.org`), it scored 0.839
similarity and would have surfaced the project's own official community
subdomain as a lookalike-impersonation candidate. Fixed by excluding both
the audited site's own domain and any of its own subdomains before the
similarity check — caught by live testing, not a fixture, the same
discipline this project has applied to every prior capability.

## `citability-audit` — CIT-13 (off-site corroboration)

New `--offsite-url URL` (repeatable, optional) added to the existing
per-page mode — CIT-13 runs alongside the normal audit when supplied, and
is entirely omitted from `agent_judgement_required` (not `unknown`) when
not. Reuses CIT-04's own claim extraction (`find_citation_recall_candidates`
— a sentence with a number and no in-sentence link) as its candidate pool,
the same reuse-upstream-infrastructure pattern CIT-07 already established
against CIT-02. For each candidate, a deterministic numeric-survival check
(same shape as REN-04/RET-01) against every fetched off-site page's text:
a claim whose own significant number appears nowhere off-site becomes an
`agent_judgement_required` candidate; whether it is genuinely fragile for
being single-sourced (appendix D) or an obviously fine self-reported detail
(a price, a model number) is the agent's call, same as CIT-04's own
load-bearing distinction.

## Verification

- 29 new unit tests in `tests/test_entity_audit.py` (brand-collision
  candidates, lookalike-domain candidates including the subdomain-exclusion
  regression test, off-site judgement-request shape, `audit_offsite`
  end-to-end, robots-check convention) — entity-audit total 53 → 82.
- 15 new unit tests in `tests/test_citability_audit.py` (significant-number
  extraction, corroboration candidates, judgement-request shape,
  `audit_html`'s off-site path, robots-check convention) — citability-audit
  total 46 → 61.
- Full suite: 574/574 passing (up from 541 after cycle 19's Cluster B).
- Live-validated end-to-end against real hosts: `robots_allows_offsite_fetch`
  correctly returns `False` against reddit.com (`Disallow: /` for all
  agents, confirmed by reading its robots.txt directly) and Quora/Stack
  Overflow (broad `Disallow: /` or `Content-signal: ai-train=no` policies),
  and `True` against a Discourse forum whose robots.txt only blocks named
  bots by product token. A full `check_entity.py --offsite-url` run against
  a real, robots-allowed forum thread produced a correctly-shaped ENT-05/06
  `agent_judgement_required` output and a correctly-populated
  `unknown_checks` entry for the disallowed reddit.com URL in the same run.
- **Found and fixed, unrelated pre-existing bug:** while re-verifying
  citability-audit, `tests/measure_citability.py` (not part of the standard
  `python3 -m unittest discover` run, and apparently never run standalone in
  recent cycles) reported a false positive on `clean-full-citability` — its
  fixture's one external citation sat at 99% through a 979-word page,
  genuinely late per CIT-07's own ≥80%-threshold rule shipped cycle 18. The
  fixture was mislabeled `clean`, not a code defect; fixed by adding an
  early external citation so the page has at least one non-late citation.
  `measure_citability.py` is back to precision/recall 1.000.
- **Found, NOT fixed — flagged, out of scope for this cycle:**
  `tests/measure_perimeter_extras.py` independently reports 3 false
  positives (`clean-valid-sitemap`, `clean-sitemap-referenced-in-robots`,
  and an extra finding on `defect-sitemap-not-referenced-in-robots`),
  precision 0.727. This is in `perimeter-access-audit` (PER-06/PER-08),
  untouched by either this cycle or cycle 19 — a pre-existing regression in
  a measure script this project apparently does not run as part of its
  standard verification loop. Left for a dedicated investigation; noted
  here so it isn't silently lost.

## Wiring

- `audit-orchestrator`'s SKILL.md updated: Procedure gained optional
  off-site invocation steps for both ENT-05/06 and CIT-13 (agent finds
  candidate URLs first, then a `--offsite-url`-bearing invocation, then
  the usual `agent_judgement_required` resolution before composing); the
  skill registry table's `entity-audit`/`citability-audit` rows updated.
  `compose_report.py` itself needed no change (arbitrary `--skill NAME
  PATH` list, not a hardcoded roster).
- `entity-audit`/`citability-audit` SKILL.md and their judgement-rubric
  references updated: new Inputs, Procedure steps, "What it checks" rows,
  Excludes notes, and Failure-modes rows for the off-site additions;
  `entity-judgement-rubric.md` gained §ENT-05/§ENT-06 with worked
  calibration examples (including the live-found subdomain false-candidate
  case); `citability-judgement-rubric.md` gained §CIT-13.
- `tests/test_marketplace_manifest.py`'s third-party-import allowlist
  gained `difflib` (stdlib, used for ENT-06's domain-similarity check).

## Capability matrix

ENT-05, ENT-06, CIT-13 move from `NOT_STARTED`/`DEFERRED` to `IMPLEMENTED`.
CIT-11 stays `DEFERRED` — its own blocker (claim-vs-forum-opinion provenance
matching) is a fuzzy-matching complexity problem, not the policy that was
just lifted.

## Next

Both halves of the cycle-19/20 policy reversal are now built. Natural next
steps, not started: fixing the newly-flagged `measure_perimeter_extras.py`
regression; wiring ENT-05/06/CIT-13 into a live orchestrator end-to-end
validation pass the way prior cycles did for other capabilities; deciding
whether REN-03/REN-09 (still `NOT_STARTED`, Cluster B) are worth building
under some narrower scope.
