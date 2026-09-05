
 Cycle 23 — Extension Selection & Implementation Roadmap

 Context

 brand-ai-readiness-audit (v0.23.0, 8 skills, 58/89 capabilities implemented) was built under a
 hard "stdlib only" constraint. That constraint is now relaxed: third-party packages are allowed
 provided they are vendored into the submission zip (≤50 MB total, no install step at grade
 time, no pre-trained model weights). research3.md catalogues 20+ candidates and names specific
 packages for many of them (rapidfuzz, networkx, httpx, tldextract, datasketch, pysbd).

 This plan answers two questions: which of those packages actually ship, and what gets built
 in cycle 23 now that the blocker is gone.

 The headline result of the selection pass: the relaxation buys almost nothing in code. Every
 package that would have added a capability stdlib lacks is either platform-locked (breaks on a
 grader that isn't Linux/x86_64/CPython 3.14), drags in a compiled transitive dependency, or is
 strictly worse than something this repo already has. The relaxation's real yield is one data
 asset — the Public Suffix List — plus the freedom to stop treating "no packages" as the reason
 several capability rows stayed blocked. Those rows were never really blocked on packages; they
 were blocked on missing infrastructure (page sampling, a shared fetch layer, a budget governor),
 which is where cycle 23's effort belongs.

 Current zip is 276 KB, so the 50 MB ceiling is not a binding constraint anywhere in this plan.
 The binding constraints are cross-platform portability and the 5-minute runtime budget.

 ---

 Part 1 — Extension selection

 Verdict: adopt zero third-party code packages; vendor one data asset

 Every verdict below is from a wheel actually downloaded and inspected during planning, not from
 package metadata read second-hand.

 Package: rapidfuzz
 research3.md says: A9, B3, B4, B9, C1
 Wheel observed: rapidfuzz-3.14.6-cp314-cp314-manylinux_2_28_x86_64.whl
 Verdict: Reject. Platform and interpreter locked. A vendored copy runs only on Linux/x86_64/CPython 3.14. The documented pure-Python fallback is not what pip resolves
 and is not a supported shipping mode.
 ────────────────────────────────────────
 Package: lxml / selectolax
 research3.md says: (not named; considered)
 Wheel observed: cp314-manylinux… (5.2 MB / 2.4 MB)
 Verdict: Reject. Same lock.
 ────────────────────────────────────────
 Package: charset-normalizer
 research3.md says: (not named; considered)
 Wheel observed: cp314-manylinux…
 Verdict: Reject. Same lock.
 ────────────────────────────────────────
 Package: datasketch
 research3.md says: D3
 Wheel observed: py3-none-any (107 kB)
 Verdict: Reject. Requires-Dist: numpy, scipy — both compiled and huge. MinHash/LSH's sub-linear advantage is irrelevant at this project's N (dozens of findings).
 ────────────────────────────────────────
 Package: tldextract
 research3.md says: B2
 Wheel observed: py3-none-any (106 kB)
 Verdict: Reject. Requires-Dist: idna, requests, requests-file, filelock — requests pulls charset-normalizer (compiled). Also fetches a live PSL on first use, which
 fails in a sandbox. Vendor the PSL data instead.
 ────────────────────────────────────────
 Package: httpx
 research3.md says: D2
 Wheel observed: py3-none-any (73 kB)
 Verdict: Reject. Requires-Dist: anyio, certifi, httpcore, idna (+ sniffio, typing-extensions transitively) — six vendored packages for zero capability urllib.request
 lacks here. D2's value is the shared bundle, not the client.
 ────────────────────────────────────────
 Package: networkx
 research3.md says: A6, B1, B8
 Wheel observed: py3-none-any (2.1 MB)
 Verdict: Reject. Requires-Python: !=3.14.1,>=3.11 imposes a hard Python floor on the whole submission; 505 ms import measured. Buys ~45 lines of union-find + PageRank
 power iteration on graphs of ≤30 nodes.
 ────────────────────────────────────────
 Package: pysbd
 research3.md says: D5
 Wheel observed: py3-none-any (71 kB, zero deps, MIT, 35 ms)
 Verdict: Reject — the cleanest package in the set, and still not worth it. shared/text_spans.py:359 split_sentences was tested against pysbd's own hard cases and
 segments all of them correctly: "Founded in the U.S. in 2010.", "It raised $4.5 million from Acme Inc. and others.", "Dr. Smith joined in Jan. 2011.". D5 is a
 consolidation problem, not a package problem — see Phase 0.
 ────────────────────────────────────────
 Package: beautifulsoup4
 research3.md says: (not named; considered)
 Wheel observed: py3-none-any (109 kB) + soupsieve + typing-extensions, all pure, 278 ms
 Verdict: Reject. With no lxml/html5lib available it falls back to the html.parser backend — the same parser the repo's existing HTMLParser subclasses already use
 (shared/text_spans.py:151, check_entity.py:134). Identical parse fidelity; the only gain is CSS selectors, at the cost of two parsing idioms coexisting across 10k
 shipped lines. Net hygiene regression.
 ────────────────────────────────────────
 Package: Public Suffix List
 research3.md says: B2 (via tldextract)
 Wheel observed: public_suffix_list.dat, 328 KB, MPL-2.0
 Verdict: Adopt. Data, not code. Zero portability risk, zero import cost. Unblocks correct registrable-domain grouping for ENT-07.

 Why "zero packages" is the right posture, stated once

 The rubric scores skill-format/engineering hygiene and generalization. A vendored package that
 silently fails to import on the grader's machine converts a working check into an unknown — or,
 worse, a traceback — on a run we never get to observe. Every rejected package above was rejected
 because it either carries that risk or delivers something we can write in under 60 tested lines.
 The two we would have adopted for real capability (rapidfuzz, charset-normalizer) are exactly
 the two that are platform-locked.

 The vendoring contract (established now, for the PSL and anything later)

 Even one data asset needs the discipline, and establishing it now means a future package decision
 is a one-file change rather than a re-litigation.

 - vendor/ at the marketplace root, sibling to shared/.
 - vendor/public_suffix_list.dat — pinned snapshot, not fetched at runtime.
 - vendor/VENDORED.md — for each asset: name, upstream URL, version/snapshot date, license,
   SHA-256, and the capability rows that depend on it.
 - vendor/LICENSE-public-suffix-list.txt — MPL-2.0 text, alongside the repo's own MIT LICENSE.
 - scripts/build_submission_zip.sh gains vendor in its zip -r argument list.
 - Consumption is via shared/public_suffix.py, which loads the .dat lazily and degrades to a
   documented two-label heuristic with a confidence: low note if the file is missing — never
   raises.
 - If a code package is ever added: it must be py3-none-any, vendor/ must contain no .so
   or .pyd, and its import must be try/except ImportError guarded into an UnknownCheck.

 Critical files: brand-ai-readiness-audit/scripts/build_submission_zip.sh,
 brand-ai-readiness-audit/tests/test_marketplace_manifest.py.

 Test changes this forces

 tests/test_marketplace_manifest.py:128 test_scripts_import_no_third_party_packages keeps an
 explicit allowed_roots allowlist. It must gain the new shared/ module names
 (page_fetch, page_sample, budget, graph_metrics, fuzzy_match, shingles,
 public_suffix) plus the stdlib roots the new code uses (math, itertools, xml, os).
 The test's glob must also cover shared/*.py generically instead of its current hardcoded
 three-file list, so a new shared module cannot slip past it.

 Add one new test to the same SafetyTests class: vendor/ contains no compiled artifact and
 no .py file — i.e. the zero-code-packages posture is enforced, not just documented. If a
 future cycle adopts a package, that test is where the decision gets recorded.

 ---

 Part 2 — Stdlib micro-modules replacing the rejected packages

 Each is a new file under shared/, each with a unit-test file under tests/, each following the
 existing shared/ conventions: pure functions, no network, no file I/O except where noted,
 dataclass returns, module docstring stating the contract (see shared/text_spans.py:1-30 for the
 house style).

 ┌─────────────────────────┬────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────┬──────────────┐
 │         Module          │  Replaces  │                                                 Contents                                                  │    Serves    │
 ├─────────────────────────┼────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────┤
 │ shared/graph_metrics.py │ networkx   │ Union-find connected components; degree; PageRank by power iteration (damping 0.85, ~20 iterations,       │ A6, B1, B8   │
 │                         │            │ converges instantly at N≤30)                                                                              │              │
 ├─────────────────────────┼────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────┤
 │ shared/fuzzy_match.py   │ rapidfuzz  │ token_sort_ratio and partial_ratio over difflib.SequenceMatcher; single-linkage clustering at a threshold │ A9, B3, B4,  │
 │                         │            │                                                                                                           │ C1           │
 ├─────────────────────────┼────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────┤
 │ shared/shingles.py      │ datasketch │ k-shingle sets, Jaccard similarity, pairwise near-duplicate grouping                                      │ B6, D3       │
 ├─────────────────────────┼────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────┼──────────────┤
 │ shared/public_suffix.py │ tldextract │ PSL parse (incl. wildcard *. and exception ! rules), registrable_domain(host), same_entity(a, b)          │ B2           │
 └─────────────────────────┴────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────┴──────────────┘

 difflib is already in the allowed_roots allowlist and is fast enough: the largest comparison
 set in this project is a bounded page sample of ~30, i.e. ~450 pairwise comparisons.

 ---

 Part 3 — Cycle 23 roadmap

 Ordered by dependency. Phases 1–2 are the actual unlock; everything after depends on them.
 Every new detection capability follows the shipped pattern: Finding/UnknownCheck from
 shared/finding_contract.py, deterministic IDs via the existing _stable_slug, a corpus fixture
 under tests/corpus/<cluster>/, and a measure_*.py precision/recall harness.

 Phase 0 — Hygiene, no dependencies (do first, it's cheap)

 - D5 — sentence-splitter consolidation. Three skill scripts carry an independent
   _split_sentences that is a naive re.split(r"(?<=[.!?])\s+|\n+", …):
   check_citability.py:265, check_retrieval_readiness.py:641, check_content_quality.py:217.
   All three mis-split on U.S., Inc., Jan. — which skews every percentile- and
   position-based finding downstream of them. Replace all three with
   shared/text_spans.split_sentences, returning [s.text for s in ...] at the call sites to
   preserve the existing list[str] signature. The RET docstring's "independently-runnable-skill
   convention" rationale no longer holds: shared/ is already a hard runtime dependency of every
   script via sys.path.insert.
 - Add the golden abbreviation cases to tests/test_text_spans.py so the fix is pinned.

 Phase 1 — Infrastructure (INF-01, INF-02, INF-04, INF-10)

 This is the highest-leverage work in the cycle and needs no packages at all.

 - shared/page_sample.py (D1 / INF-01) — template-stratified sitemap sampling.
   Today, page selection is a prose instruction to the LLM in
   skills/audit-orchestrator/SKILL.md ("pick a small, representative sample of pages that carry
   claims worth getting right"). That is precisely the interest-biased selection that research3.md
   identifies as having silently disabled near-duplicate detection (B6) — the check can't find
   duplicate clusters because the sampler never picks two members of one.
   Implementation: parse sitemap URLs (reuse the loader behind check_entity.py:1329 audit_sitemap),
   normalize each path's numeric/UUID/slug segments to a wildcard to derive a template key, cluster
   by key, then allocate a fixed budget (default 25) proportionally with a floor of ≥1 per stratum,
   force-including the homepage and any process page (/contact, /checkout, /search, /pricing).
   Emit the sample as JSON so every skill consumes the same list.
   Orchestrator SKILL.md changes from "pick a sample" to "run the sampler, then iterate its output".
 - shared/page_fetch.py (D2 / INF-02, INF-04) — PageBundle + one-fetch cache.
   fetch_page_html currently exists in six near-identical copies
   (check_engagement.py:935, check_content_quality.py:1042, check_entity.py:1297,
   check_citability.py:758, check_static_extraction.py:1542,
   check_retrieval_readiness.py:1813), each with its own decode_content_encoding and its own
   USER_AGENT/FETCH_TIMEOUT_SECONDS. Consolidate into one module exposing an immutable
   PageBundle (raw bytes, decoded HTML, response headers, final URL after redirects, extracted
   blocks, JSON-LD blocks, links) with an in-process URL cache. Keep urllib.request; keep the
   existing gzip/deflate handling and the deliberate ValueError on br (tests/test_gzip_decoding.py:87).
   check_perimeter.py keeps its own fetch path — it deliberately varies User-Agent per
   AI-crawler and must not share a cache keyed on URL alone.
   This is a pure refactor: tests/test_gzip_decoding.py already imports decode_content_encoding
   from every module and is the regression net.
 - shared/budget.py (D4 / INF-10) — stage budget + coverage ledger.
   Monotonic-clock caps per pipeline stage; on breach, emit a typed UnknownCheck per unreached
   capability naming the cap as the reason, rather than dropping coverage silently. Attach a
   coverage manifest to the report via finding_contract.build_report. Precondition for every
   multi-page check below being safe to ship inside 5 minutes.

 Phase 2 — New capabilities, single-page, zero new infrastructure

 Cheap, high-evidence, independent of Phase 1. Can proceed in parallel.

 - A5 → new PER-* row: RFC 9727 API catalog. GET /.well-known/api-catalog, validate
   Content-Type: application/linkset+json, parse anchor/service-desc. Highest
   evidence-strength in the backlog (the RFC fixes path and MIME exactly, so a malformed response
   is unambiguous). Lands in check_perimeter.py beside the existing well-known probes.
 - A2 + A8 + C2 → closes EN-09 (PARTIALLY_COVERED): machine-readable action availability.
   Two detectors, one row: (a) potentialAction/EntryPoint/ReserveAction/OrderAction in
   JSON-LD (reuse shared/jsonld_graph.py flatten + iter_references); (b) static text scan of
   inline <script> and same-origin .js for WebMCP signatures (navigator.modelContext.registerTool)
   and declarative toolname/tooldescription form attributes. Cross-reference: a form with no
   WebMCP attribute but a matching potentialAction endpoint is fine. Report the WebMCP half as a
   proactive suggestion only — it is a draft spec, not a defect. Extends the shipped
   unlabeled-form-field check in check_engagement.py.
 - A3 → new PER-* row: AI-crawler content-parity diff (cloaking). Fetch each sampled page
   twice back-to-back from the same session — browser UA, then 2–3 real AI-crawler UAs — and diff
   status, byte length, visible text (via text_spans.extract_blocks), and JSON-LD presence. Flag
   when the crawler version is missing content the browser version has. check_perimeter.py
   already varies User-Agent per crawler (check_perimeter.py:675), so the fetch machinery exists;
   this adds the diff. Genuinely novel axis — same permission, different payload.
 - B7 → closes the single-page half of CQ-10: freshness self-contradiction. Compare a visible
   "Last updated"/"As of" string or JSON-LD dateModified against the HTTP Last-Modified header.
   check_perimeter.py:1809 fetch_page_with_headers already captures headers for PER-09.
   Cap at Medium confidence and cross-check ETag — some CDNs report request time.
 - A6 → new ENT-* row: JSON-LD entity-graph fragmentation. Build a graph from already-parsed
   JSON-LD (nodes by @id/type, edges from iter_references), run   graph_metrics.connected_components and degree. Flag ≥2 substantial components, or an
   graph_metrics.connected_components and degree. Flag ≥2 substantial components, or an
   Organization node with degree ≤1. Gate to fire only at ≥5 entities. Distinct from the shipped
   referential-integrity check, which catches broken @id refs; this catches a valid but
   disconnected graph.

 Phase 3 — Engagement grounding (depends on Phase 1 sampling)

 - C1 → closes EN-11 (content-to-action coherence) and the EN-08 findability slice:
   information-scent link/CTA coherence. Grounds the EN cluster — the rubric's weaker half, and
   the only cluster authored rather than research-derived — in Information Foraging Theory
   (Pirolli & Card 1999, Psychological Review 106:643–675), which all three research sources
   converged on independently. Cite it in the SKILL.md the same way the retrieval cluster cites
   "Lost in the Middle".
   Implementation: extract internal anchor text and each page's primary CTA from the bounded
   sample; score lexical overlap between cue text and the target's title/H1/topic terms
   (fuzzy_match.token_sort_ratio, or plain stemmed Jaccard — measure both against the corpus and
   keep the better one). The script narrows candidates only; low-overlap pages go to the LLM
   judge with a written rubric asking whether a page-specific cue exists nearby that the lexical
   score missed. Ship agent-judged, capped at Medium severity — generic brand-voice CTAs are
   common and not always defects. Follows the existing agent_judgement_required pattern
   (EN-01/EN-03, CQ-01/02/04/09/12).

 Phase 4 — Multi-page capabilities (hard-depends on Phase 1)

 - B6 → near-duplicate / template dilution. Was rejected for a sampling reason, not a
   technique reason. With Phase 1's stratified sampler, near-identical pages co-land in a stratum;
   run shingles.jaccard within strata on extracted main-content text only (excluding template
   chrome) to avoid flagging legitimate SKU variants.
 - B2 → closes ENT-07: cross-domain service attribution. Extract outbound links from the
   sample; keep domains that recur and look service-related (support/help/docs/status);
   group by public_suffix.registrable_domain; fetch each candidate's homepage once and check for
   a sameAs/Organization bridge back. Reuses the shipped off-site fetch path
   (check_entity.py:1371 fetch_offsite_pages, check_citability.py:813). The one capability
   that genuinely needed the vendored PSL.
 - B3 → closes ENT-08's address half (phone half already ships via REN-10). Extract address
   candidates (postal-code + street-suffix heuristics) across the sample, cluster with
   fuzzy_match, flag disagreement — but only after an explicit "multiple locations" language
   check, which is the dominant false positive.
 - B4 → closes CQ-10's cross-page half. Within same-template strata, extract typed facts
   (prices, dates, counts) near matching labels; flag identical-label/different-value collisions.
   High threshold plus agent-judge on survivors; per-SKU variation is the dominant false positive.
 - B1 + B8 → closes EN-04 and the CIT-08 slice: link-authority starvation and dead ends.
   Build a directed graph from sampled internal links; graph_metrics.pagerank and in-degree.
   Adopt the minority objection's discipline even while implementing the majority view: a
   PageRank over a bounded, template-stratified subgraph is a systematically biased estimate of
   site-wide authority, because pages reachable only via pagination or deep facets are structurally
   excluded — and that exclusion correlates with the very starvation being measured. Therefore:
   cap severity at Medium, and make every such finding state its sample coverage in its own
   evidence string ("within the 25 pages sampled…"). Never let the finding claim site-wide scope.
   The dead-end half (B8a: zero internal outbound links and no CTA) carries no such bias and can
   be stated plainly.
 - B5 → closes CIT-09: comparison-content gap. Zero-crawl lexical scan of sitemap slugs and
   titles for vs/versus/alternative to/compared to. Proactive-suggestion track only —
   absence proves nothing.

 Explicitly not doing (record in docs/capability-matrix.md with these reasons)

 - A11 OpenIE triple extraction and B11 REN-09 image-of-text OCR — re-confirmed blocked
   independently of the package relaxation. Both require pre-trained model weights (statistical
   parsers; Tesseract v4+ LSTM .traineddata), which the guardrail bans outright. Tesseract also
   needs a system binary outside the Python ecosystem entirely.
 - B10 full-scope orphan detection — the full-crawl form needs inbound-link breadth no bounded
   sample can honestly approximate. The bounded version is B1/B8, with the caveat above.
 - B9 CIT-11 hearsay provenance — stays DEFERRED. A fuzzy prefilter solves the matching
   problem but not the judgment problem; the target is inherently paraphrastic and candidate
   generation collides with the runtime budget.
 - B12 EN-10 — stays rejected, absorbed by C1's information-scent framing.
 - D3 findings dedup (INF-08) — build shared/shingles.py for B6 regardless, but hold the
   cross-skill merge until a real duplicate appears in a composed report. The project checked twice
   across four real reports and found none; re-check after Phase 4 adds overlapping capabilities.
 - D6 evidence-strength confidence scoring (INF-07) — defer to cycle 24. It completes existing
   infrastructure but adds no detection, and Phase 1 already consumes the infrastructure budget.

 ---

 Verification

 Run at each phase boundary, from brand-ai-readiness-audit/:

 1. Full suite — python3 -m unittest discover -s tests -v. Baseline is 662 passing; nothing
    may regress. tests/test_gzip_decoding.py and tests/test_marketplace_manifest.py are the
    two that will fail loudly if Phase 1's refactor or the vendor/ addition is done wrong.
 2. Constraint gates specifically — python3 -m unittest tests.test_marketplace_manifest -v.
    Must pass with the extended allowed_roots, the generalized shared/*.py glob, and the new
    "vendor contains no code" test.
 3. Detection quality — the tests/measure_*.py harnesses against tests/corpus/. Every new
    capability ships with corpus fixtures for both a true positive and its dominant false positive
    (the FP fixture is not optional — it is what the "few false positives" rubric criterion scores).
 4. Live end-to-end — run the orchestrator against 3–4 real sites of different shapes
    (a docs site, an e-commerce site, a marketing SPA, a small local business), and confirm:
    report validates against validate_floor_shape; total wall-clock stays under 5 minutes with
    the new multi-page checks active; the coverage ledger reports any budget-limited stage rather
    than silently dropping it.
 5. Portability check for the zip — build with scripts/build_submission_zip.sh, then unzip to
    a clean directory and run the entrypoint from there with PYTHONPATH unset. This is the check
    that would have caught a platform-locked wheel, and it is the reason the answer to Part 1 is
    "zero code packages".
 6. PSL asset — verify vendor/public_suffix_list.dat SHA-256 matches vendor/VENDORED.md,
    and that deleting the file degrades public_suffix.registrable_domain to the heuristic path
    with a confidence: low note instead of raising.
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
