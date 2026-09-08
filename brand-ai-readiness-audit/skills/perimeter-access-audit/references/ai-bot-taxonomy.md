# AI user agents: the three tiers, and why the distinction changes severity

Reference for `perimeter-access-audit`. The machine-readable list lives in
`scripts/check_perimeter.py` (`BOT_TIERS`); this file explains what each tier
does and why blocking it earns the severity it earns.

Reviewed: 2026-09. User agents change; re-verify against each provider's own
published documentation before relying on this list, and treat an unlisted
agent as unchecked rather than as allowed.

---

## Why tiers at all

"Is the site blocking AI bots?" is the wrong question, and answering it
produces both false alarms and missed failures. Three different mechanisms hide
behind that phrasing:

1. A crawler collecting text to train a future model.
2. A crawler building the live index an assistant retrieves from while
   composing an answer with citations.
3. A fetcher that opens one URL because a user asked the assistant to.

A site that blocks (1) and allows (2) and (3) has made a deliberate,
defensible licensing decision and is fully citable today. A site that blocks
(2) is invisible in cited answers no matter how good its content is. Reporting
both as "AI bots blocked" at the same severity is a false positive of severity
— the check fires correctly and the conclusion drawn from it is wrong.

---

## Tier 1 — model-training crawlers

`GPTBot` · `ClaudeBot` · `Google-Extended` · `CCBot` · `Applebot-Extended` ·
`meta-externalagent` · `Bytespider`

**What a block does.** Withholds the site's text from future training corpora.
Affects what a model can say about the brand *unprompted*, months to years out.
It does not affect whether today's assistant can fetch and cite the page.

**Severity: `medium`, confidence `high`.** Real effect, delayed and indirect,
and frequently intentional. Publishers block training crawlers as a rights
position. The finding is framed as a decision to confirm, not a fault to fix:
*if the brand wants assistants to describe it without being handed a URL,
remove the disallow; if the block is a licensing position, keep it and make
sure tier 2 stays allowed.*

`Google-Extended` and `Applebot-Extended` control AI training use only; they do
not govern ordinary search indexing by `Googlebot` or `Applebot`. Do not report
them as search-visibility problems.

---

## Tier 2 — real-time AI search crawlers

`OAI-SearchBot` · `PerplexityBot` · `Claude-SearchBot` · `DuckAssistBot`

**What a block does.** Removes the site from the retrieval pass that assistants
run while composing an answer. The causal chain is short and needs no study to
defend: not fetched, therefore not read, therefore not quoted and not linked.

**Severity: `critical`, confidence `high`.** This is gate 1's whole point. A
brand can rank well in conventional search, publish excellent content, and
still be entirely absent from cited AI answers on the strength of these four
lines in a text file.

The blocking is also usually costless to reverse: these crawlers are
low-volume, so the bandwidth argument for excluding them does not hold.

---

## Tier 3 — on-demand, user-triggered fetchers

`ChatGPT-User` · `Claude-User` · `Perplexity-User` · `Meta-ExternalFetcher`

**What a block does.** Prevents the assistant from opening a page when a user
pastes or names its URL — the highest-intent moment a brand gets, since
somebody is asking about it by name.

**Severity: `high`, confidence `medium`.** Confidence is deliberately reduced.
Providers differ on whether a fetch made in direct response to a user request
counts as crawling governed by robots.txt or as user-directed access outside
it, and provider behaviour here has changed over time. The finding is therefore
phrased as degradation rather than as a guaranteed block, and it must never be
written as though the outcome is certain.

---

## Blanket block (PER-02)

When every agent in all three tiers is disallowed at `/`, the tier distinction
is moot and three separate findings for one root cause is report noise. One
finding is emitted instead, in one of two forms:

- **Wildcard group disallows `/`.** Everything is blocked, conventional
  crawlers included. Correct for a staging host, total visibility loss for a
  production one — so the finding says exactly that rather than assuming a
  mistake.
- **AI agents disallowed while the wildcard group is not.** A deliberate,
  targeted exclusion of AI assistants. The finding separates what that
  withholds (training data, defensible) from what it costs (citations in
  answers being generated right now, usually not intended).

---

## Edge/CDN blocking (PER-03) — a second, stronger layer

robots.txt is the origin's published policy. A CDN or WAF sitting in front of
the origin enforces its own bot-management rules first, and can return a
block before the request ever reaches the origin — before robots.txt is even
in the picture. A site can publish full permission and still be invisible to
the exact agents it claims to welcome, because the block happens one layer up
from where robots.txt is checked. This is the divergence PER-03 detects:
robots.txt says yes, the edge says no.

**Detection.** One representative agent per tier — `OAI-SearchBot`,
`ChatGPT-User`, `GPTBot` — is sent a live GET to `/` under its exact user
agent, alongside a control request under an ordinary browser user agent. If
the control succeeds and the agent request gets HTTP 403/429, or 200 with a
recognised bot-management challenge page, that tier's block is reported. The
severity table is unchanged from PER-01: PER-03 changes which layer produced
the block, not what a block of that tier costs.

**Why one agent per tier, not all fifteen.** Edge bot-management products
typically block by vendor category — "AI crawlers," "known bots" — rather than
by individually enumerated agent, so one probe per tier is the signal a
finer-grained scan would rarely improve on, at a quarter of the request
volume. Stated as a chosen tradeoff, not a hidden limitation.

**Why the control request comes first, always.** Confirmed live against two
sites running aggressive bot-management CDNs: the control itself was
challenged, meaning *every* visitor without a real browser is challenged there,
not AI bots specifically. A check that probed only the AI-bot user agents would
have reported an AI-bot-specific block on both sites — a false positive with a
plausible-looking mechanism attached. PER-03 refuses to draw a conclusion
whenever the control does not succeed, and is reported `unknown` instead.

**Why an agent robots.txt already disallows is never probed.** This is
enforced in code, not left to judgement. Two independent reasons: sending that
request would itself violate "respect robots.txt," since a compliant crawler
of that name would never make it; and it would write a hit under that agent's
exact user-agent string into the target's own bot-traffic logs, for an agent
the site explicitly excluded. PER-01 already reports the robots-level block for
that tier, so nothing is lost by not also probing the edge.

**Ambiguous statuses are `unknown`, never a block.** A 5xx, a redirect, or an
unusual code that names no deliberate access decision (HTTP 402 was observed
live, from a real site, against a probe agent) is reported unknown for that
tier rather than asserted as a block — the same false-positive-of-severity
concern that governs llms.txt severity above.

---

## How a group is matched to an agent

Exactly, case-insensitively, on the full product token, with `*` as the
fallback group — RFC 9309. Not by substring.

The distinction is not academic. A widely-read site carries a group for the
historical `Fetch` crawler; `fetch` is a substring of `meta-externalfetcher`,
and substring matching therefore reports Meta's fetcher as blocked on a site
whose robots.txt never mentions Meta. A group named `Claude` would likewise
capture `Claude-User` and `Claude-SearchBot`, and one named `Search` would
capture `OAI-SearchBot`.

Python's `urllib.robotparser` matches by substring, so group selection is
implemented here rather than delegated. Rule evaluation — path matching,
`Allow`/`Disallow` precedence — is still the standard library's, applied to
the one group that genuinely applies.

## PER-05/06/07/08 — the rest of Cluster A

Added after PER-01/02/03/04 were already frozen and field-validated.
Deliberately kept in this skill rather than a new one: same gate, same
"first, cheapest, veto-item" role, same owner-per-capability boundary as the
rest of Cluster A.

**PER-05 (llms-full.txt) and PER-07 (`.md` negotiation) are calibrated like
PER-04:** `low` severity, proactive track, absence alone not flagged for
PER-05 specifically (it is llms.txt's optional companion, one step further
from established practice than llms.txt itself). Neither convention has
measured evidence of citation impact — the same severity-calibration
discipline established for llms.txt applies here without modification.

**PER-06 (sitemap.xml) parses with a regex, not `xml.etree.ElementTree`.**
The sitemap is fetched from the audited site — untrusted input — and a
regex has no entity-expansion attack surface at all, so "billion laughs" and
external-entity classes of attack a fuller XML parser can be vulnerable to
are structurally not a concern. The same reasoning already governs this
marketplace's other parsers: JSON-LD stays on `json.loads` (safe by
construction), HTML stays on a restricted `HTMLParser`. Confirmed against a
real, large sitemap live (apple.com, 857 `<url>` entries, standard default
namespace) before trusting the happy path; the root-element pattern also
tolerates a namespace-prefixed root (`<s:urlset xmlns:s="...">`), legal XML
that a plain `<urlset` match would miss, even though no live site sampled
happened to use one.

**PER-08 (sitemap referenced in robots.txt) only evaluates once PER-06
confirms a sitemap exists**, and distinguishes *confirmed absent* from
*status unknown* for `sitemap_status` — collapsing the two was an actual bug
caught by the project's own test suite before shipping: a caller passing
`sitemap_status="unavailable"` (fetch failed, applicability itself unknown)
was silently treated the same as `"absent"` (confirmed no sitemap, PER-08
correctly has nothing to say), losing a genuine unknown. Fixed to report
`unknown` for the former and stay silent only for the latter.

## PER-09 — cross-layer access-signal contradiction

PER-01 through PER-08 each ask "is X present and valid?" of one file or
header at a time. PER-09 asks a structurally different question: "do the
site's own declarations agree with each other?" A site states its access
policy in up to six places — robots.txt, `X-Robots-Tag`, `<meta
name="robots">`/`<meta name="googlebot">`/`noai`/`noimageai`, TDMRep
(`/.well-known/tdmrep.json`), llms.txt, sitemap.xml — and nothing before
PER-09 ever compared them.

**Why this needed new infrastructure.** Response headers were fetched and
discarded everywhere in this skill until `fetch_page_with_headers` was added
specifically for PER-09. `<meta name="robots">` was never parsed at all. Both
gaps are why PER-01 through PER-08 could not have caught any of PER-09's five
rules, however thorough each individually is.

**C1 — sitemap URL vs. a path-specific robots.txt rule.** The one place this
reference's taxonomy widens past root-only reachability: a sitemap-declared
URL can be checked against a robots.txt `Disallow` rule for its *own path*,
not just `/`. `can_fetch_path` (a sibling of `can_fetch_root`, same
group-selection contract) does this. **Overlap control is load-bearing
here**: a bot only counts as a C1 contradiction if it *can* fetch the root
but *cannot* fetch this specific path — a bot with no root access at all is
already PER-01/02's finding, and re-reporting it under a new ID would be the
same root cause counted twice. Severity is TIER_SEVERITY degraded one notch:
a weaker claim than a whole-tier root block, since only one path is affected.

**C2 — noindex/noai on a page declared canonical.** A sitemap or llms.txt
entry advertises a page as content an AI answer engine should retrieve from.
If that same page's response carries `X-Robots-Tag: noindex` or a `<meta
name="robots" content="noindex">` (or a `noai` signal in either channel),
the site is simultaneously advertising and un-indexing the same URL.
`severity: high` — the header/meta layer always wins in practice, so this is
not a stylistic disagreement, it is a page that will not appear.

**C3 — a TDM reservation robots.txt doesn't back up.** TDMRep expresses
something robots.txt structurally cannot: "index me, do not train on me."
When `tdmrep.json` (or a page-level `tdm-reservation` header/meta) reserves
rights while GPTBot, ClaudeBot or CCBot can still crawl the root, the
reservation is unenforced in practice, since crawling and training happen
through the same fetch these three agents make. Scoped to exactly these
three names — the crawlers TDMRep's own spec discussion names — not this
project's broader `training` tier, so the claim never outruns what TDMRep is
understood to govern.

**C4 — header and meta robots tag disagreeing.** Requires both channels to
carry an explicit, comparable signal — an *absent* meta tag is C2's
contradiction (against sitemap/llms.txt), not this one, since there is
nothing to disagree with a header that was simply never restated. When both
are present and one says noindex while the other doesn't, the header always
wins, and a content author who only edits the page's own meta tag usually
has no visibility into that.

**C5 — no TDMRep declaration, despite named AI-agent rules.** Proactive,
`low`, and gated behind a precision guard stated as a hard requirement in
the implementing plan: only suggest TDMRep to a site that has *already*
engaged with AI access, by naming a specific agent in its own robots.txt
group (not just the wildcard). A site that has never named an AI agent gets
no suggestion — the guard exists specifically so this does not read as
generic noise on every report. Requires *confirmed* absence
(`tdmrep_status == "absent"`, a real 404); a caller that never attempted the
fetch (`"unavailable"`) is not the same as "missing" and must not have a
finding fabricated from an unknown state — the same default-is-unknown
discipline PER-05 through PER-08 already follow.

**No `sameAs`-style liveness fetching anywhere in PER-09.** Every rule reads
data already fetched for another capability, or one of exactly two new GETs
(the root page with headers, `tdmrep.json`) plus whatever `--page-url`
widens explicitly. Nothing here follows a link to check if it resolves.

## What this reference does not cover

- **Crawl-delay and rate limits.** Not modelled here.
- **Per-path rules for PER-01/02/03.** Those three stay root-only by design.
  PER-09's C1 is the one exception: it checks path-specific robots.txt rules,
  but only for URLs a sitemap actually declares, and only to detect a
  contradiction with that declaration — it is not a general per-path
  reachability scan, and a site that allows `/` while disallowing an
  undeclared documentation tree still has a real problem this reference does
  not see.
