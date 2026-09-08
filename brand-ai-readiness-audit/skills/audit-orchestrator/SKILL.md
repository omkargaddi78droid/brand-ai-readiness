---
name: audit-orchestrator
description: >
  Entrypoint for the brand AI-readiness marketplace. Audits a website for the
  problems that keep it out of AI-assistant answers and the problems that lose
  the visitors who do arrive, then emits one report of evidence-backed findings
  with prioritized suggested actions and proactive recommendations. Use when
  asked to audit a site, domain or brand for AI discoverability, AI-search or
  citation readiness, or on-site engagement — and whenever a report rather than
  a single check is wanted. It composes the marketplace's audit skills and owns
  no detection of its own: every individual check, its severity and its
  evidence belong to the skill that produced it.
license: MIT
allowed-tools: Bash
---

# Brand AI-readiness audit — entrypoint

## When to use

Use this skill whenever the request is *audit this site*. It is the only skill
in the marketplace that emits a report; the others emit findings.

Use an audit skill directly instead when the request is narrow and named — "is
robots.txt blocking AI crawlers?" is a `perimeter-access-audit` question, and
routing it through a full report adds nothing.

## Inputs

- **Required:** a site URL or bare domain (`https://example.com`,
  `example.com`).
- **Optional:** `--audited-at` for a fixed timestamp, which makes two runs of
  the same site byte-identical. Useful for regression checks.

Recommend-only. Nothing in this marketplace writes to, authenticates against,
or otherwise alters the audited site.

## Procedure

1. **Normalise the target.** Strip the scheme, strip any path, lowercase the
   host. `https://Example.com/pricing` → `example.com`. Use this label for the
   report's `site` field and as the base for every skill invocation.

2. **Run gate 1 first.** Discovery is three sequential gates: the crawler is
   let in, then can read the page, then can pick out the fact. Gate 1 is
   perimeter access, and its result changes how everything else is reported.

   ```bash
   python3 ../perimeter-access-audit/scripts/check_perimeter.py \
       --url https://example.com > /tmp/audit/perimeter.json
   ```

3. **Apply the gate rule.** If gate 1 reports a `critical` blanket block
   (`PER-02`), the site is unreachable to AI assistants and downstream content
   findings describe pages nobody can fetch. Keep running the later skills —
   the recommendations stay useful for after the block is lifted — but say in
   the report that the perimeter failure is the precondition for all of them.
   Never present a content finding as an independent cause when a gate above it
   has failed.

4. **Build the page sample once per site**, before running any per-page skill
   below. `sample_pages.py` replaces picking pages by eye: it fetches
   `sitemap.xml`, clusters URLs by template shape (same path structure,
   different instance), and allocates a fixed page budget across clusters
   proportionally, always including the homepage and any `/contact`,
   `/checkout`, `/search`, `/pricing` page found — so the sample spans the
   site's different page *kinds* instead of just its most numerous one (a
   hand-picked "interesting pages" sample tends to under-sample near-duplicate
   templates, the exact gap that later disables near-duplicate detection):

   ```bash
   python3 ../audit-orchestrator/scripts/sample_pages.py \
       --url https://example.com --budget 25 > /tmp/audit/page-sample.json
   ```

   If `sitemap.xml` is absent (`total_urls: 0`), fall back to picking pages by
   hand as before. Otherwise, read `sample_urls` from the output and use it as
   the page list for every per-page skill below — the 5-minute budget still
   does not allow running every skill against every sampled URL, so prioritize
   pages that carry claims worth getting right (pricing, specs, policies,
   dated announcements, how-to guides) within that list rather than the full
   set.

   Write `sample_urls` to a plain one-URL-per-line file too
   (`/tmp/audit/page-sample.txt`) — several multi-page checks below
   (`content-quality-audit`'s CQ-13/CQ-10, `entity-audit`'s ENT-07/ENT-08,
   `engagement-audit`'s EN-04/EN-08/EN-11, `citability-audit`'s CIT-08/CIT-09)
   consume it directly via their own `--sample-file` flag, once per site,
   alongside their normal per-page invocations. `retrieval-readiness-audit`
   and `static-extraction-audit` also consume it via their own
   `--sample-file` flag — for them it is the PREFERRED way to run, not an
   addition alongside per-page invocations (see step 5 below).

5. **Run the remaining audit skills** listed in the registry below, each
   writing its JSON to its own file. Skills are independent; a failure in one
   does not stop the others.

   `content-quality-audit` runs per page, not per site, against pages drawn
   from the sample built above. Five of its per-page capabilities (CQ-01,
   CQ-02, CQ-04, CQ-09, CQ-12) are judgement calls the script deliberately
   does not resolve, the same pattern as `engagement-audit` and
   `citability-audit` below. The same `--url` invocation also runs CQ-10's
   freshness half (script-decided, no judgement needed) off the same fetch,
   comparing the page's own claimed update date against its HTTP
   `Last-Modified` header:

   ```bash
   python3 ../content-quality-audit/scripts/check_content_quality.py \
       --url https://example.com/pricing > /tmp/audit/content-pricing.json
   ```

   Read the resulting file's `agent_judgement_required` array and resolve it
   yourself, per `content-quality-audit`'s own SKILL.md procedure, **before**
   passing the file to `compose_report.py`. Run it again per page in the
   sample; each invocation's findings carry that page's URL, so composing
   several runs keeps every finding attributable to the page it came from.

   Also run `content-quality-audit`'s multi-page mode (CQ-13 near-duplicate
   detection + CQ-10 cross-page fact collision) once per site, against the
   whole page-sample file built in step 4:

   ```bash
   python3 ../content-quality-audit/scripts/check_content_quality.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/content-near-dup.json
   ```

   CQ-13's findings in this file are final (script-decided). Resolve
   `agent_judgement_required` (CQ-10) against
   `references/content-judgement-rubric.md` §CQ-10 the same way as
   CQ-01/02/04/09/12, before composing.

   `entity-audit` runs the same way, per page — homepage/About page for
   Organization markup and canonical hygiene, product or review pages for
   rating agreement, category/breadcrumbed pages for taxonomy consistency.
   One of its capabilities (ENT-09) is a judgement call the script
   deliberately does not resolve — read the resulting file's
   `agent_judgement_required` array and resolve it yourself, per
   `entity-audit`'s own SKILL.md procedure, before passing the file to
   `compose_report.py`:

   ```bash
   python3 ../entity-audit/scripts/check_entity.py \
       --url https://example.com/ > /tmp/audit/entity-home.json
   ```

   If perimeter-access-audit's gate-1 run found a real sitemap, also run
   `entity-audit`'s sitemap-scoped half of ENT-04 once per site: it flags
   trailing-slash/`www.`/scheme URL forks directly from the sitemap's own
   declared URL list — extract the `<loc>` URLs from the already-fetched
   sitemap.xml into a file, one per line:

   ```bash
   python3 ../entity-audit/scripts/check_entity.py \
       --site example.com --sitemap-file /tmp/audit/sitemap-urls.txt > /tmp/audit/entity-sitemap.json
   ```

   Also run `entity-audit`'s multi-page mode (ENT-07 cross-domain service
   attribution + ENT-08 address clustering) once per site, against the same
   page-sample file used for CQ-13/CQ-10 above:

   ```bash
   python3 ../entity-audit/scripts/check_entity.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/entity-service-domains.json
   ```

   **Optional, off-site brand-visibility (ENT-05/ENT-06):** if checking for
   brand collision or lookalike-domain impersonation matters for this audit,
   first find candidate off-site pages yourself — a Reddit thread, forum
   post, or review-site page mentioning the brand name, or a domain that
   looks confusable with it (your own search step; this project does not
   crawl or search the web itself — it only queries specific pages you
   supply, direct and robots.txt-respecting) — then run entity-audit's
   off-site mode once per site:

   ```bash
   python3 ../entity-audit/scripts/check_entity.py \
       --site example.com --brand-name "Acme Widgets" \
       --offsite-url https://forum.example/t/acme-widgets-review-123 \
       --offsite-url https://acme-w1dgets.com/ > /tmp/audit/entity-offsite.json
   ```

   Resolve the resulting `agent_judgement_required` array (ENT-05 and
   ENT-06) against `references/entity-judgement-rubric.md` §ENT-05/§ENT-06
   the same way as ENT-09, before composing. Skip this call entirely when
   no off-site candidates were found or worth checking — ENT-05/06 are not
   reported `unknown` for being omitted.

   `engagement-audit` runs the same way, per page — but its output is not
   final on its own. Two of its four capabilities (EN-01, EN-03) are
   judgement calls the script deliberately does not resolve:

   ```bash
   python3 ../engagement-audit/scripts/check_engagement.py \
       --url https://example.com/ > /tmp/audit/engagement-home.json
   ```

   Read the resulting file's `agent_judgement_required` array and resolve it
   yourself, per `engagement-audit`'s own SKILL.md procedure, **before**
   passing the file to `compose_report.py` — append any findings you
   author into the file's `findings` array and remove
   `agent_judgement_required` entirely. `compose_report.py` treats an
   unresolved entry as an `unknown_checks` entry rather than crashing or
   dropping it silently, but resolving it properly is still your job, not a
   fallback to rely on.

   Also run `engagement-audit`'s multi-page mode (C1's information-scent
   check, EN-11 + the EN-08 slice; and B1+B8's dead-end/orphan detection,
   EN-04) once per site, against the same page-sample file used for
   CQ-13/CQ-10/ENT-07/ENT-08 above:

   ```bash
   python3 ../engagement-audit/scripts/check_engagement.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/engagement-multi-page.json
   ```

   EN-04's findings in this file are final (script-decided, same rule as
   EN-05/06/07/09). Resolve `agent_judgement_required` (EN-08 and EN-11)
   against `references/engagement-judgement-rubric.md` §EN-08/§EN-11 the
   same way as EN-01/EN-03, before composing.

   `citability-audit` runs the same way, per page, with the same
   `agent_judgement_required` resolution step for its agent-judged
   capability (CIT-04):

   ```bash
   python3 ../citability-audit/scripts/check_citability.py \
       --url https://example.com/guide > /tmp/audit/citability-guide.json
   ```

   **Optional, off-site corroboration (CIT-13):** if this page makes a
   striking or competitively significant numeric claim worth checking
   off-site, add the same kind of agent-supplied `--offsite-url` candidates
   used for ENT-05/06 above — one call per page, alongside its normal
   citability audit:

   ```bash
   python3 ../citability-audit/scripts/check_citability.py \
       --url https://example.com/guide \
       --offsite-url https://forum.example/t/does-this-claim-check-out \
       > /tmp/audit/citability-guide.json
   ```

   Resolve CIT-13's `agent_judgement_required` entry against
   `references/citability-judgement-rubric.md` §CIT-13 the same way as
   CIT-04. Omit `--offsite-url` entirely when there is nothing worth
   off-site-checking on this page — CIT-13 simply does not run, and is not
   reported `unknown` for it.

   Also run `citability-audit`'s hub/authority mode (CIT-08 link-graph
   structure + CIT-09 comparison-content gap) once per site, against the
   same page-sample file used for CQ-13/CQ-10/ENT-07/ENT-08 above:

   ```bash
   python3 ../citability-audit/scripts/check_citability.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/citability-link-graph.json
   ```

   Both capabilities' findings in this file are final (script-decided) — no
   `agent_judgement_required` resolution needed for this mode. CIT-09's
   finding, if present, carries `"track": "proactive"` — compose it as a
   suggestion, not a defect.

   `retrieval-readiness-audit` and `static-extraction-audit` are unlike the
   other four skills above: every one of their capabilities is inherently
   per-page (there is no separate site-wide capability), so **prefer their
   `--sample-file` bulk mode over one `--url` invocation per page** — it
   fetches the whole page-sample file concurrently in one process instead of
   spawning one sequential subprocess per page, closing the gap that made
   this project's own 5-minute budget unrealistic on a full 25-page sample
   across every skill (Defect 2 / INF-10 follow-up):

   ```bash
   python3 ../retrieval-readiness-audit/scripts/check_retrieval_readiness.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/retrieval-sample.json

   python3 ../static-extraction-audit/scripts/check_static_extraction.py \
       --site example.com --sample-file /tmp/audit/page-sample.txt > /tmp/audit/static-extraction-sample.json
   ```

   `static-extraction-audit`'s nine capabilities are all script-decided, so
   there is no `agent_judgement_required` step for it either way.
   `retrieval-readiness-audit` still has four agent-judged capabilities
   (RET-02/03/05/06) — in bulk mode, every sampled page's judgement requests
   arrive together in one `agent_judgement_required` array, each entry still
   carrying its own `observations.page_url` (stamped by the skill itself),
   so resolve them exactly as you would per-page findings: per entry, using
   that entry's own `page_url` to know which page it's about, **before**
   passing the file to `compose_report.py`.

   Fall back to a single `--url` invocation only for a one-off page outside
   the sample worth checking specifically (e.g. a product page for REN-04's
   price-render gating that the template-stratified sample didn't happen to
   include):

   ```bash
   python3 ../static-extraction-audit/scripts/check_static_extraction.py \
       --url https://example.com/product/widget > /tmp/audit/static-extraction-widget.json
   ```

6. **Compose one report.**

   ```bash
   python3 scripts/compose_report.py --site example.com \
       --skill perimeter-access-audit /tmp/audit/perimeter.json \
       --skill content-quality-audit /tmp/audit/content-pricing.json \
       --skill content-quality-audit /tmp/audit/content-checkout.json \
       --skill content-quality-audit /tmp/audit/content-near-dup.json \
       --skill entity-audit /tmp/audit/entity-home.json \
       --skill entity-audit /tmp/audit/entity-service-domains.json \
       --skill entity-audit /tmp/audit/entity-offsite.json \
       --skill engagement-audit /tmp/audit/engagement-home.json \
       --skill citability-audit /tmp/audit/citability-guide.json \
       --skill retrieval-readiness-audit /tmp/audit/retrieval-sample.json \
       --skill static-extraction-audit /tmp/audit/static-extraction-sample.json
   ```

   Repeat `--skill NAME PATH` once per invocation that ran, including once per
   page for skills like `content-quality-audit` that run per page rather than
   per site — the same skill name may appear more than once. Add
   `--floor-only` for the minimal required schema instead of the full report.

7. **Return the JSON the script printed, unmodified.** It has already been
   validated. Do not add findings, re-word evidence, re-rank severities or
   summarise the report into prose in place of the JSON — a finding's severity
   and mechanism are set by the skill that has the evidence.

8. **If a skill produced nothing usable**, the composer records it as an
   `unknown_checks` entry naming that skill, and the report is still emitted
   from whatever did run. Reduced coverage is reported, never hidden. The
   six `--sample-file` skills (`entity-audit`, `content-quality-audit`,
   `citability-audit`, `engagement-audit`, `retrieval-readiness-audit`,
   `static-extraction-audit`) each fetch their page sample concurrently and
   cap the whole fetch loop at 90s via `shared/budget.StageBudget` (INF-10)
   — if that cap is hit mid-run, `compose_report.py` merges each skill's own
   `coverage.stages` entry into the final report's `coverage.stages`, so a
   partially-covered sample is visible in the report itself, not just
   inferrable from a shorter-than-expected findings list.

## Skill registry

Every skill the entrypoint invokes, and what it owns. One owner per capability:
two skills reading the same signal is fine, two skills reporting on it is a
composition bug.

| Skill | Owns | Gate | Runs |
|---|---|---|---|
| `perimeter-access-audit` | PER-01 AI-crawler access by tier · PER-02 blanket block · PER-03 CDN/edge blocking · PER-04 llms.txt presence and validity · PER-05 llms-full.txt · PER-06 sitemap discovery · PER-07 Markdown negotiation · PER-08 sitemap discoverability (robots.txt reference + llms.txt/sitemap URL-set agreement) · PER-09 cross-layer access-signal contradiction (robots.txt/`X-Robots-Tag`/meta-robots/TDMRep/llms.txt/sitemap.xml agreement) | 1 | Once per site |
| `content-quality-audit` | CQ-03 template leakage · CQ-05 relative-date anchors · CQ-07 scope-ambiguous numerics · CQ-08 computed-stat integrity · CQ-10 freshness self-contradiction (`--url` mode) · CQ-11 fluency/readability · CQ-13 near-duplicate/template dilution (multi-page) · CQ-01 answer extractability (agent-judged) · CQ-02 non-answer templates (agent-judged) · CQ-04 granularity mismatch (agent-judged) · CQ-09 marketing/procedure interleaving (agent-judged) · CQ-10 cross-page fact collision (agent-judged, multi-page) · CQ-12 signal-to-filler ratio (agent-judged) | 3 | Once per sampled page (CQ-10 freshness half included), plus once per site for CQ-13/CQ-10 fact-collision's `--sample-file` mode |
| `entity-audit` | ENT-01 schema.org/JSON-LD validity · ENT-02 knowledge-graph grounding · ENT-03 markup/text agreement · ENT-04 canonicalisation (single-page + sitemap-scoped fork detection) · ENT-07 cross-domain service attribution + ENT-08 address/NAP clustering (multi-page) · ENT-11 JSON-LD graph referential integrity (dangling/cross-page @id references, orphan identity nodes) · ENT-12 JSON-LD entity-graph fragmentation · ENT-09 taxonomy consistency (agent-judged) · ENT-05 brand-name collision + ENT-06 lookalike-domain impersonation (agent-judged, optional off-site mode) | 3 | Once per sampled page, plus once per site for ENT-04's sitemap-scoped half, ENT-07/08's `--sample-file` mode, and (optional) ENT-05/06's off-site mode |
| `engagement-audit` | EN-01 visitor orientation (agent-judged) · EN-03 conversion-path friction (agent-judged) · EN-05 mobile usability · EN-06 interstitial/consent-wall friction · EN-07 perceived-performance friction · EN-09 autonomous-agent usability · EN-04 dead-end/orphan pages (multi-page) · EN-11 content-to-action coherence (multi-page, agent-judged) · EN-08 findability link-scent slice (multi-page, agent-judged) | none — engagement, not gated | Once per sampled page, plus once per site for the `--sample-file` multi-page mode |
| `citability-audit` | CIT-01 trust-signal authority · CIT-02 source attribution · CIT-06 statistics density · CIT-07 citation-position weighting · CIT-08 hub/authority link-graph structure + CIT-09 comparison-content gap (multi-page, proactive) · CIT-04 citation recall (agent-judged) · CIT-13 off-site corroboration (agent-judged, optional) | 3 | Once per sampled page, plus once per site for CIT-08/09's `--sample-file` mode |
| `retrieval-readiness-audit` | RET-01/04/07/08/09/10 (script), RET-02/03/05/06 (agent-judged) | 3 | Once per site via `--sample-file` (preferred), or once per page via `--url` for a one-off page |
| `static-extraction-audit` | REN-02 hydration-state coverage · REN-04 price-render gating · REN-05 availability freshness · REN-06 semantic HTML5 boundary · REN-07 content ratio · REN-08 multimodal accessibility · REN-10 NAP render asymmetry (phone) · REN-11 PDF-only fact lock (proactive) · REN-12 concealed agent-directed instruction scanner — all script-decided, no headless browser | 2 | Once per site via `--sample-file` (preferred), or once per page via `--url` for a one-off page |

## Output

One JSON object, the sole output of the marketplace. It satisfies the required
report schema and extends it:

```json
{
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "summary": {
    "total_findings": 3,
    "critical": 1,
    "high": 0,
    "medium": 1,
    "low": 1,
    "defects": 2,
    "proactive_suggestions": 1,
    "checks_unknown": 0
  },
  "findings": [
    {
      "id": "F-001",
      "title": "robots.txt blocks every AI assistant while allowing conventional crawlers",
      "severity": "critical",
      "evidence": "robots.txt disallows / for all 15 AI user agents checked across the training, AI-search and on-demand tiers (...), while the wildcard group is not blocked at the root.",
      "suggested_action": {"summary": "Allow the AI-search and on-demand tiers at the root ...", "priority": "critical"},
      "check_id": "PER-02-all-ai-agents-blocked",
      "category": "discoverability",
      "capability_id": "PER-02",
      "owner_skill": "perimeter-access-audit",
      "mechanism": "...",
      "track": "defect",
      "gate": 1,
      "confidence": "high"
    }
  ],
  "unknown_checks": []
}
```

What the extra fields buy, and why each is worth its space:

- **`mechanism`** — why this finding has the severity it has, stated so a
  reader can argue with it instead of taking it on trust.
- **`track`** — `defect` means a problem was observed. `proactive` means no
  defect was found and the change would still strengthen the site. Both are
  actionable; conflating them would dress up suggestions as faults.
- **`confidence`** — reduced where the underlying mechanism is genuinely
  contested, so a hedge is visible rather than buried in wording.
- **`check_id`** — the stable semantic id of the check, so a finding can be
  traced across runs while report ids stay short and ordered.
- **`unknown_checks`** — checks that could not run, with the reason. A check
  that did not run is never reported as a pass.

Findings are ordered defects first, then by severity, then by id. Ids are
assigned sequentially in that order, so the same set of findings always
produces the same report.

## Failure modes

| Situation | Result |
|---|---|
| An audit skill exits non-zero or emits unparseable JSON | One `unknown_checks` entry naming the skill; the report is still produced |
| A skill emits a finding missing evidence, mechanism or a suggested action | The composer aborts loudly. That is an authoring bug in the skill, and a report whose evidence cannot be trusted is worse than no report |
| Two skills emit the same finding id | The composer aborts. One owner per capability is a checkable rule |
| The site is unreachable entirely | Gate 1 reports `unknown`; the report says the audit could not reach the site rather than reporting a clean site |

## Excludes

- **No detection.** The entrypoint runs nothing that reads a page. If a check
  seems to belong here, it belongs in an audit skill.
- **No re-scoring.** Severity, mechanism and evidence pass through untouched.
- **No writes.** Nothing modifies the audited site, and no suggested action is
  ever applied — the marketplace recommends.
