# Phase 4 (capability cycle 4 of N) — EN-01, EN-03, EN-06, EN-09

Phase 4 output, fourth capability cycle. New skill: `engagement-audit` — the
first engagement-cluster skill, and the first agent-judged capabilities
actually built (not just planned) in this marketplace. Also: one
cross-cutting bug found and fixed across every page-fetching skill in the
project, including a retroactive correction to cycle 3's field-validation
record.

---

## A — Gap confirmation

Not baseline-covered: baseline-capabilities.md's own coverage summary marks
Cluster G (engagement) at "0.5 of 11" — popup/CTA-overload signals only, as
score contributions with no usable evidence string. `BUILD_REQUIRED`,
resolved by building. This is also the first cycle to touch the engagement
half of the rubric at all — three prior cycles were entirely discoverability.

## B — Resource evaluation

stdlib only: `hashlib`, `re`, `html.parser.HTMLParser`, `ipaddress`,
`socket`, `urllib`, `zlib` (added this cycle, see §F). No new dependency.

## C — Design

**The capability matrix itself said EN-01 is a judgement call** ("FP risk:
medium — EN-01/EN-11 are judgement calls"), and EN-03's own stated test
criterion ("3 steps vs 8 steps") needs multi-page navigation a single-page
script cannot observe. Rather than force a script verdict on either — which
would be asserting a judgement the evidence does not support, the exact
failure mode this project's severity-calibration discipline exists to
prevent — this cycle splits the four capabilities by who decides:

- **EN-06, EN-09: the script decides.** Both are objectively present-or-
  absent given the markup: an overlay with wall language and no dismiss
  option, or a form field with no accessible name. Same evidence-quality bar
  as every prior detector in this marketplace.
- **EN-01, EN-03: the agent decides.** The script extracts structural
  signals only (`extract_orientation_signals`,
  `extract_conversion_path_signals`) into an `agent_judgement_required`
  array and emits no verdict. `references/engagement-judgement-rubric.md`
  gives the calibration — six worked examples across the two capabilities,
  each stating not just the verdict but *why*, so the judgement is
  repeatable rather than arbitrary. This is the pattern
  `skill-engineering-principles.md` §3 and §1c described from the start
  ("the host agent is the LLM") but that no prior cycle had actually built.

**A composition gap, caught before it shipped, not after.** An unresolved
`agent_judgement_required` array reaching `compose_report.py` would have been
silently ignored — the composer only ever read `findings` and
`unknown_checks`, so a forgotten resolution step would make two whole
capabilities vanish from the report with no trace. Fixed in
`compose_report.py` itself: any unresolved entry becomes one `unknown_checks`
entry per capability, `"reduced coverage is reported, never hidden"` applied
to a judgement nobody rendered, exactly as it already applied to a skill that
failed to run.

**First use of `category: "engagement"`.** Every prior finding in this
marketplace has been `"discoverability"`. Engagement findings carry
`gate: null` — they are not part of the perimeter → render → retrieval gate
chain and are never suppressed by an upstream discoverability failure, by
design: a site can be unreachable and still have engagement problems, and a
perfectly reachable site can still lose its visitors.

## D — Implement

`_PageParser` (forms/labels, H1, CTA text, visible text — one pass),
`find_unlabelled_fields`, `find_interstitial_walls` (+ finding builder),
`extract_orientation_signals`, `extract_conversion_path_signals`,
`build_agent_judgement_requests`, `audit_html`, `_stamp_page`,
`is_public_host`, `fetch_page_html`, CLI — plus, cross-cutting, `zlib`-based
Content-Encoding handling added to all four page-fetching skills (§F).

## E — Test

**28 unit tests** for engagement-audit + **10 new gzip-regression tests**
(`test_gzip_decoding.py`, covering all four affected scripts against a real
local HTTP server, not a mock) + **6-case measured corpus** for EN-06/EN-09
(precision 1.000, recall 1.000, 5.8 ms; EN-01/EN-03 have no script verdict to
measure, calibration lives in the rubric's worked examples instead) + the
existing 176-test suite from cycles 1–3, unaffected except where the gzip fix
touched shared fetch code. **215 tests total project-wide.**

Caught before any of this shipped, by sweeping fixtures against the code
before writing formal tests (same discipline as every prior cycle):

- `<label for="pw">` appearing *after* its `<input>` (legal, common — a
  checkbox-then-label or floating-label pattern) was not recognised as
  labeling the field, because the labeled-or-not decision was made at
  input-open time using an as-yet-incomplete set of seen labels. Fixed by
  deferring the `for`-based check to `finalize()`, after the whole document
  (and therefore every label) has been seen.
- A finding id built from Python's built-in `hash()` on the matched text —
  caught **before** it was ever run twice, by recognising that `hash()` on a
  string is randomised per process (`PYTHONHASHSEED`) and would silently
  break "same site audited twice → same report" across separate CLI
  invocations, the exact acceptance criterion this project tests for. Fixed
  with `hashlib.sha256` before the first test ran; verified with three
  separate `PYTHONHASHSEED` values producing identical output.

## F — Review: the cross-cutting bug

**Found live, on the very first URL of this cycle's field validation, more
consequential than any single bug in cycles 1–3 because it silently affected
every page-reading skill in the marketplace at once, not just one:**

`www.python.org`'s CDN (`varnish`/`nginx`) sends `Content-Encoding: gzip`
regardless of whether the client's `Accept-Encoding` header advertised
support for it. `urllib.request` — unlike the third-party `requests`
library — never auto-decompresses a response body. Every fetch function in
this marketplace (`perimeter-access-audit`'s `fetch_text` and
`probe_with_user_agent`; `content-quality-audit`'s, `entity-audit`'s and
`engagement-audit`'s `fetch_page_html`) read the raw bytes and decoded them
straight to UTF-8, so a gzip-compressed response became binary garbage in
`h1_text`, `first_150_words`, and every other extracted-text field — visible
immediately in this cycle's first `agent_judgement_required` payload.

**Impact assessment, not assumed:** checked every distinct URL used in field
validation across all four cycles (23 URLs) for `Content-Encoding`.
`python.org` was the *only* affected host. Two specific claims were
retroactively wrong:

1. **cycle 3 (`entity-audit`)**, `docs/phase-4-completion-3.md`: claimed
   "no structured data, no canonical" for `python.org`, "verified" by a
   `curl` command that was itself blind to the same gzip issue (`curl`
   without `--compressed` doesn't decompress either — the manual
   verification step gave false confidence, not real confidence). Corrected
   in place in that file, struck rather than silently edited away, with the
   real result: a genuine `WebSite` node missing `name`, genuinely no
   canonical.
2. **cycle 2 (`content-quality-audit`)**, `python.org/about/`: reported
   "(clean)". Re-checked after the fix — still genuinely clean; the garbage
   text happened not to trip any of the four detectors, and there was no
   real defect either. Correct by coincidence, not by the tool having worked
   correctly at the time. Noted here rather than left unstated.

**Fixed in all four scripts identically**: a `decode_content_encoding`
function (duplicated per script, the same independence tradeoff already
documented in `entity-audit`'s reference doc) reads `Content-Encoding`,
decompresses gzip/deflate via `zlib`, passes through `identity`/absent
unchanged, and **raises rather than guesses** on an unrecognised encoding
(e.g. `br` — no stdlib Brotli support) so an unhandled case fails loudly as
`unknown` instead of silently reintroducing the same bug for a different
codec. Bounded to 20 MB decompressed output as a decompression-bomb guard,
since these functions read from the audited site — a legitimate target the
operator chose, but not one to be trusted to be well-behaved.
`perimeter-access-audit`'s `probe_with_user_agent` (PER-03's edge-blocking
probe, which reads a deliberately truncated 4096-byte prefix for
classification) uses a lenient variant that falls back to the raw bytes on a
decompression failure, since a truncated gzip stream can legitimately fail
to decompress even when the response itself was fine — the existing
`"ambiguous"` classification path already covers text that doesn't look like
anything recognisable, so this degrades safely rather than needing to be
strict.

**Regression coverage**: `test_gzip_decoding.py`, new. Pure round-trip tests
(gzip, deflate, identity, unsupported-encoding-raises, gzip-bomb-rejected)
against all four modules' copies of the function, plus four end-to-end tests
against a real local HTTP server serving genuinely gzip-compressed content —
not a mock — so a regression in the actual fetch wiring, not just the
decoder it calls, would fail these tests. The SSRF guard on
`content_quality`/`entity_audit`/`engagement_audit`'s fetch functions
correctly refuses the local server's loopback address; those three tests
patch `is_public_host` for the duration of the decompression check only,
since that guard is orthogonal to this bug and is already covered by each
module's own dedicated SSRF tests.

**Why this is a bigger deal than "one more field-found bug":** three
consecutive cycles have now each found a real bug this way (PER-03's tuple
shape, cycle 2's substring matches, entity-audit's self-closing tags, and now
this one) — but this is the first that was silently present across *every
skill that fetches a page*, the first that also fooled the manual
verification step meant to catch tool errors, and the first to require a
correction to an already-written project document rather than just a code
fix. The standing rule this earns, alongside the ones from cycles 1–3: **a
manual `curl` check is not independent verification of a fetch bug if it
uses the same defaults the tool does** — verifying `urllib`-fetched content
with plain `curl` (no `--compressed`) checks nothing about decompression.

## G — Document

This file; `SKILL.md`, `references/engagement-judgement-rubric.md`, README,
`marketplace.json` (0.7.0 → 0.8.0), `docs/capability-matrix.md` (EN-01 →
IMPLEMENTED, EN-03 → PARTIALLY_COVERED, EN-06 → IMPLEMENTED, EN-09 →
PARTIALLY_COVERED), entrypoint `SKILL.md` (registry, including the
`agent_judgement_required` resolution step), `docs/00-project-plan.md`, and
the correction to `docs/phase-4-completion-3.md` described in §F.

## H — Freeze

EN-06/EN-09 frozen at this design. EN-01/EN-03's rubric is frozen at six
calibration examples; re-open if a real judgement call in practice doesn't
fit any of them well — add the new case to the rubric rather than letting
the agent freelance a seventh interpretation. The gzip fix is frozen as a
per-script duplication; if a fifth page-fetching skill is added, copy the
same `decode_content_encoding` function rather than inventing a variant.

---

## Field validation

Five live pages, read-only, single GET each: python.org, Wikipedia's main
page, nytimes.com, stripe.com, and apple.com/contact — chosen to include the
one host already known to trigger the gzip bug, so the fix was proven against
the exact failure case, not just a synthetic one.

**Result: the gzip bug (§F), found and fixed; one genuine, hand-verified
true positive after the fix; zero further false positives:**

| Site | Result | Verified against |
|---|---|---|
| `python.org` | Corrupted binary text in `agent_judgement_required` before the fix; sane `h1_text` ("Intuitive Interpretation") after | Raw response confirmed `Content-Encoding: gzip`; decompressed manually and compared |
| `en.wikipedia.org` | `EN-09`: 1 of 8 fields unlabelled ("1 search") | Raw source has **two** search `<input>` elements — one with `aria-label="Search Wikipedia"`, one with only a `placeholder`. The tool correctly found the second and correctly did not flag the first |
| `nytimes.com`, `stripe.com`, `apple.com/contact` | No script findings | Consistent with each having accessible-enough forms and no bare wall overlay in the fetched markup |

The Wikipedia result is the clearest true positive this project has found
for a "unlabelled field" class of check: two visually similar search boxes,
one correct, one not, on one of the most-engineered pages on the public web —
exactly the kind of inconsistency a manual audit is likely to miss and a
mechanical one catches by construction.

## Next

Continue Phase 4 with the remaining front-loaded work: `REN-02…REN-04`
(render-diff mechanics — pre/post-render DOM comparison), gated on first
proving the runtime budget can absorb headless rendering, per the capability
matrix's own risk note. Alternatively, continue rounding out gate 3
(`CIT-*`, remaining `CQ-*`) if rendering infrastructure is deferred again.
Either way: every future cycle now includes `test_gzip_decoding.py`-style
end-to-end fetch verification against a real server as a template, not just
pure-function fixture pairs.
