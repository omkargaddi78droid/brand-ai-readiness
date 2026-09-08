# Cycle 24 Candidate Scoring: External Suggestions vs. Real Code

## Context

An external review proposed 20 code-level improvements across:

1. Architecture/orchestration
2. Content-quality patterns and heuristics
3. Replacing hardcoded data with third-party libraries

Each suggestion was verified against the repository and scored using the same criteria as the Cycle-22 candidates. Nothing in this document is implemented; this is the decision record.

Ground truth was checked directly in the fetch/orchestration layer, `check_content_quality.py`, and the hardcoded-data areas.

### Project constraints

* No pre-trained model weights.
* No external service required at runtime. Public-site GET requests are allowed where explicitly permitted.
* No headless browser.
* Deterministic results.
* Portable/self-contained package.

Originally, the project also followed a strict zero-third-party-dependency and no-compiled-binary policy. This was later relaxed: vendored packages are allowed if the combined vendor footprint remains under 50 MB, no runtime external service is required, and no model weights are included. Compiled extensions are also allowed under the same vendor/size rule.

---

# 1. Architecture & Orchestration

## 1.1 Enforce `robots.txt`

**Finding:** The primary fetch layer does not currently check `robots.txt`, although several skills already apply a robots gate to off-site requests.

The orchestrator intentionally continues downstream skills after a site-wide block is detected, so that behavior should remain unchanged.

**Decision: Shipped-worthy.**

Use stdlib `urllib.robotparser` in `shared/page_fetch.py`, cache the decision per audit run, and treat a disallowed path as unavailable rather than aborting the skill. Do not add `protego`; the existing stdlib implementation is already proven in the repository.

## 1.2 Agent-judgement merge helper

**Finding:** Agent-generated findings are currently merged into JSON through manual editing.

**Decision: Shipped-worthy.**

Add a small stdlib-only helper/CLI that:

* accepts structured judgment objects,
* validates them against the finding schema,
* inserts valid findings,
* removes the corresponding stub key,
* preserves valid JSON.

This removes a mechanical source of LLM editing errors without changing the agent's actual judgment role.

## 1.3 Async I/O

The current fetcher is synchronous `urllib`. `httpx`/`aiohttp` would introduce unnecessary dependencies, while `ThreadPoolExecutor` could provide concurrency without them.

However, INF-10 already mitigates the main problem by handling budget exhaustion gracefully. Concurrent fetching would also require explicit output ordering to preserve determinism.

**Decision: Rejected/deferred for this cycle.**

Revisit only if INF-10 proves insufficient.

## 1.4 Retry/backoff

No retry logic currently exists.

**Decision: Shipped-worthy.**

Implement a small fixed retry loop in `shared/page_fetch.py`:

* 2–3 attempts
* fixed delay
* no random jitter

This improves transient failure handling without adding a dependency.

## 1.5 Persistent disk cache

The current cache is intentionally process-local. The project explicitly decided against persistent caching because audits should fetch fresh content.

A disk cache could also serve stale content across separate audits.

**Decision: Rejected.**

This conflicts with an existing project design decision, independent of the dependency policy.

---

# 2. Pattern & Heuristic Refinements

## 2.1 CQ-07/CQ-08: `th/td` and `dt/dd` extraction

Current text extraction separates table/definition-list labels and values, preventing the existing `Label: value` checks from recognizing valid markup.

**Decision: Shipped-worthy.**

With third-party packages now permitted, use `beautifulsoup4` as the canonical HTML parser. This can provide structural pairing rather than adding more custom parsing logic. It also addresses the HTML-tag duplication discussed below.

## 2.2 CQ-01: Main-content boundary detection

The original review treated this as an oversight, but the repository shows that H1-based anchoring was already tried and reverted because of false positives. CQ-01 intentionally uses agent judgment for deciding whether the opening content is meaningful.

However, semantic HTML boundary extraction is different from H1 anchoring.

**Decision: Shipped-worthy, narrowed scope.**

Use `trafilatura`, or a `beautifulsoup4` pass that handles `<main>/<article>` and removes `<nav>/<header>/<footer>`, to improve the candidate `opening_block`. Continue sending that candidate to the existing agent-judgment step. Never let the library directly produce the finding.

## 2.3 CQ-05: Date suppression proximity

Current logic suppresses a relative-date finding whenever an absolute date appears anywhere in the same sentence.

**Decision: Shipped-worthy.**

Use character-distance between the absolute date and the relative-date/claim position. Add calibration fixtures covering both valid suppression and previously missed findings.

## 2.4 CQ-11: Syllable counter

The current vowel-group approach already handles trailing silent `e`, but not common `-ed`, `-es`, and `-ly` cases, which can inflate Flesch scores.

**Decision: Shipped-worthy.**

Strip common suffixes before vowel-group counting while preserving the existing silent-`e` behavior. Add tests.

## 2.5 HTML-tag duplication

Investigation found six separate `BLOCK_TAGS`/`VOID_TAGS`/`SKIP_TAGS` definitions across skills, despite `shared/text_spans.py` already providing a shared implementation.

**Decision: Shipped-worthy.**

Make the shared implementation canonical and migrate the skills to it. The new HTML parser work in §2.1 can provide the common implementation.

---

# 3. Hardcoded Data → Libraries

## 3.1 AI bot taxonomy

`BOT_TIERS` is currently a static list of 15 bots, although the code already contains a seam for a future baseline taxonomy.

A live API is prohibited because runtime external services are not allowed. A build-time vendored snapshot is acceptable.

**Decision: Shipped-worthy.**

Vendor a dated, licensed bot-taxonomy snapshot, expand coverage, and document the manual re-snapshot process using the existing PSL vendor pattern.

## 3.2 Weasel words / marketing fluff

**proselint:** Primarily replaces one curated rule set with another without a demonstrated current gap.

**Decision: Rejected.**

**textblob:** Its lexicon mode provides a potentially useful subjectivity/polarity signal without requiring a trained model.

**Decision: Deferred.**

Measure its footprint first and consider it as a separate capability rather than simply replacing `_FILLER_PHRASES`.

## 3.3 Public suffix list

`shared/public_suffix.py` already provides a vendored PSL implementation equivalent to the proposed `tldextract` functionality.

**Decision: Rejected — already implemented.**

Only the inaccurate “under 90 lines” module documentation needs correction.

## 3.4 English grammar

`spaCy` is now technically vendorable because compiled extensions are allowed, provided no pretrained model is included. However, there is no demonstrated current defect justifying the footprint.

`nltk` is riskier because resources such as `punkt` involve trained statistical data.

**Decision:**

* spaCy Matcher — **Deferred**
* nltk — **Rejected**

Also consolidate the three duplicated stopword lists into `shared/text_spans.py`.

## 3.5 Schema.org vocabularies

The existing `_ENTITY_VALUED_PROPERTIES` list is centralized, reused by multiple skills, and has no demonstrated coverage defect.

**Decision: Deferred.**

Do not introduce `extruct`/`rdflib` without evidence of a real gap.

## 3.6 HTML element specifications

Covered by §2.1 and §2.5.

**Decision: Shipped-worthy through the shared `beautifulsoup4` extraction layer.**

## 3.7 Phone numbers

The current regex is effectively NANP-focused and misses common international formats.

`phonenumbers` is pure Python and fits the revised dependency policy.

**Decision: Shipped-worthy.**

Vendor it and replace `_PHONE_PATTERN`.

## 3.8 Calendar/date parsing

Two separate month lists exist, and the current date detection is English-specific.

**Decision: Shipped-worthy, pending size check.**

Vendor `dateparser` if the combined footprint remains within the 50 MB limit. Otherwise, at minimum consolidate the existing month lists.

## 3.9 Process/page-purpose URLs

The current `_FORCE_INCLUDE_PATHS` contains five English paths. Expanding this into a larger multilingual heuristic would not solve the underlying semantic problem.

**Decision: Rejected as specified; redesign recommended.**

Use anchor text, link metadata, and Schema.org signals to surface candidate pages, then let the agent confirm or expand the force-include set.

---

# 4. Revised Dependency Policy

The dependency policy was relaxed during this review:

* Third-party packages may be vendored.
* Total vendor payload must remain under **50 MB**.
* No runtime external service/API dependency.
* No pretrained model weights.
* Compiled extensions are allowed.
* Determinism remains mandatory.

This changes several earlier decisions.

### Revised decisions

| Item                                     | Decision                           |
| ---------------------------------------- | ---------------------------------- |
| `protego` for robots.txt                 | Not needed; keep `robotparser`     |
| `httpx`/async I/O                        | Deferred                           |
| `beautifulsoup4`                         | **Shipped-worthy**                 |
| `trafilatura` / semantic HTML extraction | **Shipped-worthy, narrowed**       |
| Bot taxonomy snapshot                    | **Shipped-worthy**                 |
| proselint                                | Rejected                           |
| textblob                                 | Deferred                           |
| spaCy Matcher                            | Deferred                           |
| nltk                                     | Rejected                           |
| extruct/rdflib                           | Deferred                           |
| phonenumbers                             | **Shipped-worthy**                 |
| dateparser                               | **Shipped-worthy, size dependent** |
| page-purpose URLs                        | Unchanged; needs design            |

The key change is that `beautifulsoup4` can now become the shared HTML extraction layer instead of implementing separate parsing fixes in individual skills.

---

# 5. Overall Pattern

The 20 suggestions fall into a few recurring categories:

* **Dependency/policy issues:** Many proposals were initially blocked by the old zero-dependency policy.
* **Already implemented:** The PSL/tldextract proposal is already covered by `shared/public_suffix.py`.
* **Architecture conflicts:** CQ-01 and page-purpose detection involve semantic judgment and should remain agent-assisted rather than becoming increasingly complex deterministic heuristics.
* **Straightforward defects:** robots enforcement, retry, CQ-05, CQ-11, and the judgment merge helper can be implemented directly.
* **Real gaps requiring policy decisions:** phone-number and date parsing have genuine limitations that libraries address well.

---

# 6. Recommended Scope for Cycle 24

## Shipped-worthy — stdlib-only

1. **Primary-path `robots.txt` enforcement** — `urllib.robotparser`
2. **Agent-judgement merge helper/CLI**
3. **Fixed retry/backoff**
4. **CQ-05 proximity-bound date suppression + fixtures**
5. **CQ-11 syllable-counter improvements**
6. **Stopword-list consolidation**

## Shipped-worthy — vendored

7. **BeautifulSoup** as the canonical HTML extractor, replacing the six hand-rolled tag implementations and fixing `th/td` and `dt/dd` pairing.
8. **Trafilatura or equivalent semantic HTML extraction** for better CQ-01 candidates while retaining agent judgment.
9. **Vendored bot-taxonomy snapshot** with a documented update process.
10. **Phonenumbers** for international phone detection.
11. **Dateparser**, provided it fits the shared vendor budget.

## Deferred

* **textblob** — potentially useful marketing-tone signal; confirm size first.
* **spaCy Matcher** — technically compatible but currently lacks demonstrated need.
* **extruct/rdflib** — no demonstrated gap.
* **Agent-supplied page-purpose hints** — needs a small design pass.

## Rejected

* **httpx/aiohttp async I/O** — unnecessary given current budget handling and available stdlib concurrency.
* **hishel persistent cache** — conflicts with the deliberate no-persistent-cache design.
* **proselint** — insufficient demonstrated value.
* **tldextract** — already implemented through `shared/public_suffix.py`.
* **nltk** — `punkt` creates a pretrained/statistical-data concern.

### Before implementing vendored items

Measure the combined footprint of:

* BeautifulSoup
* Trafilatura/lxml, if used
* Bot taxonomy
* Phonenumbers
* Dateparser
* Existing PSL data

against the **50 MB total vendor limit**. If the limit is exceeded, drop `dateparser` first, then prefer BeautifulSoup's stdlib backend over lxml where practical.

**Implementation order:** start with the six stdlib items immediately, while measuring the vendor footprint for items 7–11 in parallel.

