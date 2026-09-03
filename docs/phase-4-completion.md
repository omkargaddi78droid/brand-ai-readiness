# Phase 4 (capability 1 of N) — PER-03, CDN/edge blocking

Phase 4 output for the first capability cycle. Gate A–H, all measured.

---

## A — Gap confirmation

Not baseline-covered. The baseline's `geo access --format json` reports it
(Phase 3, `docs/baseline-test-report.md` §4.3), but Phase 3 also established
the baseline is untestable offline — its SSRF guard rejects loopback, so
nothing routed through it can get local-server regression coverage. PER-03's
mechanism (a GET under a different user agent, classify the response) is
simple enough to own outright with full test coverage, so it was built
locally rather than integrated. `BUILD_REQUIRED`, resolved by building.

## B — Resource evaluation

stdlib only (`urllib.request`), same as PER-01/02/04. No new dependency.

## C — Design

**Inputs:** the parsed robots.txt groups (reused from PER-01/02's own parse,
computed independently on this call since PER-03 fetches robots.txt itself),
a live base URL.

**Compliance rule, decided before anything else, enforced in code:** never
probe an agent robots.txt already disallows. Two independent reasons — sending
that request would itself violate "respect robots.txt" (P5), since a compliant
crawler of that name would never make it; and it would write a hit under that
agent's exact user-agent string into the target's own bot-traffic logs, for an
agent the site explicitly excluded. This makes PER-03 strictly complementary
to PER-01/02, never redundant with them: a tier already known blocked at the
robots layer is never re-probed at the edge.

**One representative agent per tier**, not all fifteen — `OAI-SearchBot`,
`ChatGPT-User`, `GPTBot`. Edge bot-management products typically block by
vendor category, not by individually enumerated agent, so a finer-grained scan
would rarely add signal at four times the request volume. Stated as a chosen
tradeoff, not hidden.

**A reachability control precedes every probe.** An ordinary-browser-UA GET to
the same path establishes the origin is up before any bot-specific request is
interpreted. Without it, "the AI bot got a 403" and "the whole site is down"
are indistinguishable — and, as §4 shows, so are "the AI bot got challenged"
and "everyone gets challenged here."

**Severity is unchanged from PER-01's table.** PER-03 changes which layer
produced the block (edge vs. origin), not what a block of that tier costs.

**Architecture:** three pure functions (`classify_response`,
`plan_edge_probes`, `interpret_edge_results`) carry all the logic and take
no network I/O, so they are unit tested with fixed inputs exactly like
PER-01/02/04. One impure function (`probe_with_user_agent`) does the actual
GET; everything upstream of it is deterministic and offline-testable.

PER-03 runs only in `--url` mode. Offline/fixture mode (`--robots-file`) skips
it and reports `unknown: no --url given` — it cannot be exercised without a
live target, and pretending otherwise would be worse than saying so.

## D — Implement

Done: `classify_response`, `plan_edge_probes`, `interpret_edge_results`,
`_edge_block_finding`, `probe_with_user_agent`,
`fetch_and_evaluate_edge_access`, plus `--no-edge-probe` and the `main()`
wiring. Only this capability — no other check touched.

## E — Test

**34 new tests**, all offline:

- `classify_response`: 403/429 → blocked, challenge markers → challenge
  (even over a 403), 2xx → ok, ambiguous statuses (500, 301, 402, no status)
  → ambiguous, never blocked.
- `plan_edge_probes`: the compliance rule directly — a tier blocked by robots
  is never planned, all tiers blocked plans nothing, a wildcard root block
  skips even the control, a scoped disallow does not suppress probing.
- `interpret_edge_results`: findings only after a successful control; a failed
  or challenged control suppresses everything to one `unknown`; ambiguous
  per-tier results are `unknown`, not findings; every emitted finding
  satisfies the contract.
- `probe_with_user_agent`, against a local `http.server` instance (127.0.0.1,
  no external network): the actual HTTP round trip for 200/403/403-with-body/
  500/unreachable, including a type assertion on the return shape — this is
  the class of test that would have caught §4's bug before it shipped.
- CLI wiring: offline mode and `--no-edge-probe` each report PER-03 `unknown`
  with the right reason.

Regression run: `python3 -W error::ResourceWarning -m unittest discover -s
tests` — **97 tests**, 0 failures, 0 warnings, 3.7 s.

## F — Review

- **Duplication:** none — PER-03 reuses `parse_groups`/`can_fetch_root`/
  `BOT_TIERS`/`TIER_SEVERITY`/`TIER_MECHANISM` from PER-01 rather than
  reimplementing tier logic.
- **Dependency cost:** zero — stdlib only.
- **Security:** every probe carries an honest `X-Audit-Purpose` header even
  while wearing a bot's UA; a short delay separates probes; at most 4 extra
  requests per audit; the compliance rule is enforced in `plan_edge_probes`,
  not left to the caller to remember.
- **Runtime delta:** +4 requests worst case, ~1–3 s on the sites tested.
  Cluster-A budget (`<5s`, capability-matrix §Cluster A) is a rough target for
  the whole perimeter cluster on a fast host; PER-03 alone stays well inside
  the 5-minute audit budget regardless.

**Two real bugs found by field testing, not by the fixture suite:**

1. **Silent return-shape corruption.** `probe_with_user_agent`'s two non-
   exception branches returned a bare classification string instead of the
   documented `(classification, status)` tuple. `baseline_classification, _ =
   probe_with_user_agent(...)` then unpacked the two-character string `"ok"`
   into `baseline_classification = "o"`, which compared unequal to `"ok"` and
   silently routed every live audit into the "control failed" branch. Found on
   the very first live run, against nytimes.com. Fixed; given permanent
   offline coverage via the local-server tests in §E, including a test that
   asserts the *type* of the return value, not just examples of its content.
2. **Unclosed `HTTPError` objects**, in both `probe_with_user_agent` and the
   pre-existing `fetch_text`. `urllib.error.HTTPError` wraps a file-like
   response body that must be explicitly closed; neither function did. Silent
   in a short CLI run, a real resource leak in anything longer-lived, and
   invisible to the test suite until it was run with
   `-W error::ResourceWarning`. Fixed in both functions; that flag is now part
   of the standard verification command for this project, not a one-off.

Neither bug could have been found by the pure-function unit tests, because
both live entirely inside the one function that touches the network. That is
the argument for the local-HTTP-server test pattern (§E) over "network code is
untestable, so trust it" — it is not free, but it is far cheaper than a live
run at review time, and it is now a template for every future capability that
does its own I/O.

## G — Document

This file; `SKILL.md`, `references/ai-bot-taxonomy.md`, `README.md`,
`marketplace.json` (0.2.0 → 0.4.0), `docs/capability-matrix.md` (PER-03 →
IMPLEMENTED), `docs/00-project-plan.md`.

## H — Freeze

PER-03 is frozen at this design. Re-open only if: the representative-agent
sample proves too coarse against evidence (would need a documented case of a
CDN blocking one agent in a tier while allowing another), or the challenge-
marker list needs a vendor added.

---

## Field validation

Nine live sites, read-only. None exhibited the positive case (robots allows,
edge blocks) in this sample — every one of the mechanism-relevant edge cases
the design anticipated fired correctly instead, which is itself the evidence
that matters for a check whose job is *not* to produce a false positive:

| Site | What happened | Correct because |
|---|---|---|
| `nytimes.com`, `cnn.com`, `bbc.com`, `theverge.com` | Robots already blocks most/all AI tiers (PER-02/PER-01 fire); PER-03 silently probes only what remains, finds nothing, adds nothing | Never redundant with PER-01/02, and never probes what robots already disallows |
| `forbes.com` | `GPTBot` got HTTP 402 | Reported `unknown` for that tier, not asserted as a block — an unrecognised status names no deliberate decision |
| `stackoverflow.com` | `/robots.txt` returned HTTP 418 | PER-01/02/03 all correctly `unknown` — robots.txt could not be established, so nothing about compliant probing is knowable |
| `zillow.com`, `nike.com` | The ordinary-browser control itself was challenged | One `unknown`, not an AI-bot-specific finding — confirms the control-first rule is load-bearing, not defensive boilerplate. A naive per-agent-only check would have produced a false positive on both |
| `target.com`, `wikipedia.org`, `python.org` | Clean: robots allows, no agent blocked at the edge | Correct silence |

The Phase 3 evidence for PER-03's mechanism (nytimes.com's CDN blocking
`GPTBot`, `OAI-SearchBot`, `PerplexityBot`, `Claude-SearchBot` per the
baseline's `geo access`) was against a site robots.txt already blocks, so this
implementation's compliance rule correctly does not re-probe it — that
positive case remains unconfirmed by this implementation specifically, and is
recorded here rather than assumed. The next capability that touches live
CDN behaviour should keep watching for a genuine robots-allows/edge-blocks
site to close this gap.

## Next

Continue Phase 4 with the next front-loaded capabilities: `CQ-03, CQ-05,
CQ-07, CQ-08` (deterministic content anti-patterns — cheap, high evidence
quality, no live-network dependency at all, a useful contrast after two
network-heavy cycles).
