# Baseline Capabilities

Phase 1 output. What the baseline covers, mapped to capability-matrix IDs.

**Coverage claims here are documentation-derived, not execution-verified.** Every row is a
*claim to test at Step A*, not a settled `BASELINE_COVERED` status. Nothing in the matrix
changes status on the strength of this document alone.

Coverage key: **Full** = plausibly complete for our purposes · **Partial** = covers some of
the capability · **Signal** = produces a score contribution but likely no usable evidence
string · **None**.

---

## 1. Scored categories (the audit core)

Point allocations are the baseline's own. We do not inherit them — see baseline-gaps §2.

| Its category | Pts | Matrix IDs | Coverage | Notes |
|---|---|---|---|---|
| Robots.txt | /18 | PER-01, PER-02 | **Full** | 27 AI bots across 3 tiers (training / search / user). Explicitly checks whether citation bots are allowed — this is the correct question, not just "is anything blocked" |
| llms.txt | /18 | PER-04, PER-05 | **Full** | Presence, H1, blockquote, sections, links, depth; companion llms-full.txt. Structurally thorough. **Severity must be re-derived — see baseline-gaps §2** |
| Schema JSON-LD | /16 | ENT-01 | **Full** | WebSite, Organization, FAQPage, Article; richness threshold at 5+ attributes |
| Meta tags | /14 | ENT-04 (partial) | **Partial** | Title, description, canonical, Open Graph. Canonical presence ≠ canonicalisation analysis across a crawl |
| Content | /12 | CIT-06, CIT-07, RET-08 | **Partial** | H1, statistics, external citations, heading hierarchy, lists/tables, front-loading. Front-loading maps to CIT-07 (position weighting); statistics to CIT-06 |
| Brand & Entity | /10 | ENT-02, ENT-05 | **Partial** | Brand coherence, knowledge-graph links (Wikipedia/Wikidata/LinkedIn/Crunchbase), about page, geo signals, topic authority |
| Signals | /6 | CQ-10 (partial) | **Partial** | `<html lang>`, RSS/Atom, `dateModified` freshness |
| AI Discovery | /6 | PER-07 (adjacent) | **Partial** | `.well-known/ai.txt`, `/ai/summary.json`, `/ai/faq.json`, `/ai/service.json`. Note: these are *not* the `.md` content-negotiation check PER-07 specifies; they are a different, more speculative convention |

## 2. Bonus checks — the material re-examinations

These were marked build-from-scratch in Phase 0.2. Each now needs Step A gap confirmation
rather than assumption. **Documentation states these are informational and do not affect
the score, which raises the question of whether they emit usable evidence at all** —
§7 q4 in baseline-analysis.

| Its check | Matrix IDs | Coverage | Step A question |
|---|---|---|---|
| CDN Crawler Access (Cloudflare/Akamai/Vercel blocking AI bots) | **PER-03** | **Full** | Does it report *which* bot got which status code? Evidence quality depends on it. **C** — independently corroborated as a real and common failure: Cloudflare-network research found a meaningful share of sites blocking AI crawlers at the CDN while robots.txt says allow |
| JS Rendering / SPA detection | REN-02 | **Partial** | Detects *that* content needs JS. Does not diff pre/post-render DOMs, so REN-03 and REN-04 remain ours |
| Multimodal Readiness | **REN-08** | **Full** | Alt coverage, captions, VideoObject/AudioObject schema, subtitle tracks, transcripts. Broader than REN-08 as specified |
| Negative Signals (8) | RET-04, REN-07, EN-06 (partial) | **Partial** | CTA overload, popups, thin content, keyword stuffing, missing author, boilerplate ratio. Popups + CTA overload are the first engagement-adjacent checks found anywhere in the baseline |
| Prompt Injection Detection (8 patterns) | **INF-11 → promote** | **Full** | Hidden text, invisible Unicode, LLM instructions, HTML comment injection, monochrome text, micro-font, data-attr injection, aria-hidden abuse. No other candidate has this |
| Trust Stack Score (5 layers) | CIT-01 | **Signal** | Composite A–F grade. Aggregate scores rarely carry per-finding evidence |
| RAG Chunk Readiness | RET-06, RET-07 | **Full** | Section word counts, definition openings, heading boundaries, anchor sentences. This is precisely the atomic-paragraph / chunk-quality capability |
| Content Decay Prediction | CQ-05, CQ-06, CQ-10 | **Partial** | Temporal, statistical, version, event, and price decay; evergreen score 0–100. Adjacent to our relative-date and price-invariance checks, not identical |
| Platform Citation Profile | — | **Signal** | Per-platform readiness for ChatGPT/Perplexity/Google AI. Interesting framing; no matrix ID |
| WebMCP Readiness | **EN-09 (adjacent)** | **Partial** | `registerTool()`, `toolname` attributes, `potentialAction` schema. The only baseline check that touches autonomous-agent usability |

## 3. Additional commands

| Command | Matrix IDs | Coverage | Notes |
|---|---|---|---|
| `geo access` | PER-01, PER-03 | **Full** | Browser vs AI-bot access simulation. Likely the strongest evidence generator in the tool |
| `geo coherence` | ENT-09 | **Partial** | Cross-page terminology consistency via sitemap |
| `geo authority` | CIT-08 | **Partial** | Topic clusters, interlinking depth, pillar pages — adjacent to hub/authority link-graph |
| `geo perception` | — | **Signal** | "What an AI would extract from this page." Useful as *supporting evidence* attached to our findings, not as a finding itself |
| `geo drift` | — | **None** | Requires two runs over time. Out of scope for a single audit |
| `geo logs` | — | **None** | Requires server access logs the auditor does not have |
| `geo diff` | REN-02 (adjacent) | **None** | Compares two URLs, not pre/post-render of one |
| `geo_factual_accuracy` (MCP) | CIT-03, CIT-04 | **U** | Claims to audit unsourced claims, contradictions, broken citations. If real, this is the hardest capability in our matrix arriving free. Inspect before believing |

## 4. Coverage summary against the 62-capability matrix

| Cluster | Capabilities | Plausibly covered | Comment |
|---|---|---|---|
| A — Perimeter | 8 | 6 | Strongest area. PER-06 (sitemap completeness) and PER-07 (`.md` negotiation) remain ours |
| B — Render/extract | 11 | 3 | Detects the symptom (SPA), not the mechanism (render diff) |
| C — Entity | 10 | 4 | ENT-03, ENT-06, ENT-07, ENT-08 remain ours |
| D — Retrieval | 8 | 3 | No BM25, no synonym/intent coverage |
| E — Citability | 13 | 4 | Plus one U (`factual_accuracy`) |
| F — Content anti-patterns | 12 | 3 | The deterministic four (CQ-03/05/07/08) are largely ours |
| G — Engagement | 11 | **0.5** | Popups + CTA overload only, and as score signals |
| H — Infrastructure | 11 | 2 | URL validation, prompt-injection scanning |
| **Total** | **62** | **~25** | |

**The shape of the remaining work is now clear.** The baseline plausibly covers about 40% of
the matrix, heavily concentrated in perimeter and entity. It covers essentially none of the
engagement cluster and none of the deterministic content anti-patterns — which, per the
Phase 0.2 front-loading analysis, are the two areas with the best evidence quality and the
highest rubric leverage. The baseline buys us the boring, necessary half. The differentiated
half is ours to write.
