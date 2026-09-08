"""Shared constants for the perimeter-access-audit skill's split modules (bot taxonomy, tier calibration, timeouts, user agents) — previously module-level globals in check_perimeter.py itself.
"""

from __future__ import annotations

OWNER_SKILL = "perimeter-access-audit"
CAPABILITY_IDS = [
    "PER-01", "PER-02", "PER-03", "PER-04", "PER-05", "PER-06",
    "PER-07", "PER-08", "PER-09", "PER-10", "PER-11",
]
USER_AGENT = "brand-ai-readiness-audit/0.1 (+read-only site audit; robots-respecting)"
FETCH_TIMEOUT_SECONDS = 10
EDGE_PROBE_DELAY_SECONDS = 0.3

# Three tiers, because a block on one tier means something different from a
# block on another. Collapsing them into "AI bots" is what produces both false
# alarms and missed critical failures. See references/ai-bot-taxonomy.md.
BOT_TIERS: dict[str, tuple[str, ...]] = {
    "training": (
        "GPTBot",
        "ClaudeBot",
        "Google-Extended",
        "CCBot",
        "Applebot-Extended",
        "meta-externalagent",
        "Bytespider",
    ),
    "ai_search": (
        "OAI-SearchBot",
        "PerplexityBot",
        "Claude-SearchBot",
        "DuckAssistBot",
    ),
    "on_demand": (
        "ChatGPT-User",
        "Claude-User",
        "Perplexity-User",
        "Meta-ExternalFetcher",
    ),
}

TIER_LABELS = {
    "training": "model-training crawlers",
    "ai_search": "real-time AI search crawlers",
    "on_demand": "on-demand user-triggered fetchers",
}

# Severity is derived from the causal chain, not from how alarming the block
# looks. Each entry states the chain it is claiming.
TIER_SEVERITY = {
    # Blocking these removes the site from the live retrieval pass that builds
    # cited answers. Direct, immediate, and the reason gate 1 exists.
    "ai_search": ("critical", "high"),
    # A user asked the assistant to open this specific page. Providers often
    # treat that as user-directed access rather than crawling, so a disallow
    # here is less reliably decisive than it looks.
    "on_demand": ("high", "medium"),
    # Affects what the model absorbs into parametric memory over time, not
    # whether today's answer can cite the page — and it is frequently a
    # deliberate content-licensing decision, not a defect.
    "training": ("medium", "high"),
}

TIER_MECHANISM = {
    "ai_search": (
        "Assistants that answer with citations run a live retrieval pass with these "
        "user agents. A disallow stops the fetch, and a page that is never fetched "
        "cannot be quoted or linked, however good its content is."
    ),
    "on_demand": (
        "These agents fetch one URL because a user asked the assistant to open it. "
        "Providers vary in whether they treat that as user-directed access outside "
        "crawl rules, so a disallow here degrades — rather than reliably prevents — "
        "the brand appearing when a user pastes or names one of its pages."
    ),
    "training": (
        "These crawlers gather text for future model training, so a disallow shapes "
        "what a model knows about the brand without being prompted. It does not stop "
        "today's cited answers. Blocking them can be a deliberate licensing position; "
        "it is only a defect if the brand also expects assistants to know it unprompted."
    ),
}

# One representative agent per tier. Probing all fifteen would multiply
# request volume for signal CDN rulesets rarely provide — edge bot-management
# products typically block by vendor category ("AI crawlers"), not by
# individually enumerated agent — so one probe per tier is the cheap,
# considerate design, stated here as a chosen tradeoff rather than hidden.
# Chosen because each is the most commonly named agent in published CDN
# AI-bot-blocking rule sets for its tier.
REPRESENTATIVE_AGENTS: dict[str, str] = {
    "ai_search": "OAI-SearchBot",
    "on_demand": "ChatGPT-User",
    "training": "GPTBot",
}

# An ordinary browser UA, used only as a reachability control: is the origin up
# at all, for a request that carries no AI-bot identity? Without this, "the AI
# bot got a 403" and "the whole site is down right now" are indistinguishable,
# and reporting the former when the truth is the latter is a false positive.
CONTROL_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

AUDIT_PURPOSE_HEADER = "read-only accessibility audit; single GET; no data collected; see brand-ai-readiness-audit"
