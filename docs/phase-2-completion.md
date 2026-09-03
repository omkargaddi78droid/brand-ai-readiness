# Phase 2 — Skeleton, manifest, baseline wrapper, finding contract

Phase 2 output. **Gate satisfied:** a skill runs end-to-end through our own
interface and the entrypoint composes its output into a schema-valid report.

Everything below was measured, not estimated. 50 tests, 0.02 s, pure stdlib.

---

## 1. What was built

```
brand-ai-readiness-audit/
  marketplace.json                      one entrypoint, two skills, no external service
  README.md · LICENSE                   MIT
  shared/finding_contract.py            INF-05
  skills/audit-orchestrator/            entrypoint (composes; detects nothing)
    SKILL.md · scripts/compose_report.py
  skills/perimeter-access-audit/        PER-01, PER-02, PER-04
    SKILL.md · scripts/check_perimeter.py · references/ai-bot-taxonomy.md
  tests/                                50 tests, 11 fixtures
```

## 2. The finding contract (INF-05)

The required report schema is a floor. Our contract is a superset that
serialises down to it exactly (`to_floor_schema`), and `validate_floor_shape`
proves the projection every run.

Fields beyond the floor, each with the job it does:

| Field | Why it exists |
|---|---|
| `mechanism` | Severity must be arguable from the report, not asserted. Validation **rejects a finding without one** — this is the contract-level defence against the severity-calibration failure recorded in baseline-gaps §2 |
| `track` | `defect` (observed problem) vs `proactive` (no defect, still worth doing). Satisfies M19 without dressing suggestions up as faults |
| `confidence` | Lets a genuinely contested mechanism carry a visible hedge instead of a buried one |
| `capability_id` / `owner_skill` | One owner per capability, so a duplicate is a detectable composition bug |
| `gate` | The suppression input the orchestrator needs at Phase N-1 |
| `check_id` | Stable semantic id survives renumbering, so findings are traceable run to run |
| `structured_evidence` | Machine-readable counterpart to the evidence sentence |
| `unknown_checks` | Checks that could not run, with reasons. Separate from findings, because an unknown is not a severity |

Three decisions worth stating, because they are load-bearing:

**`unknown` is a result type, not a severity.** A fabricated `pass` is a silent
false negative; a fabricated `fail` is a false positive. Both are worse than
"could not evaluate, here is why".

**An invalid finding aborts the report; a failed skill does not.** A skill
whose output is missing or unparseable becomes one `unknown_checks` entry and
the audit proceeds — coverage degrades, the report survives. A finding that is
missing evidence or a mechanism aborts the run loudly, because that is an
authoring bug, and a report whose evidence cannot be trusted is worse than no
report.

**Report ids are sequential, semantic ids are stable.** Skills emit
`PER-02-all-ai-agents-blocked`; the report shows `F-001` and keeps the semantic
id in `check_id`. Same finding set, same numbering, always.

## 3. The baseline wrapper, and what it actually is

Phase 1 left six of seven questions about `geo-optimizer-skill` unverified
(`pip` egress is blocked here). The wrapper is built accordingly:

`_baseline_bot_taxonomy()` is the accelerator seam. **It returns `None` today
and is documented as doing so.** Every call site falls back to the built-in
taxonomy, which is the real, tested implementation. Wiring speculative calls
against an API whose shape is graded **U** would encode guesses as fact — the
opposite of what Phase 1 concluded.

What this buys, tested rather than asserted: the audit produces identical
output with or without the accelerator. When Phase 3 execution testing resolves
the SARIF-granularity question, the accelerator can only widen the agent list —
it cannot remove coverage, change a severity, or break a run.

## 4. Detection decisions in the first skill

Three tiers of AI user agent, because collapsing them produces both false
alarms and missed failures:

| Tier | Severity | Confidence | Reasoning |
|---|---|---|---|
| Real-time AI search | `critical` | high | Short causal chain: not fetched → not read → not cited. Gate 1's whole point |
| On-demand user fetchers | `high` | **medium** | Providers differ on whether a user-directed fetch is governed by crawl rules. The hedge is in the field, not just the prose |
| Model-training crawlers | `medium` | high | Delayed, indirect, and frequently a deliberate licensing position. Rating this `critical` would be a false positive of severity |

`llms.txt` is capped at `low` and travels in the proactive track, per the
evidence in baseline-gaps §2. The finding says plainly that it is a
forward-compatibility measure, not a citation lever.

When every agent in every tier is blocked, one PER-02 finding is emitted rather
than three PER-01 tier findings — one root cause, one finding — and its wording
splits by whether the wildcard group is also blocked, because a staging host
and a targeted AI exclusion are different situations that deserve different
advice.

## 5. False-positive control

Every detector has a lookalike fixture that must stay silent. The clean set:

| Fixture | Must not fire |
|---|---|
| `staging_path_only.txt` | `Disallow: /staging/` is not a site-wide block |
| `allow_all.txt` | Ordinary permissive robots.txt |
| `malformed.txt` | An HTML error page served at `/robots.txt` with status 200 — parse permissively, no crash, no finding |
| missing `robots.txt` | Absence permits everything under the exclusion protocol; not a finding, and explicitly not an `unknown` either |
| `llms_txt/valid.txt` | A conforming file produces nothing |

## 6. Verification

- [x] Positive and negative fixtures pass for every detector (50 tests)
- [x] Report validates against the required schema on every composition path
- [x] Determinism asserted, not assumed: same input → byte-identical report
- [x] Runtime measured: 0.02 s for the full suite; a live run is two GETs with
      a 10 s timeout each, against a 5-minute budget
- [x] Zero third-party imports, enforced by a test that reads the import lines
- [x] No request body can be sent from any script, enforced by a test
- [x] Manifest hygiene enforced by a test: exactly one entrypoint, every listed
      path exists, no orphan skill folder, no URL in the manifest
- [x] Every `SKILL.md` checked for `name`/`description`/`license`/
      `allowed-tools`, the 64- and 1024-char limits, the four required
      sections, the 500-line cap, and a stated exclusion clause

## 7. What was deliberately not done

- **No accelerator call.** See §3.
- **No gate suppression logic.** The `gate` field is populated and the rule is
  written into the entrypoint's procedure, but with one skill there is nothing
  downstream to suppress. Implementing it now would be untestable.
- **No dedup or aggregation (INF-08).** Same reason: one skill cannot collide
  with itself. The duplicate-id abort is in place as the tripwire.
- **No PER-03/05/06/07/08.** Named as exclusions in the skill description
  rather than half-built.
- **No engagement skill yet.** Half the rubric, still entirely ahead.

## 8. Capability candidate found while building

**`/robots.txt` returning an HTML page with status 200.** Common on
misconfigured hosts, currently handled only as a false-positive guard (parse
permissively, report nothing). It is a real, cheap, near-zero-FP signal —
a server that cannot serve robots.txt correctly is likely misconfigured for
crawlers generally. Recorded here as an intake candidate for Phase 4 rather
than smuggled into this phase.

## 9. Next

**Phase 3 — baseline testing.** Measure the wrapper against fixtures that
exhibit real defects, record TP/FP/FN and runtime as the comparison point, and
resolve as many of the seven baseline questions as execution allows.
