# Baseline Selection

Phase 0.4 output. One baseline selected. No integration performed.

**Decision: `Auriti-Labs/geo-optimizer-skill`, pinned to an exact version, used as an
optional accelerator behind our own interface — not as a hard dependency, and not as the
product.** Rationale and the four qualifications that make this safe are below.

---

## 1. What the decision had to answer

From Phase 0.2: *does the candidate emit per-finding evidence we can normalise, or only a
score?* A 0–100 score cannot serialise into `{id, title, severity, evidence,
suggested_action}` without inventing the evidence, and invented evidence fails the rubric's
central criterion.

The answer for the leading candidate is **both, and that matters.** Its Python API is
score-shaped (`result.score`, `result.band`, `result.score_breakdown`,
`result.recommendations` as flat strings) — unusable for us directly. But it also emits
**SARIF**, which is finding-shaped by construction: rule ID, message, level, location. That
is a normalisable surface. Phase 1 must confirm the SARIF output carries per-check
granularity and observation detail rather than one blob per category; if it does not, the
JSON format (documented as a stable integration contract) is the fallback.

---

## 2. Candidates scored

Scale 1–5. Weights reflect the rubric, not general merit.

| Criterion | Weight | geo-optimizer-skill | Composed stack (crawl4ai+trafilatura+advertools+bm25s) | squirrelscan | From scratch |
|---|---|---|---|---|---|
| Relevance to the problem | ×3 | 5 — purpose-built for AI citation readiness | 3 — general web tooling, no GEO logic | 4 — broad site QA incl. Agent Experience | 3 |
| Coverage of our matrix | ×3 | 4 — strong on Gate 1, entity, parts of Gate 3; **zero** engagement | 3 — strong Gate 2 + structure, nothing else | 4 — broad but shallow per area | 1 |
| Per-finding evidence output | ×3 | 4 — SARIF + JSON; score-shaped Python API | 2 — libraries return data, findings are ours to build | 4 — per-rule findings with fixes | 5 (by construction) |
| Composability | ×2 | 4 — Python API, CLI, plugin entry points | 5 — plain libraries, no opinions | 2 — CLI + hosted MCP | 5 |
| Security posture | ×2 | 5 — SSRF validation, DNS pinning, private-IP blocking | 3 — crawl4ai executes site JS | 3 — cloud auth path | 3 |
| Package size / offline | ×2 | 5 — 478 KB pure-Python wheel, `py3-none-any` | 2 — Playwright + Chromium | 1 — Bun binary, PATH dependency | 5 |
| No external service / key | ×2 | 4 — core is local; two subcommands need keys | 5 | 1 — cloud rendering and AI analysis need auth | 5 |
| Maturity | ×1 | 4 — v4.17, production/stable, 1,720 tests | 5 — all four are established | 3 — young | 1 |
| Extensibility | ×1 | 4 — documented plugin entry points | 5 | 2 | 5 |
| Correctness confidence | ×2 | **2 — tests are "all mocked"** | 4 | 3 | 3 |
| **Weighted total** | | **86** | 72 | 62 | 66 |

---

## 3. Why the winner wins

**It is the only candidate that already encodes the problem domain.** Verified from the
published documentation, it ships: a 27-bot / 3-tier robots taxonomy; llms.txt and
llms-full.txt validation including structural depth; JSON-LD richness scoring; brand entity
coherence with Wikipedia/Wikidata/LinkedIn/Crunchbase knowledge-graph linkage; and eight
scoring categories with explicit point allocations.

Several bonus checks map onto capabilities I had marked build-from-scratch in Phase 0.2 and
must now be re-examined at Step A rather than assumed:

| Bonus check it ships | Matrix ID I had marked "build" |
|---|---|
| CDN Crawler Access (Cloudflare/Akamai/Vercel blocking AI bots) | PER-03 |
| JS Rendering / SPA detection | REN-02 (partial) |
| Multimodal Readiness (alt coverage, captions, transcripts, subtitle tracks) | REN-08 |
| Negative Signals (CTA overload, popups, thin content, keyword stuffing, boilerplate ratio) | RET-04, REN-07, parts of EN-06 |
| RAG Chunk Readiness (section word counts, definition openings, anchor sentences) | RET-06, RET-07 |
| Content Decay Prediction (temporal, statistical, version, event, price decay) | CQ-05, CQ-06, CQ-10 |
| `geo coherence` — cross-page terminology consistency | ENT-09 (partial) |
| Prompt Injection Detection (hidden text, invisible Unicode, monochrome text, micro-font, aria-hidden abuse) | INF-11 — and see §6 |

That is a materially larger head start than Phase 0.2 credited. It also means the honest
build-from-scratch count drops on the discoverability side and the engagement gap becomes
proportionally *more* of the remaining work.

Practical properties that matter: a 478 KB pure-Python `py3-none-any` wheel (no compiled
extensions, no platform wheels, trivial against the 50 MB cap); MIT; SSRF protection with
DNS pinning and private-IP-range validation, which is exactly the defence a URL-taking
audit tool needs; and `--max-urls` on sitemap batch audits, which is a lever on the
five-minute budget.

---

## 4. Why the alternatives lose

**Composed stack** — no domain logic at all. Choosing it means writing every GEO check from
scratch while also owning Playwright's install weight. It is not a baseline; it is a set of
libraries we will draw on for specific capabilities in Cluster B and D regardless of this
decision. Selecting it as *the baseline* would confuse "dependency" with "foundation".

**squirrelscan** — genuinely good, and its Agent Experience category is the closest published
prior art to our engagement cluster. But it requires the `squirrel` binary in PATH (Bun),
and its rendering and AI analysis are cloud features behind OAuth or an API key. That fails
the self-contained-manifest rule and the portability requirement. It stays what Phase 0.2
made it: a taxonomy to learn from, cited in the README, not linked against.

**From scratch** — scores well on control and terribly on time. It also contradicts the
project's central principle. Rejected as a baseline; retained as the *method* for the
engagement cluster, where no adequate resource exists.

---

## 5. Four qualifications that make this safe

The baseline is adopted **with these constraints, which are binding from Phase 2 onward.**

**(a) Subcommand allowlist. Two commands are permanently forbidden.**
- `geo fix --apply` — writes files. The competition rule is recommend-only, absolute. This
  command must never appear in any script, any SKILL.md, or any example.
- `geo citations` — requires a third-party API key and queries live answer engines. Fails
  the no-external-service rule, and its results are non-deterministic by nature
  (personalisation, appendix E). Excluded.

Permitted: `audit`, `citability`, `schema`-validation, bot checks, negative signals,
`access`, `coherence`, `authority`, `perception`. `geo llms` and `geo schema` generate files
— usable only to produce *example snippets inside a recommendation*, never written to disk
at a target's location.

**(b) It is an accelerator, not a hard dependency.**
Every check routes through our own interface. If the library is missing or errors, the check
degrades to our own minimal implementation (for the gate-1 essentials, which are tens of
lines of stdlib) or emits `status: unknown` with a reason. The audit never crashes because a
dependency is absent. This also protects the "manifest is self-contained" requirement:
Phase 1 measures the full dependency closure and decides vendor-vs-pin on evidence.

**(c) Its recommendations do not pass through.**
`result.recommendations` is a flat list of strings. The rubric asks for fixes that are
*correctly targeted, mechanism-sound, and prioritized*. We generate suggested actions from
our own finding contract, with the mechanism explained. Pass-through would forfeit an entire
rubric criterion.

**(d) Its score does not pass through.**
We emit findings with severities, not a 0–100 band. The score is useful internally as a
sanity signal and nothing more. Category point allocations (Robots /18, llms /18, Schema
/16…) are *their* weighting of *their* categories, and our severity model is gate-based.

---

## 6. Two findings worth acting on immediately

**Its tests are "all mocked."** 1,720 tests is an impressive number that proves the code
paths execute against fixtures the authors wrote. It does not prove the parsers behave on
real-world HTML — which is precisely where extraction tools fail. This is the reason
correctness confidence scored 2 while maturity scored 4. **Consequence:** Phase 3 baseline
testing is not a formality. We measure its detections against our own fixtures and record
its false positives as *our* false positives, because in the report they will be.

**Its prompt-injection detection is a check we should promote, not just consume.** It scans
the audited page for hidden text, invisible Unicode, monochrome text, micro-fonts, HTML
comment injection, and aria-hidden abuse. Phase 0.2 treated prompt injection purely as a
defence (INF-11: page content is data, never instruction). It is *also* a legitimate audit
finding — a site carrying hidden instructions aimed at LLMs has an AI-readiness problem and
a reputational risk, and no other candidate detects it. Add it to the matrix as a finding-
producing capability, not only a guardrail.

---

## 7. Risks accepted, with mitigations

| Risk | Evidence | Mitigation |
|---|---|---|
| Single maintainer | One PyPI maintainer listed | Pin an exact version; MIT permits vendoring if the project moves |
| Rapid version churn | ~50 releases Feb–Aug 2026 | Pin exact; never a range. Re-verify before submission |
| Documentation inconsistency | Roadmap lists v4.17.0-rc1 as "Planned Jan 2027" while 4.17.0 shipped Aug 2026 | A sloppiness signal, not a correctness one. Reinforces (b): never trust it as a sole source of truth |
| Commercial upstream (GeoReady) | Hosted platform built on the same engine | CLI is MIT and local-first with zero telemetry as documented. Verify no network calls beyond the target in Phase 1 |
| Mocked-only tests | Stated in the repo | Phase 3 measures behaviour on real fixtures |
| Optional extras pull weight | `[llm]`, `[embedding]`, `[pdf]`, `[web]` | Install the base package only. `[llm]` and `[embedding]` are forbidden — model weights and API keys |

---

## 8. What the baseline explicitly does not cover

Stated now so it is never quietly assumed later:

- **The entire engagement cluster (EN-01…EN-11).** Zero coverage. Half the rubric. This is
  our authorship, and it is where the submission differentiates.
- **Render-diff mechanics** (REN-03, REN-04): it detects SPAs; it does not diff pre- and
  post-render DOMs to catch gated prices or scroll-locked content.
- **The deterministic content anti-patterns** (CQ-03 template leakage, CQ-07 scope-ambiguous
  numerics, CQ-08 computed-stat integrity). Content-decay prediction is adjacent, not the
  same check.
- **Citation precision/recall** (CIT-03, CIT-04) beyond its factual-accuracy MCP tool, which
  Phase 1 must inspect rather than assume.

---

## 9. Phase 1 must answer

1. Does SARIF output carry per-check findings with observation detail, or category blobs?
2. What is the full dependency closure, installed size, and does anything need compiling?
3. Does any code path make a network call to a destination other than the audit target?
4. Which of the §3 bonus checks produce evidence strings we can normalise, and which only
   contribute points?
5. Where are its false positives? Specifically: does keyword-stuffing detection fire on spec
   tables and glossaries; does thin-content fire on legitimate short pages?
6. What does it do on failure — exception, silent zero, or typed unknown? Our `unknown`
   contract depends on the answer.
7. Runtime for a single URL, and for a 25-URL sitemap batch, measured.

**Do not modify the baseline.** Phase 1 is read-only forensics.
