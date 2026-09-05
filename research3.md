# Cycle 23 Research Backlog — Consolidated

Synthesized from three independent research passes. Overlapping candidates are merged into single entries;
where the sources disagreed on verdict, tier, or implementation choice, both views are presented and flagged
(⚠️ **Disagreement**). Legend: **[A]** new capability · **[B]** fresh angle on deferred/blocked item ·
**[C]** on-site engagement research · **[D]** infrastructure hardening.

---

## Area A — Genuinely New Capability Dimensions

### A1. Common Crawl / Training-Corpus Footprint Audit
**Detects:** Whether the site's pages appear in Common Crawl's recent index — a proxy for whether content
has ever reached the large-scale-crawl/training pipeline most LLM pretraining draws on. Distinct from
permission checks (robots.txt access ≠ actual capture).
**Method:** Query the public CDX Index Server (`index.commoncrawl.org`) with sitemap URLs; compute coverage
ratio and recency from raw returned rows (timestamp, status, digest) — no third-party scoring involved, so
this stays within "fetch raw, judge ourselves."
**Package:** None (stdlib HTTP + JSON).
**Risk:** Single external, rate-limited public service; must degrade to `unknown` on timeout/failure, never
hard-fail. Politeness: ~1 req/sec, single-threaded.
**Evidence:** e.g. "0 of 8 sampled product pages appear in the last 3 Common Crawl snapshots (5 months);
homepage last captured 14 months ago."
**False positives:** Non-appearance is evidence *toward*, not proof of, poor discoverability (CC crawls a
large but incomplete slice); new sites are legitimately absent; "absent from CC" ≠ "absent from any given
model's training data."
**Verdict:** All three sources agree this is a strong, previously-underrated candidate (reopened from an
earlier ambiguous rejection). Ranked #1 by two of three sources.
**Tier: A** · Complexity: Low · Innovation: 8–9 · Evidence: 6–9

---

### A2. Machine-Readable Action Availability (WebMCP + `potentialAction`)
**Detects:** Whether the site exposes its core actions (booking, ordering, search, contact) via a
machine-callable path — schema.org `potentialAction`/`ReserveAction`/`OrderAction` in JSON-LD, and/or the
emerging **WebMCP** standard (`navigator.modelContext.registerTool`, or declarative `toolname`/
`tooldescription` form attributes — a real, active W3C Web Machine Learning CG draft co-edited by Google/
Microsoft engineers, with a Chrome origin trial).
**Method:** (a) Parse existing JSON-LD for `potentialAction`/`EntryPoint`. (b) Static regex/text scan of
inline `<script>` and same-origin `.js` for WebMCP registration signatures or declarative form attributes —
no JS execution or browser needed. (c) Extends the already-partial EN-09 (unlabeled form fields).
**Package:** None (stdlib).
**Risk:** None technical. Under-detection if JS is loaded from an uncrawled CDN domain — scope to
same-origin only and note the limitation.
**Evidence:** e.g. "No `potentialAction` in JSON-LD and no WebMCP signature found — the site offers no
machine-callable path to its booking flow, only a human-oriented form."
**False positives:** Low for presence detection (literal string/structure match). Absence of the
early-stage WebMCP half should always report as a **proactive suggestion**, not a confirmed defect — it's
a draft spec, not yet mainstream.
**Verdict:** Unanimous across all three sources — directly closes the named EN-09 gap, cheap, standards-backed.
Ranked #1–2 by two of three sources.
**Tier: A** · Complexity: Low–Medium · Innovation: 8–9 · Evidence: 7–9

---

### A3. AI-Crawler Content-Parity Diff (Cloaking Detection)
**Detects:** Silent content substitution served specifically to named AI-crawler user agents (GPTBot,
ClaudeBot, PerplexityBot, etc.) vs. a standard browser UA — the AI-crawler analogue of classic SEO cloaking,
measured as a content diff rather than a block/allow event. Distinct from existing permission checks (those
check *if* crawlers are let in, not *what* they receive).
**Method:** Fetch a small page sample twice — once with a browser UA, once with 2–3 real AI-crawler UA
strings — from the same IP/session in immediate succession. Compare status code, byte-length delta, visible
text diff, and structured-data (JSON-LD) presence. Flag when the AI-crawler version is missing content
present in the browser version.
**Package:** None (stdlib HTTP, custom header). No browser needed — explicitly allowed as direct HTTP with
header spoofing, not browser automation.
**Risk:** None specific. Degrade to unknown per-page on fetch failure.
**Evidence:** e.g. "GPTBot receives 340 words; a browser receives 1,120 words on the same URL — the missing
780 words include the page's only JSON-LD Product block."
**False positives:** A/B testing, geo-IP/CDN edge personalization keyed off IP rather than UA — mitigated
by same-IP/session fetch pairing.
**Verdict:** Proposed by one source only; not covered by the other two. Genuinely novel axis (same
permission, different payload) with no overlap to existing checks.
**Tier: A** · Complexity: Low · Innovation: 8 · Evidence: 8

---

### A4. Intra-Page Bridge-Fact Fragmentation
**Detects:** A page's single most important fact requiring two separate, un-bridged statements to
reconstruct (e.g., "Founded in 2010" under one heading, "by Jane Doe" under another, with no sentence ever
combining them). The single-page analogue of the dominant "bridge entity" failure mode in multi-hop
retrieval research (HotpotQA-style; attributed to a majority of RAG retrieval errors in some failure-mode
analyses).
**Method:** Script identifies candidate fact-bearing sentence pairs in different headed sections sharing a
likely subject but minimal vocabulary overlap; hands the narrow candidate set to an LLM judge with a
written rubric ("do these combine into one load-bearing fact, and is that combined fact ever stated as one
sentence anywhere on the page?").
**Package:** None (stdlib for extraction; reuses existing agent-judge pattern).
**Risk:** None.
**False positives:** Over-triggering on legitimately separate facts — mitigated by rubric requiring same
specific claim, not mere proximity; scope to top 2–3 candidate pairs per page.
**Verdict:** Proposed by one source only. Research-backed inference (well-studied mechanism, novel
single-page adaptation).
**Tier: A** · Complexity: Medium · Innovation: 8 · Evidence: 7

---

### A5. RFC 9727 API Catalog Discovery
**Detects:** Absence, malformation, or wrong `Content-Type` of the `/.well-known/api-catalog` endpoint — a
2024 RFC-standardized, machine-readable index of a site's API surface (OpenAPI specs, Agent-to-Agent cards)
via `application/linkset+json`.
**Method:** Direct GET to the well-known path; validate Content-Type and parse for `anchor`/`service-desc`
links.
**Package:** None (stdlib).
**Risk:** None.
**Evidence:** Boolean presence/validity + count of exposed API endpoints.
**False positives:** Low — RFC specifies exact path/MIME; malformed responses are unambiguous defects.
**Verdict:** Proposed by one source only. No overlap with existing checks — a distinct, newly-published
discovery standard.
**Tier: A** · Complexity: Low · Innovation: 9 · Evidence: 10

---

### A6. JSON-LD Entity-Graph Fragmentation (Connected-Component / Cohesion Audit)
**Detects:** Structural fragmentation in the site's own JSON-LD entity graph — e.g. Organization, Products,
and Reviews forming ≥2 disconnected clusters instead of one cohesive graph, or a brand/Organization node
with degree ≤1. Distinct from existing referential-integrity checks (those catch broken `@id` references;
this catches a *valid but poorly-connected* graph).
**Method:** Parse already-extracted JSON-LD into a graph (nodes = entities by `@id`/type, edges = property
references); compute connected components and node degree. Flag ≥2 substantial components or a starved
brand node, scaled to entity count (only fire when ≥5 entities exist).
**Package:** `networkx` (PyPI, BSD-3, pure Python, no compiled extension) — **or** a stdlib union-find
implementation, which avoids the dependency entirely.
**Risk:** Low either way; if using networkx, degrade to "unknown" on import failure.
**Evidence:** e.g. "11 declared entities split into 3 disconnected components — no structural path from the
brand entity to its own products."
**False positives:** Small sites naturally have few/shallow entity graphs — threshold scales with entity
count.
**Verdict:** Proposed independently by two sources with matching mechanism, differing only on package
choice.
⚠️ **Disagreement:** One source recommends `networkx` as the implementation; another recommends stdlib
union-find specifically *to avoid* the dependency, since the algorithm is simple enough not to need it.
**Tier: A/B** (two sources rank Tier A; treat as A if networkx risk is deemed acceptable, B if avoided)
· Complexity: Low–Medium · Innovation: 7–8 · Evidence: 6–7

---

### A7. Reciprocal Rank Fusion (RRF) Context-Fragmentation / Compression-Survival Probes
**Detects:** Two related sub-checks: (a) text blocks that lose all entity-keyword context when
chunked for retrieval (causing them to score poorly on sparse/BM25 retrieval and drop out of RRF-fused
rankings even when semantically relevant); (b) whether a page's most load-bearing facts would survive a
simple position-and-salience content-compression pass (lead paragraph + headings + first sentence per
block). Distinct from existing chunk-self-containment and positional-burial checks — this measures keyword
survival under retrieval fusion / compression specifically.
**Method:** Simulate standard token-chunking (e.g. 512 tokens); compute term frequency of the primary
entity per chunk, flag zero-instance chunks. For the compression probe, apply a rule-based extractive
keep-set and check fact-string presence.
**Package:** None (stdlib).
**Risk:** None.
**False positives:** Low for (a); (b) is a speculative approximation of real compressors (which are
salience-weighted, not purely positional) — calibrate as Medium severity.
**Verdict:** Proposed by one source only (two related variants). Reasonable inference from established RAG
architecture but not directly studied in this form.
**Tier: A/B** · Complexity: Medium · Innovation: 9 (RRF half) / 7 (compression half) · Evidence: 10 / 5

---

### A8. WebMCP Declarative Form Accessibility (narrower variant of A2)
**Detects:** Specifically whether critical transactional forms (search, contact, subscription) carry
WebMCP declarative attributes or a `potentialAction` fallback — a form-level slice of A2, proposed
independently with a stronger DOM-level framing.
**Note:** Materially the same capability as A2; merge into A2's implementation, but retain the
form-vs-JSON-LD cross-reference check ("if no WebMCP attribute, check for a matching `potentialAction`
targeting the same endpoint") as an implementation detail worth keeping.
**Tier: A** (merged into A2)

---

### A9. Self-Referential Brand-Name Variant Fragmentation
**Detects:** A page (or bounded sample) referring to its own organization by multiple unlabeled string
variants ("Acme Corp," "Acme Corporation," "ACME, Inc.") without declaring the relationship via
`alternateName`/`legalName`. First-party fuzzy matching, distinct from adversarial off-site matching
(lookalike domains, hearsay matching) elsewhere in the backlog.
**Method:** Extract candidate name mentions near the known brand name; cluster with
`rapidfuzz.fuzz.token_sort_ratio`/`WRatio` (similarity 85–92, not 100); flag clusters with no declared
`alternateName`.
**Package:** `rapidfuzz` (PyPI, MIT, prebuilt wheels for all major platforms + documented pure-Python
fallback if compilation fails — the license-cleaner choice over GPL'd `python-Levenshtein`).
**Risk:** Low-medium (native extension, but degrades cleanly to exact-match-only if unavailable).
**False positives:** Legitimately distinct entities sharing a similar name (subsidiary vs. parent) —
require high threshold + shared context (same paragraph/contact block).
**Verdict:** Proposed by one source only.
**Tier: B** · Complexity: Low · Innovation: 6 · Evidence: 6

---

### A10. Freshness-Signal Triangulation (cross-layer)
**Detects:** RSS/Atom `lastBuildDate` vs. sitemap `lastmod` vs. JSON-LD `dateModified` vs. HTTP
`Last-Modified` header disagreeing about what changed and when — e.g. sitemap `lastmod` gamed weekly while
the feed and markup show no real change. The cross-*layer infrastructure* analogue of the existing
intra-page date-contradiction check.
**Method:** Parse RSS/Atom + sitemap + JSON-LD timestamps already fetched; flag inversions and stale-feed
gaps.
**Package:** None (stdlib XML parsing).
**Risk:** None.
**False positives:** Sites without a feed — gate to fire only when a feed exists and contradicts other
layers.
**Verdict:** Proposed by one source only.
**Tier: B** · Complexity: Medium · Innovation: 6 · Evidence: 7

---

### A11. OpenIE Triple-Extraction Yield — ❌ Reconsidered, Stays Blocked
**Detects (would have):** Open-information-extraction triples from page text.
**Verdict:** Unanimous across all three sources — every practical path (spaCy, Stanford CoreNLP, Stanza,
even classic NLTK taggers) requires a trained/statistical parser or tagger, which counts as pretrained
model weights under the hard constraint banning them, even after the general dependency-ban relaxation. No
rule-based path reaches usable accuracy on open web text.
**Tier: C — do not implement.**

---

## Area B — Fresh Angles on Deferred/Blocked Items

*Shared infrastructure assumption: a bounded, sitemap-scoped, template-stratified page sample (see D1)
underlies nearly every candidate below — it is the shared plumbing that makes bounded multi-page checks
tractable inside the runtime budget.*

### B1. Internal PageRank / Link-Authority Starvation
**Detects:** A page marked important by first-party signals (sitemap priority, breadcrumb depth) but
receiving near-zero internal inbound links from the rest of a bounded sample.
**Method:** Build a directed graph from sampled pages' internal links; compute in-degree/PageRank
(`networkx`) within the *bounded* subgraph only.
**Package:** `networkx` (verified pure-Python, BSD-3, no compile step).
⚠️ **Disagreement — this is the sharpest split across the three sources:**
- **Two sources rank this Tier A**, arguing that at N≈20–30 pages the computation is cheap, the finding
  can be honestly framed as "within our sampled page set" (not full-site authority), and this directly
  answers a previously-rejected candidate once the dependency ban lifted.
- **One source explicitly re-rejects it (Tier C) even after the dependency relaxation**, arguing the
  methodology itself is broken, not just previously blocked: PageRank on a depth-1, template-bounded
  partial graph isn't a degraded estimate of site-wide authority — it's a *systematically biased* one,
  since pages reachable only via pagination/faceted nav/deep category trees are structurally excluded, and
  their exclusion correlates with exactly the "starvation" the check claims to measure. That source
  recommends a sitemap-scoped sibling (B4 below) as the "honest version" instead.
**Recommendation if implemented:** Adopt confidence-capped framing (Medium, not High) and disclose sample
coverage explicitly in every finding, per the majority view; treat the minority objection as the reason to
never let this finding claim more than the sample supports.
**Tier: A (majority) / C (minority, methodology objection)** · Complexity: Medium · Innovation: 7–9 ·
Evidence: 6–10

---

### B2. Cross-Domain Service Attribution (ENT-07)
**Detects:** Marketing content on the primary domain and support/docs/help content on an unlinked
subdomain or separate registrable domain, with no `sameAs`/`Organization` markup declaring the relationship.
**Method:** Extract outbound links from the bounded sample; identify domains that recur (genuine service
relationship, not a one-off link) and look service-related (support/help/docs/status keywords); fetch each
such domain's homepage once and check for a `sameAs`/`Organization` bridge.
**Package:** `tldextract` (PyPI, BSD, pure Python, correctly parses public-suffix-aware registrable
domains) — **or** stdlib `urllib.parse` with a maintained note, to avoid the dependency.
**Risk:** `tldextract` fetches a live Public Suffix List on first use by default — must be pinned to
offline/bundled-snapshot mode to avoid a sandbox network failure.
⚠️ **Disagreement:** One source recommends the `tldextract` package; another recommends stdlib parsing
specifically to skip the dependency. Functionally equivalent outcome; pick based on risk tolerance for the
PSL-fetch behavior.
**False positives:** Many cross-domain links are irrelevant (social, payment, ads) — scope to
service-keyword subdomains only.
**Verdict:** Proposed independently by all three sources — strong convergence.
**Tier: B** · Complexity: Medium · Innovation: 6–8 · Evidence: 5–9

---

### B3. NAP Address Consistency (ENT-08, address half — phone half already shipped)
**Detects:** A business address disagreeing across a site's own pages (footer vs. Contact page vs. JSON-LD
`PostalAddress`).
**Method:** Extract candidate address strings (ZIP/postal-code + street-suffix heuristics) from the bounded
sample; normalize and cluster with `rapidfuzz` fuzzy matching; flag disagreeing clusters unless multi-location
language is present.
**Package:** `rapidfuzz` (see A9) — degrade to stdlib `difflib.SequenceMatcher` if unavailable (slower but
functionally identical at this small N).
**False positives:** Multi-location businesses — require explicit "multiple locations" language check
before flagging.
**Verdict:** Proposed independently by all three sources — strong convergence.
**Tier: B** · Complexity: Medium · Innovation: 6 · Evidence: 6–7

---

### B4. Cross-Page Fact Contradiction (CQ-10, cross-page half)
**Detects:** The same fact stated with contradictory values on two different pages of the same site (e.g.
warranty "2 years" on one page, "3 years" on another).
**Method:** Sample same-template page groups (via D1); extract typed facts (prices, dates, counts) near
matching labels; flag identical-label/different-value collisions via fuzzy label matching.
**Package:** `rapidfuzz` (or stdlib fallback).
**False positives:** Legitimate per-SKU differences misread as contradictions — mitigated by
template-grouping + high match threshold + agent-judge on survivors.
**Verdict:** Proposed independently by two sources; framed by a third as the sitemap-scoped "honest"
alternative to B1's link-based approach specifically because it needs no biased partial-graph assumption.
**Tier: A/B** (one source ranks Tier A for the honest, non-graph-based version specifically)
· Complexity: Medium–High · Innovation: 6 · Evidence: 6

---

### B5. Comparison-Content Gap (CIT-09)
**Detects:** Absence of first-party "X vs Y" / alternative / competitor-comparison content — a category of
query AI answer engines field heavily, ceded to third-party sites if absent.
**Method:** Zero-crawl lexical scan of sitemap URL slugs and titles for comparison-intent patterns ("vs,"
"versus," "alternative to," "compared to"); optionally cross-check against an agent-supplied competitor
list. Report only via the proactive-suggestion track — absence proves nothing definitively.
**Package:** None.
**Verdict:** Proposed independently by two sources; matching methodology.
**Tier: B** · Complexity: Low · Innovation: 5–6 · Evidence: 5

---

### B6. Cross-Page Near-Duplicate / Template Dilution — Methodology Fix
**Detects:** Near-duplicate/thin-template pages diluting a retrieval index — previously rejected not for a
technique reason but a sampling-bias reason: interest-biased page selection systematically hides the exact
clusters this check exists to find.
**Fix:** Template-stratified sampling (D1) guarantees near-identical pages co-land in the same stratum and
get co-sampled; then run shingle-Jaccard / MinHash-LSH similarity within strata.
**Grounding:** Peer-reviewed URL-clustering stratified-sampling method (*Frontiers of Information
Technology & Electronic Engineering*) and the W3C WAI-ERT accessibility sampling methodology independently
converge on the same fix.
**Package:** None required for small N (stdlib shingle-Jaccard); `datasketch` (MinHash/LSH) only relevant
at much larger N than this project's bounded samples require.
**False positives:** Legitimately templated variant pages (size/color SKUs) — exclude common template
chrome, compare only extracted main-content text.
**Verdict:** Unanimous across all three sources — this is the strongest "unblock via methodology, not
algorithm" case in the backlog, with a citable diagnosis and a citable fix.
**Tier: A** (once D1 exists) · Complexity: Medium · Innovation: 6 · Evidence: 7

---

### B7. Temporal Freshness Self-Contradiction (CQ-10, single-page half) — Reconsidered
**Detects:** A page claiming to be "updated"/"current" (visible date string or `dateModified`) while its
actual HTTP `Last-Modified` header shows the underlying bytes are stale relative to that claim.
**Method:** Compare visible "Last updated"/"As of" strings or JSON-LD `dateModified` against the HTTP
`Last-Modified` header; flag gaps beyond a threshold.
**Package:** None (stdlib header + regex) — needs no crawl/sample at all for this half.
**Risk:** `Last-Modified` reliability varies by CDN/framework (some always report request time) — treat as
Medium-confidence, cross-check `ETag` stability where available.
**Verdict:** Proposed by one source (matches CQ-10 as descoped-not-rejected, legitimate to revisit).
**Tier: A** (single-page half; cheap, immediate, no dependency) · Complexity: Low · Innovation: 6 ·
Evidence: 6

---

### B8. Hub-Authority Structure & Bounded Engagement Graph (dead-ends / nav depth)
**Detects:** Two related engagement-side structural gaps within a bounded sample: (a) pages with zero
internal outbound links and no CTA (dead ends); (b) key sitemap pages unreachable within shallow nav depth
from the homepage.
**Method:** Reuses bounded-sample link data (from B1/D1); depth-1 nav expansion for (b), no full crawl.
**Package:** None, or `networkx` if reusing B1's graph.
**False positives:** Intentionally link-free landing pages — flag only when no action element exists at
all.
**Verdict:** Proposed by two sources with converging methodology (one frames it jointly with CIT-08/CIT-09
hub/authority; another frames it as EN-04/EN-08).
**Tier: B** · Complexity: Medium · Innovation: 6 · Evidence: 6

---

### B9. Hearsay/Provenance Fuzzy-Match Slice (CIT-11) — Narrow, Low-Confidence
**Detects:** A first-party declarative claim that appears to paraphrase forum/social opinion laundered into
stated fact, for the narrow subset of claims carrying a specific numeric/named anchor that tends to survive
paraphrase.
**Method:** Restrict matching to claim sentences with a specific number/product name/proper noun; fuzzy-
match the windowed text around that anchor against off-site text obtained the same way other off-site
checks already do (agent-supplied URLs, direct fetch, robots.txt-respecting).
**Package:** `rapidfuzz`.
⚠️ **Disagreement:** One source frames this as a real but narrow Tier B candidate, shippable only as a
low-confidence proactive suggestion given high false-positive risk (common marketing phrases coincidentally
overlap). Another source investigated the same idea and concluded it should **stay Tier C** — arguing that
a fuzzy prefilter solves the matching problem but not the actual judgment problem (the target is inherently
semantic/paraphrastic, and candidate generation at real scale collides with the runtime budget).
**Tier: B (narrow, low-confidence) / C (per one source's re-investigation)** · Complexity: Medium-High ·
Innovation: 6–8 · Evidence: 4–7

---

### B10. Full-Form AI-Reachable Subgraph Orphan Detection — Stays Blocked
**Detects (would have):** Pages allowed and sitemap-listed but actually unreachable via any internal link
path, at full-site scope.
**Verdict:** Proposed by one source and rejected in the same pass: the full-crawl-scope version needs
inbound-link breadth beyond what any bounded sample can honestly approximate — same bias objection as B1's
minority view. The cheap 80% (sitemap ∩ robots-allowed) is already covered elsewhere.
**Tier: C — do not implement** (full form only; bounded partial version is B1/B8, with the caveats noted
above).

---

### B11. Image-of-Text Facts via OCR (REN-09) — ❌ Reconsidered, Stays Blocked
**Verdict:** Unanimous across all three sources. Doubly blocked, confirmed independently of the general
dependency relaxation: (1) `pytesseract` is only a wrapper — it requires the separate `tesseract-ocr` system
binary, which is outside the Python/Node package ecosystem entirely and won't be present in a locked
sandbox; (2) the actively-maintained Tesseract engine (v4+) is itself LSTM-based and requires downloading
per-language `.traineddata` files — these are pretrained model weights in every meaningful sense, and remain
categorically blocked regardless of the general package-dependency relaxation (which only lifted the ban on
packages running their own bundled algorithm, not on downloaded trained models). Every pip-only alternative
(EasyOCR, RapidOCR, keras-ocr) has the same model-weight problem or a native-compile problem (tesserocr).
**Tier: C — do not implement**, and document as a confirmed, re-verified "no."

---

### B12. EN-10 Trust & Transparency Overlap — Confirmed, Stays Out
**Verdict:** Reviewed against existing trust-signal and grounding checks: no clean non-overlapping slice
remains. "Pricing hidden"/"contact hard to find" collapse into existing retrieval-structure and
NAP-findability checks; "no proof at the decision point" collapses into the information-scent framing (C2
below) rather than needing its own row.
**Tier: C — stays rejected**, absorbed by C2 once implemented.

---

## Area C — On-Site Engagement Research

*This area was explicitly the weakest-grounded cluster in the existing rubric. All three sources
independently converged on the same academic anchor: **Information Foraging Theory** (Pirolli & Card,
1999, Psychological Review 106:643–675) and its "information scent" construct — users and scent-following
agents estimate the value of a link/CTA from the similarity between its cue text and the actual destination
content. This is treated as [established] research, not inference, by all three sources, and gives the
engagement cluster grounding on par with "Lost in the Middle" for the retrieval cluster.*

### C1. Information-Scent Link/Target & CTA Coherence Audit
**Detects:** Two related failure patterns, unified under one mechanism: (a) internal navigation links/CTAs
using generic, low-scent text ("Learn More," "Click Here") that carries no predictive information about the
destination; (b) specific cue-target mismatch, where a link's anchor text or a page's primary CTA
diverges from what the target/page actually delivers (closing the previously-blocked "content-to-action
coherence" gap).
**Method:** Extract internal anchor text and primary CTA text from the bounded sample; compute lexical
overlap (stemmed keyword Jaccard, or `rapidfuzz` token-set comparison) between cue text and target
title/H1/topic terms. Low-overlap pages are passed to an LLM judge with a written rubric citing the
information-scent mechanism, asking whether a page-specific cue exists nearby that the lexical score missed
— narrowing which pages get judged rather than flagging on lexical score alone.
**Package:** None required (stdlib token-set overlap is sufficient); `rapidfuzz` optional if fuzzy
token-level matching outperforms plain overlap in testing.
**Risk:** None.
**Evidence:** e.g. "Page topic: 'Enterprise Security Compliance'; primary CTA: 'Get Started' — zero shared
vocabulary with the page's own heading or first two paragraphs."
**False positives:** Deliberately generic, brand-voice CTAs are extremely common and not always a defect —
rubric must check for *any* page-specific supporting cue nearby before flagging; deliberately transitional
CTAs (blog → newsletter) are coherent even at low lexical overlap. Ship as agent-judged with script signal
only narrowing candidates, capped at Medium severity.
**Verdict:** Unanimous across all three sources — the strongest, best-grounded engagement candidate in the
backlog, closing multiple previously-blocked rows (content-to-action coherence, generic navigation
findability) with one mechanism. Ranked in the top 5 by all three sources.
**Tier: A** · Complexity: Medium · Innovation: 7–8 · Evidence: 8–10

---

### C2. Machine-Readable Conversion Path Verification
**Note:** This is the engagement-cluster framing of A2 (machine-readable action availability) — same
mechanism, same detection method, applied specifically to conversion/booking/purchase flows. Merge with A2
in implementation; keep only as a distinct framing if the engagement and discoverability clusters need
separately-labeled findings.
**Tier: A** (merged into A2)

---

## Area D — Infrastructure Hardening

### D1. Bounded, Sitemap-Scoped, Template-Stratified Sampling Layer
**Improves:** Replaces the current apparent-interest-biased page selection with a stratified sample drawn
to maximize page-template/content-type coverage within a fixed page budget. This is the single piece of
shared infrastructure that unlocks or strengthens nearly every Area B candidate (B1–B8) and C1's
navigation-findability extension.
**Grounding:** Two independent, authoritative sources converge on the same prescription — a peer-reviewed
URL-clustering stratified-sampling method (*Frontiers of Information Technology & Electronic Engineering*)
and the W3C WAI-ERT accessibility conformance sampling methodology (representative sample = one instance of
every distinct template + every key process + most-frequent pages).
**Method:** Parse the sitemap into URL-path segments; cluster by structural pattern (normalize
numeric/UUID/slug segments to a wildcard); allocate a fixed page budget (e.g. 20–30 pages) proportionally
across strata with a floor of ≥1 page per stratum; oversample the homepage and any distinct "process" page
(checkout, contact, search). Publish the sample list as shared plumbing every skill consumes, rather than
each skill sampling independently.
**Package:** None (stdlib string/regex clustering).
**Risk:** None.
**Verdict:** Unanimous across all three sources — the single highest-leverage infrastructure change in the
backlog, with direct, already-observed evidence that getting this wrong silently disabled a real capability
(B6's near-duplicate detection failure).
**Tier: A** · Complexity: Medium · Innovation: 7–9 · Evidence: 8–10

---

### D2. Shared Fetch Layer / Single-Fetch Page Bundle
**Improves:** One fetch per URL, cached and shared as one immutable `PageBundle` (raw HTML, extracted text,
JSON-LD, hydration-state JSON, headers, links) consumed by every skill that needs that page — eliminating
redundant independent fetches across skills.
**Package:** `httpx` (PyPI, BSD, fully pure-Python dependency chain — `httpcore`, `certifi`, `idna`,
`sniffio`; optional HTTP/2 via `h2`, also pure Python, no native compile step anywhere in the stack) — one
of the lowest-risk package additions in the entire backlog.
**Risk:** Low. Degrade path: fall back to stdlib `urllib`/`http.client` if `httpx` fails to import; the
shared bundle interface doesn't change based on which client built it.
**Verdict:** Unanimous across all three sources.
**Tier: A** · Complexity: Medium · Innovation: 5–6 · Evidence: N/A (engineering, not a detection claim)

---

### D3. Findings Deduplication (Cross-Skill Near-Duplicate Merge)
**Improves:** Merges near-duplicate findings generated by different skills for the same underlying root
cause, before final report assembly. Currently unresolved: the project's own two prior checks against real
composed reports found no actual case yet, but the sample (4 sites) is thin, and Area B's new overlapping
candidates make redundancy more likely going forward.
**Method:** Shingle each finding's evidence text; compute pairwise similarity; merge findings whose
evidence exceeds a high similarity threshold (e.g. ≥0.85 Jaccard), concatenating evidence sources and
keeping the highest severity.
⚠️ **Disagreement:** Two sources recommend `datasketch` (MinHash/LSH, PyPI MIT, pure Python + a numpy
dependency) as the standard technique for this. One source explicitly evaluated and **rejected** `datasketch`
for this specific use, arguing that at the actual scale involved (dozens of findings, not millions) plain
stdlib shingle-Jaccard is sufficient and avoids the larger numpy/scipy-adjacent dependency surface entirely
— MinHash/LSH's sub-linear lookup advantage is irrelevant at this N.
**Recommendation:** Prefer stdlib shingle-Jaccard given the small N involved; reserve `datasketch` only if
finding volume grows enough to need sub-linear lookups.
**Risk:** Low either way; degrade path is simply skipping the merge step and emitting findings unmerged (a
strict superset of current behavior — failure here cannot make the report worse than today).
**Tier: B** · Complexity: Low–Medium · Innovation: 4–8 · Evidence: N/A

---

### D4. Budget/Timeout Governor with Coverage Ledger
**Improves:** A two-level time budget — a fixed global ceiling split across pipeline stages (sampling,
fetch, per-skill analysis ×8, report assembly), and within each skill stage, a coverage-mode degrade ladder
(full sample → reduced sample → skip sub-check → emit `confidence: unknown`) rather than an all-or-nothing
timeout.
**Why now:** Every new package this cycle (`networkx`, `rapidfuzz`, `httpx`, `tldextract`, possibly
`datasketch`) adds real import/init cost on top of the pre-existing 5-minute runtime ceiling — this
candidate is a precondition for the rest of the backlog being safe to ship, not just a nice-to-have.
**Method:** Wrap skill execution in a monotonic-clock budget with per-stage caps; on cap breach, emit typed
`unknown` findings with the cap as the stated reason for every check that stage didn't reach, rather than
silently dropping coverage.
**Package:** None (stdlib `time`/`concurrent.futures`, or `asyncio` timeouts if D2's async client is used).
**Risk:** None — this candidate manages *other* candidates' cost, not its own.
**Evidence produced:** A coverage manifest attached to the final report (e.g. "ENT cluster: reduced coverage,
12/30 pages, budget-limited. CIT-11: skipped, budget exhausted.").
**Verdict:** Unanimous across all three sources.
**Tier: A** · Complexity: Medium · Innovation: 5–9 · Evidence: N/A

---

### D5. Rule-Based Sentence-Boundary Precision Layer
**Improves:** Several already-shipped detectors implicitly depend on correct sentence segmentation
(claim-verb-in-sentence checks, positional/percentile-based findings). A naive `split('.')` approach
silently miscounts boundaries on abbreviations, decimals, and initials ("Founded in the U.S. in 2010,"
"$4.5 million"), skewing every percentile/position-based finding downstream.
**Package:** `pysbd` (PyPI, MIT, zero dependencies, pure Python, rule-based — not statistical/trained,
published with an accompanying peer-reviewed paper at an EMNLP 2020 workshop).
**Risk:** Low technically (zero transitive deps, tiny package), but flagged as low-recent-maintenance —
verify it imports cleanly under the sandbox's Python version before depending on it. Degrade path: fall back
to current segmentation method if unavailable — precision regresses, nothing breaks.
**Verdict:** Proposed by one source only.
**Tier: B** · Complexity: Low · Innovation: 3 · Evidence: 6

---

### D6. Evidence-Strength Confidence Scoring
**Improves:** Completes the existing typed-`unknown`/confidence infrastructure by scoring evidence
*strength* per finding — count and diversity of evidence artifacts behind it (pages sampled, cross-layer
agreement, reproducibility) — feeding the severity model.
**Package:** None (rule-based, stdlib).
**Risk:** None.
**Verdict:** Proposed by one source only.
**Tier: B** · Complexity: Low · Innovation: 5 · Evidence: 7

