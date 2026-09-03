# Baseline Analysis — geo-optimizer-skill

Phase 1 output. Read-only. The baseline was not modified, installed, or executed.

## 0. Method and its limits — read this first

> **Superseded in part by Phase 3.** `pip` egress works as of 2026-09-02; the baseline was
> installed at 4.17.1 and executed. Six of the seven questions in §7 are now answered by
> measurement — see `docs/baseline-test-report.md`. The **U** grades below are preserved as
> the Phase 1 record, not as current status.

`pip` egress is blocked in this environment. One check confirmed it; no retries. Phase 1
therefore proceeded as **documentation and published-source forensics**, not runtime
forensics.

Everything below carries an explicit evidence grade:

| Grade | Meaning |
|---|---|
| **V** | Verified from the maintainer's published package metadata or documentation |
| **C** | Corroborated by independent third-party evidence |
| **I** | Inferred from V/C facts; reasoning stated |
| **U** | Unverified. Requires execution. Listed in §7 |

No U-graded claim may be relied on in Phase 2 design without either resolving it or
designing so that it does not matter.

---

## 1. What it is

**V** — MIT-licensed Python toolkit, v4.17.1 current (4.17.0 inspected), Python ≥3.9,
`py3-none-any` wheel at 478.5 KB, sdist 599.2 KB. Development status: 5 — Production/Stable.
Single maintainer. Published to PyPI via Trusted Publishing with Sigstore attestation
(transparency log entry 2654734729) — supply-chain provenance is genuinely good.

**V** — Four surfaces: CLI (16 commands), Python API, MCP server (12 tools), Astro build
integration. Extras: `rich`, `config`, `async`, `web`, `pdf`, `mcp`, `embedding`, `llm`,
`dev`, `all`.

## 2. Inputs

**V** — A single URL (`--url`) or a sitemap (`--sitemap`, with `--max-urls N` to bound the
batch). `geo logs` takes a server access-log file. `geo diff` takes two URLs.

**I** — `--max-urls` is the runtime lever we need. It is the only documented bound on batch
size, so our budget governor (INF-10) will be built around it rather than around a page
count we manage ourselves.

## 3. Outputs

**V** — Seven formats: `text`, `json`, `rich`, `html`, `sarif`, `junit`, `github`. JSON is
described by the maintainer as a stable machine-readable integration contract across minor
versions.

**V** — Python API returns a score-shaped object: `.score` (int), `.band` (str),
`.citability.total_score`, `.score_breakdown` (dict of category → points),
`.recommendations` (list of strings).

**I — the central architectural fact.** The Python API is unusable as a finding source. It
gives a number, a category breakdown, and prose recommendations with no attached
observation, location, or rule identity. Normalising that into
`{id, title, severity, evidence, suggested_action}` would require inventing the evidence.

**I** — SARIF is the promising surface because SARIF 2.1.0 is finding-shaped by
specification: `runs[].results[]` each carrying `ruleId`, `message`, `level`, and
`locations[]`, with rule metadata in `tool.driver.rules[]`. If the baseline populates those
honestly, one SARIF result maps to one of our findings almost directly, and `level`
(error/warning/note) gives a severity hint we can re-derive from.

**U** — Whether its SARIF output is per-check or one result per scoring category. This is
question 1 of §7 and the single most consequential unknown in the project.

## 4. Dependencies and footprint

**V** — Pure Python, no compiled extensions, no platform-specific wheels. 478.5 KB installed
wheel before dependencies.

**U** — The transitive dependency closure and its installed size. **I** — near-certain to
include an HTTP client and an HTML parser; the `[web]`, `[pdf]`, `[async]` extras imply the
core is deliberately thin.

**Binding decision regardless of the answer:** install the base package only. `[llm]` and
`[embedding]` are forbidden — they imply API keys and model weights, both of which fail
competition rules.

## 5. Security posture

**V** — All URL inputs validated against private IP ranges (RFC 1918, loopback, link-local,
cloud metadata endpoints) with DNS pinning before any request. This is proper SSRF defence,
and it is exactly the control a URL-accepting audit tool needs. It is the strongest single
argument for this baseline over writing our own fetcher.

**V** — Documented as local-first with zero telemetry in the CLI.

**U** — Whether any code path contacts a host other than the audit target. §7 question 3.

**I** — Two commands are structurally incompatible with the competition rules and are
permanently forbidden (already recorded in baseline-selection §5a):
- `geo fix --apply` writes files → violates recommend-only.
- `geo citations` requires a third-party API key and queries live answer engines → violates
  no-external-service, and is non-deterministic by construction because answer engines
  personalise (Round-2 appendix E).

## 6. Failure behaviour and correctness

**V** — 1,720 tests, described by the maintainer as *all mocked*.

**I** — This is the correctness caveat that drove the low score in baseline-selection §2.
Mocked tests prove code paths execute against fixtures the authors wrote. They do not
exercise real-world HTML, which is where extraction and heuristic tooling actually fails.
Phase 3 must therefore treat the baseline as **unvalidated on real input** and measure it
against our own fixtures. Its false positives will appear in our report as our own.

**U** — What it does when a fetch fails or a parse breaks: raises, returns a silent zero, or
reports a typed unknown. Our entire `unknown`-is-first-class contract (principles §7)
depends on this. **I** — a scoring tool has structural pressure toward "0 points" on
failure, which is indistinguishable from "genuinely absent" and would manufacture false
positives. Phase 2 must wrap every call and treat *absence of positive evidence* as
`unknown` unless the baseline explicitly distinguishes the two.

**V** — Documentation inconsistency: the roadmap lists v4.17.0-rc1 as "Planned Jan 2027"
while 4.17.0 shipped 30 Aug 2026. A sloppiness signal about the docs, not a correctness
claim about the code — but it reinforces that published documentation is not a substitute
for measurement.

## 7. The seven questions from baseline-selection §9

Answered by execution in Phase 3. Full evidence in `docs/baseline-test-report.md` §4.1.

| # | Question | Status | Answer |
|---|---|---|---|
| 1 | SARIF per-check or category blobs? | **V** | Per-check: 7 category rules, 17 results on one page. Structurally normalisable; the message text is not usable as evidence |
| 2 | Dependency closure, size, compilation? | **V** | 10 packages, ~21 MB, 9 compiled `.so` files (lxml). Pure-Python core, platform-dependent closure |
| 3 | Network calls beyond the target? | **V** | None. DNS-traced: every lookup during an audit went to the target host |
| 4 | Which bonus checks emit evidence vs only points? | **V** | None via SARIF — only the 7 scored categories appear. `geo access --format json` is a separate, better surface |
| 5 | Where are its false positives? | **V** | Three classes measured: missing robots.txt as `error`, HTML soft-404 parsed as a malformed llms.txt, llms.txt severity overclaim |
| 6 | Failure behaviour? | **V** | Exit 1, stderr message, **no output document**. Not a typed unknown — our wrapper must supply it |
| 7 | Runtime, single URL and 25-URL batch? | **Partly V** | Single URL 4.2–10.0 s, measured. Batch still unmeasured; that is where the 5-minute risk sits |

*Phase 1's position, kept for the record:* **Six of seven remain unverified, and that is an
acceptable Phase 1 result** provided Phase 2
is designed so none of them can silently break us. The design rule that achieves this is
already chosen: the baseline is an accelerator behind our own interface, never a hard
dependency, and every check degrades to `unknown` rather than to a fabricated `pass` or
`fail`.

## 8. Reuse disposition

| Component | Disposition |
|---|---|
| SSRF/DNS-pinning URL validation | **Reuse directly.** Best-in-class for our threat model |
| Robots + 27-bot 3-tier taxonomy | **Reuse, re-severity.** Data is valuable; its weighting is not (baseline-gaps §2) |
| SARIF emitter | **Wrap**, pending §7 q1 |
| Prompt-injection detection | **Reuse and promote** to a finding-producing capability |
| JSON-LD / schema extraction | **Wrap** |
| Score, bands, point allocations | **Do not use.** Our severity model is gate-based and independent |
| `.recommendations` strings | **Do not use.** We generate mechanism-explained actions from our own contract |
| `geo fix --apply`, `geo citations` | **Forbidden** |
| `[llm]`, `[embedding]` extras | **Forbidden** |
