**Status: both bugs below are FIXED (2026-09-11).** See "Fixes applied" at the
end of this file for what changed, why, and how each fix was verified (unit
tests + a fresh live run against tryhackme.com).

# Bugs found — live-site test run against tryhackme.com (2026-09-11)

Full orchestrator run executed against `https://tryhackme.com` (perimeter gate,
27-page sample, all six per-page/site skills, composed report written to
`results/result_tryhackme.com.json`). Findings were spot-checked against the
live site with `curl`/direct HTTP requests. Two issues found; one is a
confirmed false positive, the other is a detection gap. No crashes, no
schema/composer errors — `compose_report.py` ran clean over 19 input files
(149 unresolved `agent_judgement_required` entries were left un-resolved for
this test run and correctly surfaced as `unknown_checks` rather than being
silently dropped or crashing the composer).

## Bug 1 — REN-10 false positive: config ID misdetected as a phone number

**Where:** `shared/phone_numbers.py:find_phone_numbers`, used by
`skills/static-extraction-audit/scripts/check_static_extraction.py`'s REN-10
(`find_nap_script_only_phone`).

**What happened:** REN-10 fired on both
`https://help.tryhackme.com/en/articles/7262866-cancelling-your-subscription`
and `https://help.tryhackme.com/en/collections/3665117-billing-and-subscription`,
claiming a phone number is present in an inline `<script>` block but not in
visible text. The actual matched text is `"helpCenterId":3107781` — a plain
numeric config ID in a JSON blob embedded in the page (Intercom/Help Scout
style app config), not a phone number.

**Root cause:** `find_phone_numbers` calls
`phonenumbers.PhoneNumberMatcher(text, default_region)` with
`default_region="US"` (chosen deliberately per the comment at
`check_static_extraction.py:924-930`, to preserve matching bare NANP numbers
with no country code). Google's libphonenumber, given `region="US"`, accepts
a bare 7-digit string with no area code, no `+`, no formatting, and no phone-
like context (no `tel:`, no "phone"/"call" label nearby) as a "valid" local
number. Any 7-digit numeric literal anywhere in a script — a config ID, a
timestamp fragment, an internal object ID — can trigger this.

**Verified:**
```
$ python3 -c "
import sys; sys.path.insert(0,'third_party')
import phonenumbers
text = '\"helpCenterId\":3107781,\"url\"'
for m in phonenumbers.PhoneNumberMatcher(text, 'US'):
    print(m.raw_string, m.number, phonenumbers.is_valid_number(m.number))
"
3107781 Country Code: 1 National Number: 3107781 True
```

**Suggested fix:** Require some phone-like context before accepting a
no-country-code, no-area-code 7-digit match — e.g. only accept bare NANP
matches that came from a formatted separator (`-`/`.`/` ` between the 3 and 4
digit groups, as a real 7-digit number would usually be written), or require
adjacency to a phone-signaling token (`tel:`, `"phone"`, `"telephone"`, a
`<a href="tel:...">`) before trusting a script-only match. Alternatively, drop
`default_region="US"` matching for the script-vs-visible-text comparison
specifically (REN-10 only cares about numbers that were visibly rendered
elsewhere as a "real" contact number — those normally include a country code
or clear formatting) and keep the lenient bare-digit matching only for
`+`-prefixed international numbers, which is already unambiguous.

## Bug 2 — CDN/edge bot-challenge (HTTP 429) not distinguished from generic fetch failure

**Where:** `skills/perimeter-access-audit/scripts/check_perimeter.py`'s
`fetch_text`/`fetch_page_with_headers` (used for PER-04 llms.txt, PER-05
llms-full.txt, PER-07 index.md negotiation, PER-10 api-catalog), and
`shared/page_fetch.py` (used by static-extraction-audit/retrieval-readiness-
audit for per-page fetches in `--sample-file` mode).

**What happened:** On tryhackme.com, `/llms.txt`, `/llms-full.txt`,
`/index.md`, and `/.well-known/api-catalog` all return **HTTP 429** — every
single time, from every client tested (curl default UA, a full desktop
Chrome UA string, Python's default urllib UA, and `GPTBot`), including after
a 20+ second cooldown. The response carries `server: Vercel`,
`x-vercel-mitigated: challenge`, and an `x-vercel-challenge-token` header —
this is Vercel's bot-management edge challenge, not a rate limit that clears
on retry. The same edge challenge also blocks specific content routes in the
page sample: `/module/advanced-client-side-attacks`,
`/path/outline/advancedendpointinvestigations`, and
`/room/ho-aoc2025-yboMoPbnEX` all return the same 429 + `x-vercel-mitigated:
challenge` for every UA tested, while the homepage, `/pricing`, `/contact`,
`/about`, `/business`, etc. all return normal 200s.

**Root cause:** `check_perimeter.py`'s `fetch_text`/`fetch_page_with_headers`
only distinguish three states — "present", "absent" (404/410), and
"unavailable" (everything else, including 429, 403, network failure). A 429
edge challenge is bucketed into "unavailable" exactly like a transient
network blip, and the resulting `unknown_checks` reason is just
"`<url>` returned HTTP 429" — it never surfaces that this is a deliberate,
persistent CDN-level bot block. The marketplace *already has* the logic to
tell a genuine block from an ambiguous error —
`skills/perimeter-access-audit/scripts/_perimeter_edge_probe.py`'s
`classify_response`/`CHALLENGE_MARKERS` (used by PER-03) — but that logic is
never reused by the llms.txt/llms-full.txt/index.md/api-catalog fetches, or
by `shared/page_fetch.py`'s per-page fetches for static-extraction-audit and
retrieval-readiness-audit. PER-03 itself only ever probes root `/` with
representative bot UAs, so it never observes this either — root `/` is not
edge-challenged, only these specific paths and content routes are, so PER-03
correctly reports nothing.

**Why it matters:** This is exactly the story the perimeter-access-audit
skill exists to catch — a CDN/WAF rule that blocks a path everyone (including
real AI crawlers, and ordinary browsers with no session) is challenged on —
but on this site it's currently invisible in the composed report. The
audit's `unknown_checks` entries for PER-04/05/07/10 read as "we couldn't
tell," when in fact the evidence needed to say "this is blocked, not just
unreachable" was already collected (the HTTP status and response headers)
and simply discarded.

**Suggested fix:** In `fetch_text`/`fetch_page_with_headers`, when the status
is 429 or 403, capture the response headers and run the same
`classify_response`/`CHALLENGE_MARKERS` check (or at minimum flag a vendor
bot-management header like `x-vercel-mitigated: challenge`,
`cf-mitigated: challenge`, or a body match against `CHALLENGE_MARKERS`) before
falling back to a generic "unavailable" — then have PER-04/05/07/10 report a
`blocked`-flavored finding (or at least a more specific `unknown_checks`
reason: "edge challenge, not absence") instead of a bare "unavailable".
Consider extending PER-03 itself to probe one or two of these
well-known-file paths in addition to root `/`, since a CDN can clearly rule-
match on path, not just be a blanket allow/block at `/`.

## Confirmed-correct findings (spot-checked, not bugs)

- **F-001 (EN-09, high)** — "Form fields have no accessible name" on
  `/contact`: verified by inspecting the raw HTML. The `fullName`/`email`
  inputs and the message `<textarea>` have no `id` attribute, and their
  visible `<label>` elements are unlabeled siblings with no `for` attribute
  — a real accessible-name gap, not a false positive.
- **F-012/F-019 (REN-02)** — Next.js App Router RSC hydration stream
  (`self.__next_f.push(...)`) detected on the homepage and 21 other sampled
  pages, reported at `low` severity/confidence as an acknowledged detection
  limit (not a false "content missing" claim) — matches the modern-hydration
  fix already shipped this cycle. On 2 pages the hydration payload was
  compared and genuinely contains content absent from extracted visible
  text (`medium`, correctly escalated).
- **Paginated-finding merge** — composing this run's per-page REN-02 findings
  (22 separate per-page JSON files worth) collapsed correctly into single
  `F-012`/`F-019` report entries instead of 22 duplicate findings, while
  EN-04's per-page orphan findings (which carry distinct per-URL hashed ids
  by design) correctly stayed separate. Confirms the `merge_paginated_findings`
  fix from the previous cycle works against a real multi-page run, not just
  the synthetic test fixture.

## Fixes applied (2026-09-11)

### Bug 1 fix — REN-10 false positive

`shared/phone_numbers.py:find_phone_numbers` now rejects any match that
`phonenumbers.is_possible_number_with_reason` classifies as
`ValidationResult.IS_POSSIBLE_LOCAL_ONLY` — libphonenumber's own name for a
bare-digit match (no country code, no area code, no formatting) that is only
"valid" as a backward-compatible local-dialing format. That is precisely the
shape of the false positive (`"helpCenterId":3107781`), and the check is a
principled library-provided distinction rather than an ad-hoc length or
punctuation heuristic, so it generalizes to any `default_region`, not just
"US".

Verified:
- New regression test `test_a_bare_local_only_number_with_no_area_code_is_rejected`
  in `tests/test_phone_numbers.py`, reproducing the exact live string.
- All 8 pre-existing tests in that file still pass unchanged (every one uses
  a 10-digit or `+`-prefixed number, none of which are local-only).
- Re-ran `find_phone_numbers` directly against the saved
  `help.tryhackme.com` page that produced the false positive: no match found
  post-fix.
- Full suite: 1350 passed (was 1345; +5 from this fix's and bug 2's new
  tests), 116 subtests passed.

### Bug 2 fix — CDN edge-challenge blindspot

`classify_response`/`CHALLENGE_MARKERS`/`EDGE_BLOCK_STATUS_CODES` moved from
`_perimeter_edge_probe.py` (PER-03-only) into `_perimeter_fetch.py`, the
lower-level module PER-03 already imports `fetch_text` from — single source
of truth, re-exported from `_perimeter_edge_probe` so every existing
`from _perimeter_edge_probe import classify_response` (including
`check_perimeter.py` and `tests/test_edge_access.py`) keeps working
unchanged.

Both fetch primitives now reuse it on a non-404/410 HTTPError:
- `_perimeter_fetch.py:fetch_text` (used for PER-04 llms.txt, PER-05
  llms-full.txt, PER-07 index.md) — reads the response body (bounded to
  4KB, same budget PER-03's own probes use), classifies it, and folds a
  "blocked"/"challenge" result into the returned error text instead of a
  bare HTTP code.
- `check_perimeter.py:fetch_page_with_headers` (used for PER-10
  api-catalog) — same classification added on the same branch, without
  disturbing what this function exists for: response headers on a non-404
  error are still captured and returned (a 403/429's `X-Robots-Tag` etc.).

Added the vercel challenge page's own title string
(`"vercel security checkpoint"`) to `CHALLENGE_MARKERS` — this is a real
vendor challenge page's own signature, same category as the existing
Cloudflare/PerimeterX markers, and it's what tryhackme.com's edge actually
serves (status 429 alone was already enough to classify it as "blocked",
since 429 is in `EDGE_BLOCK_STATUS_CODES`, but the body marker gets it the
more accurate "challenge" label when present).

Verified:
- New test classes `FetchTextEdgeChallengeTests` (5 tests) and one added
  test in `FetchPageWithHeadersTests` in `tests/test_perimeter_audit.py`,
  against a real local HTTP server (not mocked) serving 429/403/500/404 with
  and without a challenge body — including a control asserting a 500 is
  *not* reported as a block (5xx stays outside `EDGE_BLOCK_STATUS_CODES` on
  purpose: an origin fault is not a deliberate edge decision).
- Full suite: 1350 passed, 116 subtests passed — no regressions in PER-03's
  own tests (`test_edge_access.py`) or anywhere else.
- Re-ran `check_perimeter.py --url https://tryhackme.com` live. All four
  previously-opaque `unknown_checks` entries now read, e.g.:
  > `PER-04 - https://tryhackme.com/llms.txt returned HTTP 429, classified as
  > a CDN/edge challenge (server: Vercel): the edge answered with a
  > bot-management challenge page rather than a generic error, so this is
  > not confirmation the file is absent — see PER-03 for the same
  > classification applied to root access`

  Same for PER-05, PER-07, and PER-10 (api-catalog) — all four now name the
  edge challenge explicitly instead of a bare "returned HTTP 429".
