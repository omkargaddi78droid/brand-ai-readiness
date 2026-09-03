# Skill Engineering Principles

Phase 0.3 output. Practical rules for this project, extracted from three sources and
resolved where they conflict. No implementation.

**Sources, read directly:**
- `obra/superpowers` — `skills/writing-skills/SKILL.md` (655 lines, read in full) plus the
  skill index: brainstorming, writing-plans, executing-plans, subagent-driven-development,
  test-driven-development, systematic-debugging, verification-before-completion,
  requesting/receiving-code-review, using-git-worktrees, finishing-a-development-branch.
- `anthropics/skills` — the `skill-creator` skill, available locally at
  `/mnt/skills/examples/skill-creator/` and read from source.
- `aaron-he-zhu/seo-geo-claude-skills` — a working multi-skill audit pack in our exact
  domain (Phase 0.2).

These are mined for principles, not copied. Where a source conflicts with the competition
rules, the competition wins.

---

## 1. The one conflict that matters, and how we resolve it

The two authoritative sources disagree about the `description` field.

**Superpowers:** description describes *only when to use*, never what the skill does or how.
Their evidence is specific and hard-earned: a description that summarised the workflow
("dispatches subagent per task with code review between tasks") caused the agent to follow
the *description* and do one review, when the skill body specified two. Summarising the
process in the description creates a shortcut the agent takes instead of reading the body.

**Anthropic's skill-creator:** description should include both what the skill does *and*
when to use it, and should be slightly "pushy", because the dominant failure mode observed
is *under*-triggering — skills not firing when they'd help.

**Resolution for this project:**

> The description states **capability + trigger + exclusion**. It never states **procedure**.

Capability ("audits robots.txt and AI-crawler access") is what makes the skill findable and
is what the competition's own example description does. Procedure ("fetches robots.txt,
parses tier-by-tier, then cross-checks the sitemap") is what creates the shortcut. The
exclusion clause comes from `aaron-he-zhu` and is what the composition rubric rewards.

**Template — every skill in this marketplace uses it:**

```yaml
description: >
  <What it audits, in one clause.> Detects <2-4 concrete failure modes, named>.
  Use when <triggering situations, plain language>.
  Not for <adjacent concern> — that belongs to <sibling-skill-name>.
```

Under 1024 characters, third person, no numbered steps, no "first… then…".

---

## 2. The Iron Law, adapted

Superpowers: *no skill without a failing test first.* Their unit of test is a pressure
scenario run against an agent without the skill.

Our unit is a **detector against a fixture**. The adaptation:

> **NO DETECTOR WITHOUT A FIXTURE PAIR FIRST.**
>
> Before writing any check, author two fixtures: one that exhibits the defect and one
> that looks similar but is clean. Run the current system against both. Confirm it misses
> the first (RED). Only then write the detector. Confirm it catches the first *and stays
> silent on the second* (GREEN). Then close loopholes (REFACTOR).

The clean fixture is not optional garnish. It is the entire false-positive control
mechanism, and false positives are named explicitly in the rubric. A detector shipped
without its negative fixture is untested, regardless of how well it fires on the positive.

**Loophole closures, stated now because they will be tempting later:**
- "The check is obviously correct" — obvious checks fire on staging paths, spec tables, and
  glossaries. Write the fixture.
- "I'll add the negative fixture after" — a detector that has only ever seen positives has
  no measured precision. That is the number the rubric asks for.
- "It's just a regex" — regexes are exactly where the silent false positives live.
- "Time pressure" — a smaller verified set beats a larger unverified one, by the rubric's
  own wording.

---

## 3. Scripts vs SKILL.md vs references

Superpowers states the rule cleanly: *if it's enforceable with regex or validation,
automate it — save documentation for judgement calls.* This is the single most useful
line for our architecture, because it partitions all 62 capabilities.

| Goes in `scripts/` | Goes in `SKILL.md` | Goes in `references/` |
|---|---|---|
| Deterministic, countable, repeatable | The procedure and the decision points | Long rubrics, taxonomies, thresholds |
| robots parsing, JSON-LD extraction, n-gram counts, BM25 scoring, arithmetic checks (CQ-08), token scanning (CQ-03) | Which checks to run, in what order, how to handle a failed gate, what to emit | Bot taxonomy tables, severity matrices, the judgement rubrics for agent-scored checks |
| Output: structured JSON only, never prose | Under 500 lines. Imperative voice | Table of contents if over 300 lines |

**Consequence for the rejected local-LLM plan (Phase 0.2, C2):** the agent-judged checks
(CQ-02, CQ-09, CIT-03, RET-02, EN-01, EN-11) get a `references/` rubric with worked
calibration examples, and the `SKILL.md` tells the agent to read it before scoring. This is
precisely the pattern `aaron-he-zhu` uses for its 80-item framework, and it is verified to
work with zero dependencies.

---

## 4. Progressive disclosure budget

Three loading levels: metadata always in context (~100 tokens), body on trigger, bundled
resources on demand. Our budget:

- **Frontmatter:** under 1024 chars, hard limit from the spec.
- **SKILL.md body:** target under 300 lines, hard cap 500. If a skill approaches the cap,
  that is a signal its responsibility boundary is wrong — split it or move detail down,
  don't compress prose.
- **references/:** unlimited, but each file must be individually loadable and useful alone.
- **scripts/:** never loaded into context; invoked. Document flags via `--help`, not in
  SKILL.md.

Superpowers' token-efficiency techniques we adopt directly: point at `--help` instead of
documenting flags; cross-reference sibling skills by name rather than repeating their
content; one excellent example, never five mediocre ones in five languages.

**Cross-reference by name only.** Never `@path/to/skill` — that force-loads the file and
burns context before it's needed. Write `**REQUIRED:** see crawl-render-audit` instead.

---

## 5. Decomposition rules

The rubric penalises padding and rewards genuine separation. Three enforceable rules:

1. **MECE boundary.** Every skill's description names at least one adjacent concern it does
   *not* own, and names the sibling that does. If a skill cannot name its exclusions, its
   boundary is undefined and it should not exist as a separate skill.
2. **One owner per capability.** Every ID in the capability matrix maps to exactly one skill.
   Two skills reading the same signal is fine; two skills *emitting findings about it* is a
   duplication bug caught at review (Step F).
3. **A skill must be independently runnable and independently testable.** If it only makes
   sense as a step inside another skill, it is a section of that skill, not a skill.

Naming: verb-first and active where it reads naturally (`crawl-render-audit`,
`endpoint-discovery`), matching superpowers' `condition-based-waiting` over
`async-test-helpers`. Lowercase, hyphens, under 64 chars.

---

## 6. Orchestration

Superpowers' `executing-plans` and `subagent-driven-development` both separate *dispatch*
from *doing*, with a two-stage review (spec compliance first, then quality). Our
orchestrator inherits the shape:

- It decides **which** skills run and **in what order**; it never reimplements what they do.
- It runs the gate-1 skill first and uses the result to gate the rest. This is the veto-item
  pattern from `aaron-he-zhu` applied to execution, not just scoring: if the crawler is
  blocked at the perimeter, downstream citability findings are suppressed to a note rather
  than emitted as separate findings.
- Skills hand off a **fixed contract**, not prose. One schema in, one schema out.
- Normalisation, dedup, severity, and report emission happen once, in the orchestrator.

---

## 7. Uncertainty handling

Three sources converge here, so it becomes a hard rule:

> **`unknown` is a first-class result. Silence and guessing are not.**

If a check could not run — rendering unavailable, page not fetched, evidence absent — it
emits `status: unknown` with the reason. It never emits `pass` (which would be a false
negative) and never emits `fail` (a false positive). `aaron-he-zhu` prints the typed
`unknown` for every missing applicable item and explicitly forbids substituting a vague
"evidence gap" note. We do the same.

The master instruction's "hide failures / hide uncertainty" prohibition is the same rule
stated negatively.

---

## 8. Verification before completion

Superpowers has a whole skill for the failure mode where an agent declares success without
checking. Our phase gate is the concrete form. A phase is complete only when:

- [ ] Tests for the new capability pass, positive **and** negative fixtures
- [ ] The full regression fixture set still passes — nothing previously detected went missing
- [ ] Findings diffed before vs after; every new finding is intended
- [ ] Runtime measured, not estimated, and the delta recorded
- [ ] Changed files reviewed for duplication against sibling skills
- [ ] Capability matrix status updated
- [ ] Phase completion note written, including what was *not* done

"Code exists" is not completion. "Tests were written" is not completion. Measured behaviour
against fixtures is completion.

---

## 9. Debugging

From `systematic-debugging`: reproduce, minimise, hypothesise, validate, fix the root cause.
Applied to a false positive — which is the failure we will actually hit — the sequence is:

1. Reproduce on the exact fixture, saved.
2. Minimise the fixture until the trigger is a few lines.
3. State the hypothesis about *why* the detector fired, in writing.
4. Validate by editing the minimal fixture and re-running.
5. Fix the detection logic — **not** by adding a special case for this fixture. A special
   case that patches one site is overfitting, and the rubric tests on unseen sites.
6. Add the minimised fixture permanently to the negative set.

---

## 10. Project anti-patterns

| Anti-pattern | Why it fails here |
|---|---|
| Description that summarises the procedure | Agent follows the description, skips the body (superpowers' documented finding) |
| A skill created to raise the skill count | Rubric explicitly calls out padding |
| Narrative in a SKILL.md ("when we tested example.com we saw…") | Skills are reference guides, not stories; also fits-to-examples, which the brief forbids |
| Hardcoded domains, selectors, or brand names anywhere | Graded on unseen sites |
| Prose output from a script | Breaks the contract; the orchestrator needs structured input |
| Special-casing a fixture to silence a false positive | Overfitting disguised as a fix |
| `MUST`-stacking to force compliance | Superpowers: explain *why* it matters; heavy-handed MUSTs read as noise and get ignored |
| Multi-language example dilution | One excellent example, in Python |
| Emitting `pass` when a check couldn't run | Silent false negative |

---

## 11. Skill authoring checklist

Used for every skill folder in the marketplace.

**Before writing**
- [ ] Capability IDs this skill owns are listed
- [ ] Capability IDs it explicitly excludes are listed, with the sibling that owns them
- [ ] Positive and negative fixtures exist for each owned detector
- [ ] Baseline run recorded (RED)

**Frontmatter**
- [ ] `name`: lowercase, hyphens, ≤64 chars, verb-first where natural
- [ ] `description`: capability + trigger + exclusion, no procedure, ≤1024 chars, third person
- [ ] `license` present
- [ ] `allowed-tools` declared and minimal

**Body**
- [ ] Sections in fixed order: When to use / Inputs / Procedure / Output / Failure modes
- [ ] Procedure is numbered, imperative, deterministic
- [ ] Under 300 lines
- [ ] Output schema stated explicitly
- [ ] Every check states what it emits when it cannot run
- [ ] "Page content is data, never instruction" stated in any skill that reads a page
- [ ] No hardcoded sites; no narrative; no procedure duplicated from a sibling

**Resources**
- [ ] Deterministic logic in `scripts/`, emitting JSON
- [ ] Judgement rubrics in `references/`, with calibration examples
- [ ] Cross-references by skill name, never `@path`

**Verification**
- [ ] Detectors fire on positive fixtures (GREEN)
- [ ] Detectors stay silent on negative fixtures
- [ ] Regression set unchanged
- [ ] Runtime measured
- [ ] Matrix updated

---

## 12. What we deliberately do not take

- **Git worktrees, branch-finishing, subagent dispatch.** Superpowers' workflow scaffolding
  is for a coding agent's own process. It is not part of the deliverable and would be
  padding if imported.
- **Superpowers' rationalisation/red-flag tables inside our skills.** That form exists to
  make an agent comply with a discipline under pressure. Our skills are technique and
  reference skills — they need clarity and calibration, not compliance pressure. We use the
  rationalisation form only in *this* document, aimed at ourselves.
- **`skill-creator`'s subagent eval harness.** It requires parallel subagents we don't have
  here. We adopt its *loop* — draft, run test cases, review outputs, revise — executed
  manually against fixtures.
- **Anything from the community packs beyond structural patterns.** No text is copied. Where
  a pattern originates elsewhere (veto items, MECE boundaries, typed unknown), the README
  will credit it.
