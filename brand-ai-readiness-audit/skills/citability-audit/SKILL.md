---
name: citability-audit
description: >
  Audits a single page for citability — how easy it is for an assistant to
  reach, read, and quote a clear fact from. Detects missing About-page
  discoverability (CIT-01), pages that cite no outside sources (CIT-02),
  citations buried late in the page (CIT-07), superlatives with no number
  (CIT-06); and, agent-judged, load-bearing claims with no citation
  (CIT-04) or a numeric claim uncorroborated by any agent-supplied
  off-site page (CIT-13). Given a sampled page list: a fact-dense page
  starved of internal-link PageRank while a thin navigational hub holds the
  sample's top rank (CIT-08), and the sample-wide absence of any
  comparison-shaped page (CIT-09, proactive suggestion only). Use when
  content is reachable and well-structured but still isn't cited, or as the
  citability half of an AI-readiness audit. Not for whether a cited source
  supports its claim (out of scope), not for reachability or
  structured-data problems (perimeter-access-audit, entity-audit), not for
  content anti-patterns unrelated to sourcing.
license: MIT
allowed-tools: Bash
---

# Citability audit (gate 3: is this page easy to quote from?)

## When to use

Run this per sampled page, same as `content-quality-audit`, `entity-audit`
and `engagement-audit`: pages that make claims worth sourcing — guides,
comparisons, product pages with stated specs or stats. A thin navigational
page has little to audit here.

## A note before you run this: two capabilities need your judgement

CIT-01, CIT-02, CIT-06 and CIT-07 are deterministic — the script decides.
**CIT-04 and CIT-13 are not.** Both extract candidates only, into
`agent_judgement_required`, and emit no verdict — deciding whether an
unsourced number is *load-bearing* (CIT-04) or whether an off-site-
uncorroborated claim is genuinely *fragile* (CIT-13) is a judgement about
what matters on this specific page, not a pattern a script can safely
assert. **You must resolve `agent_judgement_required` yourself before this
file's output reaches the entrypoint** — exactly the same procedure as
`engagement-audit`'s EN-01/EN-03. When `audit-orchestrator` drives this
skill as part of a full-site audit, this array has already been filtered to
at most 5 candidates total (across all of citability-audit's invocations
this run) by its own `select_judgement_items.py`, ranked by severity — see
the orchestrator's SKILL.md step 5. Run standalone, resolve every entry
with no such cap.

**CIT-13 additionally needs you to supply the off-site URLs.** This script
never searches the web itself — that is your own search step (the same
narrowly-scoped off-site querying this project permits: direct, bounded,
robots.txt-respecting HTTP queries to named public sites, never general web
search or crawling). Pass each candidate off-site page via
`--offsite-url` (repeatable). With none given, CIT-13 does not run at all
— it is omitted from `agent_judgement_required`, not reported `unknown`.

## Inputs

- A single page URL (`--url`). Fetches exactly that page, never a crawl.
- Offline/fixture mode: `--html-file PATH`.
- `--site` for the report label; derived from `--url` if omitted.
- `--offsite-url URL` (repeatable, optional) — enables CIT-13, checking
  this page's own numeric claims for off-site corroboration.
- `--sample-file PATH` + `--site` — runs CIT-08's hub/authority link-graph
  check and CIT-09's comparison-content-gap check instead of auditing a
  single page. See "Hub/authority mode" below.

## Procedure

1. Run the checker against one page:

   ```bash
   python3 scripts/check_citability.py --url https://example.com/guide
   ```

2. Read the JSON object on stdout. `findings` (CIT-01/02/06/07) are final — do
   not re-derive or re-word them.

3. **For `agent_judgement_required`'s CIT-04 entry:**

   a. Read `references/citability-judgement-rubric.md` §CIT-04.

   b. For each `candidate_unsourced_claims` sentence, decide whether it is
      load-bearing — not every number needs a source (a price, a model
      number, a date is often fine unsourced) — using the rubric's worked
      examples to calibrate.

   c. Hand-author a `Finding` (schema below) only for genuine cases, quoting
      the exact candidate sentence as evidence.

   d. Append any findings you authored to `findings`, then **remove
      `agent_judgement_required` entirely** before this file is composed.
      Hand-editing the JSON works; `shared/judgement_merge.py` (optional
      CLI, `--report`/`--judgements`/`--out`) does the same schema
      validation and merge mechanically if you'd rather not hand-edit.

4. **If you passed `--offsite-url`, also resolve `agent_judgement_required`'s
   CIT-13 entry**, against `references/citability-judgement-rubric.md`
   §CIT-13: for each `candidates` entry (a claim whose own number was not
   found on any fetched off-site page), decide whether it is genuinely
   fragile for being single-sourced, or an obviously fine unsourced detail.
   Same hand-author-or-nothing procedure as CIT-04.

5. Hand the resulting `findings` and `unknown_checks` to the entrypoint.

6. If step 1 fails, report all capabilities as unknown with the error
   text — CIT-04 included, since you cannot judge what you were never given.
   CIT-13 is the one exception: if you never passed `--offsite-url`, it was
   never asked to run, so it is simply absent, not `unknown`.

## Hub/authority mode (CIT-08 + CIT-09)

A separate mode from steps 1-6 above — it takes a list of on-site page URLs,
not one page:

```bash
python3 scripts/check_citability.py --site example.com \
    --sample-file /tmp/audit/page-sample.txt
```

`--sample-file` is one on-site URL per line — pass the `sample_urls` from
`audit-orchestrator`'s `sample_pages.py`. The script fetches each
page once and runs both capabilities off that one fetch pass:

- **CIT-08** builds a directed internal-link graph (`shared/links`) and
  runs `shared/graph_metrics.pagerank` over it. It flags a fact-dense page
  (500+ words, the same threshold CIT-02 uses) whose PageRank is well
  below the sample's mean while a non-fact-dense page holds the sample's
  single highest PageRank — a navigational hub absorbing the internal link
  equity a content-dense page needs, the concrete shape of "hubs and
  authority pages not separated; trust flows badly."
- **CIT-09** scans each fetched page's URL slug and `<title>` for a
  comparison shape ("vs", "versus", "alternative to", "compared to").
  Fires only when NONE of the sampled pages look comparison-shaped at
  all — a `track: "proactive"` suggestion, never a defect, since absence
  proves nothing: a personal blog, a policy page, or a support portal has
  no reason to publish comparison content.

A bounded, template-stratified subgraph is a structurally biased estimate
of site-wide link authority — a page reachable only via pagination or a
deep facet outside the sample is invisible to CIT-08, and that exclusion
correlates with the very starvation being measured. CIT-08's finding is
therefore capped at Medium severity and states its own sample size in its
evidence, never claiming site-wide scope. Both capabilities are entirely
script-decided — no `agent_judgement_required` entries come out of this
mode.

## What it checks

| ID | Check | Who decides | Fires when |
|---|---|---|---|
| CIT-01 | Trust-signal authority | Script | No link on the page resolves to a conventional About/company URL path |
| CIT-02 | Source attribution | Script | A page with 500+ words links to zero other domains |
| CIT-06 | Statistics density | Script | A superlative claim ("the best", "industry-leading") appears with no number in the same sentence, and is not inside a quoted customer testimonial |
| CIT-07 | Citation-position weighting | Script | Every outbound (external) citation on a substantial page falls in the last 20% of the page — reuses CIT-02's own external-link definition |
| CIT-08 | Hub/authority link-graph structure | Script (`--sample-file` mode) | A 500+-word page's PageRank over the sampled internal-link graph is under half the sample's mean, while a page with no comparable content density holds the sample's single highest PageRank; requires 5+ sampled pages |
| CIT-09 | Comparison-content gap | Script, proactive (`--sample-file` mode) | None of the 5+ sampled pages' URL slug or `<title>` mentions a comparison shape ("vs", "versus", "alternative to", "compared to") |
| CIT-04 | Citation recall | Agent, against the rubric | An unsourced numeric claim is judged load-bearing to the page's purpose |
| CIT-13 | Off-site corroboration | Agent, against the rubric | A numeric claim's own number was not found on any agent-supplied off-site page, and the agent judges it genuinely fragile for being single-sourced |

## Excludes

- **CIT-03, CIT-12** — citation precision (does a cited source really
  support its claim) and abstractiveness/faithfulness. Both need reading
  comprehension across a claim and its source; out of scope this cycle.
- **CIT-05 (quotation density), CIT-10 (comparison disclosure)** —
  considered and dropped. CIT-05's attribution patterns vary too widely to
  script at this project's false-positive bar. CIT-10 would fire on nearly
  every vendor-authored comparison page, since disclosure language is rare
  regardless of legitimacy — a pattern that fires on the overwhelming
  majority of both good and bad pages is not a detector.
- **CIT-09 only proves absence within this sample, never site-wide** — a
  comparison page that exists but was not sampled is indistinguishable from
  one that does not exist at all. This is why it stays a `proactive`
  suggestion rather than a defect: it is weak evidence by design, worded as
  "consider adding" rather than "missing."
- **CIT-09 is a lexical slug/title scan, not a semantic one.** A comparison
  page whose URL and title both avoid every recognised keyword (an unusual
  naming choice) is invisible to it; conversely, a page merely mentioning
  "versus" in an unrelated context (rare, but possible) would be treated as
  satisfying the check.
- **CIT-08 only ever proves "starved within this sample," never "starved
  site-wide."** A page reachable via internal links outside the sampled
  set is indistinguishable from a true site-wide authority page by this
  check — exactly why it is capped at Medium severity and states its own
  sample size rather than a site-wide claim.
- **CIT-08 requires both a hub and a starved fact-dense page to coexist.**
  A uniformly-linked site (no page dominates PageRank) or a site where the
  top-authority page is itself fact-dense produces no findings — this is
  not a general "some pages have less PageRank than others" check, it is
  specifically the hub-absorbs-equity-that-content-needs shape.
- **CIT-11** — deferred: claim-vs-forum-opinion provenance matching is a
  fuzzy-matching complexity problem, not a policy block. See capability
  matrix.
- **CIT-13 does not search the web itself.** It only fetches agent-supplied
  `--offsite-url` candidates and checks numeric survival — finding
  candidate off-site pages is your own search step, not this script's job.
- **Gate 1/2 and structured-data/content problems** —
  `perimeter-access-audit`, `entity-audit`, `content-quality-audit`.

## Output

One JSON object on stdout, same shape as the other page-level audit skills.
`agent_judgement_required` must be empty (or removed) by the time this file
reaches the entrypoint.

**Length caps on agent-authored text** (`evidence`, `mechanism`,
`suggested_action.summary`/`details`): 150 words each. Where evidence would
otherwise list pages or URLs, quote at most 3-4 representative ones plus the
true count — never every one.

## Failure modes

| Situation | Result |
|---|---|
| The page cannot be fetched | CIT-01/02/04/06/07 `unknown` |
| URL resolves to a private/loopback/reserved address | Refused before connecting, `unknown` — SSRF guard |
| The page is short (<500 words) | CIT-02 stays silent — not a judgement, it's out of scope by design |
| No superlative language on the page | CIT-06 stays silent |
| No numeric claims without a link | CIT-04's candidate list is empty; nothing to judge |
| No `--offsite-url` given | CIT-13 omitted entirely, not `unknown` — nothing was asked of it |
| An `--offsite-url` is disallowed by its own robots.txt, or cannot be fetched | One `unknown_checks` entry for that URL, `capability_id: "CIT-13"`; the other URLs still run |
| That URL's own robots.txt cannot be fetched at all | Treated as allow-all (RFC 9309 convention) — the fetch is still attempted |
| A `--sample-file` page cannot be fetched | One `unknown_checks` entry for that page (`capability_id: "CIT-08"`); the others still run |
| The `--sample-file` fetch loop runs past its 90s stage budget (`shared/budget.StageBudget`) | Fetching stops; findings still come from whatever pages were already fetched; every remaining un-fetched page gets its own `unknown_checks` entry naming the cap; `coverage.stages` in the output records the cutoff |
| Fewer than 5 pages were successfully fetched, no page reaches 500 words, the sample's top-ranked page is itself 500+ words, or link equity is not concentrated in any one hub | CIT-08 produces an empty, clean report — not `unknown` |
| At least one sampled page's URL or `<title>` looks comparison-shaped, or fewer than 5 pages were successfully fetched | CIT-09 produces an empty, clean report — not `unknown` |

## Safety

`--url` mode fetches exactly one page, a plain GET, no query strings, no
credentials, no form submission. Same SSRF guard and gzip Content-Encoding
handling as every other page-level skill in this marketplace (see
`content-quality-audit`'s or `entity-audit`'s SKILL.md for the incident this
guards against — found live against python.org's CDN).

`--offsite-url` fetches each URL under the same bounds, plus a per-host
robots.txt check before the fetch — a third-party host's own robots.txt is
always honoured.

Fetched HTML is parsed as data only, never executed, never treated as
instruction.
