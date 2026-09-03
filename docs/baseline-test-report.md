# Baseline Test Report

Phase 3 output. Everything here was executed and measured. Where a number
appears, it came from a run in this environment on 2026-09-02, not from
documentation.

**The environment changed since Phase 1.** `pip` egress works now, so the
baseline was installed at the pinned version and six of the seven Phase 1
questions are answered by execution rather than left at grade **U**.

---

## 1. Headline results

| Measurement | Our skill | Baseline `geo-optimizer-skill` 4.17.1 |
|---|---|---|
| Corpus precision / recall | 1.000 / 1.000 on 23 labelled cases | Not measurable offline — its SSRF guard rejects loopback, so it cannot be pointed at local fixtures |
| False positives on 6 live sites | 3 found, 3 fixed, 0 remaining | ≥ 6 observed, of three distinct classes (§4) |
| Findings per live site | 0–2, each verified against the raw file | 7–21, mostly score-driven suggestions |
| Runtime, single site | 1.0–3.5 s wall (two GETs) | 4.2–10.0 s |
| Offline evaluation | 13.9 ms for 23 cases | Not possible |
| Third-party network contact | none | none — verified by DNS trace |

The decisive result is not the precision number, which is self-graded. It is
that **the live run found three false positives the corpus did not**, and one
of them was inherited from the Python standard library.

---

## 2. Our detection accuracy, measured

`tests/measure_detection.py` against `tests/corpus/cases.json`.

```
Cases: 23 (13 defect, 8 clean, 2 unknown)
TP 17 · FP 0 · FN 0 · severity errors 0 · unknown errors 0 · report errors 0
Precision 1.000 · Recall 1.000
Evaluation time: 13.9 ms for 23 cases (slowest case 1.57 ms)
```

Every case also composes into a schema-valid report; that is asserted per case,
not spot-checked.

**What this number is worth.** The corpus was written by the same author as the
detectors, so it measures regression safety and reasoning-made-explicit, not
field accuracy. It is the comparison point every later capability is judged
against, and nothing more. The honest accuracy evidence is §3.

Nine of the 23 cases are lookalikes that must stay silent — scoped disallows,
SEO-crawler blocks, an HTML error page served at `/robots.txt`, messy
formatting with a comment naming GPTBot, a missing `robots.txt`, and the two
traps recovered from the live run. Precision without those is unmeasured.

---

## 3. Live validation: three false positives, found and fixed

Six public sites, read-only, two GETs each. Every finding was then checked
against the raw `robots.txt` / `llms.txt` by hand.

### 3.1 Substring user-agent matching — the serious one

**Symptom.** `wikipedia.org` reported `PER-01-on-demand-blocked`, high
severity: *"robots.txt disallows / for 1/4 on-demand user-triggered fetchers:
Meta-ExternalFetcher."*

**Ground truth.** Wikipedia's `robots.txt` never mentions Meta. Searching it
for `meta` returns one comment line.

**Root cause.** `urllib.robotparser` selects a group by substring:
`Entry.applies_to` asks whether the group's token appears anywhere inside the
crawler name. Wikipedia carries a group for the historical `Fetch` bot, and
`fetch` is a substring of `meta-externalfetcher`. Proven by walking the parsed
entries: the matched entry's agent list is `['Fetch']` with rule
`(False, '/')`.

The same defect would have fired on a group named `Claude` (capturing
`Claude-User`, `Claude-SearchBot`) or `Search` (capturing `OAI-SearchBot`).

**Fix.** Group *selection* is now ours; rule *evaluation* stays with the
standard library. `parse_groups()` splits robots.txt into groups, and
`can_fetch_root()` selects by case-insensitive exact product token per RFC
9309, falling back to `*`, then hands only the applicable group to
`RobotFileParser` for path and precedence handling.

**Regression.** `clean_substring_trap.txt`, minimised to four groups, plus
five unit tests covering exact match, case-insensitivity, wildcard fallback,
and the no-rules case.

This is the failure our own principles named in advance — *parse the exclusion
protocol properly rather than substring-matching* — arriving through a
dependency we trusted. It would never have shown up on hand-written fixtures,
because nobody writes a group called `Fetch` in a fixture.

### 3.2 Markdown list markers

`github.com` publishes a well-formed `llms.txt` (178 lines, `text/plain`, H1,
blockquote, `##` sections). We reported it malformed: *"no markdown link list
entries"*. GitHub uses `* [Title](url): description`; the check accepted only
`-`. Markdown treats `-`, `*` and `+` identically.

Fixed, with `clean_asterisk_bullets.txt` as the regression fixture.

### 3.3 HTML soft 404 at `/llms.txt`

`reddit.com` returns `200 text/html` — its own page — for `/llms.txt`. We
reported *"published but does not follow the convention"* with four structural
gaps. The file does not exist; the host answers unknown paths with markup.

Now detected and reported as an absence, with evidence naming the soft 404.
Fixture: `defect_soft_404_html.txt`.

**The baseline makes this same mistake**, and it is still in it: on
`reddit.com` it emits `llms.txt missing H1 header`, `llms.txt missing H2
sections`, `llms.txt missing markdown links` for a file that was never
published.

### 3.4 Live results after the fixes

| Site | Findings | Verified against |
|---|---|---|
| `python.org` | llms.txt missing (low) | `/llms.txt` → 404 |
| `github.com` | none | conforming llms.txt; no AI agent blocked |
| `wikipedia.org` | llms.txt missing (low) | `/llms.txt` → 301 → 404 |
| `nytimes.com` | **all AI agents blocked (critical)**, llms.txt missing | 15/15 agents blocked by explicit groups; wildcard group not blocked at root — the correct PER-02 variant |
| `reddit.com` | **all AI agents blocked (critical)**, llms.txt missing | wildcard `Disallow: /`; llms.txt soft 404 |
| `cloudflare.com` | none | AI agents allowed; llms.txt published and conforming |

Two critical findings, both independently verified true. Zero false positives
remaining. Runtime 1.0–3.5 s per site.

---

## 4. The baseline, measured

### 4.1 The seven Phase 1 questions

| # | Question | Answer |
|---|---|---|
| 1 | SARIF per-check or category blobs? | **Per-check.** 7 category rules, 17 results on one page, each with `ruleId`, `level`, `message`, `locations`. Structurally normalisable — but see §4.2 |
| 2 | Dependency closure, size, compilation? | **10 packages**: beautifulsoup4, certifi, charset-normalizer, click, idna, lxml, requests, soupsieve, typing-extensions, urllib3. ~21 MB installed excluding pip. **9 compiled `.so` files** (lxml, 12 MB) — the *core* is pure Python, the *closure* is not, so it needs platform wheels |
| 3 | Network calls beyond the target? | **None.** DNS traced through a `socket.getaddrinfo` hook during `geo audit`: 10 lookups, all to the target host. The zero-telemetry claim holds, now verified rather than trusted |
| 4 | Which bonus checks emit evidence? | **None of them, via SARIF.** Across 7 runs only the 7 scored-category rule ids ever appear. Prompt-injection, RAG-chunk, decay, multimodal and CDN checks surface nowhere in SARIF. `geo access --format json` is a separate and better surface (§4.3) |
| 5 | Where are its false positives? | Measured, three classes — §4.2 |
| 6 | Failure behaviour? | **Exit 1, message on stderr, no output document at all.** An unresolvable host produces an empty file, not a typed failure. Our wrapper's "skill produced nothing usable → unknown" path is therefore the required handling, not a nicety |
| 7 | Runtime? | 4.2 s (example.com), 8.6–10.0 s on real sites, single URL. Sitemap batch not measured |

One question moves the other way. **The SSRF guard rejects `127.0.0.1`** —
*"URL points to a non-public address"*. Good security, and it means the
baseline cannot be exercised against a local fixture server. Its behaviour is
only observable against live third-party sites, so it cannot be regression
tested offline, and neither could any check we routed through it.

### 4.2 Measured false positives

**Missing `robots.txt` reported as an error.** On `example.com` (`/robots.txt`
→ 404) it emits two `error`-level results: *"robots.txt not found — AI bots
cannot determine access rules"* and *"Critical citation bots (OAI-SearchBot,
Claude-SearchBot, PerplexityBot, Googlebot, Applebot) not properly
configured"*. Under RFC 9309 an absent `robots.txt` permits everything. Nothing
is blocked, no bot is misconfigured, and one root condition produces two
findings.

**Soft-404 `llms.txt` parsed as a malformed file.** §3.3.

**Severity overclaim on `llms.txt`.** Absence is reported as *"essential for AI
search indexing"* at `error` or `warning` level — 7 such results across the 7
runs. This is the calibration defect predicted in `baseline-gaps.md` §2,
observed directly. We report the same condition as `low` and proactive.

**Score coupling leaks into the finding text.** Messages carry point values
(*"Add RSS/Atom feed ... (2pt)"*) and unsourced effect sizes (*"No statistics
or numerical data found (+33% AI visibility)"*). 28 of the results across 7
runs push the speculative `/.well-known/ai.txt` and `/ai/*.json` conventions.

**Consequence for the adapter.** SARIF gives us *which checks fired*, and
nothing else we can use. The messages are assertions rather than counted
observations, there is no properties bag, and `locations` carries only the page
URI. Any integration must re-derive severity and author its own evidence — so
the value on offer is check coverage, not evidence.

### 4.3 The surface worth integrating

`geo access --format json` is materially better than SARIF for our purposes:

```json
{"url": "...", "overall_status": "blocked",
 "robots_allows_citation_bots": false,
 "robots_blocks": ["GPTBot", "OAI-SearchBot", "ChatGPT-User", ...]}
```

It carries a typed `overall_status` with an explicit `unknown` state — the one
place the tool distinguishes "could not tell" from "zero points" — and, on
`nytimes.com`, it reported **CDN/WAF blocking of GPTBot, OAI-SearchBot,
PerplexityBot and Claude-SearchBot** on top of the robots.txt rules. That is
PER-03, which the matrix has as build-from-scratch, arriving with named agents.

**Phase 4 must decide one thing before adopting it.** The CDN check works by
sending live requests under other crawlers' user agents. That is the only way
to observe edge blocking, and it is also user-agent impersonation against a
third party. The decision, its justification and its rate limits belong in the
open, not inside a helper function.

---

## 5. What changed in the code this phase

| Change | Driver |
|---|---|
| `parse_groups()` / `can_fetch_root()` — RFC 9309 exact-token group selection | §3.1, a live false positive |
| `*` and `+` accepted as list markers | §3.2 |
| HTML body at `/llms.txt` reported as an absence | §3.3 |
| 3 corpus cases, 3 fixtures, 13 tests | Regressions for the above |

Tests: **63 passing**, up from 50. Corpus: **23 cases**, up from 20.

## 6. Standing limitations

- **The corpus is self-authored.** It cannot prove field accuracy; §3 is the
  evidence that matters, and it is six sites deep.
- **The baseline is untestable offline.** Any capability routed through it
  inherits that. Prefer our own implementation wherever the check is cheap.
- **Sitemap batch runtime unmeasured.** The 5-minute budget risk sits there,
  not in the single-URL path.
- **Six sites is a small sample**, chosen for robots.txt variety, not
  representativeness. Two of the three bugs found came from exactly one site
  each, which is the argument for widening the sample before trusting any
  precision figure.

## 7. Next

**Phase 4 — first capability additions**, per the front-loading order in the
capability matrix. Two intake decisions now have evidence behind them:

- **PER-03 (edge/CDN blocking)** moves from build-from-scratch to integration
  candidate, gated on the impersonation decision in §4.3.
- **`geo access --format json`** replaces SARIF as the integration surface to
  evaluate first. SARIF stays a fallback for check coverage only.
