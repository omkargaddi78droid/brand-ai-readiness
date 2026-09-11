# Brand AI-Readiness Audit

An Agent Skill Marketplace that answers one question for any website: why don't AI assistants find, cite, or correctly describe this brand, and why do the visitors who do arrive leave without engaging?

Point it at a URL. Get back one report: findings with evidence and severity, plus prioritized fixes.

Recommend-only. No skill here writes to, logs into, or changes the audited site in any way.

## Two failure modes, one report

Round 2 of this project studied why AI assistants cite some brands and ignore others. Two patterns kept showing up:

- **Discoverability failures.** A crawler gets blocked, or gets in but can't parse the page, or parses it but can't find the one fact it needed. Any of the three breaks the chain, and the brand never makes it into an answer.
- **Engagement failures.** A visitor lands on the page anyway, from a link or a search result, and leaves because the page doesn't orient them, buries the point, or throws up friction before they get value.

This marketplace runs eight skills against both halves of that problem and merges everything into one validated report.

## The skills

| Skill | Entrypoint | Covers |
|---|---|---|
| `audit-orchestrator` | yes | Takes the audit request, runs the other skills in order, validates and merges their findings into one report. Detects nothing on its own. |
| `perimeter-access-audit` | no | Gate 1, can a crawler even get in. robots.txt rules across AI-agent tiers, CDN/WAF blocks that only trigger for AI bots, llms.txt, sitemap discoverability, and contradictions between the different signals a site can send about who's allowed in. |
| `static-extraction-audit` | no | Gate 2, can a plain HTTP fetch (no headless browser) read what matters. Facts that only exist after JavaScript runs, prices that live only in JSON-LD, phone numbers assembled by a script, thin main content, and text hidden from people but readable by a machine. |
| `content-quality-audit` | no | Gate 3, page-level content problems: unrendered template code, dates given only in relative time ("3 weeks ago"), the same metric stated twice with different numbers, hedge-heavy prose, and marketing copy dropped into how-to steps. |
| `entity-audit` | no | Is the brand a resolved, unambiguous entity. Schema.org/JSON-LD correctness, a link to an authoritative identity source, markup that agrees with the page's own text, and name collisions with unrelated brands. |
| `engagement-audit` | no | On-site friction once a visitor lands: unlabeled form fields, dismiss-free consent walls, broken mobile layout, render-blocking resources, and unclear page orientation. |
| `citability-audit` | no | How easy the page is to quote a fact from: outbound sourcing, unqualified superlatives with no number behind them, and claims an assistant would need corroboration for before repeating them. |
| `retrieval-readiness-audit` | no | Does the page's structure help retrieval: heading hierarchy, Q&A framing, load-bearing numbers buried in the middle with no restatement, and paragraphs that mix too many ideas to quote cleanly. |

Some checks run purely in script (fast, deterministic, no judgment call). A few genuinely need a human-like read, so the script extracts the structural signal and hands it to the calling agent with a calibrated rubric instead of faking a verdict.

## Alignment with the Round-2 appendix

The problem statement's appendix lays out six mechanisms behind why assistants find, trust, and repeat some content and not others. Here's where each one lands in the skills:

| Concept | Mechanism | Where it's implemented |
|---|---|---|
| A. Search visibility (crawl, read, extract) | A page has to survive three steps in order, or it doesn't exist for the machine | The three gates: `perimeter-access-audit` (crawler let in), `static-extraction-audit` (page read without JS), `retrieval-readiness-audit` (fact picked out of structure) |
| B. How assistants use sources | An assistant looking things up in the moment only cites what it can reach, read, and quote cleanly | `citability-audit` (outbound sourcing, unqualified claims, quotable numbers) and `retrieval-readiness-audit` (Q&A framing, one clean answer per idea) |
| C. How machines read a page | Facts assembled only after page load, or locked in a non-text form, don't reach a simple reader even though a person sees them fine | `static-extraction-audit`: hydration-only JSON, prices only in JSON-LD, phone numbers built by inline script, text with no static rendering |
| D. Agreement across the web | A fact repeated consistently across independent sources gets trusted; a name shared by several entities gets confused unless something disambiguates it | `entity-audit` (authoritative identity links, name collisions, lookalike-domain impersonation) and `citability-audit`'s off-site corroboration check |
| E. Personalization and prior context | Two people asking the same question get different answers depending on who's asking and what context the assistant already holds on them | Not implemented, and not attempted. This is a per-user, stateful property of the assistant serving the answer, not a property of the page. A stateless, unauthenticated, single-fetch auditor has no session to observe and no user to personalize for, so a check here would have to fake a verdict with no real signal behind it. `engagement-audit` explicitly excludes this (see its SKILL.md, EN-02/EN-10) rather than pretend to measure it. |
| F. Why machines drop content from summaries | Real substance surrounded by low-value filler, or carried by something a summarizer can't read, gets left out of the summary | `content-quality-audit`: boilerplate hedging, vague magnitude words with no number, and a dedicated signal-to-filler ratio check (CQ-12) |

Five of six concepts get a direct, testable check. The sixth (E) gets an explicit, reasoned exclusion instead of a check that would only simulate coverage. That's a design choice, not a gap: a recommend-only auditor that never authenticates and never holds a session across requests structurally cannot observe personalization, and claiming otherwise would be the kind of false positive this project explicitly tests against everywhere else.

## How the entrypoint composes them

Discoverability is three gates in sequence: get the crawler in, let it read the page, let it find the fact. Each gate matters more once the one before it passes. `audit-orchestrator` runs perimeter checks first, because a blocked crawler makes every downstream content finding a consequence of that block, not an independent problem. Findings still get reported either way, just attributed correctly.

Every skill writes into one shared finding contract (`shared/finding_contract.py`). The orchestrator collects those findings, validates them, orders them, counts them by severity, and emits one JSON report. It never rewrites a finding's evidence or re-scores it; whichever skill observed the problem owns how it gets described.

If a skill fails, the audit doesn't fail. Its checks land in `unknown_checks` with a reason, and the report gets built from whatever did run. A check that couldn't run is never reported as a pass.

## Running an audit

```bash
python3 skills/perimeter-access-audit/scripts/check_perimeter.py \
    --url https://example.com > /tmp/perimeter.json

python3 skills/content-quality-audit/scripts/check_content_quality.py \
    --url https://example.com/pricing > /tmp/content-pricing.json

mkdir -p report

python3 skills/audit-orchestrator/scripts/compose_report.py \
    --site example.com \
    --skill perimeter-access-audit /tmp/perimeter.json \
    --skill content-quality-audit /tmp/content-pricing.json \
    > report/result_example.com.json
```

Every audit writes to `report/result_<site>.json` at the marketplace root instead of printing the report into the chat — re-auditing the same site overwrites its own file rather than piling up duplicates. Add `--floor-only` for the minimal required schema. Add `--audited-at` to pin the timestamp so two runs come out byte-identical.

## Report shape

Every report meets the required floor: `site`, `audited_at`, a counts-by-severity `summary`, and `findings` with `id`, `title`, `severity`, `evidence`, `suggested_action`. On top of that floor, each finding also carries `mechanism` (why this severity, not just what was seen), `confidence`, `track` (a confirmed defect versus a proactive suggestion), and `structured_evidence` a person can check by hand. `unknown_checks` lists what couldn't be evaluated and why.

Evidence is always a counted observation, never an adjective: "robots.txt disallows / for 2 of 4 real-time AI search crawlers: OAI-SearchBot, PerplexityBot," not "robots.txt looks restrictive."

## Design choices worth knowing about

- **Severity follows the causal chain, not how alarming a signal looks.** Blocking a real-time AI crawler is critical because the chain is short: not fetched, not read, not cited. A missing `llms.txt` is a low-severity suggestion, because the evidence that it changes citation outcomes is weak, and calling it critical would be a false positive of severity, not of detection.
- **Every check has a clean fixture that must stay silent.** A false positive costs as much as a miss. `Disallow: /staging/` is not a site-wide block, and the test suite makes sure a check agrees.
- **Fixtures aren't enough, so checks also got run against live sites.** Every false positive this project found came from a real site, not a fixture. One came from Python's own standard library: `urllib.robotparser` selects a robots.txt group by substring match, so a group written for `Fetch` also captured `Meta-ExternalFetcher`. Group selection here matches the product token exactly instead, per RFC 9309.
- **A check never claims more than its control allows.** The CDN/edge-blocking check only reports an AI-bot-specific block once a plain browser request to the same path succeeded first. Two sites with aggressive bot-management CDNs challenged that control request too, meaning everyone gets challenged there, not just AI bots. Skip the control and both would have shown up as false positives.
- **No check probes what robots.txt already disallows.** Testing edge behavior against a blocked path would itself break "respect robots.txt," and would leave a real hit under that bot's name in the target's own traffic logs.
- **`unknown` means something specific: confirmed absent versus status unknown.** A check that can't tell those two apart drops a genuine unknown into a silent bucket. This codebase keeps them separate on purpose.
- **Untrusted XML gets parsed with a regex, not a full XML parser.** Sitemap.xml comes from the audited site, so it's untrusted input; a regex reader sidesteps entity-expansion attacks structurally, the same reasoning already applied to JSON-LD (`json.loads`) and HTML (`HTMLParser`) elsewhere in the codebase.
- **Page content is data, never instruction.** Fetched text gets parsed structurally and never forwarded anywhere that would interpret it as a command, which closes off prompt-injection attempts hidden in a page's own text.
- **Deterministic.** Same input, same report, down to finding order and IDs.
- **The prose-level checks are English-only, on purpose and disclosed.** Hedge/filler/marketing/superlative phrase matching, the Flesch readability formula, and month-name/relative-date detection all run against hardcoded English vocabulary. They won't crash on a non-English page; they'll just never fire, so those specific capabilities read as silently clean rather than genuinely checked. Structural, markup, and access checks (the majority of this marketplace) carry no such limit.

## Layout

```
marketplace.json                  manifest; one entrypoint
shared/finding_contract.py        the finding contract every skill emits into
skills/audit-orchestrator/        entrypoint: composes, validates, emits
skills/perimeter-access-audit/    gate-1 checks + AI-agent tier reference
skills/static-extraction-audit/   gate-2 checks (no headless browser)
skills/content-quality-audit/     gate-3 content checks + judgment rubric
skills/entity-audit/              gate-3 entity/identity checks
skills/engagement-audit/          on-site engagement checks + judgment rubric
skills/citability-audit/          gate-3 citability checks + judgment rubric
skills/retrieval-readiness-audit/ gate-3 retrieval-structure checks + judgment rubric
tests/                            fixture pairs, labeled corpora, contract tests
report/                           one result_<site>.json per audited site
third_party/, vendor/             vendored dependencies (see below)
```

## Tests

```bash
python3 -m unittest discover -s tests     # 1,312 tests
python3 tests/measure_detection.py        # perimeter-access-audit accuracy
python3 tests/measure_perimeter_extras.py
python3 tests/measure_content_quality.py
python3 tests/measure_entity.py
python3 tests/measure_engagement.py
python3 tests/measure_citability.py
python3 tests/measure_retrieval_readiness.py
python3 tests/measure_static_extraction.py
```

Each `measure_*` script runs its skill against a labeled corpus and reports true positives, false positives, false negatives, precision, and recall, then exits non-zero on any regression. Together the corpora cover well over a hundred hand-labeled cases across all eight skills, split roughly half defect and half clean, specifically so a check that starts firing on clean pages gets caught immediately. Checks that need agent judgment instead of a script verdict (a handful across engagement, citability, content-quality, and retrieval-readiness) get calibrated through worked examples in their own reference docs, since there's no script verdict to measure them against.

## Dependencies

`bs4`, `soupsieve`, `phonenumbers`, and `typing_extensions` are vendored directly under `third_party/` (trimmed where possible, `phonenumbers` cut from 23 MB down to about 3.2 MB by dropping unused geodata/carrier metadata). Nothing gets installed at runtime and the tests make no network calls. No pre-trained model weights anywhere. Full marketplace comes in under 10 MB, well inside the 50 MB submission cap.

## License

MIT. See `LICENSE`.
