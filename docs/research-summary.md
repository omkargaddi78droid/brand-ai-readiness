# Research Summary

Phase 0.2 output. Sources:
1. `AI_Readiness_Audit_Tool_Research.pdf` — the 47-point audit specification + library shortlist.
2. `Revalent_skills_from_skills_sh.pdf` — 48 named skills / packs from skills.sh and adjacent registries.
3. Live verification (web) of the load-bearing claims in both.

No implementation. Companion document: `capability-matrix.md`.

---

## 1. Verification status of every load-bearing resource

The research names many resources. Some are real and strong; some are unverified; one
would break a hard competition rule. **Nothing enters the build unverified.**

| Resource | Status | License / access | Verdict |
|---|---|---|---|
| `Auriti-Labs/geo-optimizer-skill` | **VERIFIED** | MIT, PyPI, v4.17.x, 1720 tests, SSRF protection, zero cloud dependency in CLI, MCP server | Strong baseline candidate → Phase 0.4 |
| `squirrelscan/squirrelscan` + `/skills` | **VERIFIED** | MIT engine; **278 rules / 21 categories incl. an "Agent Experience (AX)" category**; hosted API + cloud rendering are private & auth'd | Excellent *rule taxonomy reference*, esp. for engagement. Hard runtime dependency (`squirrel` CLI, Bun binary) → reject as dependency, mine as prior art |
| `aaron-he-zhu/seo-geo-claude-skills` | **VERIFIED** | **Zero-dependency markdown skills**; CORE-EEAT 80-item + CITE 40-item frameworks; veto items, critical-fail cap, MECE boundary rule, handoff schema | Best available *skill-engineering* exemplar for this domain → feeds Phase 0.3 |
| `crawl4ai`, `trafilatura`, `advertools`, `bm25s` / `rank_bm25` | Well-established Python libs | Permissive | Integration candidates, subject to size/runtime review |
| `seoscoreapi` | Hosted third-party API | Key + network required | **REJECT** — violates the self-contained-manifest rule; see §4 |
| `TheSmokeDev/geo-skills`, `Cognitic-Labs/geoskills`, `garrettjsmith/localseoskills`, `coreyhaines31/marketingskills`, `mykpono/ultimate-seo-geo`, `AgriciDaniel/claude-seo` | **NOT INDEPENDENTLY VERIFIED** | unknown | Treat as *capability signal only* — they tell us which checks practitioners consider worth building. Do not install, do not depend on |
| `firecrawl/cli`, `brightdata/skills` | Commercial, keyed services | API keys | Reject — external service dependency |
| The PDF's "OpenClaw / Claw Hub" ecosystem and its malware statistics | **UNVERIFIABLE as described** | — | Do not cite in deliverables. The underlying lesson (community skill registries carry supply-chain risk; natural-language instructions bypass static scanning) is sound and is retained as a design constraint |

**Rule adopted:** every dependency must be (a) verified to exist, (b) permissively
licensed, (c) installable offline or vendored, (d) functional with no account or key.
Anything failing one of these is prior art, not a dependency.

---

## 2. What the 47-point spec actually contains

Reorganised from the PDF's flat list into the three-gate mechanism model from the
Round-2 appendix. This regrouping is the substantive contribution of this phase — the
research's ordering is alphabetical-ish and hides the dependency structure.

**Gate 1 — Can the crawler get in?** (perimeter)
robots.txt AI-bot policy across the 3-tier bot taxonomy (training bots / real-time search
indexers / on-demand user fetchers), llms.txt, llms-full.txt, sitemap.xml, `.md` content
negotiation. *Highest severity in the whole audit: a gate-1 failure makes every
downstream finding moot.*

**Gate 2 — Can the machine read the page?** (render + extraction)
Pagination and infinite scroll, client-side price rendering, real-time availability,
semantic HTML5 boundaries, alt-text and transcripts, click-to-reveal NAP, facts locked
in PDFs.

**Gate 3 — Can it find and quote the specific fact?** (retrieval + citability + quality)
Everything else: BM25 exact-match survival, dense/synonym coverage, atomic paragraphs,
answer extractability, attribution density, quotation and statistics density, citation
precision/recall, position weighting, and the anti-pattern family (non-answer templates,
template leakage, relative dates, ambiguous numerics, computed-stat integrity,
marketing/procedure interleaving).

**Cross-cutting — Is the entity resolvable?** (identity)
Schema.org/JSON-LD, Wikidata QID grounding, canonicalisation, brand collision,
lookalike domains, cross-domain attribution, taxonomy consistency, address drift.
This is not a gate; it is a multiplier on all three.

24 of the 47 are flagged build-from-scratch by the research. My count after regrouping
is similar, but the *distribution* matters: the build-from-scratch items cluster almost
entirely in gate 3 and identity — i.e. exactly where the differentiated scoring is.

---

## 3. The engagement gap — the most important finding of this phase

The problem statement weights **on-site engagement** equally with discoverability.

- The 47-point research covers it with roughly one category (`conversion-path-friction`).
- The skills-registry research covers it with roughly three: squirrelscan's *Agent
  Experience* category, `coreyhaines31/conversion-optimization` (landing-page friction,
  conversion paths), and accessibility rules used as a proxy.

That is not enough for half a rubric. **An engagement cluster must be authored.** Drafted
in `capability-matrix.md` as EN-01…EN-11, derived from three sources:

1. The Round-2 appendix, generalised. Section F says substance carried in non-readable
   form vanishes from AI summaries and important lines drown in filler — the same is
   true of a human landing on a page. Signal density is auditable.
2. Section A's "invisible to the machine, plainly visible to the human" inverted: the
   engagement failures are *visible to the machine, useless to the human* — a page that
   parses perfectly but never says what the company does, for whom, or what to do next.
3. squirrelscan's AX framing: a site is also consumed by an **autonomous agent acting on
   a user's behalf**. Labelled forms, machine-readable contact paths, and low-step
   checkouts serve both the human and the agent. This is the cleanest bridge between the
   two halves of the rubric and worth building explicitly.

---

## 4. Conflicts between the research and the rules

| # | Research says | Rule says | Resolution |
|---|---|---|---|
| C1 | Use `seoscoreapi` SDK for 4 categories | Manifest self-contained, no external service; deterministic; <5 min | **Reject.** All four (answer extractability, atomic paragraphs, fluency, multimodal accessibility) are cheap local heuristics over extracted text. Reimplement |
| C2 | Deploy "lightweight locally hosted LLMs" for zero-shot semantic classification | No model weights; zip ≤50 MB | **Reject.** The host agent *is* the model. Semantic judgement → `SKILL.md` procedures + `references/` rubrics. Confirmed viable by `aaron-he-zhu`'s zero-dependency markdown pack |
| C3 | Install core packs via `npx skills add ...` | Manifest self-contained, no external service to resolve | **Reject as a runtime path.** We may vendor permissively-licensed code with attribution; we may not depend on registry installs at grade time |
| C4 | `squirrelscan` as broad audit engine | Determinism, portability, no auth | **Reject as dependency** (Bun binary + PATH + cloud auth for rendering). Mine its AX rule taxonomy as prior art |
| C5 | Research is ~90% discoverability | Rubric is 50% engagement | Author EN-01…EN-11 (§3) |
| C6 | Chase all 47 categories | Rubric penalises false positives and padding | Ship fewer, higher-precision detectors. Coverage is not the metric; **precision × actionability × composition** is |

---

## 5. Transferable engineering patterns (feeds Phase 0.3)

From `aaron-he-zhu/seo-geo-claude-skills`, verified and directly applicable:

- **Veto items + critical-fail cap.** A small set of items that, when failed, cap the
  overall score regardless of the other 79 passing. Prevents "79 pass, 1 catastrophic
  fail → looks healthy". Our gate-1 failures are natural veto items.
- **MECE boundary rule.** Each skill's description states what it does *and explicitly
  what it does not do, naming the sibling skill that owns it* ("Not for structural
  on-page tags — use on-page-seo-auditor"). This is exactly what the composition rubric
  rewards, and it is nearly free to implement.
- **Typed `unknown` instead of silence.** Missing evidence is recorded as an explicit
  `unknown` state per item, not omitted and not guessed. Direct false-positive control.
- **Handoff schema.** Skills emit a fixed contract to the next skill, not prose.
- **Severity-tier routing** over flat finding lists.
- **Deterministic rounding** specified in the runbook, not left to the agent.

From `squirrelscan`: a rule *catalogue* structure (categories → rule IDs → docs URL per
rule), per-rule embedded fix instructions, and coverage modes (quick 25 pages / surface
100 with pattern sampling / full 500). The coverage-mode idea is our answer to the
5-minute budget.

From `geo-optimizer-skill`: 3-tier bot classification, per-platform readiness profiles,
SARIF-style output, regression/drift comparison between runs.

---

## 6. Carried into Phase 0.4 (baseline selection)

Candidates to score: `geo-optimizer-skill` (leading), a `crawl4ai + trafilatura +
advertools` composed stack, `squirrelscan`, and a from-scratch skeleton.

The decisive question is not coverage breadth. It is: **does the candidate emit
per-finding evidence we can normalise, or only a score?** A 0–100 citability score
cannot be serialised into `{id, title, severity, evidence, suggested_action}` without
inventing the evidence — and inventing evidence fails the rubric's central criterion.
Phase 1 forensics must answer this before any code is written.
