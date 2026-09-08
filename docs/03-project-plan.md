# Cycle 24: external-review candidates — scoring, dependency-policy revision, and implementation

## Context

Cycle 23 shipped CQ-10 freshness detection, INF-10 budget governance across
all four multi-page skills, and closed out the post-Phase-4 gap list. A
review external to this project's own research pipeline then proposed 20
code-level improvements across three buckets: architecture/orchestration,
CQ-check heuristic refinements, and replacing hardcoded data with
third-party libraries. Per this project's standing discipline
(`01-project-plan.md` §2), nothing gets adopted without being scored
individually against the project's constraints and the same five criteria
used for the original 28 cycle-22 candidates — no batch adoption.

The full scored analysis (every claim checked against the real code, every
suggestion checked against the five hard constraints, redundancy against the
capability matrix, and architecture-pattern fit) lives in the session's plan
file, not duplicated here in full — this document is the **decision record
and implementation tracker**: what was decided, what changed about the
dependency policy mid-cycle, and exactly what is done vs. still open.

## Dependency-policy revision (mid-cycle, explicit user decision)

The zero-third-party-dependency **precedent** (not a competition rule — this
project's own unbroken practice through cycles 19-23) was explicitly relaxed
this cycle. Revised rule, as given:

- A third-party package may be **vendored** (its actual files placed in the
  repo, never pip-installed or fetched at runtime) provided the **total
  vendored payload stays under 50MB** and **no runtime call to an external
  service** is made — vendoring replaces live API calls, never coexists with
  them.
- Compiled C-extension binaries were initially asked about and the user's
  first answer allowed them if vendored+sized. **This was then narrowed by a
  follow-up, final decision: bs4 stays on the stdlib `html.parser` backend
  only, as a fixed choice independent of size — not `lxml`, not
  `trafilatura`.** Treat "no compiled binaries" as the operative rule for
  everything actually implemented this cycle; every vendored package below
  is pure Python with zero compiled extensions, confirmed by inspecting the
  actual wheel contents (not just assumed from the package's reputation).
- **Unchanged:** no pre-trained model weights, no external service required
  at runtime, and determinism — those five original constraints are exactly
  as strict as before. Only the "must be stdlib-only" precedent moved.

### The user's final narrowing decision on items 7-8 (verbatim intent, preserved)

> 1. Keep bs4 on the **stdlib `html.parser` backend only** — not as a
>    size-budget fallback, but as a fixed decision independent of size.
> 2. For CQ-01's opening-block candidate quality, skip trafilatura and do
>    the `<main>/<article>/<nav>/<header>/<footer>` stripping directly in
>    bs4-on-stdlib.
> 3. Confirm phonenumbers, textblob (lexicon mode), and dateparser are
>    genuinely pure-Python with no C-extension anywhere in their own
>    dependency chains.
>
> Net effect: items 9, 10, 11 (bot-taxonomy snapshot, phonenumbers,
> dateparser) stand as scored — pure data/pure Python. Items 7 and 8 (bs4,
> trafilatura) narrow to "bs4-on-stdlib only, no lxml, no trafilatura."

**Verification done against that instruction (via `pip download`, inspecting
actual wheels, not assumed):**

- **bs4 (4.15.0) + soupsieve (2.9.2) + typing_extensions (4.16.0):** all
  three are `py3-none-any` pure-Python wheels, zero `.so`/`.pyd` files. bs4
  runs fully on stdlib `html.parser` with no `lxml` present — verified by
  actually parsing HTML through it. typing_extensions is a genuine runtime
  dependency of bs4 4.15 (unconditional imports in `formatter.py`,
  `_typing.py`, `element.py`, `dammit.py`), not merely a type-checking
  extra — it had to be vendored too. Combined footprint: 748KB.
- **phonenumbers (9.0.38):** pure Python (`py2.py3-none-any`), zero compiled
  extensions, confirmed. Full package is 23MB (mostly `geodata/` for reverse
  geocoding, `carrierdata/`, `tzdata/`, `.pyi` stubs) — none of that is
  needed for parse/validate/format, which is all this project uses. Trimmed
  to 2.6MB by deleting those directories; re-verified `parse` /
  `is_valid_number` / `format_number` still work correctly after trimming.
- **dateparser and textblob — DO NOT vendor. Finding from this cycle's
  verification, not from before:** both transitively depend on the
  third-party `regex` package (`dateparser` directly; `textblob` via its
  hard, unconditional `nltk>=3.9` dependency, which itself requires
  `regex`), and `regex` ships as a **platform- and Python-ABI-specific
  compiled wheel** (`regex-2026.9.3-cp314-cp314-manylinux2014_x86_64...`) —
  not a pure-Python fallback. This is a real portability risk beyond the
  abstract "compiled binaries" question: a wheel pinned to CPython 3.14 on
  manylinux2014/x86_64 will not import at all on a grading environment with
  a different Python version or OS/arch, silently breaking every skill that
  imports it. `textblob` additionally re-raises the `nltk` `punkt`-tokenizer
  pretrained-statistical-model gray-zone risk already flagged against the
  "no pre-trained model weights" constraint. **Decision: both dropped.**
  `phonenumbers` has no such transitive dependency and was the only one of
  the three actually vendored.
- **Bot-taxonomy snapshot:** not a Python package at all — a single JSON
  data file (see below), MIT-licensed, no dependency question applies.

### `vendor/` vs `third_party/` — a new distinction, and why

`tests/test_marketplace_manifest.py`'s existing `SafetyTests.
test_vendor_contains_data_only_no_code` enforces that `vendor/` may contain
**no** `.py`/`.so`/`.pyd` file — this predates cycle 24 and was written for
the public-suffix-list data asset. Vendoring actual package *code* under
`vendor/` would have silently broken that guarantee's intent (data-only).
Rather than weaken that test's meaning, a new sibling directory,
`third_party/`, was created specifically for vendored package **code**,
with its own, separately-scoped safety test
(`test_third_party_contains_only_declared_packages_no_compiled_binaries`)
enforcing exactly the declared package list and zero compiled binaries.
`vendor/` keeps its original data-only meaning unchanged and gets one new
data asset (`bot_taxonomy.json`). This split is the intended, permanent
structure going forward, not a temporary cycle-24 workaround.

## What's implemented (done, on the working tree, uncommitted)

### Vendored assets

- **`third_party/bs4/`, `third_party/soupsieve/`, `third_party/
  typing_extensions.py`, `third_party/phonenumbers/`** — package code,
  748KB + 2.6MB. Licenses copied to `third_party/licenses/`.
- **`vendor/bot_taxonomy.json`** — a snapshot of
  `https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/
  robots.json` (MIT, snapshot date 2026-09-07, license copied to
  `vendor/LICENSE-ai-robots-txt.txt`), 175 bots, deterministically
  classified into this project's existing 3-tier scheme (`training`/
  `ai_search`/`on_demand`) by a keyword classifier over each entry's
  `function`/`description` fields. **The original 15 hand-curated bot→tier
  assignments in `check_perimeter.py`'s `BOT_TIERS` are preserved verbatim
  as overrides** — cross-checked 14/15 auto-classified identically, the one
  divergence (`DuckAssistBot`: auto-classifier said `on_demand`, original
  said `ai_search`) was resolved in favor of the original to guarantee zero
  regression on already-shipped, already-tested bot classifications. The
  other 160 bots are new coverage, not individually hand-verified — this is
  documented in the JSON's own `_meta` block.
- **`docs/../vendor/VENDORED.md`** — **NOT YET updated** with the
  `bot_taxonomy.json` entry (still only documents `public_suffix_list.dat`).
  **TODO**, see below. `third_party/VENDORED.md` (documenting the four
  vendored packages, versions, sources, trim rationale for phonenumbers) —
  **NOT YET written**. **TODO.**

### Tests infrastructure (`tests/test_marketplace_manifest.py`)

- `test_vendor_contains_data_only_no_code` — unchanged (still valid,
  `bot_taxonomy.json` is data).
- New: `test_third_party_contains_only_declared_packages_no_compiled_
  binaries` — asserts zero `.so`/`.pyd`/`.dylib` under `third_party/` and
  that its top-level contents exactly match the declared set.
- New: `test_vendored_payload_stays_under_the_50mb_budget` — sums
  `vendor/` + `third_party/` and asserts under 50MB (actual total: ~24.4MB
  before the phonenumbers trim discussed above got it down further; well
  inside budget either way).
- `test_scripts_import_no_third_party_packages` — allowlist extended with
  `bs4`, `soupsieve`, `typing_extensions`, `phonenumbers` (vendored,
  allowed) plus the new shared module names (`judgement_merge`,
  `html_extract`, `phone_numbers`).
- New: `test_html_extract_and_phone_numbers_put_third_party_on_sys_path_
  before_importing_vendored_packages` — guards against silently falling
  back to an ambient pip install of bs4/phonenumbers if one happens to
  exist wherever this runs; asserts the `sys.path.insert(..., "third_party")`
  line appears before the `import bs4` / `import phonenumbers` line in each
  consuming module's source.

### New shared modules

- **`shared/html_extract.py`** — vendored-bs4 wrapper, stdlib `html.parser`
  backend only. Two functions, both additive (never replace an existing,
  separately-tested extractor):
  - `extract_labeled_pairs(html) -> list[str]`: DOM-walks `<tr>` for
    `<th>`+`<td>` siblings and `<dl>` for `<dt>`+`<dd>` pairs, returns
    synthetic `"label: value"` lines. Fixes the real, confirmed CQ-07/CQ-08
    gap — `extract_visible_text()` puts table/dl cells on separate lines by
    design, so the same-line `Label: value` regex those checks use can never
    see real tabular markup.
  - `extract_main_content_text(html) -> str | None`: finds the first
    `<main>` or `<article>`, strips nested `<nav>`/`<header>`/`<footer>`/
    `<aside>`, returns the remaining text — or `None` if neither tag exists
    (caller must fall back to existing behavior, never treat `None` as an
    error).
- **`shared/phone_numbers.py`** — vendored-phonenumbers wrapper.
  `find_phone_numbers(text, default_region=None) -> list[str]`, E.164
  formatted, dedup'd, first-seen order. **Not yet wired into any skill** —
  see TODO.
- **`shared/judgement_merge.py`** — the agent-judgement merge helper (item
  1.2 from the scoring). `merge_judgements(report, judgements) -> dict`
  validates every agent-authored judgement against the `Finding` schema
  (`finding_contract.Finding`) before merging into `report["findings"]` and
  removing `agent_judgement_required`; raises `JudgementMergeError` naming
  every offending judgement and field if any fail validation, rather than
  partially applying or crashing on a JSON syntax error. Also has a CLI
  (`--report`, `--judgements`, `--out`). **Not yet referenced from any
  skill's SKILL.md procedure** — see TODO (the skills' hand-editing
  instructions still describe the old raw-JSON-editing workflow; they should
  be updated to point at this helper, though it works standalone as an
  optional tool regardless).

### `shared/page_fetch.py` — robots.txt gate + retry (items 1.1 and 1.4)

- `robots_allows_fetch(url) -> bool`: per-origin (scheme+netloc, not just
  hostname — a robots.txt is origin-scoped) robots.txt check using stdlib
  `urllib.robotparser`, cached per-origin for the process lifetime
  (`_robots_cache`, cleared by `clear_cache()` alongside `_page_cache`).
  Unreachable robots.txt defaults to allow (RFC 9309 convention), matching
  the exact convention `entity-audit`'s pre-existing `robots_allows_offsite_
  fetch` already established for off-site fetches — this closes the real
  gap that convention never covered: the *primary* site's own fetches
  through `fetch_text`/`fetch_page_html`/`fetch_page` were never gated at
  all before this. `_raw_get()` is a private, unretried, un-gated GET used
  only to fetch robots.txt itself (avoiding self-recursion).
- `_urlopen_with_retry()`: fixed 3-attempt, fixed 1-second-delay retry (no
  jitter, no third-party `tenacity`) for a transient failure only — a
  timeout, a connection-level `URLError`, or HTTP 5xx. A 4xx or other
  permanent failure raises on the first attempt, unretried.
- Wired into all three fetch functions (`fetch_text`, `fetch_page_html`,
  `fetch_page`) — each gets the robots check as an early return (matching
  the existing `is_public_host` early-return shape) and the retry wrapper in
  place of the bare `urllib.request.urlopen` call.
- **`tests/test_page_fetch.py` updated to match** — every test that hits a
  `_LocalServer` now also patches (or, for the two new `RobotsGateTests`
  cases, genuinely exercises) `robots_allows_fetch`; the cache-hit
  call-counting test was rewritten to assert "no *new* calls on the second
  fetch" rather than "exactly one call total" (the robots.txt lookup is a
  legitimate first call now). New test classes: `RobotsGateTests` (4 tests:
  unreachable-defaults-to-allow, a real disallow blocks the fetch, an
  allowed path still fetches, the decision is cached per origin) and
  `RetryTests` (2 tests: a transient 503 retried into a success, a
  permanent 404 not retried). **Ran in isolation and passed (22/22)** before
  the session's later instruction to stop running tests mid-implementation
  — not re-run since; needs inclusion in the final full-suite pass.

### `skills/content-quality-audit/scripts/check_content_quality.py`

- **CQ-05 (relative-date proximity bounding, item 2.3) — done.** Added
  `_DATE_PROXIMITY_CHARS = 30` and `_span_gap()`. `find_relative_date_
  anchors` now only suppresses when an absolute-date match's span is within
  30 characters of the relative-time phrase's span, not "anywhere in the
  sentence." Verified by hand (not yet by running the suite) that the
  existing passing test (`test_a_bare_year_counts_as_an_absolute_anchor`,
  gap ≈17 chars) still suppresses correctly, and added two new tests in
  `tests/test_content_quality.py`: a same-sentence-but-far-apart date now
  correctly fires (gap ≈89 chars), and a genuinely close date still
  suppresses (gap ≈5 chars).
- **CQ-11 (syllable counter, item 2.4) — done.** `_count_syllables`
  rewritten: strips a trailing `-ed` unless the stem ends in `t`/`d` (where
  it's a real syllable — "wanted", "needed"), and a trailing `-es` unless
  the stem ends in a sibilant or soft g/c (`s`/`x`/`z`/`ch`/`sh`/`g`/`c` —
  "boxes", "watches", "changes", "places" all keep it). `-ly` was evaluated
  and deliberately left alone — the existing vowel-group regex already
  counts trailing "y" correctly in the common case, so no evidence-free
  change was made there. Hand-verified against 24/25 known words (the one
  miss, "terminology" undercounting by one syllable, is the vowel-adjacency
  "hiatus" limitation inherent to any vowel-group heuristic — genuinely out
  of scope for a suffix-stripping fix, not a regression). Seven new unit
  tests added (`SyllableCounterTests`) — not yet run as part of the suite.
- **CQ-07/CQ-08 (bs4 labeled-pair extraction, item 2.1) — done.** New
  `_text_with_labeled_pairs(text, html)` appends `extract_labeled_pairs`'s
  synthetic lines to the text handed to `find_scope_ambiguous_numbers` and
  `find_computed_stat_mismatches` **only** — every other check still sees
  unmodified `text`, so nothing that depends on `extract_visible_text`'s
  exact tested behavior is touched. `audit_text` now builds `labeled_text`
  once and passes it to just those two functions. **No new tests added yet
  for this wiring specifically** — see TODO (the `html_extract.py` module
  itself has no direct unit tests yet either).
- **CQ-01 (bs4 main-content candidate, item 2.2, narrowed per the user's
  final decision — trafilatura dropped, bs4-on-stdlib only) — done.**
  `find_answer_extractability_signal` gained an optional `main_content_text`
  parameter; when given (non-empty), it's windowed instead of `text` for the
  150-word opening block, and the output dict gained an
  `opening_block_source` field (`"main_content"` or `"document_start"`) so
  the agent-judgement rubric can see which source was used. Falls back to
  `text` (old behavior, byte-for-byte) when no `<main>`/`<article>` tag
  exists on the page. `build_agent_judgement_requests` gained an `html`
  parameter, computes `extract_main_content_text(html)` once, and threads it
  through. `audit_text` now passes `html` into `build_agent_judgement_
  requests`. Docstring updated to explain why this is a different technique
  from the H1-anchoring that was tried and reverted (structural tag-based
  stripping, not text-offset anchoring) so it doesn't reproduce that
  documented failure. **No new tests added yet** — see TODO.

## Cycle 24 TODO list — status: all items complete

All ten items below (numbered per the earlier version of this doc) are now
implemented, tested, and validated by one full suite run
(`python3 -m unittest discover -s tests`, 1228 tests, all passing). What
follows is what each turned into, including one real design fork discovered
mid-implementation (item 3) that changed the plan.

1. **`vendor/VENDORED.md`** — done. `bot_taxonomy.json` entry added: source
   URL, snapshot date 2026-09-07, MIT license, SHA-256, consumed-by, the
   overrides-preserve-the-original-15 note, and the classification/known-
   upstream-duplicate note (see item 3 below).
2. **`third_party/VENDORED.md`** — done. Written from scratch: bs4 4.15.0 /
   soupsieve 2.9.2 / typing_extensions 4.16.0 / phonenumbers 9.0.38, each
   with source, license, why it's here, and phonenumbers' trim rationale.
3. **Wired `vendor/bot_taxonomy.json` into `check_perimeter.py`** —
   `_baseline_bot_taxonomy()` now loads the snapshot, degrading to `None`
   (falling back to `BOT_TIERS`) on a missing/unparseable file, exactly the
   `shared/public_suffix.py` pattern. `resolve_bot_tiers()` widens `BOT_TIERS`
   with it, case-insensitively deduplicated across all tiers.

   **Real design fork found while wiring, not anticipated when this item was
   scored:** the pre-existing seam already called `resolve_bot_tiers()` from
   inside `evaluate_robots` (PER-01/PER-02) and `_c1_sitemap_url_ai_
   disallowed` (C1). Populating the accelerator therefore widened PER-02's
   "blocks every AI agent" threshold from the 15 curated bots to all 175
   vendored ones — meaning a robots.txt that blocks the ~15 famous bots
   (GPTBot, ClaudeBot, PerplexityBot, ...), the realistic real-world "block
   all AI" pattern, would stop tripping the critical PER-02 finding at all,
   only the quieter per-tier PER-01 findings. **Put to the user explicitly;
   decision: PER-01/PER-02/C1's threshold stays on the 15 curated `BOT_TIERS`
   bots** (`evaluate_robots`, `_is_blanket_blocked`, `_c1_sitemap_url_ai_
   disallowed` all now read `BOT_TIERS` directly, not `resolve_bot_tiers()`).
   `resolve_bot_tiers()` remains implemented, tested, and correct, just not
   called by any of the three threshold checks — available for a future
   capability that wants the wider list for something other than that
   threshold.

   Also found and fixed during wiring, a real upstream data bug rather than
   a design question: the raw snapshot lists the same crawler under two
   tiers with different casing (`meta-externalagent` in `training`,
   `Meta-ExternalAgent` in `on_demand`) — the same robots.txt product token
   under RFC 9309's case-insensitive matching. `resolve_bot_tiers()` now
   deduplicates case-insensitively across all tiers (first tier to claim a
   name wins; builtin `BOT_TIERS` entries always claim first), with a
   regression test (`test_resolve_bot_tiers_never_puts_the_same_bot_in_two_
   tiers`).
4. **Wired `shared/phone_numbers.find_phone_numbers` into REN-10** —
   replaced `_PHONE_PATTERN` entirely (phonenumbers subsumes NANP
   detection). Used `default_region="US"` rather than the originally-
   floated conservative `None`: the detector it replaced was itself
   NANP-only (bare 3-3-4, no `+` required), so `None` would have silently
   dropped detection of every already-shipped bare-NANP-format phone number
   with no country code — a real regression, not a fixture nit. `"US"`
   preserves that exact behavior while adding new coverage for any
   `+`-prefixed international number regardless of default region. Existing
   fixture tests updated from an invalid-exchange "555-123-4567" (which the
   real validator correctly rejects, unlike the old permissive regex) to the
   NANP-reserved-for-fiction "202-555-0173", plus new international-number
   test cases proving the actual capability gain.
5. **BLOCK_TAGS/VOID_TAGS/SKIP_TAGS dedup — done, option (a) as planned.**
   Added `VISIBLE_TEXT_SKIP_TAGS`/`VISIBLE_TEXT_BLOCK_TAGS` to
   `shared/text_spans.py` and imported them (aliased to each file's existing
   local name, zero algorithm/control-flow change) in all six skills.
   `content-quality-audit`'s own wider `BLOCK_TAGS` (adds `dt`/`dd`/
   `figcaption`) stayed local — a genuine, deliberate difference, not
   accidental drift.
6. **Stopword-list dedup — done.** `KEYWORD_FOLDING_STOPWORDS` (the 15-word
   set) added to `shared/text_spans.py`, imported by `entity-audit` and
   `content-quality-audit`. `retrieval-readiness-audit`'s separately-tuned
   37-word set stayed local, as planned.
7. **`_MONTHS` dedup — done.** `shared/text_spans.py` now exposes an ordered
   `MONTH_NAMES` tuple (`_MONTHS` becomes `frozenset(MONTH_NAMES)`, same
   membership-test behavior); `retrieval-readiness-audit`'s `_RET09_MONTHS`
   is now `"|".join(MONTH_NAMES)` instead of its own literal.
8. **SKILL.md procedures updated** — all five agent-judged skills
   (retrieval-readiness, content-quality, entity, engagement, citability)
   now mention `shared/judgement_merge.py` as an optional mechanical
   alternative to hand-editing at the exact step that resolves
   `agent_judgement_required`.
9. **Unit tests — done.** `tests/test_html_extract.py` (19 tests),
   `tests/test_phone_numbers.py` (8 tests), `tests/test_judgement_merge.py`
   (11 tests), plus CQ-07/CQ-08 wiring tests (`LabeledPairsWiringTests`,
   proving a table-shaped fixture now fires a CQ-07 finding line-separated
   text alone cannot) and CQ-01 wiring tests (`MainContentTextWiringTests`,
   proving nav text ahead of `<main>` no longer poisons `opening_block`) in
   `tests/test_content_quality.py`.
10. **Final validation pass — done.** `python3 -m unittest discover -s
    tests`: 1228 tests, all passing, run once after every item above was
    complete (plus a couple of earlier full runs while resolving item 3's
    design fork, to confirm each fix). `git status`/`git diff` reviewed —
    only the files this cycle touched, no stray `__pycache__` staged
    (already covered by the top-level `.gitignore`).

## Items scored but explicitly NOT part of this implementation pass

For completeness/traceability — these were scored in the session's plan file
and are **not** being built this cycle, so a future session doesn't
re-propose them without first reading why:

- Async I/O (httpx/aiohttp) — stdlib `ThreadPoolExecutor` would clear the
  (now-relaxed) dependency bar, but overlaps with the already-shipped INF-10
  budget governor and still owes a determinism/output-ordering answer.
  Deferred, not rejected outright, but not this cycle.
- Persistent disk cache (hishel) — conflicts with the project's own,
  already-decided "no caching layer" determinism policy
  (`01-project-plan.md:44-45`). Rejected.
- `dateparser`, `textblob` — dropped this cycle specifically because of the
  transitive compiled-`regex`-wheel portability risk discovered during
  verification (see above), not because they were re-scored as low-value.
  If pure-Python versions or vendored source builds of `regex` ever become
  available, this is worth revisiting.
- `nltk`, `spaCy` (even rule-based `Matcher`) — `nltk`'s `punkt` tokenizer
  sits in a genuine gray zone against "no pre-trained model weights";
  `spaCy` core ships compiled Cython extensions the user's final decision
  (bs4-stdlib-only, no compiled binaries as the operative rule) rules out
  even without a statistical pipeline. Rejected.
- `proselint`, `extruct`/`rdflib` — no demonstrated defect in what's
  already shipped to justify either. Rejected.
- `tldextract` — already shipped, better-tailored, under a different name:
  `shared/public_suffix.py`. Rejected as redundant.
- Dynamic page-purpose URL detection (replacing `_FORCE_INCLUDE_PATHS`) —
  architecture-pattern conflict: this is a judgment problem (page purpose
  across languages/customs) that belongs routed through the existing
  agent-judged pattern (à la ENT-05/06's agent-supplied off-site
  candidates), not solved with more deterministic script heuristics. Needs
  its own short design pass before it's implementable at all — not started.

## Verification plan — completed

1. `python3 -m unittest discover -s tests`: 1228 tests, all passing.
2. `tests/test_marketplace_manifest.py`'s vendoring safety tests pass
   (`third_party` package allowlist, the 50MB budget — actual total well
   under it — and the sys.path-before-import ordering check).
3. `vendor/bot_taxonomy.json`'s tier assignments for the original 15
   hand-curated bots are asserted directly by
   `test_resolve_bot_tiers_preserves_original_15_curated_assignments`, and
   the cross-tier-duplicate fix by
   `test_resolve_bot_tiers_never_puts_the_same_bot_in_two_tiers`.
4. `git status`/`git diff` reviewed — only the files this cycle touched, no
   stray `__pycache__` staged. Committed as one commit.
