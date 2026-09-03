# Novel AI-Discoverability Audit Techniques — Innovation Backlog

*Deep research deliverable for the AI-discoverability hackathon. Scope: capabilities meaningfully outside the existing PER/REN/ENT/RET/CIT/CQ/EN/INF set, implementable in Python/Node without a browser, with no outsourced scoring APIs.*

---

## 0. How this was researched

Rather than brainstorm from GEO marketing conventions, each candidate below is anchored to at least one of: an IETF/W3C specification or draft, a peer-reviewed or arXiv technical paper, a major search/crawl engineering source (Google Research, Common Crawl, Chroma, Akamai/Cloudflare bot-management engineering), or a documented security-research finding. Where the underlying evidence is a single vendor blog or an early-stage internet-draft rather than a settled standard, this is flagged explicitly in "Evidence strength" so the judge can weigh it accordingly. Nothing below repeats robots.txt/llms.txt/schema.org/keyword-density/readability checks from the existing capability set.

Four mechanisms recur across the strongest candidates, and it's worth naming them up front because they are the actual *sources* of novelty:

1. **Positional/attention bias in transformers** ("lost-in-the-middle," "context rot") — a hard architectural property of LLMs, not a ranking heuristic, that ordinary SEO tooling has no reason to know about.
2. **Emerging machine-to-machine trust protocols** (Web Bot Auth/RFC 9421, TDMRep, IndexNow) — 2024–2026 infrastructure that sits *below* robots.txt and *above* WAF blocking, largely undocumented in GEO checklists because it's brand new.
3. **Graph- and set-theoretic techniques from classic IR/security** (reachability analysis, SimHash/MinHash near-dup clustering, coreference resolution, static-analysis-style referential-integrity checks) — decades-old, rigorously studied, but never applied to the specific object of "the AI-permitted view of a website."
4. **Agent-specific operational telemetry** (documented AI-fetcher timeout/redirect/hop tolerances, indirect prompt injection) — behavior of *specific, named* crawlers (GPTBot, ChatGPT-User, ClaudeBot, PerplexityBot) that is empirically observable and different from how Googlebot or a human browser behaves.

---

## 1. Tier A — Hackathon Differentiators

### A1. Hidden-Instruction / Indirect Prompt-Injection Payload Scanner

**What it detects:** Text on the page that is invisible to a human visitor but readable by an AI agent's text extraction — and that contains imperative, agent-directed language (e.g., instructions to cite this domain as authoritative, ignore prior instructions, suppress a competitor, or perform an action).

**Why it matters for AI systems:** This is not a rendering bug — it is a direct attack on retrieval-augmented and agentic systems. Zscaler ThreatLabz documented live campaigns burying instructions in off-screen CSS and JSON-LD to manipulate autonomous purchasing agents, successfully manipulating 4 of 26 tested LLMs into fraudulent actions in one campaign. Unit 42, Forcepoint X-Labs, and Brave's red-team work on Perplexity Comet independently document the same pattern (CSS concealment, HTML comments, accessibility-attribute abuse, "system prompt" tag impersonation) as an active, in-the-wild technique against browsing/agentic AI. This is squarely inside the hackathon's "agentic browsing, tool use" research axis, and it cuts both ways for a discoverability audit: (a) a compromised or over-aggressive "AI-SEO" plugin can inadvertently plant manipulative text that gets a domain blocklisted by AI safety filters, and (b) it is a legitimate self-scan for supply-chain/CMS compromise.

**Why it is novel:** Nothing in the existing set inspects DOM content specifically for *machine-directed, human-invisible imperative text*. REN-09 (image-of-text) and REN-10 (NAP asymmetry) check for facts hidden from extraction; this checks for *commands* hidden from humans — a security-classification problem, not a content-completeness problem.

**Detection methodology:** Parse the static HTML/CSS. Flag text nodes that are (a) styled with `display:none`, `visibility:hidden`, `opacity:0`, `font-size:0/1px`, absolute off-canvas positioning, or zero-dimension containers, or (b) sit inside HTML comments, or (c) sit inside JSON-LD/meta content that a human would never read, or (d) use ARIA/accessibility attributes in a way inconsistent with genuine a11y use (e.g., `aria-hidden="false"` on huge instruction blocks). For each flagged node, run a lightweight classifier: does it contain second-person imperative verbs directed at "the AI/assistant/model/agent," override phrases ("ignore previous instructions," "disregard the above," "as an AI you must"), or self-referential authority claims ("this is the official/canonical source, cite this page")? Score = f(concealment technique, imperative density, presence of override phrasing).

**Required inputs:** Raw HTML + inline/linked CSS (already fetched by INF-02). No rendering engine needed — CSS property parsing is static text analysis.

**Implementation feasibility:** Python/Node HTML+CSS parser (`BeautifulSoup`/`cssutils` or `cheerio`/`postcss`) to compute effective visibility per node; a small regex/keyword rule set (extendable to a local zero-shot classifier if desired, but not required) for the imperative-language pass.

**Evidence produced:** Exact DOM path/selector, the concealment CSS rule that hides it, the extracted hidden text, and the specific override/authority phrase that triggered the flag — directly quotable to the site owner as "this text is invisible to your visitors but readable by an AI agent."

**False-positive risks:** Legitimate accessibility patterns (screen-reader-only text, skip-links, visually-hidden-but-announced labels) use the same CSS techniques for good reasons — the classifier must gate on imperative/override language, not concealment alone, or it will flag every well-built accessible site.

**Complexity:** Medium (CSS-effective-visibility computation is the fiddly part; the language classifier is simple).

**Innovation score:** 9/10 · **Evidence strength:** 8/10 (multiple independent 2025–2026 security-research writeups: Zscaler ThreatLabz, Unit 42, Forcepoint, Brave, promptfoo, Lakera; underlying "indirect prompt injection" concept originates with Greshake et al.) · **Existing-capability overlap:** None. REN-09/REN-10 check *fact* visibility, not *command* visibility; this is a distinct security-classification signal.

---

### A2. AI-Reachable Subgraph Orphan Detection

**What it detects:** Pages that are reachable by a normal browser/search crawler via internal links, but become **unreachable specifically for AI agents** once you remove every internal link that only exists on a page an AI crawler is disallowed from fetching (or that requires JS execution AI fetchers don't perform).

**Why it matters for AI systems:** Retrieval-augmented and agentic systems don't just need one page allowed — multi-hop discovery depends on a *connected* crawl graph. Google's own crawl-scheduling and PageRank literature treats the web as a directed graph where reachability determines whether a page is ever discovered at all; the same graph-theoretic logic applies to an AI crawler's permitted subgraph. A page can pass every per-URL check (robots.txt allows it, content is clean, schema is valid) and still never be found by an AI crawler because the *only* paths to it run through pages that are disallowed, are orphaned behind client-side navigation, or sit behind a `noai`/`Disallow` gate. This is a systemic, graph-level failure mode that no single-URL audit (PER-01 through PER-08 all operate per-page or per-directive) can see.

**Why it is novel:** The existing set audits individual perimeter rules and individual link-graph *authority* (CIT-08 hub/authority structure, EN-08 on-site findability). Neither computes actual graph reachability under a *filtered edge set* — i.e., "take the real internal link graph, delete every edge that originates on a page an AI crawler cannot fetch, and find the connected components that only survive because of deleted edges." That's a distinct algorithm (BFS/DFS reachability diff on two graphs), not a per-page rule.

**Detection methodology:** From the already-crawled page bundle (INF-04), build graph G = all internal links discovered. Build G′ = G with all outbound edges from any page disallowed to the target AI agent (per PER-01 findings) removed, and (optionally) with edges that only exist inside client-rendered navigation (per REN-02 hydration diff) also removed. Compute reachable-from-root(G) and reachable-from-root(G′) via BFS from the homepage/sitemap roots. Flag every URL in `reachable(G) − reachable(G′)` as an **AI-orphan**: real, high-value content invisible to any AI crawler that starts from the homepage and follows only AI-permitted links, even though a human or Googlebot would find it in one or two clicks.

**Required inputs:** Full internal link graph from the crawl (already gathered per INF-01/02), robots.txt per-agent directives (already parsed per PER-01), hydration-diff results (REN-02, optional refinement).

**Implementation feasibility:** Pure graph algorithm — `networkx` in Python (or a hand-rolled adjacency-list BFS in Node) over data structures the crawler already produces. No new fetching required beyond what INF-02 already does.

**Evidence produced:** A concrete list of orphaned URLs plus the "cut edge" — the specific page/link that, if it weren't disallowed, would restore reachability — so the fix is a one-line recommendation ("un-disallow /blog/index or add a direct sitemap/internal link to /product/x").

**False-positive risks:** Sites that rely on a submitted XML sitemap rather than internal links as the primary discovery path will show "orphans" that AI search crawlers (which do consume sitemaps, per PER-08) can actually still reach — the detector should cross-reference sitemap coverage before flagging, or report it as a lower-severity "link-graph-only orphan."

**Complexity:** Low–Medium (the algorithm is simple; correctness depends on having a reasonably complete crawl).

**Innovation score:** 9/10 · **Evidence strength:** 7/10 (graph reachability under edge deletion is standard, well-established CS; its application to "AI-permitted subgraph" is a novel-but-straightforward adaptation, not itself published) · **Existing-capability overlap:** None — distinct from PER-01 (per-page directive), CIT-08 (authority/centrality, not reachability), EN-08 (human findability, not AI-filtered reachability).

---

### A3. Chunk-Fracture Simulation

**What it detects:** Whether the specific fixed-size/sliding-window chunking schemes that real production RAG pipelines commonly use would physically split an answer-critical fact (a number, an entity, a date, a claim) across two separate retrieval chunks — meaning even a system that *can* find the page would retrieve a truncated, half-formed fact.

**Why it matters for AI systems:** RAG systems don't retrieve whole pages; they retrieve chunks, most commonly fixed-token or fixed-character windows (with or without overlap) because that remains the simplest and most widely deployed strategy in production pipelines, despite active research into proposition/semantic/adaptive chunking. A fact that straddles a chunk boundary is either split into two low-relevance fragments (neither of which individually matches a query well) or is retrieved with its subject/qualifier severed from its value — a completely different failure mode from "the paragraph is badly written" (CQ-01) or "the paragraph isn't atomic" (RET-06). This is a *positional/structural* risk that exists independent of prose quality.

**Why it is novel:** RET-06 asks "are your paragraphs atomic and well-chunked *as authored*?" — a qualitative content-authoring check. This capability instead *simulates the mechanical act of chunking* the way an off-the-shelf RAG ingestion pipeline actually would (e.g., 512-token windows with 10–20% overlap, or fixed 1000/1500-character windows — the de facto defaults in LangChain/LlamaIndex-style pipelines and the fixed-token baselines used as controls in published chunking-strategy evaluations), then checks whether that mechanical process — not the author's paragraphing — fractures specific facts. It is a simulation/testing technique, not a style check.

**Detection methodology:** Extract clean body text (reusing REN-06/REN-07 boundary detection). Identify "atomic facts" via lightweight NER + numeric/date pattern matching (price, date, quantity, named entity + adjacent verb/number). Run 2–3 standard fixed-window chunking configurations (e.g., 512 tokens/0% overlap, 512 tokens/15% overlap, 1000 chars/0% overlap) across the text. For each configuration, check whether any atomic fact's span crosses a chunk boundary. Report the fraction of extracted facts that survive intact vs. get bisected, per configuration, and flag the specific facts most likely to fracture (e.g., "$49.99" split from "per month" in the 512-token/no-overlap configuration).

**Required inputs:** Extracted clean body text, a tokenizer (any BPE tokenizer for the "token" simulations — exact vendor tokenizer not required, an open one like `tiktoken` is a fair proxy), a lightweight NER/regex fact extractor.

**Implementation feasibility:** Pure Python/Node text processing — `tiktoken` (or any open BPE tokenizer) for windowing, `spaCy`/regex for fact-span extraction, and simple interval-overlap arithmetic to detect boundary crossings. No network calls, no ML training.

**Evidence produced:** A concrete, reproducible table: "In a 512-token/no-overlap chunking pass, the fact '$1,299 starting price' is split at token offset 507, separating the number from its currency/context" — with the exact chunk boundary shown, which is far more convincing than a generic "improve your paragraph structure" note.

**False-positive risks:** Real production RAG pipelines vary widely in chunk size/overlap/strategy (many now use semantic or proposition chunking, which this technique cannot observe from outside); results should be framed as "risk under common baseline configurations," not "guaranteed fracture in every AI system."

**Complexity:** Low (once text extraction exists, the simulation itself is simple arithmetic).

**Innovation score:** 8/10 · **Evidence strength:** 7/10 (fixed-window chunking as a common baseline, and its documented failure to preserve semantic units, is well attested across multiple 2025 chunking-strategy evaluation papers, e.g. clinical-decision-support and academic-text chunking studies) · **Existing-capability overlap:** Adjacent to RET-06/RET-07 but methodologically distinct — a simulation of a mechanical ingestion process vs. a qualitative structure check.

---

### A4. Positional Fact-Placement / "Lost-in-the-Middle" Exposure Audit

**What it detects:** Whether the single most important, differentiating fact on a page (the answer to the page's obvious primary query — price, verdict, key spec, safety warning) is buried deep in the middle of a long page/chunk rather than positioned near the start or end.

**Why it matters for AI systems:** This is arguably the best-evidenced mechanism in this entire report. The "lost-in-the-middle" effect (Liu et al., Stanford/UC Berkeley/Samaya AI, 2023) and its architectural explanation via U-shaped attention bias / RoPE long-term decay (Hsieh et al., "Found in the Middle," 2024) show that LLMs systematically under-attend to information in the middle of whatever context they're given — whether that's a single long chunk, or several retrieved chunks concatenated together. Chroma's 2025 "Context Rot" study extended this across 18 frontier models (including GPT-4.1, Claude 4, Gemini 2.5) and found the degradation is not a solved problem in modern long-context models; strikingly, it also found *shuffled* documents sometimes outperform *logically coherent* ones, because coherent narrative flow produces more plausible-looking distractors. A page that puts its key fact in paragraph 14 of 20 is measurably more likely to have that fact ignored by a synthesizing LLM than the identical fact placed in paragraph 1 or paragraph 20 — independent of retrieval succeeding.

**Why it is novel:** Every "structure" item in the existing set (RET-07 retrieval-oriented structure, RET-08 heading hierarchy, CQ-01 answer extractability) asks whether a fact is *marked up* well. None of them asks *where in the token sequence* it physically sits, which is the actual mechanism the positional-bias literature identifies as causal.

**Detection methodology:** Extract clean body text and its token-offset positions (reuse the tokenizer from A3). Identify the page's primary answerable fact(s) — reuse the atomic-fact extractor from A3, or infer the primary query from title/H1/meta description and locate the sentence most lexically similar to it. Compute the fact's normalized position (0.0 = start, 1.0 = end) within the page and within the position it would occupy inside a plausible retrieved chunk. Score risk using a simple weighting derived from the published U-shaped curve (elevated risk in roughly the middle third, 0.3–0.7 normalized position, lowest risk at the extremes).

**Required inputs:** Clean extracted text with token offsets, title/H1/meta description for primary-intent inference.

**Implementation feasibility:** Pure text-position arithmetic; no model calls needed beyond the same tokenizer/NER already used in A3.

**Evidence produced:** "Your page's price disclosure sits at normalized position 0.52 (dead center) of a 3,400-token page — in the zone the 'lost-in-the-middle' and 'context rot' research identifies as highest-risk for LLM omission. Moving it into the first or last 20% of the page, or repeating it near the end, is a low-cost mitigation directly supported by published attention-bias research."

**False-positive risks:** The bias is probabilistic, not absolute, and interacts with chunk boundaries (A3) and retrieval reranking in ways a single-page auditor cannot fully see; frame findings as elevated-risk, not guaranteed omission.

**Complexity:** Low.

**Innovation score:** 9/10 · **Evidence strength:** 9/10 (Liu et al. 2023 is one of the most-cited empirical LLM papers of its era; the 2024 mechanistic follow-up and Chroma's 2025 multi-model replication substantially strengthen the causal story) · **Existing-capability overlap:** None — distinct mechanism from every markup/structure item in RET/CQ.

---

### A5. Chunk Anaphora / Coreference Self-Containment Risk

**What it detects:** Sentences or paragraphs whose subject is only established via pronoun or referring expression from an *earlier* paragraph — "it," "this model," "the company," "these results" — such that, if that paragraph is retrieved on its own (the normal RAG unit of retrieval), the sentence is semantically incomplete or actively ambiguous.

**Why it matters for AI systems:** Because chunks are retrieved and embedded independently, a chunk's dense-retrieval embedding is computed from whatever text is inside it — if the entity is never actually named inside the chunk (only referenced pronominally), the embedding drifts away from queries that name the entity explicitly, hurting recall; and if the chunk *is* retrieved, the LLM either has to guess the antecedent or hallucinates one. Multiple 2025 papers formalize exactly this failure and show it is fixable and measurable: CoRAG (coreference-resolution preprocessing for RAG, 2025) reports accuracy gains from resolving pronouns before chunking; CLAP explicitly motivates coreference resolution by noting that "semantic chunking inevitably breaks cross-chunk context... leading to degraded expansion quality and suboptimal retrieval performance"; and an ACL 2025 student-research-workshop paper independently confirms coreference resolution measurably improves both retrieval relevance and downstream QA accuracy, especially for smaller models with less capacity to infer referents on their own.

**Why it is novel:** This is a distinct linguistic failure mode from every RET/CQ item — it's not about keyword coverage, structure, or granularity, but about whether a paragraph *names its own subject*. It is the flip side of A3 (structural fracture) and A4 (positional bias): a chunk can be perfectly sized and perfectly positioned and still fail because it depends on context outside itself.

**Detection methodology:** Split extracted body text into paragraph-level candidate chunks (the natural chunking unit). For each chunk, run a lightweight coreference/anaphora heuristic: count sentence-initial or high-salience pronouns/definite references ("it," "this," "that," "these," "the company," "the product," referring expressions without a preceding possessive/proper-noun anchor *within the same chunk*) relative to total sentences. A chunk with a high first-mention-pronoun ratio and no proper-noun anchor of its own is flagged as context-dependent. (A full coreference-resolution model such as `neuralcoref`/`spaCy`'s coref pipeline can be run locally for a stronger version of this signal; the regex/heuristic version above needs no model at all.)

**Required inputs:** Extracted body text split at natural paragraph/heading boundaries.

**Implementation feasibility:** Regex/POS-based heuristic is trivial (Python `spaCy` for POS tagging + pronoun/proper-noun anchor detection); an upgraded version can run a local open-source coreference model, still fully offline and not an "outsourced score."

**Evidence produced:** "Paragraph 6 ('It launched the feature in March, and it quickly became the most-used tool in the suite') never names its subject inside the paragraph. If this paragraph is retrieved on its own — the normal unit of RAG retrieval — an AI system cannot determine what 'it' refers to without the preceding paragraph, which research on RAG coreference (CoRAG 2025, CLAP 2025) shows measurably degrades both retrieval match and answer accuracy."

**False-positive risks:** Short, tightly-scoped FAQ-style chunks that repeat the subject by design will score well by construction; legitimate stylistic variety (e.g., a chunk that opens with "This guide..." referring to itself) can be misflagged — tune the anchor-detection window and exclude self-referential deictic openings.

**Complexity:** Low (heuristic) to Medium (full local coreference model).

**Innovation score:** 8/10 · **Evidence strength:** 8/10 (three independent 2025 papers — CoRAG, CLAP, and the ACL SRW study — converge on the same finding using different methodologies) · **Existing-capability overlap:** None — genuinely distinct linguistic mechanism from anything in RET/CQ.

---

### A6. Semantic Distractor Density ("Context-Rot Trap" Detection)

**What it detects:** Clusters of sentences on a page or across a site that are *lexically/semantically very similar to each other but factually divergent* — e.g., three different "starting price" mentions with three different numbers, or near-identical product-description paragraphs that differ only in one changed spec — the exact pattern Chroma's research shows actively *misleads* LLMs rather than merely diluting relevance.

**Why it matters for AI systems:** Chroma's controlled 2025 study specifically isolated "distractor interference": semantically similar-but-irrelevant (or similar-but-wrong) content in context actively degrades needle-retrieval accuracy, on top of and distinct from pure position effects. This is a different mechanism from simple contradiction (two facts that disagree) — it's about near-duplicate phrasing creating multiple high-similarity anchors that compete for the model's attention and confuse which value is "the" answer, and the effect gets worse, not better, as more distractor-laden content is stuffed into context.

**Why it is novel:** CQ-07 (scope-ambiguous numeric claims) and CQ-10 (temporal freshness/contradiction) look at *whether facts disagree*. This looks at *how textually similar the disagreeing (or even agreeing-but-redundant) statements are* — because it is specifically the combination of high lexical similarity + divergent payload that the context-rot literature identifies as the dangerous case, distinguishable algorithmically from a low-similarity, easily-disambiguated contradiction elsewhere on the page.

**Detection methodology:** Extract all fact-bearing sentences (reuse A3's fact extractor). For each pair of fact-bearing sentences on the same page (or across near-duplicate pages, see B1), compute lexical similarity (shingled Jaccard or a local, open embedding cosine similarity — not a paid API) between the sentence *templates* (fact value masked out) alongside a check on whether the extracted values themselves differ. Flag pairs with high template similarity (e.g., >0.8) and divergent values as high-risk distractor pairs; report density (distractor pairs per page) as the page's overall context-rot exposure score.

**Required inputs:** Extracted body text, fact spans from A3, a local sentence-similarity function (shingling or a small open-source sentence embedding model run offline).

**Implementation feasibility:** Fully local — shingling + Jaccard is trivial; if a stronger similarity signal is wanted, a small open-source sentence-transformer run on CPU is still "computed by us," not an outsourced score.

**Evidence produced:** "Your page contains 3 near-identical sentences about 'monthly subscription cost' with template similarity 0.91, but the stated values are $12, $15, and $19 — this is precisely the high-similarity/divergent-value pattern Chroma's 2025 controlled study found actively misleads LLM synthesis, not just dilutes it."

**False-positive risks:** Legitimate tiered-pricing or versioned-spec content (Basic/Pro/Enterprise) will trigger this by design; the detector needs to check for an explicit disambiguating qualifier (a tier/date/model label) co-located with each value before flagging, and treat clearly-labeled variants as lower severity.

**Complexity:** Medium.

**Innovation score:** 8/10 · **Evidence strength:** 8/10 (directly evidenced by Chroma's controlled multi-model 2025 study, which specifically isolated distractor interference as distinct from pure position bias) · **Existing-capability overlap:** Adjacent to but methodologically distinct from CQ-07/CQ-10 (those detect disagreement; this detects the similarity-plus-divergence pattern specifically shown to be dangerous).

---

### A7. Redirect-Hop / Latency Budget vs. Documented AI-Fetcher Tolerance ("Silent Abandonment Risk")

**What it detects:** Redirect chains or time-to-first-byte (TTFB) latencies that exceed the hop-count and timeout budgets specific named AI fetchers are documented to tolerate before silently abandoning a fetch — producing zero error visible to the site owner (no 404, no robots block) but a 100% failure to be cited.

**Why it matters for AI systems:** This is agent-specific operational behavior, empirically observed rather than declared in any spec. Independent 2026 crawl-log analyses report that OpenAI's real-time fetchers issue large volumes of HTTP 499 (client-abandoned) errors specifically from `ChatGPT-User` (the live, in-conversation fetcher, as opposed to the bulk `GPTBot` training crawler or the continuously-indexing `OAI-SearchBot`) — because a live fetch has to complete inside the latency budget of an interactive answer, not a batch crawl. Separately, engineering analysis of redirect handling across GPTBot, ClaudeBot, and PerplexityBot documents that training/index crawlers tolerate roughly 3–5 redirect hops before giving up, while conversational agents behave more like a lightweight browser with their own (tighter) tolerance and looser robots.txt enforcement. Content that survives fine for Googlebot (which tolerates much deeper chains and longer waits) can be silently invisible to a live AI answer specifically because of hop count or latency, independent of any block-list or content-quality issue.

**Why it is novel:** PER-03 detects *explicit* blocking (403/429/challenge). REN-01–REN-11 assume the fetch succeeded and examine what came back. This capability instead targets the specific quiet-failure zone between "allowed" and "successfully retrieved" — a page that is never blocked, never errors visibly to a human, and is simply too slow or too many hops deep for the specific fetcher class that matters (live/real-time vs. bulk/training).

**Detection methodology:** During the crawl, record (a) full redirect chain length and hop codes (301/302/307/308) for every URL, and (b) TTFB and total-fetch-time. Compare hop count against published/observed tolerance bands per fetcher family (training crawlers: ~3–5 hop tolerance, strict robots.txt; real-time search crawlers: lower hop tolerance, stricter timeout; conversational/on-demand fetchers: browser-like hop tolerance but tightest latency budget, documented single-digit-second abandonment). Flag any URL whose chain/latency crosses into the "silent abandonment" zone for a given fetcher class, and — where the crawler supports it — replay the fetch using each fetcher's published user-agent string to see whether the chain differs (some CDNs vary redirect behavior by UA).

**Required inputs:** Full redirect chain + timing already captured by the fetch layer (INF-02); a small reference table of documented per-fetcher-family tolerance bands (kept as configuration, updated as vendors publish more).

**Implementation feasibility:** Pure HTTP timing/hop-count analysis already available from `requests`/`httpx` response history — no new fetching capability required, just a comparison layer against the tolerance table.

**Evidence produced:** "This URL resolves through a 4-hop redirect chain (301→302→301→200) totaling 3.8s TTFB. Documented behavior for OpenAI's live ChatGPT-User fetcher shows abandonment (HTTP 499 from the fetcher's perspective) well within this range, while the bulk GPTBot/training crawler would likely tolerate it — meaning this page can plausibly be trained on but never cited in a live answer."

**False-positive risks:** Fetcher tolerance thresholds are not officially published by any vendor and are inferred from third-party log analysis, which can shift as vendors change infrastructure — this must be labeled a heuristic estimate, refreshed periodically, not a certified limit.

**Complexity:** Low.

**Innovation score:** 8/10 · **Evidence strength:** 6/10 (grounded in real crawl-log engineering analysis and confirmed multi-bot documentation of separate crawler classes with different purposes, but the exact numeric tolerance thresholds come from third-party observational blogs rather than vendor specs or peer review) · **Existing-capability overlap:** None — distinct failure zone from PER-03 (explicit blocking) and from REN-01 (fetch-succeeded assumption).

---

### A8. Emerging Machine-Trust-Protocol Adoption & Contradiction Audit (Web Bot Auth + TDMRep)

**What it detects:** Two independent, brand-new machine-readable protocols that sit *outside* robots.txt/llms.txt and can silently override or contradict them: (1) **Web Bot Auth** (IETF draft, built on RFC 9421 HTTP Message Signatures) — cryptographic request-signing that CDNs (Akamai, Cloudflare, AWS WAF, Vercel) increasingly require before treating a bot as legitimate, meaning an unsigned AI agent can be edge-blocked even when robots.txt explicitly allows it; and (2) the **W3C TDM Reservation Protocol (TDMRep)** — a `/.well-known/tdmrep.json` file (or equivalent headers/meta tags) through which a publisher can reserve text-and-data-mining rights *independently of and without conflicting with* robots.txt/indexing signals, meaning a site can technically "allow" crawling for indexing while simultaneously reserving AI-training rights in a way robots.txt cannot express at all.

**Why it matters for AI systems:** These are not hypothetical — Web Bot Auth is a live IETF working group (chartered after a BoF at IETF 123, targeting standards-track publication with milestones through 2026) already deployed by Akamai, Cloudflare, AWS WAF, Vercel, and Shopify, and OpenAI's ChatGPT traffic is documented as already sending `Signature`, `Signature-Input`, and `Signature-Agent` headers per this exact mechanism. A site that adopts CDN-level Web Bot Auth enforcement without publishing its own signing-agent allowlist policy, or without accounting for AI agents that don't yet sign requests, creates an invisible perimeter *below* robots.txt that PER-01/PER-02/PER-03 cannot see because it isn't UA-string or IP-based blocking — it's cryptographic-signature-based gating. TDMRep, meanwhile, is explicitly endorsed as the machine-readable mechanism for the EU AI Act / CDSM Directive's Article 4 TDM opt-out — a legally material signal general-purpose AI model providers operating in the EU are expected to check, and it can flatly contradict what robots.txt/llms.txt say ("crawl me for indexing" + "do not mine me for AI training" can both be true at once, expressed in two completely different files).

**Why it is novel:** PER-01/PER-02/PER-04 audit robots.txt and llms.txt specifically. Neither the existing capability set nor typical GEO tooling checks a second, orthogonal file (`tdmrep.json`) or a third, cryptographic-signature-based access-control layer that most GEO tooling doesn't even know exists yet because it postdates almost all published GEO literature.

**Detection methodology:** *Web Bot Auth:* Check for a published key directory at `/.well-known/http-message-signatures-directory`; send a baseline unsigned request and inspect whether the response (or CDN-identifying headers like `Server: cloudflare`/Akamai fingerprints) indicates signature-based bot policy is active versus simple UA/IP filtering; note when a 403/challenge response's headers or body specifically reference message-signature requirements rather than generic bot-blocking. *TDMRep:* Fetch `/.well-known/tdmrep.json`; also check for the TDMRep `tdm-reservation`/`tdm-policy` HTTP response headers and `<meta>` equivalents. Cross-reference the result against the site's robots.txt AI-agent directives (already parsed by PER-01) and flag disagreement (e.g., robots.txt allows GPTBot but tdmrep.json reserves TDM rights with no stated policy URL — a signal AI training pipelines are meant to respect but that most site owners don't realize they're sending, or aren't sending at all when they meant to).

**Required inputs:** One additional well-known-URL fetch (`tdmrep.json`) plus header inspection already captured by the fetch layer; response header/body inspection for signature-directory/challenge indicators.

**Implementation feasibility:** A handful of extra `GET`/`HEAD` requests and JSON/header parsing — trivially cheap to add to an existing crawl pass.

**Evidence produced:** "This site's robots.txt allows GPTBot (training) but its /.well-known/tdmrep.json reserves TDM rights with tdm-reservation: true and no tdm-policy URL — an explicit, standards-based signal that is likely to be honored by TDM-Act-compliant model providers and directly contradicts the training-permissive robots.txt signal. Separately, no Web Bot Auth key directory was found, so if this site's CDN [Cloudflare/Akamai — identified via headers] later enables signature enforcement, currently-unsigned AI agents would be edge-blocked with no robots.txt change required."

**False-positive risks:** Both protocols have low current adoption, so absence of either file is the overwhelmingly common (and often intentional/neutral) case, not a defect — findings should be framed as "not yet adopted" informationally rather than as a failure, except where an actual contradiction with robots.txt/llms.txt is detected.

**Complexity:** Low.

**Innovation score:** 9/10 · **Evidence strength:** 8/10 for TDMRep (finalized W3C Community Group spec with direct EU AI Act/CDSM linkage) and 7/10 for Web Bot Auth (active IETF work with real multi-vendor deployment, but still pre-RFC) · **Existing-capability overlap:** None — both protocols are entirely outside the PER-01–PER-08 file/directive set.

---

## 2. Tier B — Interesting Extensions

### B1. Template/Boilerplate Dilution via SimHash Fingerprint Clustering

**What it detects:** A site-wide pattern where a large fraction of "unique" pages are near-duplicates of each other at the SimHash/MinHash fingerprint level (Hamming distance below a small threshold) — thin templated pages (e.g., 500 near-identical location/city pages) that dilute the ratio of genuinely unique, citable content to boilerplate across the whole domain.

**Why it matters for AI systems:** SimHash (Charikar) and MinHash (Broder) are the exact techniques Google's own crawl infrastructure uses to identify and cluster near-duplicate content at web scale (Manku, Jain & Das Sarma, Google Research, WWW 2007), and near-duplicate clustering is a foundational input to both crawl-budget allocation and content-authority scoring in large-scale IR systems. Applied to a single site rather than the whole web, the same technique reveals a distinct failure mode: an AI system's dense retrieval index sees dozens of near-identical embeddings competing for the same query space, effectively canceling each other out rather than reinforcing topical authority, and a domain that is mostly template-cloned pages reads as low-value/spam-adjacent to any quality classifier trained on the same near-dup signal Google's own infrastructure uses.

**Why it is novel:** ENT-04 (canonicalization & duplicate content) checks whether `rel=canonical` tags are correctly declared for known duplicates. This computes actual *content-fingerprint* near-duplication across the whole crawled set — including duplicates the site owner never declared or realized exist — and reports it as a site-level dilution ratio, not a per-page tag-correctness check.

**Detection methodology:** Compute a 64-bit SimHash (feature-weighted shingles of extracted body text, following the Manku et al. methodology) for every crawled page. Cluster pages whose fingerprints differ by ≤3 bits (the threshold Google's own study found effective). Report the fraction of the domain's pages that fall into clusters of size >1, the average cluster size, and flag the largest clusters as candidates for consolidation/noindex.

**Required inputs:** Extracted clean body text for every crawled page.

**Implementation feasibility:** Pure Python/Node — 64-bit SimHash is a few dozen lines; clustering by Hamming distance is a nearest-neighbor problem solvable at small-to-medium site scale with brute-force or a simple LSH bucket scheme.

**Evidence produced:** "142 of 210 crawled pages (68%) cluster into 12 near-duplicate groups (Hamming distance ≤3), the largest containing 34 near-identical city-landing pages differing only in a place name — this is the same near-duplicate detection method Google's own crawl infrastructure uses, applied to your domain."

**False-positive risks:** Legitimate structured catalogs (product variants, localized pages with real content differences beyond a place name) can trigger this; the fingerprint should exclude boilerplate chrome (nav/footer) via the same boilerplate-separation logic as REN-07 before hashing, or the "duplicate" signal will just be measuring shared template, not shared unique content.

**Complexity:** Medium.

**Innovation score:** 6/10 · **Evidence strength:** 9/10 (SimHash/MinHash near-dup detection at web scale is one of the best-documented techniques in IR, directly from Google Research and Broder/Charikar's original papers) · **Existing-capability overlap:** Adjacent to ENT-04 but operates on content fingerprints rather than declared canonical tags — genuinely different detection surface (undeclared duplicates, not mistagged declared ones).

---

### B2. JSON-LD Graph Referential Integrity (Static-Analysis-Style Dangling-Reference Check)

**What it detects:** `@id` references and `sameAs`/property pointers inside a page's structured-data graph that point to nodes never actually defined anywhere in that graph (or in the crawled site's aggregate graph) — the structured-data equivalent of an undefined symbol in a compiled program.

**Why it matters for AI systems:** Knowledge-graph-grounded retrieval and entity resolution depend on being able to *walk* a JSON-LD graph to assemble a coherent entity (e.g., resolve an `Organization` node referenced by `@id` from a `Product` node's `brand` property). A dangling reference doesn't just fail schema validation (which ENT-01 already checks) — it silently breaks graph traversal for any consumer that tries to follow the pointer, producing an incomplete entity even though every individual JSON-LD block is independently well-formed and valid.

**Why it is novel:** ENT-01 checks presence/validity (does each block parse and conform to a Schema.org type) and ENT-03 checks markup/text agreement (does the markup match the visible page). Neither walks the *reference graph across blocks* to check that every `@id` a property points to actually resolves to a defined node — a classic static-analysis "undefined symbol" check adapted from compiler theory to structured data.

**Detection methodology:** Parse every JSON-LD block on a page (and, for a fuller pass, across the crawled site) into a node/edge graph keyed by `@id`. For every property value that is itself an `@id` reference (rather than an inline object or literal), check whether that `@id` is defined as a node somewhere in scope. Report dangling references, and separately report `sameAs` targets that 404/timeout when fetched (a live-link integrity check distinct from the dangling-internal-reference check).

**Required inputs:** All JSON-LD blocks from the crawled pages; for the `sameAs` live-check, a HEAD/GET on each external target.

**Implementation feasibility:** Pure JSON parsing and graph-building in Python/Node; no external tooling needed beyond a JSON-LD-aware traversal (standard `@context` expansion rules).

**Evidence produced:** "Your Product node's `brand` property references `@id: '#organization-1'`, but no node with that `@id` is defined anywhere on this page or elsewhere in the crawled site — an AI system trying to resolve the brand entity from this graph hits a dead pointer."

**False-positive risks:** Cross-page `@id` references are legitimate under JSON-LD/Schema.org conventions if the referenced node is defined on *another* page of the same site (or is a well-known external ontology `@id`) — the checker must search the full crawled-site graph, and whitelist known external vocabularies, before flagging as dangling.

**Complexity:** Medium.

**Innovation score:** 7/10 · **Evidence strength:** 6/10 (referential-integrity/static-analysis techniques are extremely well established in compiler theory; their application here is a reasonable, novel adaptation rather than a directly published technique for this exact object) · **Existing-capability overlap:** Adjacent to ENT-01/ENT-03 but checks graph connectivity, not per-block validity or text agreement.

---

### B3. IndexNow / Push-Indexing Protocol Adoption Audit

**What it detects:** Whether a site has adopted the IndexNow push-indexing protocol (a key file at `/{key}.txt` plus evidence of submission behavior) versus relying solely on passive crawl discovery — relevant because IndexNow-participating engines (Bing, Yandex, Naver, Seznam) feed directly into AI-answer surfaces, most notably Bing's index powering Microsoft Copilot and (per Bing's own indexing documentation) ChatGPT Search/DuckDuckGo's underlying result sourcing, making push-indexing latency a real, if indirect, AI-freshness lever that pure sitemap/crawl-based discovery (already covered by PER-08) cannot achieve.

**Why it matters for AI systems:** Traditional crawling is inherently pull-based and can take days to weeks to notice a change; IndexNow is explicitly a push protocol designed to collapse that to minutes, and because Bing's index is a documented upstream data source for several AI-answer products, a time-sensitive fact (price change, availability, breaking update) that would otherwise sit stale in an AI answer for days has a concrete, checkable mitigation path.

**Why it is novel:** PER-08 checks whether the *sitemap* is discoverable and consistent with llms.txt — a passive-discovery concern. This checks a completely separate, push-based protocol with a distinct key-file mechanism that PER-08 does not touch at all.

**Detection methodology:** Attempt to fetch a small set of conventionally-named key files (`{domain}/*.txt` pattern per protocol spec, or check `<meta name="indexnow-key">`) and confirm the key file's content matches the expected verification format. Cross-reference the sitemap's `lastmod` timestamps (PER-08 already parses these) against typical propagation-time expectations to flag sites with frequently-changing content but no push-indexing key present.

**Required inputs:** A small set of well-known-path fetches; sitemap `lastmod` data already parsed elsewhere.

**Implementation feasibility:** Trivial — a couple of HTTP GETs and string matching.

**Evidence produced:** "No IndexNow key file detected. Your sitemap shows 40 URLs with lastmod timestamps in the past 7 days, but with no push-indexing mechanism in place, Bing (and by extension Bing-fed AI surfaces) will discover these changes only on its next passive crawl pass rather than within minutes."

**False-positive risks:** Absence doesn't prove non-participation (some CMS/host platforms submit IndexNow pings server-side without a discoverable client-side key artifact); frame as "not verifiably adopted" rather than "not adopted."

**Complexity:** Low.

**Innovation score:** 5/10 · **Evidence strength:** 6/10 (protocol and Bing-to-Copilot pipeline are well documented; the specific "feeds ChatGPT Search" claim rests on secondary sourcing, not an OpenAI-published statement) · **Existing-capability overlap:** Low — distinct file/mechanism from PER-04/PER-08, though thematically adjacent (discovery speed).

---

### B4. Common Crawl CDX Footprint Audit (Training-Corpus Presence Proxy)

**What it detects:** Whether a domain's pages actually appear in the public Common Crawl corpus — one of the most widely used open pretraining data sources for LLMs — via the free CDX Server API, as a rough, falsifiable proxy for "has this content had any chance of being seen by open pretraining pipelines."

**Why it matters for AI systems:** Common Crawl is a named, documented upstream input to many LLM pretraining corpora, and its CDX index (`index.commoncrawl.org`) is a fully public, queryable record of exactly which URLs, at which timestamps, with which HTTP status, were captured. A domain entirely absent from recent Common Crawl snapshots has categorically failed the most basic upstream gate that a large share of open pretraining pipelines depend on — a distinct, checkable fact from "did OAI-SearchBot/GPTBot crawl me" (PER-01 checks the *permission*, not the *outcome* recorded in a third-party, publicly auditable corpus).

**Why it is novel relative to the existing set:** Nothing in PER-01–PER-08 queries an external, independently-operated corpus to verify actual historical crawl *outcome* rather than *permission*. (Note: this specific technique is beginning to appear in GEO blog content, so it is flagged as moderate rather than maximal novelty — its value here is as a cheap, hard-evidence cross-check that most tooling still doesn't implement, not as an undiscovered idea.)

**Detection methodology:** Query `index.commoncrawl.org/{latest-collection}-index?url={domain}/*&output=json` (and optionally 2–3 recent monthly collections) via the public CDX API. Parse returned capture records (URL, timestamp, HTTP status, MIME type). Report the fraction of known site URLs (from the sitemap) found in the index, the recency of the most recent capture, and whether captures are `status:200` (successfully archived) vs. blocked/errored.

**Required inputs:** Domain name/URL list (from sitemap); public CDX API responses (no auth required, rate-limit conscious).

**Implementation feasibility:** A handful of HTTP GETs to a public, free, well-documented API and JSON parsing — no infrastructure of our own required.

**Evidence produced:** "0 of 40 sitemap URLs found in the 3 most recent Common Crawl monthly collections. Given Common Crawl's role as a widely-used open pretraining source, this domain has had no confirmed opportunity to be captured by pipelines that depend on it — worth checking robots.txt's CCBot directive (already covered elsewhere) and server logs for CCBot visits."

**False-positive risks:** Presence/absence in Common Crawl says nothing about proprietary crawlers (GPTBot, ClaudeBot, etc., audited separately) or about whether a given model's *training set* actually included the captured pages after filtering — must be framed as an upstream-opportunity proxy, explicitly not proof of training inclusion or exclusion.

**Complexity:** Low.

**Innovation score:** 5/10 · **Evidence strength:** 8/10 (Common Crawl's role as a real pretraining input and the CDX API's public, documented nature are both well established) · **Existing-capability overlap:** Low-moderate — related in spirit to PER-01 (crawler access) but checks a completely different, third-party, outcome-based data source rather than the domain's own robots.txt.

---

### B5. Edge-Cache Staleness Skew for Bot vs. Browser Traffic

**What it detects:** Whether a CDN/edge cache serves a measurably *older* cached representation (via `Age`, `Last-Modified`, `ETag` comparison across repeated requests) to requests identified as AI-crawler traffic than to requests presenting as an ordinary browser — an unintentional "cache-based staleness skew" distinct from deliberate cloaking, where AI agents systematically see out-of-date content purely as a side effect of cache-key/`Vary` configuration.

**Why it matters for AI systems:** If `Vary` doesn't include `User-Agent` (or the CDN buckets bot traffic into a lower cache-priority tier), a page that was just updated for human visitors can continue serving a stale edge copy specifically to crawler traffic for longer, because bot requests are deprioritized for cache-refill scheduling at many CDNs. This produces a real, measurable content-freshness gap between what a human sees and what an AI system ingests — directly relevant to CQ-10-style freshness concerns, but caused by *infrastructure*, not *authoring*, and therefore invisible to any content-level audit.

**Why it is novel:** REN-05 (real-time availability exposure) and CQ-10 (temporal freshness/contradiction) both look at the *content itself* for freshness signals. This looks at *edge infrastructure behavior* — comparing `Age`/`ETag`/`Last-Modified` headers returned across paired requests sent with a documented AI-crawler user-agent versus a standard browser user-agent, to detect a caching-layer-induced skew that exists regardless of what the content itself says.

**Detection methodology:** Issue paired requests to the same URL — one with a standard browser UA, one with a documented AI-crawler UA (e.g., GPTBot, ClaudeBot) — in quick succession, respecting robots.txt permission for that UA. Compare `Age`, `ETag`, and `Last-Modified` headers/values. A materially larger `Age` or an older `ETag`/`Last-Modified` on the bot-UA response indicates the crawler is being served a staler cache tier.

**Required inputs:** Two fetches per sampled URL with different UA strings; response headers only.

**Implementation feasibility:** Straightforward HTTP header comparison; no rendering required. Must be UA-string-based only (per hard constraints — no browser automation), and must only test UAs the site's robots.txt actually permits.

**Evidence produced:** "Requesting this URL with a browser UA returns `Age: 12`, `Last-Modified: 09:41 today`. The identical URL requested with the GPTBot UA (permitted by robots.txt) returns `Age: 41,382` (~11.5 hours), `Last-Modified: yesterday 22:03` — this AI crawler is measurably being served an older cached version than a human visitor."

**False-positive risks:** Natural cache-timing jitter (two requests hitting different edge POPs, or landing just before/after a scheduled refresh) can produce a spurious one-off gap; the check should sample multiple times/URLs before concluding a systematic skew rather than a random timing artifact, and should account for legitimate CDN behavior that intentionally caches known-bot traffic more aggressively for load-shedding reasons (which is a real trade-off, not necessarily a "bug").

**Complexity:** Low–Medium.

**Innovation score:** 7/10 · **Evidence strength:** 5/10 (HTTP caching semantics and `Vary`/`Age` behavior are well-specified in RFC 9111, but the *specific claim* that CDNs commonly deprioritize bot-traffic cache refills is an inference from general CDN engineering practice rather than a directly cited study) · **Existing-capability overlap:** Low — distinct mechanism (infra-level cache skew) from REN-05/CQ-10 (content-level freshness signals).

---

### B6. Content-Negotiation Fidelity Test (Beyond `.md` File Existence)

**What it detects:** Whether a server actually *honors* `Accept`-header content negotiation (returning a genuinely different representation — markdown, JSON, plain text — when an AI client requests it via `Accept:`) versus merely hosting a separate `.md` file at a hand-maintained parallel URL that can silently drift out of sync with the canonical HTML.

**Why it matters for AI systems:** PER-07 checks whether a `.md` variant *exists at all*. This is a distinct and complementary check: real HTTP content negotiation (`Vary: Accept`, proper `406`/`300` handling, or actually returning `text/markdown`/`application/json` bodies keyed off the `Accept` header on the *same* canonical URL) is architecturally more robust than a hand-maintained parallel file, because it can't drift — there's only one content source with multiple serializations. Many AI fetchers and MCP-style tools increasingly send explicit `Accept` preferences; a server that ignores them and always returns full HTML regardless of what was requested forces every such client into the more failure-prone rendering/boilerplate-stripping path even when it explicitly asked for a clean format.

**Why it is novel:** PER-07 is a URL-existence check ("is there a `.md` file"). This is a protocol-behavior check ("does the server's actual negotiation logic work, and does it agree with the `.md` file if both exist") — different failure surface (a stale/drifted parallel file vs. broken negotiation is a specific, useful finding neither existing check catches).

**Detection methodology:** Send the same canonical URL multiple times with different `Accept` headers (`text/html`, `text/markdown`, `application/json`). Compare returned `Content-Type` and body. If a separate `.md` file also exists (per PER-07), diff its content against what negotiation (if any) returns, and flag disagreement as a sync-drift risk.

**Required inputs:** Multiple fetches of the same URL with varied `Accept` headers.

**Implementation feasibility:** Pure HTTP header manipulation, no new infrastructure.

**Evidence produced:** "Requesting this URL with `Accept: text/markdown` returns identical `text/html` content with no `Vary` header — content negotiation is not implemented. A separately maintained `/page.md` exists but its content diverges from the current HTML by an estimated 18% (last updated 3 months ago vs. the HTML page updated last week) — the parallel-file approach has drifted out of sync."

**False-positive risks:** Many legitimate sites intentionally don't implement negotiation and instead rely solely on the parallel-file approach, which is a valid (if more failure-prone) strategy — absence of negotiation shouldn't be scored as a failure on its own, only the *drift* finding (when both exist and disagree) is a genuine defect.

**Complexity:** Low.

**Innovation score:** 5/10 · **Evidence strength:** 6/10 (HTTP content-negotiation semantics are a mature, well-specified mechanism — RFC 9110 — even though its specific application to AI-fetcher `Accept` preferences is emerging) · **Existing-capability overlap:** Moderate — directly complementary to PER-07 but tests protocol behavior/drift rather than file existence.

---

### B7. URL Semantic Entropy vs. Agentic Navigability

**What it detects:** URL structures with high information-theoretic entropy (opaque hashed IDs, database keys, session-like tokens) versus low-entropy, semantically predictable slugs — measured as a proxy for whether an autonomous browsing agent could plausibly *construct* a correct URL by pattern inference (e.g., inferring `/products/wireless-mouse` from context) rather than needing to discover it via an explicit link or search result.

**Why it matters for AI systems:** Agentic browsing increasingly involves tool-use loops where an agent hypothesizes a URL based on a pattern it has seen elsewhere on the site (or in training data) and attempts a direct fetch before falling back to search/navigation — a documented pattern in web-agent tool-use research and a practical efficiency path real agent frameworks exploit. A site whose URLs are entirely opaque (`/p/8f3ac21e`) offers zero such shortcut and forces every access through discovery/search, while a site with predictable semantic slugs is directly navigable by inference — a genuinely different, information-theoretic property of the URL space itself, not of any single page's content.

**Why it is novel:** No item in the existing set evaluates the URL *namespace's* predictability as a standalone signal — this treats the set of URLs as a corpus and computes an entropy measure over it, an information-theory technique borrowed from data compression / language modeling and applied to URL-path tokens rather than page content.

**Detection methodology:** Tokenize the path segments of all crawled URLs (split on `/`, `-`, `_`). Compute normalized Shannon entropy per path-segment position across the URL corpus (e.g., position 2 in `/products/{x}` — is `{x}` low-entropy human-readable slugs or high-entropy opaque tokens?). Report an aggregate "navigability score" and flag specific high-traffic sections (per internal-link centrality, reusing CIT-08 graph data) that use opaque IDs, since those are the sections where predictable slugs would most help agentic shortcut-navigation.

**Required inputs:** The full list of crawled URLs; no additional fetching.

**Implementation feasibility:** Pure string/entropy computation — trivial in Python/Node (`collections.Counter` + log2 arithmetic).

**Evidence produced:** "83% of product-detail URLs use opaque 8-character hex IDs (entropy 3.9 bits/char, near-random) rather than semantic slugs. An agent that has seen '/products/wireless-mouse' patterns elsewhere on similar sites cannot productively guess this domain's URLs and must rely entirely on discovered links or search — increasing dependence on your internal link graph (see AI-Reachable Subgraph Orphan Detection) for every access."

**False-positive risks:** Opaque IDs are often a deliberate, reasonable engineering choice (avoiding enumeration, supporting renames without breaking links) — this should be framed as a navigability trade-off finding, not a defect, and weighted by whether the site's actual link graph already provides adequate discovery paths (making URL guessability moot).

**Complexity:** Low.

**Innovation score:** 6/10 · **Evidence strength:** 4/10 (information-theoretic entropy is rigorous and well established in general, but the specific claim that agentic browsers meaningfully rely on URL-guessing as a discovery shortcut is a reasonable but not yet directly studied inference) · **Existing-capability overlap:** Low — no existing item evaluates URL-namespace predictability as an aggregate corpus property.

---

## 3. Considered and rejected (to show the filter working)

For transparency, several adjacent-field ideas were explored and set aside because they collapsed into substantial overlap with the existing set, or failed the evidence-quality/false-positive bar:

- **AI-generated-content/stylometric "content farm" detection** (perplexity/burstiness analysis adapted from GPTZero-style detectors, applied across multiple "authors" on a domain) — explored under authorship-attribution literature, but public AI-text detectors are documented to have unreliable false-positive rates even in their home domain; adapting an already-shaky signal to a *new* domain (detecting programmatic content farms specifically) would inherit that unreliability and violate the evidence-quality/false-positive-safety bar this backlog is scored against. Noted here rather than promoted to a full candidate.
- **HTTP `Content-Digest`/`Repr-Digest` (RFC 9530) provenance readiness** — a real, standards-track mechanism (published Feb 2024) for cryptographically verifying that retrieved content matches what a citation claims to reference, directly relevant to CIT-02/CIT-03 citation precision. Current real-world adoption is close to zero, making it a forward-positioning signal rather than a presently-actionable finding; kept as a one-line honorable mention rather than a full Tier A/B entry.
- **Wayback Machine crawl-frequency as an external-importance proxy** — collapses substantially into CIT-13 (off-site corroboration) and B4 (Common Crawl footprint); the marginal signal beyond those two was not distinct enough to justify a separate entry.
- **Query rewriting/fan-out coverage** — on inspection, this is materially the same signal as existing RET-02 (dense/semantic coverage & synonym variation) and RET-03 (query-intent coverage) once you account for the fact that query rewriting mostly generates synonym/paraphrase variants of the same intent; not included to avoid double-counting.

## 6. Source list (representative, non-exhaustive)

- Liu, N. F. et al. "Lost in the Middle: How Language Models Use Long Contexts." 2023. arXiv:2307.03172.
- Hsieh, C.-Y. et al. "Found in the Middle: Calibrating Positional Attention Bias Improves Long Context Utilization." 2024. arXiv:2406.16008.
- Hong, K., Troynikov, A., Huber, J. "Context Rot: How Increasing Input Tokens Impacts LLM Performance." Chroma Technical Report, July 2025.
- CoRAG (coreference-resolution preprocessing for RAG). 2025 AIITA Conference (IEEE Xplore).
- "CLAP: Coreference-Linked Augmentation for Passage Retrieval." arXiv:2508.06941.
- "From Ambiguity to Accuracy: The Transformative Effect of Coreference Resolution on RAG Systems." ACL SRW 2025. arXiv:2507.07847.
- Manku, G. S., Jain, A., Das Sarma, A. "Detecting Near-Duplicates for Web Crawling." Google Research / WWW 2007.
- Broder, A. Z. et al. "Syntactic Clustering of the Web." 1997 (MinHash origin).
- Charikar, M. "Similarity Estimation Techniques from Rounding Algorithms." 2002 (SimHash origin).
- IETF Web Bot Auth Working Group; draft-meunier-webbotauth-httpsig-protocol; RFC 9421 (HTTP Message Signatures). Akamai and Cloudflare engineering blogs on deployment.
- W3C TDM Reservation Protocol Community Group Final Report, tdmrep.org / w3c-cg/tdm-reservation-protocol.
- IndexNow protocol documentation (Bing Webmaster Tools); Microsoft/Yandex joint announcement.
- Common Crawl CDX Index Server documentation (index.commoncrawl.org).
- RFC 9530 (Digest Fields — Content-Digest/Repr-Digest), RFC 9111 (HTTP Caching).
- Zscaler ThreatLabz, "Indirect Prompt Injection in Web Content Targets AI Agents," 2026; Unit 42 (Palo Alto Networks), "Fooling AI Agents: Web-Based Indirect Prompt Injection Observed in the Wild"; Forcepoint X-Labs indirect-prompt-injection payload research; Greshake et al., foundational indirect-prompt-injection formulation.
- Third-party crawl-log engineering analyses of GPTBot/ChatGPT-User/OAI-SearchBot/ClaudeBot/PerplexityBot redirect and timeout behavior (implicator.ai, captaindns.com, menra.ai) — flagged throughout as observational/engineering-grade rather than vendor-certified evidence.
