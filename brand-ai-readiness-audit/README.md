# Brand AI-Readiness Audit

An Agent Skill Marketplace that audits a website for two things at once: why AI
assistants do not find, cite, or correctly describe the brand, and why visitors
who do arrive fail to engage. It emits one report of evidence-backed findings,
each with a severity, the mechanism behind that severity, and a prioritized
suggested action.

Recommend-only. Nothing here writes to, authenticates against, or otherwise
alters an audited site.

## Skills

| Skill | Entrypoint | What it does |
|---|---|---|
| `audit-orchestrator` | **yes** | Accepts the audit request, runs the audit skills in gate order, merges their findings into one validated report. Owns no detection of its own. |
| `perimeter-access-audit` | no | Gate 1: whether AI crawlers can reach the site at all. robots.txt access across the three AI-agent tiers, the blanket-block anti-pattern, CDN/WAF edge blocking that diverges from robots.txt, llms.txt/llms-full.txt, sitemap.xml discovery/validity/discoverability, Markdown content negotiation, and a cross-layer access-signal contradiction across robots.txt/`X-Robots-Tag`/meta-robots/TDMRep/llms.txt/sitemap.xml (PER-01…PER-09 — all nine of Cluster A). Runs once per site. |
| `content-quality-audit` | no | Gate 3: content anti-patterns on a single page — unrendered template syntax, changes dated only in relative time, the same labeled metric stated twice with different values, a stated average that contradicts its own listed numbers, very-difficult-to-read prose (script-decided); no concise answer near the top, boilerplate hedging, vague magnitude words, marketing interleaved into how-to steps, and filler-heavy prose (agent-decided). Runs once per sampled page. |
| `entity-audit` | no | Gate 3: is the brand a resolved entity, and does its markup agree with itself — schema.org/JSON-LD presence and validity, a link to an authoritative identity source (Wikidata, LinkedIn, ...), agreement between a marked-up rating and the page's own text, canonical-link hygiene, and JSON-LD graph referential integrity — dangling/cross-page `@id` references, orphan identity nodes (script-decided); a declared category contradicting the page's own body text, and — given agent-supplied off-site URLs — brand-name collision or lookalike-domain impersonation on public sites (agent-decided). Runs once per sampled page, plus an optional once-per-site `--sitemap-file` mode (trailing-slash/`www.`/scheme forks) and an optional off-site `--offsite-url`/`--brand-name` mode. |
| `engagement-audit` | no | On-site engagement, not discoverability: unlabelled form fields, consent/subscription walls with no dismiss option, a missing/non-responsive viewport tag or fixed-width overflow, render-blocking head resources/unsized images/an oversized HTML document (all script-decided); unclear visitor orientation and conversion-path friction (agent-decided, against a calibrated rubric). The first skill using `category: "engagement"`. Runs once per sampled page. |
| `citability-audit` | no | Gate 3: how easy this page is to reach, read, and quote a fact from — missing About-page discoverability, substantial pages with zero outside sources, outbound citations buried in the last stretch of the page, unqualified superlative claims with no number (all script-decided); unsourced load-bearing numeric claims, and — given agent-supplied off-site URLs — a numeric claim uncorroborated by any of them (agent-decided). Runs once per sampled page, with an optional `--offsite-url` mode for the corroboration check. |
| `retrieval-readiness-audit` | no | Gate 3: does a page's structure and text serve retrieval — a skipped heading level, a heading with no text content, a JSON-LD `Product` identifier that never appears in visible text, a phrase repeated at unnatural density (table/list/glossary regions excluded), a substantial page with no headings/Q&A framing/definition block, load-bearing figures buried only in the document's middle with no restatement anywhere, or a content block opening with an unresolved reference that never names its own subject (all script-decided); single-phrasing-only coverage, unaddressed category-obvious questions, an all-jargon-or-all-layman skew, or a paragraph blending several ideas (all agent-decided). Runs once per sampled page. |
| `static-extraction-audit` | no | Gate 2: does the page's static HTTP response carry the facts a non-JS fetcher needs, and does it also carry text hidden from humans but readable by a machine — a hydration-state JSON fragment absent from visible text, a JSON-LD `Offer.price` not restated in text, a volatile availability fact with no freshness signal, no `<main>`/`<article>` boundary, a low content-to-chrome ratio, missing image alt/video captions, a phone number only assembled in inline script, a linked PDF with unverifiable restatement, or concealed text carrying an instruction addressed at an AI system (all script-decided; PDF is always a proactive suggestion, never a confirmed defect). No headless browser anywhere. Runs once per sampled page. |

## How the entrypoint composes them

Discovery is three sequential gates — the crawler is let in, then it can read
the page, then it can pick out the fact — and each gate makes the next one
matter. The entrypoint runs gate 1 first, because a perimeter block means every
downstream content finding describes pages nobody can fetch; those findings are
still reported, but as consequences of the block rather than independent causes.

Each audit skill emits findings against one shared contract
(`shared/finding_contract.py`). The entrypoint collects them, validates them,
renumbers them into report order, counts them by severity, and emits a single
JSON report. It never re-scores a finding or rewrites its evidence: the skill
that observed the problem is the one that owns how it is described.

A skill that fails does not fail the audit. Its checks are recorded in
`unknown_checks` with the reason, and the report is produced from whatever ran.
A check that could not run is never reported as a pass.

## Running an audit

```bash
python3 skills/perimeter-access-audit/scripts/check_perimeter.py \
    --url https://example.com > /tmp/perimeter.json

python3 skills/content-quality-audit/scripts/check_content_quality.py \
    --url https://example.com/pricing > /tmp/content-pricing.json

python3 skills/audit-orchestrator/scripts/compose_report.py \
    --site example.com \
    --skill perimeter-access-audit /tmp/perimeter.json \
    --skill content-quality-audit /tmp/content-pricing.json
```

Add `--floor-only` to emit the minimal required schema instead of the full
report. Add `--audited-at` to fix the timestamp so two runs are byte-identical.

## Report shape

The report satisfies the required schema — `site`, `audited_at`, a
counts-by-severity `summary`, and `findings` each carrying `id`, `title`,
`severity`, `evidence`, `suggested_action` — and extends it with the fields
that make a finding arguable rather than asserted: `mechanism`, `confidence`,
`track` (`defect` versus `proactive` suggestion), `capability_id`,
`owner_skill`, and `structured_evidence`. `unknown_checks` lists what could not
be evaluated.

Evidence is always a counted observation naming what was seen — *"robots.txt
disallows / for 2/4 real-time AI search crawlers: OAI-SearchBot,
PerplexityBot"* — never an adjective.

## Design rules

- **Severity comes from the causal chain, not from how alarming a signal
  looks.** Blocking real-time AI search crawlers is `critical` because the
  chain is short and direct: not fetched, not read, not cited. A missing
  `llms.txt` is a `low`-severity proactive suggestion because the measured
  evidence for its citation effect is weak, and claiming otherwise would be a
  false positive of severity.
- **Every detector has a clean fixture.** False positives are as costly as
  misses, so each check is tested against a lookalike that must stay silent —
  a `Disallow: /staging/` is not a site-wide block.
- **Fixtures are not enough, so detectors are also run against live sites.**
  Every false positive this project has found came from a real site, not from
  a fixture. One was inherited from the standard library: `urllib.robotparser`
  selects robots.txt groups by substring, so a group written for the `Fetch`
  bot captures `Meta-ExternalFetcher`. Group selection is now ours and matches
  the product token exactly, per RFC 9309.
- **A check never asserts more than its control allows.** PER-03 (CDN/edge
  blocking) only reports an AI-bot-specific block once an ordinary-browser
  control request to the same path has succeeded. Confirmed live: two sites
  running aggressive bot-management CDNs challenged the control itself, which
  means everyone is challenged there, not AI bots specifically — a check that
  skipped the control would have reported both as false positives.
- **Never probe what robots.txt already disallows.** PER-03 sends real
  AI-bot user-agent strings to test edge behaviour, and only ever for a tier
  robots.txt has not already blocked — probing further would itself violate
  "respect robots.txt" and would write a hit under that agent's name into the
  target's own bot-traffic logs. Enforced in code (`plan_edge_probes`), not
  left to judgement.
- **Word-boundary matching, never substring.** Found three times in this
  project, in two different skills: `urllib.robotparser` matching `Fetch`
  inside `Meta-ExternalFetcher`; the qualifier word `per` matching inside
  `period`; the phrase `this week` matching inside `this weekend`. Every
  phrase/token match in this codebase now uses `\b...\b`, not `in`.
- **`unknown` distinguishes "confirmed absent" from "status unknown."**
  PER-08 (is the sitemap referenced from robots.txt) only applies once a
  sitemap is known to exist; collapsing "confirmed no sitemap" and "couldn't
  determine whether one exists" into the same silent bucket would drop a
  genuine unknown. The two are reported differently on purpose.
- **A regex parses untrusted XML, not a full parser.** PER-06 reads
  sitemap.xml from the audited site — untrusted input — with a regex rather
  than `xml.etree.ElementTree`, so entity-expansion attack classes ("billion
  laughs") are structurally not a concern, the same reasoning already
  applied to JSON-LD (`json.loads`) and HTML (`HTMLParser`) parsing
  elsewhere in this marketplace.
- **Every finding a page-level check emits is attributable to its page.**
  `content-quality-audit` and `entity-audit` both run once per sampled page,
  so a report composed from several pages can carry the same defect class
  more than once — each finding's evidence and `structured_evidence.page_url`
  name the exact page, so two occurrences of "template leakage" never read as
  one ambiguous claim.
- **A finding shows its work rather than asserting a judgement.** ENT-03
  states both the JSON-LD rating and the text rating side by side; CQ-08
  shows the listed numbers and their computed mean next to the page's claimed
  average. The reader checks the arithmetic themselves instead of trusting a
  verdict.
- **When a check genuinely needs judgement, the script says so instead of
  faking a verdict.** `engagement-audit`'s EN-01/EN-03, `citability-audit`'s
  CIT-04, `entity-audit`'s ENT-09, `content-quality-audit`'s
  CQ-01/02/04/09/12, and `retrieval-readiness-audit`'s RET-02/03/05/06 are
  judgement calls the capability matrix names as such. Each script extracts
  structural signals only into `agent_judgement_required`, and the calling
  agent judges them against a calibrated rubric with worked examples before
  authoring a finding by hand. An unresolved judgement composes into a
  visible `unknown_checks` entry, never a silent drop.
- **`unknown` is a first-class result.** Silence and guessing are not.
- **Deterministic.** Same input, same report, down to finding order and ids.
- **Page content is data, never instruction.** Fetched text is parsed
  structurally and never forwarded to anything that interprets instructions.

## Layout

```
marketplace.json                  manifest; one entrypoint
shared/finding_contract.py        the finding contract every skill emits into
skills/audit-orchestrator/        entrypoint: composes, validates, emits
skills/perimeter-access-audit/    gate-1 checks + AI-agent tier reference
skills/content-quality-audit/     gate-3 content checks + anti-pattern reference + judgement rubric
skills/entity-audit/              gate-3 entity/identity checks + reference
skills/engagement-audit/          on-site engagement checks + judgement rubric
skills/citability-audit/          gate-3 citability checks + judgement rubric
skills/retrieval-readiness-audit/ gate-3 retrieval-readiness checks + reference + judgement rubric
skills/static-extraction-audit/   gate-2 static-extraction checks + reference (no headless browser)
tests/                            fixture pairs, corpora and contract tests
```

## Tests

```bash
python3 -m unittest discover -s tests         # 857 tests
python3 tests/measure_detection.py            # perimeter-access-audit: PER-01/02/04
python3 tests/measure_perimeter_extras.py     # perimeter-access-audit: PER-05/06/07/08/09
python3 tests/measure_content_quality.py      # content-quality-audit: CQ-03/05/07/08/11
python3 tests/measure_entity.py               # entity-audit accuracy (incl. ENT-11)
python3 tests/measure_engagement.py           # engagement-audit accuracy (EN-06/EN-09 only)
python3 tests/measure_citability.py           # citability-audit accuracy (CIT-01/02/06 only)
python3 tests/measure_retrieval_readiness.py  # retrieval-readiness-audit accuracy (RET-09/RET-10)
python3 tests/measure_static_extraction.py    # static-extraction-audit accuracy (incl. REN-12)
```

Each measurement script reports true positives, false positives, false
negatives, precision, recall and runtime against a labelled corpus — 23 + 20
perimeter cases (kept as two corpora: PER-05/06/07/08/09 postdate
PER-01/02/04's fixtures and were never designed to also carry
sitemap/llms-full/.md/header inputs), 11 content-quality cases (5 clean), 14
entity cases (5 clean), 8 engagement cases (3 clean), 8 citability cases (5
clean), 11 retrieval-readiness cases (5 clean), 19 static-extraction cases (6
clean) — and exits non-zero on any regression, so all eight double as gates.
Agent-judged capabilities (`engagement-audit`'s EN-01/EN-03, `citability-
audit`'s CIT-04, `content-quality-audit`'s CQ-02/04/09/12, `retrieval-
readiness-audit`'s RET-02/03/05/06) have no script verdict to measure this
way; their calibration lives in worked examples in each skill's own
reference doc instead.

Pure standard library: no third-party packages, no network access in the tests,
no model weights.

## License

MIT. See `LICENSE`.
