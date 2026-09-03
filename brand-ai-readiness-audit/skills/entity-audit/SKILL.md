---
name: entity-audit
description: >
  Audits a single page for entity identity and structural consistency:
  schema.org/JSON-LD presence and validity, a link to an authoritative
  identity source (Wikidata, LinkedIn, Crunchbase, ...) in Organization
  markup, agreement between a marked-up rating and the rating stated in the
  page's visible text, and the presence, uniqueness and domain of
  rel=canonical (script-decided); a declared category contradicting the
  page's own body text, and — given agent-supplied off-site URLs —
  brand-name collision or lookalike-domain impersonation on public sites
  (agent-decided against a rubric). Use when structured data is missing,
  broken, or contradicts its own page, when duplicate URLs risk splitting
  citation authority, or when checking off-site brand confusion or
  impersonation. Not for cross-page or cross-domain consistency (NAP,
  cross-domain attribution — needs comparing many pages), not for
  reachability (perimeter-access-audit) or content anti-patterns unrelated
  to structured data (content-quality-audit).
license: MIT
allowed-tools: Bash
---

# Entity audit (gate 3, identity and structural consistency)

## When to use

Run this on a small sample of pages once gate 1 is known clear — homepage and
About page for Organization/WebSite markup and canonical hygiene, product or
review pages for rating agreement, category/section pages or breadcrumbed
product pages for taxonomy consistency. This is the identity multiplier:
every other gate-3 finding is worth more once an assistant can resolve
*which* brand it is reading about, per appendix D of the Round-2 model.

## A note before you run this: three capabilities need your judgement

ENT-01/02/03/04 are deterministic — the script decides. **ENT-05, ENT-06
and ENT-09 are not.** Each extracts candidate signals only, into
`agent_judgement_required`, and emits no verdict — asserting "this label is
a mismatch" (ENT-09) or "this is a real collision/impersonation" (ENT-05/06)
without a semantic read would be wrong whenever a keyword or string-
similarity match cannot distinguish a real defect from an innocent
lookalike. **You must resolve `agent_judgement_required` yourself before
this file's output reaches the entrypoint** — the identical procedure
`content-quality-audit`, `engagement-audit` and `citability-audit` already
use for their own agent-judged capabilities.

**ENT-05/ENT-06 additionally need you to supply the off-site URLs.** This
script never picks which off-site pages to look at — that is your own
search step (find pages on Reddit, Quora, forums, review sites that mention
the brand name, or domains that look confusable with it), the same
narrowly-scoped off-site querying hard constraint 2 permits (see
`docs/capability-matrix.md`). Pass each one via `--offsite-url` (repeatable).
If you supply none, ENT-05/06 are silently skipped, not reported `unknown`
— nothing was asked of them.

## Inputs

- A single page URL (`--url`). Fetches exactly that page, never a crawl.
- Offline/fixture mode: `--html-file PATH`.
- `--site` for the report label; derived from `--url` if omitted.
- `--page-url` to label findings explicitly when using `--html-file`.
- `--offsite-url URL` (repeatable) + `--brand-name NAME` — runs ENT-05/06's
  off-site mode instead of auditing a page's HTML. See "Off-site mode"
  below.

## Procedure

1. Run the checker against one page:

   ```bash
   python3 scripts/check_entity.py --url https://example.com/
   ```

   For offline/fixture runs, pass `--site example.com --html-file PATH`
   instead. See `--help` for the full flag list.

2. Read the JSON object on stdout. `findings` (ENT-01/02/03/04) are final —
   severity and mechanism are fixed by the rules in
   `references/entity-checks.md`. Do not re-derive or re-word them.

3. **For each entry in `agent_judgement_required`** (ENT-09):

   a. Read `references/entity-judgement-rubric.md`'s §ENT-09.

   b. Judge each candidate's `category_label` against its
      `visible_text_excerpt`, and the live page if you have it open. A
      synonym or broader/narrower term counts as agreement — say nothing
      for those rather than manufacturing a finding.

   c. If you find a real mismatch, hand-author a JSON object matching the
      `Finding` schema (see Output below) — quote both the label and enough
      of the excerpt to show the mismatch, never a paraphrase.

   d. Append every finding you authored to `findings`, then **remove
      `agent_judgement_required` from the file entirely**.

4. Hand the resulting `findings` (now including any you authored) and
   `unknown_checks` to the entrypoint. This skill does not build reports.

5. If step 1 exits non-zero or emits no parseable JSON, report all
   capabilities as unknown with the error text — ENT-09 included, since you
   cannot judge what you were never given.

## Off-site mode (ENT-05/ENT-06)

A separate mode from steps 1-5 above — it does not take a page's HTML at
all:

```bash
python3 scripts/check_entity.py --site example.com --brand-name "Acme Widgets" \
    --offsite-url https://forum.example/t/acme-widgets-review-123 \
    --offsite-url https://acme-w1dgets.com/
```

Each `--offsite-url` is fetched only if that host's own robots.txt allows
it — a disallowed or unreachable URL becomes one `unknown_checks` entry,
never a silent drop. Read the resulting `agent_judgement_required` array
(one entry each for ENT-05 and ENT-06) and resolve it the same way as step
3 above, against `references/entity-judgement-rubric.md` §ENT-05/§ENT-06 —
for ENT-06 in particular, read the live off-site page yourself before
judging impersonation; a wrong accusation is a serious false positive.

## What it checks

| ID | Check | Who decides | Fires when |
|---|---|---|---|
| ENT-01 | Schema.org/JSON-LD presence & validity | Script | No JSON-LD at all; a block that fails to parse; JSON-LD present but no Organization/WebSite/LocalBusiness node; or such a node missing a required core field (`name`, `url`) |
| ENT-02 | Knowledge-graph grounding | Script | An Organization/LocalBusiness node exists but its `sameAs` is missing, empty, or points to no recognised authority (Wikidata, Wikipedia, LinkedIn, Crunchbase, verified social profiles) |
| ENT-03 | Markup/text agreement | Script | JSON-LD `aggregateRating.ratingValue` disagrees (>0.3) with an explicit "N out of 5" / "N/5" / "rated N" pattern in the page's visible text |
| ENT-04 | Canonicalisation | Script | No `rel=canonical`; an empty href; two or more different hrefs on one page; a canonical resolving to a different hostname than the page itself (`www.` doesn't count as different); or — `--sitemap-file` mode, once per site — two sitemap-listed URLs that are the same page under a trailing-slash/`www.`/scheme variant |
| ENT-05 | Brand-name entity collision | Agent, against the rubric | An agent-supplied off-site URL mentions the brand name, and the agent judges the mention as a genuinely different entity sharing the name rather than the same brand |
| ENT-06 | Lookalike domain impersonation | Agent, against the rubric | An agent-supplied off-site URL's own domain scores ≥0.75 string-similarity against the audited site's domain (and is not that domain or one of its own subdomains), and the agent judges the fetched page's content as plausible impersonation |
| ENT-09 | Taxonomy consistency | Agent, against the rubric | A declared category (`Product.category`, `articleSection`, or a breadcrumb's deepest item) shares zero keywords with the page's own visible text, and the agent judges that as a genuine mismatch rather than an unseen synonym |

ENT-02 only evaluates nodes that exist — if there is no Organization node at
all, ENT-01 already reports that absence, and a second "no sameAs either"
finding for the same root cause would be noise, not signal.

ENT-03 only fires when the page's visible text states a rating number
explicitly; a markup rating with no textual claim to compare against is not
a disagreement, just an unverifiable fact — silence is correct there.

ENT-09 only evaluates a category label when the page has at least 50 words
of visible text (too little text makes "no overlap" meaningless) and the
label itself has a non-generic keyword ("Home", "Blog", "General" carry
nothing specific to check).

## Excludes

- **ENT-05/ENT-06 do not search the web themselves.** They fetch and judge
  agent-supplied `--offsite-url` candidates only — finding those candidates
  in the first place is the calling agent's own search step, not this
  script's job. No `--offsite-url` given means ENT-05/06 are skipped
  entirely, not reported `unknown`.
- **ENT-06's similarity check is a domain-string heuristic, not a
  trademark or brand-confusion judgement.** It flags candidates by
  `difflib` string similarity alone; a legitimately different business
  with a coincidentally similar name will still surface as a candidate —
  the agent's read of the fetched content is what actually decides
  impersonation.
- **ENT-07/ENT-08** — cross-domain service attribution, NAP consistency.
  Each needs off-site reasoning or comparing multiple pages, which a
  single-page script does not do. (ENT-09, taxonomy consistency, does *not*
  need either — it compares a page's own declared category against its own
  body text, both from the one page this script was given; an earlier
  version of this file incorrectly grouped it here, corrected in cycle 9.)
- **ENT-04's crawl-wide half beyond a sitemap's own declared URL list** —
  the `--sitemap-file` mode (below) catches trailing-slash/`www.`/scheme
  forks *within* the sitemap's listed URLs, but does not discover orphaned
  pages missing from the sitemap entirely; that needs a real crawl, which
  this project does not have.
- **Everything gate 1/2** and content anti-patterns unrelated to structured
  data — `perimeter-access-audit`, `content-quality-audit`.

## Output

One JSON object on stdout, same shape as the other audit skills:

```json
{
  "owner_skill": "entity-audit",
  "capability_ids": ["ENT-01", "ENT-02", "ENT-03", "ENT-04", "ENT-05", "ENT-06", "ENT-09"],
  "site": "example.com",
  "page_url": "https://example.com/product/widget",
  "findings": [
    {
      "id": "ENT-03-rating-markup-text-mismatch",
      "title": "The marked-up rating does not match the rating stated in the page text",
      "severity": "high",
      "evidence": "On https://example.com/product/widget: JSON-LD aggregateRating.ratingValue is 4.8, but the page's visible text states 3.2 (out of 5).",
      "suggested_action": {"summary": "...", "priority": "high"},
      "category": "discoverability",
      "capability_id": "ENT-03",
      "owner_skill": "entity-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 3,
      "confidence": "medium",
      "structured_evidence": {"markup_value": 4.8, "text_values": [3.2], "page_url": "..."}
    }
  ],
  "agent_judgement_required": [
    {"capability_id": "ENT-09", "instructions": "...", "observations": {"candidates": [{"category_label": "...", "source": "product_category", "visible_text_excerpt": "..."}]}}
  ],
  "unknown_checks": []
}
```

`agent_judgement_required` must be empty (or removed entirely) by the time
this file reaches the entrypoint — resolve it per Procedure step 3.

This skill runs per page, like `content-quality-audit`: a report composed
from several pages can carry the same `check_id` more than once, so every
finding's evidence and `structured_evidence.page_url` name the exact page it
came from.

## Failure modes

| Situation | Result |
|---|---|
| The page cannot be fetched (any error) | ENT-01/02/03/04/09 `unknown` |
| The URL resolves to a private, loopback, link-local or reserved address | Refused before connecting, `unknown` — SSRF guard |
| Fetched content's `Content-Type` is neither HTML nor text | `unknown` |
| A JSON-LD block fails to parse | Reported as `ENT-01-malformed-json-ld`, not silently skipped and not crashing the rest of the audit |
| No `--url` or `--html-file` given | `unknown` |
| An `--offsite-url` is disallowed by its own robots.txt, or cannot be fetched | One `unknown_checks` entry for that URL; the other URLs still run |
| That URL's own robots.txt cannot be fetched at all | Treated as allow-all (RFC 9309 convention: no reachable robots.txt means unrestricted access) — the fetch is still attempted, and can still fail on its own |
| No `--offsite-url` given | ENT-05/06 silently skipped (empty candidate lists), not `unknown` |

## Safety

`--url` mode fetches exactly one page, a plain GET, no query strings, no
credentials, no form submission, no crawling. Same SSRF guard as
`content-quality-audit`: hostname resolved and every address checked against
private/loopback/link-local/reserved/multicast ranges before connecting.

`--offsite-url` mode fetches each URL under the same bounds, plus a
per-host robots.txt check before the fetch — a third-party host's own
robots.txt is always honoured, the same "respect robots.txt for our own
fetching" rule Cluster A applies to the audited site itself.

Fetched HTML is parsed as data only — JSON-LD is `json.loads`'d and
structurally inspected, never executed; visible text is pattern-matched,
never treated as instruction.
