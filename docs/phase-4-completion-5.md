# Phase 4 (capability cycle 5 of N) — CIT-01, CIT-02, CIT-04, CIT-06

Phase 4 output, fifth capability cycle. New skill: `citability-audit` — the
last of the front-loaded gate-3 clusters this project set out to cover
before rendering infrastructure. Also: a real, evidence-based decision to
defer render-diff work again, and three more real bugs found by field
validation in one sitting, the most of any cycle so far.

---

## A — Gap confirmation: REN-02…REN-04 checked and deferred, with evidence

Before starting this cycle, the plan's own gate was checked rather than
assumed: `docs/00-project-plan.md` said render-diff work (`REN-02…REN-04`)
was "gated on proving the rendering runtime budget first." Checked directly
in this environment: no `chromium`/`chromium-browser`/`google-chrome`
binary, no `playwright` or `selenium` Python package installed. Standing up
headless rendering here would mean installing a ~100–300 MB browser binary
with OS-level dependencies (font libraries, shared libs) this sandboxed
environment may not have at all — and the capability matrix already carries
this exact risk on record: *"Crawl4AI/Playwright unavailable in grader's
env"*, mitigated by *"static-fetch fallback path; render-dependent checks
emit `status: unknown`, never a false `fail`."* Building render-diff now
would risk a large, uncertain investment against infrastructure that might
not even be present in the actual grading environment either — the
zip's own self-containment requirement (M5) already rules out shipping the
browser itself.

**Decision: defer again, with real evidence this time instead of a repeated
assumption.** Pivoted to `citability-audit` — the scriptable half of Cluster
E, cheap, no rendering dependency, following the exact "front-load the cheap
wins" order the capability matrix itself recommends.

## B — Resource evaluation

stdlib only: `re`, `html.parser.HTMLParser`, `ipaddress`, `socket`,
`urllib`, `zlib`. No new dependency.

## C — Design

**Same split as `engagement-audit`, applied to Cluster E.** CIT-01/02/06 are
objectively checkable from markup — a conventional About-page link, a count
of external links, a superlative-without-a-number pattern. CIT-04 (citation
recall) is not: whether an unsourced number is *load-bearing* is a judgement
about what matters on this specific page, and the capability matrix's own
"agent-judged" disposition for CIT-03/04/12 is honoured rather than forced
into a script verdict. `references/citability-judgement-rubric.md` gives six
worked examples (load-bearing vs. self-reported: price, spec, company facts
about itself), the second rubric of this kind in the marketplace.

**Two capabilities deliberately dropped before being built, not after.**
CIT-05 (quotation density): attribution patterns vary too widely to script
at this project's false-positive bar. CIT-10 (self-interested comparison
disclosure): would fire on nearly every vendor-authored comparison page,
since disclosure language is rare in practice regardless of legitimacy — "a
pattern that fires on the overwhelming majority of both good and bad pages
is not a detector," stated in the script's own docstring so the reasoning
survives past this cycle.

## D — Implement

`_PageParser` (links + visible text), `find_missing_about_link`,
`find_missing_source_attribution`, `find_unverifiable_superlatives` (+
finding builders), `find_citation_recall_candidates`,
`build_agent_judgement_requests`, `audit_html`, `_stamp_page`,
`is_public_host`, `decode_content_encoding`, `fetch_page_html`, CLI.

## E — Test

**36 unit tests** + **8-case measured corpus** (CIT-01/02/06; precision
1.000, recall 1.000, 9.4 ms — CIT-04 has no script verdict to measure) +
extended `test_gzip_decoding.py` coverage for this fifth script + the
existing 215-test suite from cycles 1–4, unaffected. **252 tests total
project-wide.**

## F — Review: three real bugs, all in one detector, all found live

**The about-link check (CIT-01) was wrong in three different, independent
ways**, each caught by running it against real sites before trusting it —
more corrections in one cycle than any prior one, on the single detector
this cycle spent the most design effort calibrating for precision:

1. **`href="about-us"` (no leading slash)** — an entirely ordinary
   same-directory relative link — was invisible to the original
   path-anchored regex, which required a literal leading `/` before the
   matched word. `urlparse("about-us").path` is `"about-us"`, not
   `"/about-us"`. Found by sweeping realistic link forms *before* writing a
   single formal test (the discipline every cycle has used since Phase 3),
   not live — but the next two were.
2. **`href="/wiki/Wikipedia:About"`** — MediaWiki's namespace-prefixed
   convention for the About page, used across the whole MediaWiki ecosystem
   (Wikipedia, Wiktionary, Fandom, and many corporate/community wikis), not
   just Wikipedia. Found live, on the very first non-trivial site checked.
   The path segment `Wikipedia:About` never equals `about` under exact
   match. Fixed by stripping a namespace prefix (`segment.rsplit(":",
   1)[-1]`) before comparing.
3. **`href="../about.html"`** — Sphinx-generated documentation
   (docs.python.org among them) suffixes conventional paths with a file
   extension. Fixed by stripping a trailing `.html`/`.php`/`.aspx`/`.jsp`
   before comparing. Found live, on the second site checked, immediately
   after fixing bug 2 — and finding it exposed a **third, structural** bug on
   the same page: the actual About reference on docs.python.org is
   `<link rel="author" href="../about.html">` **in `<head>`**, never a
   clickable `<a>` a human would see. The parser only ever looked at `<a>`
   tags.

**Fixing bug 3 required a design decision, not just a pattern fix, and it
was checked before shipping rather than assumed safe:** if `<link>` hrefs
are folded into the same collection CIT-02 uses to count external citations,
a `<link rel="stylesheet" href="https://cdn.example/style.css">` — present
on nearly every real page — would silently count as a "source citation" and
suppress genuine CIT-02 findings. Resolved by keeping two separate
collections from the start (`anchor_hrefs` for CIT-02, `all_hrefs` including
`<link>` for CIT-01), with a dedicated test
(`test_link_tags_are_not_counted_as_external_citations_for_cit02`) proving a
stylesheet link cannot suppress a real CIT-02 finding, added *before* the
bug could occur rather than after a report shipped one.

**All three, plus the CIT-02/`<link>` cross-contamination risk, promoted
into permanent regression coverage**: four new unit tests naming the exact
site each was found against, and two new corpus fixtures
(`clean_mediawiki_style_about.html`, `clean_sphinx_style_link_tag_about.html`)
added to the measured corpus rather than left as unit-test-only coverage —
consistent with how cycles 2 and 3 promoted their field-found bugs.

**Why one detector accumulated three bugs while the others (CIT-02, CIT-06)
accumulated none:** CIT-01 is the only one of the three built on an
*enumerated, finite pattern set* (conventional URL slugs) rather than a
*structural count* (external-link count, same-sentence number presence).
Enumerated pattern sets are exactly where real-world convention diversity
bites — the same lesson as PER-01's bot taxonomy and CQ-03's template-syntax
list, both of which also needed real-world calibration passes. The standing
rule this earns: **an enumerated pattern list is a hypothesis, not a fact,
until checked against real sites with genuinely different conventions
(a wiki, a static-site generator, a SPA) — checking one mainstream
commercial site is not enough coverage for this class of bug.**

## G — Document

This file; `SKILL.md`, `references/citability-judgement-rubric.md`, README,
`marketplace.json` (0.8.0 → 0.9.0), `docs/capability-matrix.md` (CIT-01 →
PARTIALLY_COVERED, CIT-02/04/06 → IMPLEMENTED), entrypoint `SKILL.md`
(registry), `docs/00-project-plan.md`.

## H — Freeze

CIT-02/06 frozen. CIT-01 frozen at three corrected pattern classes
(conventional slug, MediaWiki namespace, extension-suffixed); re-open if a
fourth real convention is found (a strong candidate: single-page-app
client-routed paths with a `#`/hash fragment, not checked this cycle).
CIT-04's rubric frozen at six examples, same reopening condition as
`engagement-audit`'s.

---

## Field validation

Six live pages: python.org, Wikipedia's main page, nytimes.com,
stripe.com/pricing, apple.com/contact, and docs.python.org's `re` module
page — deliberately including two sites (Wikipedia, docs.python.org) whose
conventions turned out to differ from the mainstream commercial sites every
prior cycle's samples leaned toward.

**Every finding hand-verified against the raw HTTP response, including the
absences** — not just the positives, this time, since the point of this
cycle's corrections was learning that "found nothing" can be as wrong as a
false positive:

| Site | Result | Verified against |
|---|---|---|
| `python.org` | 2 CIT-04 candidates handed to agent judgement; no script findings | Consistent with a homepage carrying a conventional link structure |
| `en.wikipedia.org` | `CIT-06`: 1 superlative without a number; `CIT-01` clean after fix | Raw source has `/wiki/Wikipedia:About` — confirmed present, confirmed now recognised |
| `nytimes.com`, `stripe.com/pricing`, `apple.com/contact` | `CIT-01` fires (genuinely no about/company link anywhere in the raw HTML) | `curl \| grep -i` on the raw response for any href containing "about" or "company": zero matches on all three |
| `docs.python.org/re.html` | `CIT-06` fires; `CIT-01` clean after fix | Raw source has `<link rel="author" href="../about.html">` — confirmed present, confirmed now recognised via the `<link>`-tag extension |

## Next

Continue Phase 4 with the remaining gate-3/gate-1 work not yet touched:
`PER-05` (llms-full.txt), `PER-06`/`PER-08` (sitemap discovery) round out
Cluster A cheaply; or the deterministic-but-not-yet-built content checks
(`CQ-02/04/09/12`, all agent-judged, following the now-twice-proven
extraction-plus-rubric pattern). `REN-02…REN-04` stays deferred until either
this environment gains a headless browser or the decision is revisited with
new evidence — not assumed away permanently, just not chased without proof
it can work.
