# Baseline Gaps

Phase 1 output. What the baseline does not do, does poorly, or does in a way we must not
inherit.

---

## 1. Structural gaps (absent capabilities)

Uncontroversial. These are simply not in the tool.

| Cluster | Missing | Consequence |
|---|---|---|
| **Engagement (EN-01…EN-11)** | Everything except popup/CTA-overload signals | Half the rubric. Entirely our authorship |
| Render mechanics | REN-03 pagination/scroll, REN-04 price-render gating, REN-05 availability, REN-09 image-of-text, REN-10 NAP click-to-reveal, REN-11 PDF-locked facts | It detects that a page is a SPA; it never diffs pre-render HTML against post-render DOM. The diff *is* the check |
| Deterministic content anti-patterns | CQ-03 template leakage, CQ-07 scope-ambiguous numerics, CQ-08 computed-stat integrity | Highest evidence-quality detectors in the matrix. Cheap, near-zero false positives, and ours |
| Sparse retrieval | RET-01 BM25 exact-match survival, RET-02 synonym coverage, RET-03 query-intent coverage | No retrieval simulation of any kind |
| Entity edges | ENT-03 markup/text agreement, ENT-06 lookalike domains, ENT-07 cross-domain attribution, ENT-08 NAP consistency | Requires off-site or cross-page reasoning it does not do |
| Endpoint checks | PER-06 sitemap completeness, PER-07 `.md` content negotiation | Its "AI Discovery" category checks `/ai/*.json` conventions instead — a different and more speculative set |

---

## 2. The correctness gap: severity calibration

**This is the most important finding of Phase 1, and it did not require execution.**

The baseline allocates **18 of 100 points to llms.txt** — joint-largest category, equal to
robots.txt — and **16 to schema JSON-LD**. That is 34% of its score resting on two signals
whose citation effect is, on the published evidence, weak to nil.

**C — corroborated across independent server-log studies:**

| Source | Finding |
|---|---|
| Limy (500M AI-bot visits, 90 days) | 408 requests targeted llms.txt |
| EZY Research (83 sites, 12 weeks) | robots.txt vs llms.txt fetches — OpenAI 3,990 vs 7; Anthropic 3,120 vs 9; PerplexityBot 775 vs 0 |
| Longato (1,000 AEM domains, 30 days of CDN logs) | No GPTBot, ClaudeBot, or PerplexityBot requests at all; Googlebot 95% of hits; SEO tools inflating the rest |
| Ahrefs (137,210 domains, May 2026) | Retrieval crawlers barely register in llms.txt logs; AI bots never probed for the file on domains lacking it |
| Adoption | ~5.86% of Tranco top 10k; ~10% of a 300k-domain study |
| Vendor position | Google on record as not supporting it; no major provider has committed to consuming it in production |

On schema, an Ahrefs test of 1,885 pages reported roughly +2.4% AI-Mode citation lift from
adding JSON-LD — within noise. And the baseline's *own* cited research (C-SEO Bench)
concludes that most content manipulation is ineffective and infrastructure matters most.

**Why this matters to us specifically.** The rubric grades whether suggested actions are
*mechanism-sound*. Emitting "**critical**: no llms.txt found" asserts a causal claim the
evidence does not support, to a grader who may well know this literature. It is a false
positive of severity rather than of detection — the check fires correctly, and the
conclusion drawn from it is wrong. That failure mode is invisible to ordinary
positive/negative fixture testing, which is why it belongs in this document.

**Resolution, binding from Phase 2:**

1. **Severity is derived from our gate model, never from the baseline's point allocation.**
   Already decided in baseline-selection §5d; this is the concrete reason.
2. **llms.txt findings are `low` severity and belong in the proactive-suggestion track**
   (INF-09), not the defect track. Framed honestly: an agentic-retrieval and
   forward-compatibility measure — a real benefit for documentation and developer-facing
   sites, where user-configured tools do fetch it — not a citation lever.
3. **Schema findings are `medium`, framed for entity resolution and rich results**, which is
   what the evidence supports, rather than for citation lift.
4. **Perimeter access stays `critical`.** The causal chain there is direct and needs no
   study: blocked means not fetched, and not fetched means not cited. This is gate 1 of the
   Round-2 model.
5. **Every finding carries a mechanism statement**, so severity is arguable from the report
   itself rather than asserted.

Two nuances worth carrying into the perimeter skill's design:

- **C** — CDN/edge blocking diverges from robots.txt in a meaningful share of sites. This
  independently confirms PER-03 as high-value, and it is one of the few checks where the
  baseline and the evidence agree on importance.
- **C** — Real-time, user-directed agent fetches are a grey zone: providers often treat them
  as user-directed access rather than crawling, so robots.txt training rules may not govern
  them. Our tier-3 (on-demand fetcher) findings must be phrased with that uncertainty rather
  than asserting a block is decisive.

---

## 3. Architectural gaps

| Gap | Why it matters | Handling |
|---|---|---|
| Score-shaped Python API | `.recommendations` is prose strings with no observation, location, or rule identity | Do not use. Go via SARIF/JSON; generate our own actions |
| No typed `unknown` (**U**) | A scorer has structural pressure toward "0 points" on failure, indistinguishable from a genuine absence | Wrap every call. Absence of positive evidence → `unknown` unless the tool distinguishes it |
| No page-bundle sharing | It re-fetches per command; running `audit` + `access` + `coherence` + `authority` means repeated network work | INF-04 page bundle is ours. Constrain the baseline to the fewest invocations that yield the needed data |
| Aggregate composite scores | Trust Stack A–F, Platform Citation Profile — no per-finding evidence | Use as supporting context attached to our findings, never as findings |
| Mocked-only test suite | Unvalidated against real HTML | Phase 3 measures it against our fixtures; its false positives are ours |

---

## 4. Anticipated false positives to fixture against in Phase 3

Predicted from the check descriptions. Each needs a clean-but-similar negative fixture.

| Check | Predicted false positive |
|---|---|
| Keyword stuffing | Spec tables, glossaries, product-attribute lists, legitimately repetitive technical pages |
| Thin content | Legitimately short pages — contact, pricing, a definition page that correctly answers in 40 words |
| Boilerplate ratio | Documentation sites with large, correct persistent navigation |
| CTA overload | Landing pages where a repeated CTA is the correct design |
| Missing author | Corporate pages where organisational authorship is appropriate and a byline would be odd |
| Schema richness (5+ attributes) | Valid minimal schema that is correct for the page type |
| Content decay | Deliberately evergreen content with no dates because none apply |
| Prompt injection | `aria-hidden` and visually-hidden text used correctly for accessibility — the single highest false-positive risk in the tool, because the legitimate and malicious patterns are the same markup |

---

## 5. What remains unverified

Six of the seven Phase 1 questions (baseline-analysis §7) still require execution. They are
not blockers because Phase 2 is designed so that none can silently break us: the baseline
sits behind our interface, is never a hard dependency, and every check degrades to `unknown`
rather than to a fabricated `pass` or `fail`.

The one that most affects design remains SARIF granularity. **Phase 2 must therefore build
the normalisation layer against the finding contract, not against the baseline's output
shape** — so that whichever surface turns out to be usable, only the adapter changes.
