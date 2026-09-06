# Capability Matrix

The project's central capability ledger. Started as a Phase 0.2 inventory-only
snapshot; as of cycle 22, 58 capabilities below are marked IMPLEMENTED.
**Status is tracked per row — see each capability's Status column for its
actual current state (IMPLEMENTED, PARTIALLY_COVERED, NOT_STARTED, etc.),
not a single blanket claim for the whole file.**

## How to read this

- **Match** — Exact / Adjacent / None (build-from-scratch), per available resource.
- **Presumed** — presumed baseline coverage, *unverified*. Confirmed or refuted in Phase 1
  forensics and again per-capability at Step A. `?` = unknown until then.
- **Status** — NOT_STARTED · ANALYZING · BASELINE_COVERED · PARTIALLY_COVERED ·
  INTEGRATION_CANDIDATE · BUILD_REQUIRED · IMPLEMENTED · TESTING · VERIFIED · REJECTED · DEFERRED.
- Per-cluster detail blocks carry dependencies, security, runtime, FP risk and test
  strategy — these are cluster-level properties; per-capability deviations are noted inline.

## Hard constraints (confirmed with judges, cycle 19)

1. **No headless/headless-adjacent browsers.** Judges run tests in Python/Node
   environments. Detection must use direct HTTP + parsing only — `requests`/`httpx`/
   `fetch`, static HTML, embedded JSON, JSON-LD, and hydration state (e.g.
   `__NEXT_DATA__`, `window.__NUXT__`, other framework state blobs serialized into
   the raw response). No `crawl4ai`/Playwright/Chromium anywhere, including as an
   optional fallback — an optional browser path still fails a browserless grader.
   This makes permanent what Cluster B/INF-03 had left open pending evidence
   (`docs/phase-4-completion-6.md`, `-7.md`, `-9.md`: "no headless browser in this
   environment, revisit only with new evidence") — the evidence is now in: there
   will not be one. Cluster B and INF-03 are rewritten below accordingly.
2. **Off-site website querying is allowed, narrowly.** Public sites — Reddit, Quora,
   forums, review sites — may be queried directly (`requests`/`httpx` GETs, robots.txt
   respected) for brand visibility/presence/mentions/discoverability. This does **not**
   reopen general web search or crawling. Still categorically excluded: any external
   computation or third-party API that hands back a pre-computed score, metric,
   classification, or analysis in place of us computing it locally (`seoscoreapi` and
   its class remain rejected under M5, `docs/competition-requirements.md`). The
   distinction is fetch-raw-and-judge-ourselves (allowed) vs. outsource-the-verdict
   (not allowed). This reopens the off-site half of ENT-05/06 and CIT-13, previously
   blocked on the wrong reason (see their Detail blocks below).

## Capability freeze — cycle 21

After cycles 19-20 shipped both hard-constraint-driven gaps (Cluster B;
ENT-05/06/CIT-13), the user drew a hard line: stop expanding anything
already built, select exactly 3 more `NOT_STARTED` capabilities against
five criteria (core-problem impact, differentiation, feasibility within the
non-negotiable constraints, complementary/no-overlap, concrete findings not
scores), and discard every other remaining candidate with no further scope
growth. Of the 3 selected (EN-07, EN-05, CQ-10), the user then narrowed
execution to the first two only — **CQ-10 was not built**, and is discarded
alongside every other candidate below, not deferred as a future pick.

**Shipped:** EN-05 (mobile usability, narrowed to viewport + fixed-width
overflow), EN-07 (perceived-performance friction, narrowed to HTML-document
weight + render-blocking head resources + unsized images) — both in
`engagement-audit`, both script-decided, no new skill file. See
`docs/phase-4-completion-21.md`.

**Discarded, this cycle, no alternatives proposed in their place:** every
row below tagged "considered cycle 21, discarded" in its own status
text — REN-03, REN-09, ENT-07, ENT-08, CIT-03, CIT-08, CIT-09, CIT-12,
CQ-06, CQ-10, EN-02, EN-04, EN-08, EN-10, EN-11. Each row's own tag names
its specific reason (crawl-wide/multi-page context this project has no
infrastructure for; a reading-comprehension judgement with no scriptable
low-FP slice; overlap with an already-implemented capability; or, for
CQ-10 specifically, a user scope decision after selection rather than a
feasibility problem). This freeze is final for this phase — no further
capability additions without a new, explicit unfreeze decision.

## Capability unfreeze — cycle 22

Cycle 21 froze the capability set explicitly: "no further capability
additions without a new, explicit unfreeze decision." `docs/01-project-plan.md`
is that explicit unfreeze decision. Two deep-research passes (`research1.md`,
`Research2.md`) were commissioned against `prompt2.txt` to find capabilities
*outside* the existing PER/REN/ENT/RET/CIT/CQ/EN set — the research had
already been mined once (cycle 19-20's ENT-05/06/CIT-13 reopening); this pass
looked for genuinely new analysis dimensions, not more rows in existing
clusters. It returned **27 serious candidates**, scored against the same
five criteria cycle 21 used (core-problem impact, differentiation,
feasibility within this project's non-negotiable constraints,
complementary/no-overlap, concrete findings not scores). **5 selected, 4
deferred, 19 rejected** — full per-candidate scoring and reasoning in
`docs/01-project-plan.md` §2.

**Shipped, all five, folded into existing skills — marketplace stays at 8
skills, no new skill file for any of them:**

- **PER-09** — cross-layer access-signal contradiction (`perimeter-access-
  audit`). robots.txt / `X-Robots-Tag` response header / `<meta
  name="robots">` / TDMRep / llms.txt / sitemap.xml checked against each
  other for literal disagreement, not presence/validity alone (every other
  PER-0x row asks "is X present and valid?"; this asks "do the site's own
  declarations agree with each other?"). See `docs/phase-4-completion-22.md`.
- **ENT-11** — JSON-LD graph referential integrity (`entity-audit`). Walks
  `@id` edges across the structured-data graph — dangling references, a
  cross-page reference the page's own sitemap can confirm is broken,
  orphan identity nodes. Every existing ENT-0x row validates a node in
  isolation; this is the first to validate the graph *as a graph*. See
  `docs/phase-4-completion-22.md`.
- **RET-09** — positional fact interment (`retrieval-readiness-audit`).
  Load-bearing figures (price, spec, headline statistic) that exist only in
  a long page's middle band, restated nowhere — the strongest-evidenced
  mechanism in either research document (Liu et al.'s "Lost in the
  Middle", TACL 2024; Chroma's 2025 "Context Rot" study). See
  `docs/phase-4-completion-22.md`.
- **RET-10** — chunk self-containment (`retrieval-readiness-audit`,
  strictly after RET-09 — reuses and hardens the same `shared/text_spans.
  extract_blocks` infrastructure). A content block opening with an
  unresolved pronoun/demonstrative/generic-definite reference that never
  names its own subject inside the block — the unit a RAG pipeline
  actually retrieves. See `docs/phase-4-completion-22.md`.
- **REN-12** — concealed agent-directed instruction scanner
  (`static-extraction-audit`). Text invisible to a visitor (CSS-hidden, an
  HTML comment, or embedded only in JSON-LD/meta content) but fully
  present in the static text a fetcher reads, carrying an instruction
  addressed at an AI system — concealment alone never fires, a language
  trigger is always required too. Highest complexity and highest FP risk
  of the five; widens this skill's stated concern to both directions of
  the human/machine view gap (REN-02/04/10 find facts hidden *from*
  machines, REN-12 finds text hidden *from* humans). See
  `docs/phase-4-completion-22.md`.

**Deferred, 3** (a real defect, blocked on complexity or infrastructure,
not policy — distinct from a rejection): chunk-fracture simulation (folded
into RET-10's own mechanism instead — a fixed window offset is arbitrary,
RET-10's anchor test captures the same underlying risk without one);
AI-reachable subgraph orphan detection in its full graph form (needs a
link-graph crawl this project does not have; its cheap, crawl-free 80% —
robots path rules ∩ sitemap inventory — is absorbed into PER-09's own
contradiction check); `.md`-variant-vs-canonical-HTML drift (a genuine
defect, reachable on <1% of sites that serve a `.md` variant at all — a
cheap PER-07 extension for a future cycle, not its own capability).
Cross-page near-duplicate/template dilution, formerly deferred here as
"methodologically broken against this project's own agent-chosen,
variety-biased page sample", was unblocked by cycle 23's Phase 1
template-stratified sampler and shipped as **CQ-13** — see that row above.

**Rejected, 19**, across five named failure classes (full per-candidate
reasoning in `docs/01-project-plan.md` §2's table and "The pattern in the
rejections"):

- **Banned dependency or absent infrastructure**: GraphRAG k-core density
  (needs `networkx`, banned), internal PageRank starvation (same two
  blockers), OpenIE triple-extraction yield (needs a dependency parser,
  banned), self-reflective API validation (near-zero hit rate — needs a
  published OpenAPI spec).
- **Fires on everything**: Accept-header content negotiation (~99.9% of
  sites answer "no"), W3C PROV-O lineage (research states plainly almost
  all sites will flag), byte-range fetch survivability (near-universal and
  irrelevant to HTML), HTTP `Link` header relations (absent on nearly
  every site, appropriately).
- **Unfalsifiable threshold**: redirect-hop/latency vs. fetcher tolerance
  (thresholds from blog observation, not vendor specs; not reproducible
  from our network), BM25 length-normalization trap (the corpus average
  document length is unknowable, so the computed score drop is
  unfalsifiable).
- **Already shipped under another name**: semantic distractor density
  (≈ CQ-07, same defect with a similarity score attached), identifier-vs-
  prose vocabulary divergence (≈ RET-01 + RET-05), sectioning containment
  hierarchy (the intersection of RET-08 + REN-06, both already shipped),
  NCD semantic redundancy standalone (≈ REN-07's content ratio, within a
  page).
- **Conventional SEO in new clothing**: cross-page near-dup via SimHash
  (presentation, not question, novelty — also the methodology-broken case
  above), URL semantic entropy (opaque IDs are a legitimate engineering
  choice, not a defect), IndexNow adoption (absence proves nothing —
  server-side pings leave no artifact).
- **Other, each its own reason**: edge-cache staleness skew bot-vs-browser
  (highest FP risk in the pool — mechanism is inference from general CDN
  practice, not a study); Common Crawl CDX footprint (third-party service
  dependency, breaks manifest self-containment); ETag volatility vs.
  content hash (costs a 30-second sleep for a rare, low-impact signal).

This freeze is unfrozen exactly once, for exactly these five. It refreezes
after this cycle — no further capability additions without another
explicit unfreeze decision, the same discipline cycle 21 established.

---

Resource keys: `GEO` = Auriti-Labs/geo-optimizer-skill · `C4A` = crawl4ai
(**excluded — headless browser, hard constraint 1 above; kept as a table label for
history, never a real dependency**) · `TRA` = trafilatura · `ADV` = advertools ·
`BM25` = bm25s/rank_bm25 · `SQ*` = squirrelscan (prior art only, not a dependency) ·
`AZ*` = aaron-he-zhu (patterns only) · `—` = build from scratch.

Totals: **89 capabilities** — 78 audit + 11 infrastructure (84 as of cycle 21,
+5 cycle 22: PER-09, ENT-11, RET-09, RET-10, REN-12, per the unfreeze above).
47 from the research spec, 11 engagement (authored), the remainder
folded/added across phases. Build-from-scratch: **31 as of cycle 21**
(unverified against the current row count this cycle; flagged, not
recounted, to keep this fix scoped — the same disposition the cycle-21
figure itself carried forward from cycle 10).

---

## Cluster A — Perimeter & discovery (Gate 1)

*If this gate fails, everything downstream is moot. These are the veto items.*

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| PER-01 | AI crawler access audit | robots.txt blocking of AI bots across the 3-tier taxonomy: training bots (GPTBot, ClaudeBot, Google-Extended), real-time search indexers (OAI-SearchBot, PerplexityBot, Claude-SearchBot), on-demand user fetchers (ChatGPT-User, Claude-User, Perplexity-User) | GEO | Exact | ✔ | IMPLEMENTED |
| PER-02 | Blanket-block detection | The specific anti-pattern of `Disallow: /` for all AI agents — erases the brand from real-time RAG while gaining nothing | GEO | Adjacent | ? | IMPLEMENTED |
| PER-03 | Edge/WAF/CDN bot blocking | 403/429/challenge responses to AI user-agents even when robots.txt permits — robots says yes, the edge says no | — (built locally; baseline not integrated) | None | — | IMPLEMENTED — `perimeter-access-audit`, live-only. One representative agent per tier, gated on a reachability control succeeding and on robots.txt not already blocking that agent. See docs/phase-4-completion.md. First live positive case confirmed `docs/phase-4-completion-16.md` (Cloudflare-fronted site blocking `ChatGPT-User` while robots.txt allows it) — 9 live sites in the original cycle had shown none |
| PER-04 | llms.txt presence & spec validity | Missing file; or present but malformed — no H1, no summary blockquote, bare URLs without descriptions | GEO | Exact | ✔ | IMPLEMENTED |
| PER-05 | llms-full.txt ingestion audit | Missing concatenated payload; or present but truncation-risk / low semantic density | — (built locally) | None | — | IMPLEMENTED — `perimeter-access-audit`. Absence alone not flagged (optional companion); truncation-risk detection not built, only a thin-stub word-count check |
| PER-06 | sitemap.xml discovery audit | Missing, stale, or incomplete sitemap; orphaned fact-dense pages unreachable from it | — (built locally, regex not ADV) | None | — | PARTIALLY_COVERED — `perimeter-access-audit` covers presence/validity/emptiness of the sitemap itself; completeness (orphaned pages not listed) needs a crawl to compare against, not built |
| PER-07 | Markdown content negotiation | Server does not serve `.md` variants under content negotiation — a cheap, high-leverage win | — | None | ✘ | IMPLEMENTED — `perimeter-access-audit`. Path-suffix negotiation (`<path>.md`), not `Accept`-header content negotiation |
| PER-08 | AI-discoverability of the sitemap itself | Sitemap not referenced from robots.txt; llms.txt and sitemap disagree on the canonical URL set | — (built locally) | None | — | IMPLEMENTED — `perimeter-access-audit`. Both halves built cycle 18: robots.txt-reference, and llms.txt/sitemap URL-set disagreement (a llms.txt link the sitemap doesn't know about — the reverse direction, sitemap URLs llms.txt omits, is the intended curated-subset pattern, not a defect). Live-validated on 6 real sites; a `<sitemapindex>` sitemap (vercel.com, supabase.com) reports `unknown` rather than comparing against the index's own pointer URLs — sub-sitemap recursion not built, same class of gap as PER-06's completeness limitation |
| PER-09 | Cross-layer access-signal contradiction | The site's own declared-access surface disagreeing with itself across robots.txt, the `X-Robots-Tag` response header, `<meta name="robots">`, TDMRep (`tdm-reservation`), llms.txt, and sitemap.xml — not presence/validity of any one layer alone | — (built locally) | None | — | IMPLEMENTED — `perimeter-access-audit`, cycle 22. Fetches the page once for `X-Robots-Tag`/`<meta name="robots">`/`tdm-reservation` (`fetch_page_with_headers`, Phase 1.3 shared infra — the response-header-capture gap every other PER-0x row had been discarding). Five contradiction rules: a sitemap-declared URL AI crawlers are disallowed from reaching (C1); a page declared in the sitemap that also carries `noindex` (C2); a TDM reservation that contradicts robots.txt's own training-bot allowance (C3, scoped to GPTBot/ClaudeBot/CCBot); the `X-Robots-Tag` header and `<meta name="robots">` tag disagreeing with each other; and — the inverse of C3 — a training-relevant page with no TDM declaration at all where one is expected. See `docs/phase-4-completion-22.md` |
| PER-10 | RFC 9727 API catalog discovery | `/.well-known/api-catalog` served with the wrong `Content-Type` (RFC 9727 requires `application/linkset+json`), or a body that does not follow the RFC's `linkset` structure (entries missing `anchor`/`service-desc`) | GEO (research3.md A5) | Exact | ✔ | IMPLEMENTED — `perimeter-access-audit`, cycle 23. Absence alone is not flagged (a 2024 RFC with essentially no adoption yet); an SPA's client-side-routing catch-all page answering the well-known path at HTTP 200 is explicitly guarded against as the dominant false positive, the same way PER-04/07 guard against a soft-404 HTML response |
| PER-11 | AI-crawler content-parity diff (cloaking) | A tier's representative agent gets HTTP 200 at the same URL an ordinary browser also gets HTTP 200 from, but with under half the visible-text length or zero JSON-LD nodes where the browser copy has at least one — same permission, materially different payload | GEO (research3.md A3) | Exact | ✔ | IMPLEMENTED — `perimeter-access-audit`, cycle 23. Distinct from PER-03: an outright block is an honest denial; this catches the case where the agent believes it successfully fetched the page and has no signal anything is missing. Reuses PER-03's compliance plan (`plan_edge_probes` — never probe an agent robots.txt disallows) but fetches its own full response body rather than PER-03's truncated 4096-byte classification snippet, and fetches `robots.txt` independently rather than trusting a caller-supplied groups list, so a skipped or failed PER-03 run can never be silently read as "robots.txt permits everything" |

**Detail.** Deps: stdlib HTTP + `advertools` (optional). Security: read-only GETs only;
respect robots for our own fetching; never probe authenticated paths. Runtime: <5 s
total — cheapest cluster in the audit, run first. FP risk: **low**, but real —
`Disallow` on a staging path is not a site-wide block; parse the exclusion protocol
properly rather than substring-matching. Tests: fixture robots files for
allow-all / block-all / tier-selective / malformed / missing / redirecting.

---

## Cluster B — Static extraction & hydration-state analysis (Gate 2)

*Renamed from "Render & extraction" — hard constraint 1 permanently excludes headless
rendering (see above). Every row redefined against static HTTP + parsing only: raw
HTML, JSON-LD, and any hydration-state JSON blob the page embeds itself (`__NEXT_DATA__`,
`window.__NUXT__`, etc.) — never an actual rendered DOM.*

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| REN-01 | Fetch foundation | — (infrastructure for this cluster: HTTP fetch + link discovery, no rendering) | — | None | ✘ | IMPLEMENTED — `static-extraction-audit`. Infrastructure only, no finding emitted for it |
| REN-02 | Hydration-state coverage diff | Content present in an embedded hydration-state JSON blob but absent from the static HTML text a non-JS fetcher would extract | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Narrowed to `<script type="application/json">`/`__NEXT_DATA__`/`__NUXT_DATA__` blocks; Next.js App Router's RSC "flight data" streaming format (`self.__next_f.push(...)`) is a different, non-JSON-block mechanism, not parsed — reports nothing found (honest `unknown`-by-silence), live-confirmed on nextjs.org itself. See docs/phase-4-completion-19.md |
| REN-03 | Pagination / infinite scroll | Products or articles reachable only by scrolling or clicking "Load more" — autonomous crawlers do neither | — | None | ✘ | NOT_STARTED — static proxy only: absence of `<a href>`/`rel=next` pagination links alongside a "Load more"-style control with no href. Cannot confirm the JS behavior itself, only the missing static escape hatch; considered too weak to clear this project's FP bar without a fixture built to prove it first, cycle 19; reconsidered and discarded again cycle 21 for the same reason |
| REN-04 | Price-render gating | Price absent from initial HTML, or present in JSON-LD `Offer.price` but not restated in visible text (and vice versa) | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. `Offer.price`/`Product.offers.price`/`priceSpecification.price` vs. visible text, currency-symbol- and comma-tolerant numeric match — same shape as RET-01/RET-04's Cluster D detectors. See docs/phase-4-completion-19.md |
| REN-05 | Real-time availability exposure | Volatile facts (stock, slots) served only as a static snapshot with no freshness signal (timestamp, "as of", `dateModified`) nearby | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Page-level, not proximity-scoped to the specific claim (documented narrowing — static text does not preserve reliable DOM proximity). See docs/phase-4-completion-19.md |
| REN-06 | Semantic HTML5 extraction compatibility | Missing `<main>`/`<article>` boundaries → boilerplate cannot be stripped → noise floods the context window | — | None | ~ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Always was static; never actually needed a browser. 150-word floor before firing. Live-confirmed on vercel.com and docs.python.org's landing pages. See docs/phase-4-completion-19.md |
| REN-07 | Boilerplate / content separation quality | Measured ratio of extractable body text to chrome, per template | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Ratio of `<main>`/`<article>`-scoped words to total visible-text words, fires under 30%; silent when no boundary exists at all (REN-06 owns that case). See docs/phase-4-completion-19.md |
| REN-08 | Multimodal accessibility | Missing or vague alt-text, absent transcripts/captions — severs visual assets from semantic retrieval | — (was seoscoreapi) | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Missing/empty `<img alt>` (decorative images excluded via `role="presentation"`/`aria-hidden="true"`); `<video>`/`<audio>` with no `<track>`. Never needed rendering. Live-confirmed on chewy.com. See docs/phase-4-completion-19.md |
| REN-09 | Image-of-text facts | Prices, specs, hours rendered inside images with no text restatement | — | None | ✘ | NOT_STARTED — no OCR/vision capability in this project; unrelated to the browser constraint, blocked on a different missing capability. Considered cycle 21, discarded: needs OCR/vision this project does not have |
| REN-10 | NAP render asymmetry | Phone/address only assembled by client-side JS (e.g. concatenated from `data-*` fragments or a JS string) with no plain-text equivalent | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19), script-decided. Narrowed to phone numbers only — free-form street-address pattern matching needs a real address parser to keep FP low, deferred. See docs/phase-4-completion-19.md |
| REN-11 | PDF-only fact lock | Decision-critical figures only inside linked PDFs with no HTML restatement | — | None | ✘ | IMPLEMENTED — `static-extraction-audit` (cycle 19). Presence-only, always `track: proactive`, never a confirmed defect: this project has no PDF-parsing library (stdlib-only dependency rule), so it can note a PDF link exists but not verify its content. Narrower than the matrix's original "fetch + parse the PDF's text layer" framing — that framing is corrected here, not deferred. See docs/phase-4-completion-19.md |
| REN-12 | Concealed agent-directed instruction scanner | Text invisible to a visitor (CSS-hidden, an HTML comment, or embedded only in JSON-LD/`<meta content>`) but fully readable by a text extractor, carrying an instruction addressed at an AI system — indirect prompt injection, independently documented in the wild by Zscaler ThreatLabz, Unit 42, Forcepoint X-Labs, and Brave's Perplexity Comet red-team work | — | None | ✘ | IMPLEMENTED — `static-extraction-audit`, cycle 22, script-decided. A second, tree-based DOM parse (ancestor-aware concealment resolution and `<style>`-block rule matching don't fit the skill's existing single-pass parser). Concealment map: `hidden` attribute, `aria-hidden="true"`, inline style, or a matching `<style>`-block rule (last-matching-rule-per-property wins, no cascade/specificity engine — conservative, silent when ambiguous), an HTML comment, or JSON-LD/meta content (concealed by construction). Fires only on concealment **and** a language trigger — Override phrase (critical), an imperative verb near an agent noun (high), or a self-authority phrase 40+ chars (medium); concealment alone never fires. Required exclusions: `<code>`/`<pre>`/`<kbd>`/`<samp>` skipped entirely, `<noscript>` is not concealment. Per-instance finding, capped at 5. Highest complexity and highest FP risk of the five cycle-22 capabilities; widens this skill's stated concern to both directions of the human/machine view gap. See `docs/phase-4-completion-22.md` |

**Detail.** Deps: stdlib HTTP only — no `trafilatura`, no PDF-parsing library; both
were named as this cluster's resources before cycle 19's build and turned out
unnecessary (REN-06/07's boundary/ratio checks are a stdlib HTML parse;
REN-11 stayed presence-only once a PDF text-layer reader turned out to be a real
third-party dependency this project's "pure stdlib" rule doesn't allow). **No
`crawl4ai`, no Playwright, no Chromium, no optional browser fallback** — hard
constraint 1. Most of this cluster never actually needed a browser (REN-06/07/08/11
are pure static parsing and were mis-scoped as render-dependent by inheritance from
the cluster's original framing, not by their own detection logic); REN-02/04/05/10
lose real signal under the static-only redefinition, and each row above states the
approximation and its blind spot. Security: read-only GETs only, same as Cluster A.
Runtime: low — no rendering cost, dominant cost is now just page-fetch count. FP
risk: **high** for the approximated rows — a missing hydration blob or a "Load
more" control with no href is a weaker signal than an actual render diff; every one
of them must emit `unknown`, never `fail`, when its static proxy can't be found (no
hydration-state blob, no matching JSON-LD block). Tests: `static-extraction-audit`
shipped with 59 unit tests and a 10-case labelled corpus (precision 1.000, recall
1.000) — see docs/phase-4-completion-19.md. REN-03/09 remain unbuilt, so this
paragraph's FP-risk note about "approximated rows" no longer covers them.

---

## Cluster C — Entity & canonical identity (cross-cutting multiplier)

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| ENT-01 | Schema.org / JSON-LD presence & validity | Missing, malformed, or type-inappropriate structured data | — (built locally) | None | — | IMPLEMENTED — `entity-audit`. Scoped to Organization/WebSite/LocalBusiness/Product; not routed through the baseline (untestable offline per Phase 3). See docs/phase-4-completion-3.md |
| ENT-02 | Knowledge-graph grounding | No `sameAs` links to Wikidata/authoritative IDs — brand stays a probabilistic string, never a resolved entity | — (built locally) | None | — | IMPLEMENTED — `entity-audit`. Only evaluated when an identity node exists, to avoid redundant noise with ENT-01 |
| ENT-03 | Markup/text agreement | Marked-up review counts, ratings, prices that disagree with the visible page text | — | None | ✘ | IMPLEMENTED — `entity-audit`. Scoped to aggregateRating vs. visible-text rating claims; price cross-check deferred (multi-price ambiguity) |
| ENT-04 | Canonicalisation & duplicate content | Slug variants, trailing-slash forks, missing/incorrect `rel=canonical` splitting authority | — (built locally) | None | — | IMPLEMENTED — `entity-audit`. Single-page half (missing/empty/conflicting/off-domain canonical, `www.`-aware since cycle 15) plus a sitemap-scoped crawl-wide half added cycle 18: `--sitemap-file` mode detects trailing-slash/`www.`/scheme forks directly from the sitemap's own declared URL list (no crawl needed — reuses PER-06's fetch). Live-validated on 4 real sitemaps (61 to 7071 URLs), all clean, no false positives |
| ENT-05 | Brand-name entity collision | Same/similar name on other entities with different locations or ratings → attribute-merging hallucinations | GEO | Exact | ~ | IMPLEMENTED — `entity-audit`, off-site mode (`--offsite-url`/`--brand-name`), agent-judged, cycle 19. Script fetches agent-supplied off-site URLs (robots.txt-checked per host) and extracts a snippet around every brand-name mention; agent judges same-entity vs. genuine collision against `references/entity-judgement-rubric.md` §ENT-05. Does not search the web itself — candidate URLs are the calling agent's own search step. FP risk stays **very high** by design of the judgement, not the extraction — see Detail below |
| ENT-06 | Lookalike domain impersonation | Confusable non-official domains cannibalising the real entity's citations | — | None | ✘ | IMPLEMENTED — `entity-audit`, off-site mode, agent-judged, cycle 19. Domain-string similarity (stdlib `difflib`, ≥0.75 threshold) against the audited site's own domain is scriptable and deterministic; audited site's own domain and subdomains excluded (live-found: `meta.discourse.org` scored 0.839 against `discourse.org` and would have false-positived as a lookalike before the subdomain guard). Agent judges the fetched page's content for plausible impersonation intent against §ENT-06 |
| ENT-07 | Cross-domain service attribution | Marketing on `.com`, support on a third-party subdomain, with nothing linking them as one entity | — | None | ✘ | IMPLEMENTED — `entity-audit`, `--sample-file` mode, cycle 23 (B2). Unblocked by Phase 1's page sampler (`shared/page_sample.py`) and the vendored Public Suffix List (`shared/public_suffix.py`). Fetches every on-site URL in an orchestrator-supplied page sample, extracts outbound links, and narrows to third-party domains recurring across ≥2 sampled pages whose URL looks service-related (support/help/docs/status) and whose hostname carries the site's own brand token — the dominant-false-positive guard against a popular but genuinely unrelated third-party tool (a payment processor, a generic statuspage.io host) merely being linked often. For each survivor, fetches that domain's own homepage once (robots.txt-checked) and flags it only if its structured data carries no `sameAs`/`url` reference back to the audited site. Entirely script-decided, no agent judgement |
| ENT-08 | NAP consistency | Name/address/phone disagreeing across the site's own pages and its markup | — | None | ✘ | IMPLEMENTED (cycle 23, Phase 4 B3) — address ("A") half only, `entity-audit` `--sample-file` mode: extracts one US-style street address per sampled page, clusters via `shared/fuzzy_match.single_linkage_clusters`, flags 2+ mutually dissimilar clusters, gated silent behind an explicit multiple-location-language check (the dominant false positive). Phone-half still overlaps REN-10 and is not duplicated. Capped Medium severity, within-sample-only, same discipline as CIT-08/EN-04 |
| ENT-09 | Specialty/taxonomy consistency | A page's assigned category tag contradicting its own body text | — | None | ✘ | IMPLEMENTED — `entity-audit`, agent-judged. Single-page, no off-site/cross-page reasoning needed (an earlier phase-4 note incorrectly grouped it with ENT-07/08, corrected in cycle 9). Script extracts a declared category/breadcrumb label + zero-keyword-overlap candidates only; agent judges against references/entity-judgement-rubric.md |
| ENT-10 | Same-listing address drift | Unstable address text across snapshots of one listing → trust demotion | — | None | ✘ | **DEFERRED** — requires historical snapshots we cannot obtain in a single <5 min read-only audit. Documented as a limitation, not faked |
| ENT-11 | JSON-LD graph referential integrity | The structured-data graph as a graph, not isolated nodes — a `@id` reference pointing at nothing on the page; a cross-page `@id` reference the site's own sitemap can confirm is broken; an identity-bearing node (Organization/Person/Product) no other node ever references | — (built locally) | None | — | IMPLEMENTED — `entity-audit`, cycle 22. Three findings: `dangling-id-reference` (an `@id` cited within the page's own graph that resolves to nothing in it), `cross-page-id-reference` (an `@id` reference to a URL confirmed absent from an agent-supplied sitemap), `orphan-identity-node` (an identity node present but never referenced by anything else in the graph). Caller-side overlap control against ENT-01: only invoked when `nodes` is non-empty, so a page ENT-01 already flags `no-structured-data`/`malformed-json-ld` never also fires ENT-11 for the trivial reason that an empty/unparseable graph has no edges to check. See `docs/phase-4-completion-22.md` |
| ENT-12 | JSON-LD entity-graph fragmentation | A structured-data graph that is entirely valid (every `@id` reference resolves) but still splits into ≥2 disconnected clusters of 2+ nodes each, instead of one cohesive graph — distinct from ENT-11, which catches broken references, not a poorly-connected-but-valid one | GEO (research3.md A6) | Adjacent | ✔ | IMPLEMENTED — `entity-audit`, cycle 23. Built on new `shared/graph_metrics.py` (union-find connected components + degree + power-iteration PageRank — replaces `networkx`, rejected in Part 1 of `docs/02-project-plan.md` for a hard Python-version floor and a 505ms import cost). Gated to ≥5 entities on the page. Deliberately does not also restate ENT-11's `orphan-identity-node` finding — same underlying signal, already covered at a tighter node-type-specific gate; a stray singleton (a lone BreadcrumbList/ImageObject) never counts toward the ≥2-substantial-cluster threshold, which is the dominant false positive a whole-graph check like this risks |

**Detail.** Deps: an HTML/JSON-LD parser; optional `advertools` for crawl-wide
canonical maps. ENT-05/06 needed an off-site lookup — **scope decision, open since
cycle 9, held cycle 17 through cycle 18: stay strictly on-domain, do not build
either capability — reversed cycle 19.** The cycle-17 reasoning rejected two paths:
a bundled script calling a third-party search API (correctly rejected — M5,
`docs/competition-requirements.md`), and an agent-executed search (declined as not
worth the complexity). What cycle 17 did **not** have on the table is what hard
constraint 2 (confirmed with judges, cycle 19) now explicitly permits: a bundled
script issuing its own direct, bounded HTTP queries against named public sites
(Reddit, Quora, forums, review sites), robots.txt-respecting, with no third-party
scoring/classification API in the loop — fetch-raw-and-judge-ourselves, not
outsource-the-verdict. That is neither of the two paths cycle 17 weighed, so the
cycle-17 rejection doesn't reach it. ENT-05/06 shipped cycle 19, off-site mode
in `entity-audit`, agent-judged; their own FP-risk caveat is unchanged and still
real — "similar name" is a fuzzy predicate, and a wrong impersonation accusation
is a serious false positive — so query scope is bounded tightly (agent-supplied
candidate URLs only, exact brand string match, not fuzzy expansion) and every
verdict is the agent's, never the script's. `ENT-10` and `CIT-11` remain
`DEFERRED` for their own, separate reasons (historical snapshots;
provenance-tracing scope) untouched by this reversal. See
docs/phase-4-completion-20.md.
ENT-09 turned out **not** to need this decision at all — its own wording ("contradicting
its own body text") is same-page, and it shipped agent-judged in cycle 9 for a different
reason: keyword-zero-overlap cannot distinguish a real mismatch from an unseen synonym,
which is a semantic call, not an off-site or cross-page one.

---

## Cluster D — Retrieval readiness (Gate 3, sparse + dense)

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| RET-01 | BM25 exact-match retention | Product SKUs, model numbers, statute names, technical terms lost during extraction → the page fails sparse retrieval before any LLM sees it | BM25 | Exact | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 11), script-decided. Narrowed to JSON-LD `Product.sku`/`mpn`/`gtin*` values missing from extracted visible text; model numbers/statute names in free text excluded (needs a free-text heuristic, real FP risk, deferred). See docs/phase-4-completion-11.md |
| RET-02 | Dense/semantic coverage & synonym variation | Content covering one phrasing only; no synonym or conversational-query breadth | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 14), agent-judged. Script extracts the page's dominant repeated phrase + example sentences into `agent_judgement_required`; agent judges against `references/retrieval-judgement-rubric.md` §RET-02. See docs/phase-4-completion-14.md |
| RET-03 | Query-intent coverage | No content addressing the obvious question forms for the brand's own category | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 14), agent-judged. Script extracts the page's stated topic + existing Q&A signals; agent brainstorms category-obvious questions from its own knowledge and judges coverage. See docs/phase-4-completion-14.md |
| RET-04 | Keyword stuffing | Unnatural n-gram density that generative engines actively demote | ADV | Exact | ~ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 12), script-decided. 4-word n-gram, ≥5 occurrences, ≥8% prose density; table/dl/ul/ol/select regions excluded from the corpus at extraction. See docs/phase-4-completion-12.md |
| RET-05 | Domain-specific terminology balance | All-jargon or all-layman text; needs both to serve technical retrieval *and* simplified generation | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 14), agent-judged. Script extracts jargon-density stats (long-word ratio, acronym count) + opening/middle/closing sample sentences; agent judges skew. See docs/phase-4-completion-14.md |
| RET-06 | Chunk quality / atomic paragraphs | Paragraphs blending several ideas → muddied embeddings, low relevance per chunk | — (was seoscoreapi) | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 14), agent-judged. Script flags paragraphs ≥80 words/≥5 sentences as candidates; agent judges genuine idea-blending. Live-validated clean on docs.python.org (10 long-but-atomic candidates, correctly no finding). See docs/phase-4-completion-14.md |
| RET-07 | Retrieval-oriented structure | Absent headings, Q&A framing, or definition blocks that make chunks self-contained | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (cycle 13), script-decided. Narrowed to the structural half only: a substantial page (≥300 words) with zero of the three named aids present at all; whether existing chunks are semantically self-contained is out of scope (judgement call). See docs/phase-4-completion-13.md |
| RET-08 | Heading hierarchy integrity | Skipped or decorative heading levels destroying document structure | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit` (new skill, cycle 10), script-decided. Scoped to skipped heading levels and empty headings only; "decorative" heading levels excluded (needs render/CSS inspection, gate 2, not built). See docs/phase-4-completion-10.md |
| RET-09 | Positional fact interment | Load-bearing figures (price, spec, headline statistic) that exist only in a long document's middle band and are never restated at either margin — LLMs systematically under-attend to mid-context information (Liu et al., "Lost in the Middle", TACL 2024; Chroma's 2025 "Context Rot" study) | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit`, cycle 22, script-decided. Gate: 800+ words. Extracts up to 20 distinct load-bearing values (currency, unit-bearing numbers, dates, dimension patterns); fires when 3+ distinct values, and 40%+ of all extracted values, sit only at normalized position 0.25-0.75 with no restatement in the title, any h1/h2, the opening/closing 15% of prose, a table cell, a definition, or JSON-LD. Three required FP guards: an 800-word floor, a chronology-page guard (mostly-ascending years → silent), and a summary-block-heading guard. `confidence: medium` — the mechanism is probabilistic, not asserted as certain. See `docs/phase-4-completion-22.md` |
| RET-10 | Chunk self-containment | A content block opening with an unresolved reference ("It cut onboarding time by 40%") that never names its own subject inside the block — the unit a RAG pipeline actually retrieves, not the page as authored | — | None | ✘ | IMPLEMENTED — `retrieval-readiness-audit`, cycle 22, script-decided, strictly after RET-09 (reuses `shared/text_spans.extract_blocks`). Judges every block of 25+ words: fires once per page when 25%+ of judged blocks (across 4+) open with an unresolved personal/possessive pronoun, a demonstrative not immediately followed by a proper-noun-like word, or a generic definite description ("the company"/"the team"), and never name their subject via a proper noun, a shared `<title>`/`<h1>` word, or a repeated heading term. Required exemption: self-referential deixis ("This guide explains...") never fires. `confidence` drops to `high` only when none of a page's context-dependent blocks have any heading anchor at all. See `docs/phase-4-completion-22.md` |

**Detail.** The matrix names `bm25s`/`rank_bm25` and `advertools` as RET-01/04's
resources, but cycle 10 rejects both as actual dependencies — the same disposition
every `seoscoreapi`/`crawl4ai`-flagged capability in this project has received:
`test_scripts_import_no_third_party_packages` holds project-wide with zero
exceptions across 14 cycles, and a pip dependency reintroduces the "may not be
available in the grader's sandbox" risk already rejected for rendering. RET-01
shipped cycle 11 narrowed to a presence/absence check against JSON-LD-declared
identifiers, no BM25 ranking math, no dependency. RET-04 shipped cycle 12 the
same way — a stdlib n-gram frequency count, no `advertools` dependency.
**No embedding model** — RET-02/03/05/06 shipped cycle 14 agent-judged
instead, per the matrix's own explicit instruction for RET-02/03: judged by
the host agent against `references/retrieval-judgement-rubric.md`, never by
a bundled vector model (weights are prohibited). Runtime: low, all local
text math. FP risk: medium
— RET-04's own risk note ("fires on legitimately repetitive pages — spec tables,
glossaries; exclude structured regions before counting") is applied directly at
extraction: `table`/`dl`/`ul`/`ol`/`select` regions are excluded from the corpus
before any n-gram is counted, live-confirmed silent on a chess glossary
(`<dl>`-heavy) and Python's regex docs (dense, naturally repetitive terminology).
RET-01's fixture pair (a SKU that survives extraction, one swallowed by a
`<script>`/JSON-LD block) shipped cycle 11; live-confirmed on lego.com's product
pages — the JSON-LD `sku` never appears outside `<script>`/`<style>` anywhere on
the page, independently verified script-stripped. RET-07 shipped cycle 13,
scoped to whether a substantial page has zero of its three named structural
aids at all; live-confirmed live positives on paulgraham.com's table-laid-out
essay pages and, unexpectedly, python.org/about/ (1445 words, zero heading
elements anywhere, independently confirmed with a plain `grep` outside the
skill's own code). RET-02/03/05/06 shipped cycle 14, all four agent-judged
via the same `agent_judgement_required` pattern proven six times already
elsewhere in this project; live validation also caught and fixed a
project-wide-relevant extraction bug (adjacent block-level tags producing
run-together words, 438 artifacts on gymshark.com before the fix) that
predated this cycle but had gone unnoticed until RET-02/05's word-level
statistics made it visible.

---

## Cluster E — Trust, authority & citability (Gate 3)

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| CIT-01 | Trust-signal authority | Missing bylines, thin author bios, absent About depth | GEO | Exact | ✔ | IMPLEMENTED — `citability-audit`, script-decided. (Corrected in cycle 10: this row was left NOT_STARTED after the skill shipped in cycle 5 — the matrix table itself was never updated, only `00-project-plan.md`'s narrative was.) See docs/phase-4-completion-5.md |
| CIT-02 | Explicit source attribution & footnote density | No formal attribution phrasing; no outbound links to authoritative sources | GEO | Exact | ~ | IMPLEMENTED — `citability-audit`, script-decided. See docs/phase-4-completion-5.md |
| CIT-03 | Citation precision | Claims not supported by the sources actually cited | — | None | ✘ | NOT_STARTED — `citability-audit`'s own Excludes: needs reading comprehension across a claim and its source, out of scope so far. Considered cycle 21, discarded: no scriptable low-FP slice identified |
| CIT-04 | Citation recall | Load-bearing claims carrying no source at all | — | None | ✘ | IMPLEMENTED — `citability-audit`, agent-judged. See docs/phase-4-completion-5.md |
| CIT-05 | Quotation density | No attributed quotes from named people — a measurable citability signal | — | None | ✘ | REJECTED — `citability-audit`'s own Excludes: attribution patterns vary too widely to script at this project's false-positive bar. Considered and dropped, not simply unstarted |
| CIT-06 | Statistics density / numeric verifiability | Vague superlatives ("fastest on the market") where a sourced number belongs | — | None | ✘ | IMPLEMENTED — `citability-audit`, script-decided. See docs/phase-4-completion-5.md |
| CIT-07 | Citation-position weighting | Citable facts buried late in the DOM; models truncate and over-weight early tokens | — | None | ✘ | IMPLEMENTED — `citability-audit`, cycle 18. Reuses CIT-02's own external-link definition (`_is_external_link`, extracted as a shared helper); fires only when *every* outbound citation falls in the last 20% of a substantial (≥500-word) page — CIT-02's own precondition (a page must have an external citation at all) still gates this. Live-validated on 3 real pages (Wikipedia, Vercel docs, a bakery about page), no false positives; no live true-positive found yet, unit-tested against realistic buried/non-buried HTML shapes instead |
| CIT-08 | Hub/authority link-graph structure | Navigational hubs and fact-dense authority pages not separated; trust flows badly | ADV | Exact | ✘ | IMPLEMENTED — `citability-audit`, `--sample-file` mode, cycle 23 (B1+B8). Unblocked by Phase 1's page sampler bounding a link graph, `shared/links.py` extraction, and `shared/graph_metrics.pagerank` (the same power-iteration PageRank ENT-12/A6 already put to use, now over an internal link graph instead of a JSON-LD entity graph). Flags a fact-dense sampled page (500+ words, CIT-02's own threshold) whose PageRank is under half the sample's mean while a non-fact-dense page holds the sample's single highest PageRank — requires 5+ sampled pages. Adopts the minority objection's discipline alongside the majority view, identically to EN-04's orphan-within-sample half: capped at Medium severity, states its own sample size in evidence, never claims site-wide scope. Entirely script-decided |
| CIT-09 | Comparison-content gap | No first-party "X vs Y" content → the assistant sources the comparison from competitors | GEO | Exact | ~ | IMPLEMENTED (cycle 23, Phase 4 B5) — `citability-audit` `--sample-file` mode, sharing CIT-08's fetch pass: zero-crawl lexical scan of each sampled page's URL slug and `<title>` for a comparison shape (vs/versus/alternative-to/compared-to). Fires only on total absence across the sample; `track: "proactive"`, lowest severity — absence proves nothing, so this stays a suggestion, never a defect. Within-sample-only, same discipline as CIT-08 |
| CIT-10 | Self-interested comparison disclosure | Comparative pages presented as neutral with no disclosure | — | None | ✘ | REJECTED — `citability-audit`'s own Excludes: would fire on nearly every vendor-authored comparison page, since disclosure language is rare regardless of legitimacy — not a detector |
| CIT-11 | Synthesised-hearsay sourcing | Forum/social opinion laundered into declarative claims | — | None | ✘ | **DEFERRED** — categorical off-site block lifted cycle 19 (hard constraint 2), but the remaining blocker is real: this needs matching the page's own declarative claim text against forum/social opinion text for provenance, a fuzzy-matching problem, not a bounded presence query like ENT-05/CIT-13. Stays deferred on complexity/FP grounds, not policy |
| CIT-12 | Abstractiveness vs faithfulness balance | Dense but unsummarisable, or fluent but factless | — | None | ✘ | NOT_STARTED — considered cycle 21, discarded: reading-comprehension judgement, no scriptable low-FP slice identified |
| CIT-13 | Off-site corroboration | Key claims stated nowhere but the brand's own site (appendix D: single-source claims are fragile) | — | None | ✘ | IMPLEMENTED — `citability-audit`, agent-judged, cycle 19. Reuses CIT-04's own claim extraction as its candidate pool; a claim's own significant number is checked (deterministic numeric survival, same shape as RET-01/REN-04) against every agent-supplied `--offsite-url` page's text — unmatched numbers become `agent_judgement_required` candidates, never an asserted defect. Does not search the web itself |

**Detail.** Deps: text analysis only, except CIT-13 (bounded off-site query — direct
HTTP to named public sites under hard constraint 2, robots.txt-respecting, no
third-party search/scoring API). CIT-03/04/12 are **agent-judged** against a `references/` rubric — they are exactly the
capabilities the research wanted a local LLM for. Runtime: low, except CIT-13.
FP risk: **high** for CIT-03 (judging whether a source supports a claim is genuinely
hard). Mitigation: only assess claims that are explicitly cited *and* explicitly numeric;
everything else returns `unknown`. Prefer reporting *absence* (CIT-04, easy, reliable)
over *incorrectness* (CIT-03, hard, noisy).

---

## Cluster F — Content anti-patterns (Gate 3)

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| CQ-01 | Answer extractability | No concise 2–4 sentence canonical answer near the top; answer buried under marketing | — (was seoscoreapi) | None | ~ | IMPLEMENTED — `content-quality-audit`, agent-judged. Script extracts H1 + document-start opening-block + marketing-phrase hits only; no main-content boundary detection (gate 2, not built), so a nav-heavy opening is a documented blind spot, not a false positive — see references/content-judgement-rubric.md §CQ-01 |
| CQ-02 | Non-answer template detection | Boilerplate hedging ("while there is no clear answer…") standing in for a fact | — | None | ✘ | IMPLEMENTED — `content-quality-audit`, agent-judged. Script extracts hedge-phrase candidates + preceding sentence only; agent judges against references/content-judgement-rubric.md |
| CQ-03 | Template leakage | Unrendered tokens (`{{city_name}}`), duplicated entity lists from programmatic generation | — | None | ✘ | IMPLEMENTED — `content-quality-audit`. Scoped to Mustache/Liquid/ERB syntax outside code blocks; programmatic-list duplication not built (needs multi-page context). See docs/phase-4-completion-2.md |
| CQ-04 | Granularity mismatch | Stated precision coarser than the query needs ("Large" where mm are required) | — | None | ✘ | IMPLEMENTED — `content-quality-audit`, agent-judged. Extraction scoped to vague-magnitude-word + spec-context-word co-occurrence with no number |
| CQ-05 | Relative-date anchors | "Last year", "next month" with no absolute date → factually corrupt once embedded | — | None | ✘ | IMPLEMENTED — `content-quality-audit`. Requires a claim verb in the same sentence as the relative phrase, to keep precision high |
| CQ-06 | Date-context/price invariance | Identical price or metric reused across temporal or regional variants that should differ | — | None | ✘ | NOT_STARTED — considered cycle 21, discarded: needs comparing the same fact across page variants, no crawl infra |
| CQ-07 | Scope-ambiguous numeric claims | One metric given two values in one document with no scope qualifier | — | None | ✘ | IMPLEMENTED — `content-quality-audit`. Scoped to colon-labeled key:value pairs (spec-sheet style), not general prose — a fully general version needs POS tagging this project does not have |
| CQ-08 | Computed-stat integrity | Summary statistics contradicting the page's own tables (claims 4.8 avg; listed reviews average 3.2) | — | None | ✘ | IMPLEMENTED — `content-quality-audit`. Excludes weighted/filtered averages per this row's own note |
| CQ-09 | Marketing/procedure interleaving | Promotional bullets inside how-to steps → models discard the whole procedure | — | None | ✘ | IMPLEMENTED — `content-quality-audit`, agent-judged. Extraction scoped to numbered step-line markers, text-based (no DOM li/ol structure retained) |
| CQ-10 | Temporal freshness & contradiction | Stale "updated" dates; page-to-page contradictions on the same fact | — | None | ✘ | IMPLEMENTED (cycle 23, Phase 4 B4) — cross-page fact-collision half only, `content-quality-audit` `--sample-file` mode, agent-judged: within CQ-13's own same-template strata, extracts "Label: value" lines with a typed value (price/date/count) and narrows to a label stated on 3+ pages with 2+ distinct values; agent judges genuine collision vs. expected per-item variation (the dominant false positive) against references/content-judgement-rubric.md §CQ-10. Stale "updated"-date freshness half not built — that is a single-page staleness signal already distinct from this cross-page comparison and was not part of this cycle's scope |
| CQ-11 | Fluency / readability | Grammatical noise raising parse friction | — (was seoscoreapi) | None | ✘ | IMPLEMENTED — `content-quality-audit`. Flesch Reading Ease, "very difficult" band (<30) only, 300-word minimum sample, confidence capped at medium — the formula's known jargon-vs-difficulty limitation, documented, not solved |
| CQ-13 | Near-duplicate / template dilution | Several pages under one URL template substantively repeat each other's content, diluting citation authority across near-identical pages | — (was `datasketch`) | None | ✘ | IMPLEMENTED — `content-quality-audit`, `--sample-file` mode, cycle 23 (B6). Previously held DEFERRED (see "Deferred, 4" below) as "methodologically broken against this project's own agent-chosen, variety-biased page sample" — unblocked by Phase 1's template-stratified sampler (`shared/page_sample.py`), which exists specifically so near-identical pages land in the same stratum. Strips lines repeating verbatim across ≥half the sample (chrome), groups by URL template, and runs `shared/shingles.near_duplicate_groups` (k-shingle Jaccard, replacing `datasketch`, rejected in `docs/02-project-plan.md` Part 1) within each stratum only |
| CQ-12 | Signal-to-filler ratio | Substance drowning in low-value filler (appendix F, generalised to pages) | — | None | ✘ | IMPLEMENTED — `content-quality-audit`, agent-judged. Script reports a page-level filler-phrase count/word-count/examples triple only, no ratio computed; agent judges proportion |

**Detail.** Deps: none beyond extracted text. CQ-03, CQ-05, CQ-07, CQ-08 are
**deterministic and scriptable** — regex/arithmetic, near-zero FP, high evidence quality.
**These are the highest value-per-effort detectors in the whole project** and should be
front-loaded in Phase 4. CQ-11 is also scriptable (a published formula, Flesch Reading
Ease), gated to a strict threshold and 300-word minimum sample to keep its known
jargon-vs-difficulty false-positive class rare. CQ-01, CQ-02, CQ-04, CQ-09, CQ-12 are
agent-judged. Runtime: low. FP risk: low for the scriptable five (CQ-08 must exclude
weighted/filtered averages; CQ-11 capped at `confidence: medium`, never `high`); medium
for the judged ones. CQ-01 in particular has no main-content boundary detection to draw
on (gate 2, not built) — its extraction is honestly document-start, and the false-
positive guard is procedural (the agent is instructed to disregard a nav-dominated
opening) rather than in the pattern match itself.

---

## Cluster G — On-site engagement (authored; not in the research)

*Answers "why visitors who arrive don't stay" — half the rubric. See research-summary §3.*

| ID | Capability | Detects | Resource | Match | Presumed | Status |
|---|---|---|---|---|---|---|
| EN-01 | Visitor orientation | Landing page never states plainly what this is, who it's for, and what to do next | — / SQ-AX | None | ✘ | IMPLEMENTED — `engagement-audit`, agent-judged. Script extracts H1/CTA/first-words signals only; agent judges against references/engagement-judgement-rubric.md's calibration examples |
| EN-02 | Context retention on arrival | Deep-link arrivals lose their intent — no breadcrumbs, no in-context next step, interstitials that reset to the homepage | — | None | ✘ | NOT_STARTED — considered cycle 21, discarded: needs multi-page navigation context, no crawl infra |
| EN-03 | Conversion-path friction | Step count to the primary action, forced account creation, hidden costs revealed late | — / SQ-AX | None | ✘ | PARTIALLY_COVERED — `engagement-audit`, agent-judged, covers forced-account-creation and undisclosed-fees signals; step-count needs multi-page navigation this project does not build, explicitly excluded rather than guessed |
| EN-04 | Dead-end pages | Fact-dense pages offering no next action; orphaned pages with no inbound internal links | ADV | Adjacent | ✘ | IMPLEMENTED — `engagement-audit`, `--sample-file` mode, cycle 23 (B1+B8). Script-decided, two sub-checks with deliberately different evidentiary weight: dead end (B8a) is a direct fact about the fetched page — zero internal outbound links and no CTA — stated plainly at high confidence; orphan-within-sample (B1) is a structurally biased estimate over the bounded, template-stratified sample (a page reachable only via pagination or a nav path the sampler never selected is invisible to this check), so it is capped at Medium severity and states its own sample size in its evidence, never claiming site-wide scope — the minority-objection discipline adopted alongside the majority view per `docs/02-project-plan.md` Phase 4. The homepage is excluded from the orphan check (expected to have few/no inbound internal links). Unblocked by the same Phase 1 sampler and cycle-23 `shared/links.py` anchor extraction as ENT-07/C1 |
| EN-05 | Mobile usability | Viewport config, tap-target sizing, font legibility, horizontal overflow | — | None | ✘ | IMPLEMENTED — `engagement-audit`, cycle 21, script-decided. Narrowed to viewport config + inline fixed-width overflow only: tap-target sizing and font legibility need resolved CSS layout (real pixel geometry), which needs either computed rendering (banned) or a full CSS cascade resolver (out of scope, no proven low-FP path) — both excluded, stated. Live-confirmed missing-viewport positive on info.cern.ch |
| EN-06 | Interstitial & consent-wall friction | Cookie/consent/newsletter walls blocking content — hurts humans *and* crawlers; a dual-gate finding | — | None | ✘ | IMPLEMENTED — `engagement-audit`. Windowed heuristic (modal signal + wall language + no dismiss option), not true DOM scoping; the crawler-facing half (content absent from raw HTML behind the wall) belongs to a render/extraction skill, not yet built |
| EN-07 | Perceived-performance friction | Static proxies for load pain: payload weight, render-blocking resources, unsized images causing layout shift | — | None | ✘ | IMPLEMENTED — `engagement-audit`, cycle 21, script-decided. Payload weight is the fetched HTML document's own byte size only, not full page weight (this skill never fetches linked CSS/JS/image assets) — stated narrowing. Live-confirmed on vercel.com/docs.python.org/chewy.com (render-blocking head-resource counts of 5, 14, 24 respectively) |
| EN-08 | On-site findability | No site search; navigation depth burying key pages; no clear path from any page to the primary content | — | None | ✘ | PARTIALLY_COVERED — `engagement-audit`, `--sample-file` mode, cycle 23 (C1, the link-information-scent slice only). Grounds the slice in Information Foraging Theory (Pirolli & Card 1999): an internal link's anchor text scored against its target page's own H1 via `fuzzy_match.token_sort_ratio`, narrowed to below-threshold pairs where the target is itself in the sample; common navigational chrome (Home/Contact/Learn more/…) excluded before scoring as the dominant false positive. Agent-judged against the rubric, never auto-asserted. Site-search presence and navigation-depth burial — the matrix's fuller description — still need crawl-wide context this project does not have |
| EN-09 | Autonomous-agent usability | Unlabelled form fields, no ARIA, no machine-readable contact/booking path — the bridge between the two rubric halves | GEO (research3.md A2/A8/C2) | Adjacent | ✔ | IMPLEMENTED — `engagement-audit`. Unlabelled form fields (label/aria-label/aria-labelledby) plus, added cycle 23: a non-trivial form (2+ labelable fields) with no schema.org `potentialAction` in the page's JSON-LD and no WebMCP signal (`navigator.modelContext.registerTool`, or a `toolname`/`data-toolname` form attribute) — reported as a proactive suggestion, not a defect, since both conventions have near-zero adoption today. Page-level, not matched to a specific form's action URL — see the skill's own SKILL.md Excludes for why |
| EN-10 | Trust & transparency for the human | Pricing hidden, contact hard to find, no proof (reviews, cases, credentials) at the decision point | — | None | ✘ | NOT_STARTED — considered cycle 21, discarded: substantially overlaps CIT-01/ENT-02 already implemented |
| EN-11 | Content-to-action coherence | The page answers the question but the CTA is unrelated to the intent that brought the visitor | — | None | ✘ | IMPLEMENTED — `engagement-audit`, `--sample-file` mode, cycle 23 (C1). Same Information Foraging Theory grounding as the EN-08 slice: a page's own primary (first, most prominent) CTA text scored via `fuzzy_match.token_sort_ratio` against that page's own H1; below-threshold pairs go to the agent, capped at Medium severity, since a generic/brand-voice CTA ("Get Started") is common and not always a defect. Unblocked by the same Phase 1 sampler and cycle-23 `shared/links.py` anchor-text extraction as the EN-08 slice |

**Detail.** Deps: static HTML only for EN-05/EN-07 — no linked-stylesheet or other
asset fetch, no rendered DOM (hard constraint 1). EN-05 is scoped to viewport meta
and inline `style` attributes (fixed-width overflow); EN-07 is scoped to the fetched
HTML document's own byte size and render-blocking head-resource *references* (not
their fetched weight) plus unsized `<img>` tags as a CLS proxy. Both are approximated
from markup alone, not measured pixel geometry or actual linked-asset sizes;
documented as a static proxy, not a true rendered measurement. Security: never submit
forms; never traverse checkout; inspect markup only. Runtime: low, static fetches only.
FP risk:
medium — EN-01/EN-11 are judgement calls. Bound them: judge one representative page per
template, quote the exact text (or its absence) as evidence, and never fail a page for
lacking a CTA when it plainly isn't a conversion page. Tests: fixture pairs of oriented
vs disoriented landing pages, and a checkout with 3 steps vs 8 with late fees.

---

## Cluster H — Infrastructure (not audit checks; the machinery)

| ID | Capability | Purpose | Status |
|---|---|---|---|
| INF-01 | Target acquisition & scoping | URL → domain, template discovery, page sampling plan | IMPLEMENTED — `shared/page_sample.py` (D1, cycle 23): template-stratified sitemap sampling, replacing the orchestrator's prior interest-biased prose instruction; CLI wrapper `skills/audit-orchestrator/scripts/sample_pages.py` |
| INF-02 | Fetch layer | Robots-respecting, rate-limited, cached, single-fetch-many-consumers | PARTIALLY_COVERED — `shared/page_fetch.py` (D2, cycle 23) consolidates six duplicate fetch implementations into one SSRF-guarded, gzip/deflate-decoding, in-process-cached module (`fetch_page`/`fetch_page_html`/`fetch_text`); no rate-limiting yet |
| INF-03 | Render layer | Headless render of a sampled subset; graceful degradation when unavailable | REJECTED — hard constraint 1 (no headless browsers, cycle 19). Permanently excluded, not just deprioritized; Cluster B rewritten to not need this layer at all |
| INF-04 | Page bundle artifact | The shared object every skill consumes: raw HTML, extracted text, JSON-LD, embedded hydration-state JSON, headers, links | PARTIALLY_COVERED — `shared/page_fetch.py`'s `PageBundle` (D2, cycle 23) carries raw/decoded HTML, headers and final URL with an in-process one-fetch cache; extracted-text/JSON-LD/link fields not yet folded into the bundle itself — "rendered DOM" dropped from the bundle's own definition, cycle 19; superseded by hydration-state JSON per Cluster B |
| INF-05 | Normalised finding contract | Internal superset schema that serialises down to the required report shape | IMPLEMENTED — `shared/finding_contract.py` |
| INF-06 | Severity model | Gate-based: gate-1 failures are veto items; downstream findings suppressed when an upstream gate fails | PARTIALLY_COVERED — `gate` field carried and severities derived per gate; suppression not implementable until a second gate exists |
| INF-07 | Confidence model | Evidence-strength scoring; `unknown` is a first-class state | PARTIALLY_COVERED — typed `unknown` and per-finding `confidence` implemented; no evidence-strength scoring yet |
| INF-08 | Deduplication & aggregation | Related symptoms from multiple skills merged into one finding with multiple evidence sources | NOT_STARTED — checked twice, not speculative: the orchestrator validation pass and its second-round follow-up (`docs/phase-4-completion-15.md`, `-16.md`) read four real composed reports for cross-skill redundancy across four sites and found none; deferred until a real case appears |
| INF-09 | Proactive-suggestion track | Recommendations where no defect was found — separately required by the rubric | IMPLEMENTED — `track` field; first user is PER-04 |
| INF-10 | Budget & timeout governor | Coverage modes; per-stage time caps; degrade to `unknown` rather than overrun 5 minutes | PARTIALLY_COVERED — `shared/budget.py` (D4, cycle 23): `StageBudget` monotonic-clock cap, `unreached_capability_unknowns` (typed `UnknownCheck` per capability cut off by a cap), `coverage_manifest` attachable via `finding_contract.build_report`'s optional `coverage` param. Not yet consumed by any existing single-page skill; built as the precondition Phase 3/4's multi-page checks (e.g. B6 near-duplicate detection's ~450 pairwise comparisons) need to bound their own work |
| INF-11 | Prompt-injection defence | Page content is data, never instruction — enforced in every skill that reads a page | PARTIALLY_COVERED — stated in every SKILL.md; no page-body reading exists yet to enforce it against |

---

## Deferred / rejected

| ID | Disposition | Reason |
|---|---|---|
| ENT-10 | DEFERRED | Needs historical snapshots; impossible in a single read-only run. Report as a known limitation |
| CIT-11 | DEFERRED | Claim-vs-forum-opinion provenance matching is a fuzzy-matching complexity problem, not a policy block (hard constraint 2 lifted the categorical off-site rejection cycle 19; ENT-05/06/CIT-13 reversed, CIT-11 did not — see its own row) |
| — | REJECTED | All `seoscoreapi`-dependent implementations (external service rule, M5); capabilities retained, reimplemented locally |
| — | REJECTED | Local LLM classifiers (no model weights); replaced by agent-judged `references/` rubrics |
| — | REJECTED | `squirrelscan` / `firecrawl` / `brightdata` as dependencies (CLI, keys, cloud auth); taxonomy retained as prior art |
| Cluster B, INF-03 | REJECTED | `crawl4ai`/Playwright/any headless browser, including as an optional fallback — hard constraint 1, confirmed permanent cycle 19. Cluster B rewritten to static/hydration-state detection; INF-03 dropped entirely |

---

## Front-loading recommendation for Phase 4+

Ordered by *evidence quality × false-positive safety × rubric weight*, not by research order:

1. **PER-01…PER-08** — cheapest, highest severity, near-zero FP, and the veto gate the
   severity model depends on.
2. **CQ-03, CQ-05, CQ-07, CQ-08** — deterministic, scriptable, unimpeachable evidence.
3. **ENT-01…ENT-04** — the identity multiplier; well-supported by the baseline.
4. **EN-01, EN-03, EN-06, EN-09** — the engagement beachhead; without these the
   submission fails half the rubric no matter how good the discoverability half is.
5. **REN-04, REN-06, REN-07** — highest value in Cluster B under the static-only
   redefinition (JSON-LD-vs-text comparison, and two rows — REN-06/07 — that never
   actually needed a browser to begin with).
6. Everything else, in dependency order.

**Non-goal: implementing all 62.** The rubric rewards precision and composition, not
count. A frozen, tested 25 beats a shaky 62.
