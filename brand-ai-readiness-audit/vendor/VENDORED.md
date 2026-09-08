# Vendored assets

Data only — no code. `tests/test_marketplace_manifest.py`'s `SafetyTests`
enforces this: `vendor/` may contain no `.py`, `.so`, or `.pyd` file.

## public_suffix_list.dat

- **Upstream:** https://raw.githubusercontent.com/publicsuffix/list/master/public_suffix_list.dat
  (mirrors https://publicsuffix.org/list/public_suffix_list.dat, the canonical
  source; the GitHub raw URL was used only because it was reachable from this
  environment)
- **Snapshot date:** 2026-09-05
- **License:** MPL-2.0 (text: `vendor/LICENSE-public-suffix-list.txt`)
- **SHA-256:** `00dda6fa84060cca59415b5ba30bbe9d6700deb78d177f59fc83673531e30099`
- **Consumed by:** `shared/public_suffix.py`
- **Depended on by capability rows:** ENT-07 (cross-domain service
  attribution, B2, Phase 4)

`shared/public_suffix.py` loads this file lazily at first use and degrades to
a documented two-label heuristic with `confidence: low` if the file is
missing — it never raises on a missing or unreadable vendor asset.

## bot_taxonomy.json

- **Upstream:** https://raw.githubusercontent.com/ai-robots-txt/ai.robots.txt/main/robots.json
- **Snapshot date:** 2026-09-07
- **License:** MIT (text: `vendor/LICENSE-ai-robots-txt.txt`)
- **SHA-256:** `4173560ed9965bb86c1ede98100dfba6de2d6f44c92ddfac2fd5c6684f09311`
- **Consumed by:** `skills/perimeter-access-audit/scripts/check_perimeter.py`
  (`_baseline_bot_taxonomy()`, `resolve_bot_tiers()`)
- **Depended on by capability rows:** none yet as of cycle 24 — the widened
  175-bot snapshot is loaded and tested but deliberately **not** wired into
  PER-01/PER-02/C1's blanket/tier-block detection threshold, which still
  uses only the 15 hand-curated `BOT_TIERS` entries. Widening that threshold
  to require blocking all 175 (mostly obscure) bots would make the
  realistic "block the well-known AI bots" robots.txt pattern stop tripping
  the critical PER-02 finding at all — an explicit user decision this cycle
  to keep threshold accuracy over raw coverage (`docs/cycle-24.md`).
  `resolve_bot_tiers()` remains available, tested, and correct for a future
  capability that wants the wider list for something other than that
  threshold.
- **Classification:** each of the 175 bots is deterministically sorted into
  this project's existing three-tier scheme (`training`/`ai_search`/
  `on_demand`) by a one-time keyword classifier over the upstream entry's
  `function`/`description` fields, run at snapshot time — not re-run at
  audit time. The 15 bots already in `BOT_TIERS` keep their original,
  hand-curated tier verbatim as an override (cross-checked 14/15 identical
  to the auto-classifier; the one divergence, `DuckAssistBot` — auto-
  classified `on_demand`, hand-curated `ai_search` — resolves in favor of
  the hand-curated tier). The other 160 bots are new coverage, not
  individually hand-verified; see the JSON's own `_meta` block.
- **Known upstream data quirk:** the raw snapshot lists the same crawler
  under two different tiers with different casing (`meta-externalagent` in
  `training`, `Meta-ExternalAgent` in `on_demand`) — the same robots.txt
  product token under RFC 9309's case-insensitive matching. `resolve_bot_
  tiers()` deduplicates case-insensitively across all tiers (first tier to
  claim a name wins, builtin `BOT_TIERS` entries always claim first) so this
  never produces a double-counted bot.
- **Update process:** no automated re-snapshot script. To refresh: fetch the
  upstream URL, save it as `vendor/bot_taxonomy.json` with a fresh `_meta.
  snapshot_date`, re-run the keyword classifier (see the classification note
  above) or classify manually for a small diff, re-verify the 15 curated
  overrides still take precedence, and run `tests/test_perimeter_audit.py`'s
  `BotTaxonomyAccelerationTests` before committing.
