"""Unit tests for citability-audit.

CIT-01/02/06 are deterministic and tested as positive/negative pairs like
every other detector in this project. CIT-04 is agent-judged: only the
extraction function is tested, for what it hands the agent, not a verdict.

The about-link segment-matching tests document a real bug: `href="about-us"`
(no leading slash — an entirely ordinary relative link) was invisible to the
original path-anchored regex, which required a literal leading "/" before
the matched word.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_citability", REPO_ROOT / "skills/citability-audit/scripts/check_citability.py"
)
cit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cit)


class AboutLinkTests(unittest.TestCase):
    def test_a_conventional_about_link_suppresses_the_finding(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/about-us">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_no_about_link_at_all_fires(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/pricing">Pricing</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_a_relative_link_with_no_leading_slash_is_still_recognised(self):
        """Regression: urlparse('about-us').path == 'about-us' (no leading
        slash), which the original path-anchored regex never matched."""
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="about-us">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_a_dot_relative_link_is_recognised(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="./about-us">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_a_parent_relative_link_is_recognised(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="../about-us">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_a_query_string_does_not_prevent_recognition(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="about-us?ref=nav">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_a_nested_about_path_is_recognised(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/company/about-us">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_roundabout_tour_is_not_a_false_positive_match(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/roundabout-tour">Tour</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_company_news_is_not_a_false_positive_match(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/company-news/2026">News</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_team_building_tips_is_not_a_false_positive_match(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/team-building-tips">Tips</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_a_mediawiki_namespace_prefixed_about_page_is_recognised(self):
        """Regression, found live against en.wikipedia.org: 'Wikipedia:About'
        is MediaWiki's namespace-prefixed convention for the About page,
        used across the whole MediaWiki ecosystem — not just Wikipedia."""
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/wiki/Wikipedia:About">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_an_unrelated_mediawiki_namespace_page_is_not_a_false_positive(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/wiki/Talk:Random_page">Talk</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_an_extension_suffixed_about_page_is_recognised(self):
        """Regression, found live against docs.python.org (Sphinx-generated
        docs): 'about.html' carries a file extension a bare exact-match
        against 'about' never matched."""
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="../about.html">About</a>')
        self.assertEqual(cit.find_missing_about_link(hrefs), [])

    def test_an_extension_suffixed_lookalike_is_still_not_a_false_positive(self):
        _anchor_hrefs, hrefs, _ = cit.parse_page('<a href="/company-news.html">News</a>')
        findings = cit.find_missing_about_link(hrefs)
        self.assertEqual([f.id for f in findings], ["CIT-01-no-about-link"])

    def test_a_link_rel_author_in_head_counts_as_an_about_signal(self):
        """Regression, found live against docs.python.org: the About page
        was referenced only via `<link rel="author" href="../about.html">`
        in <head> — never a clickable <a> a human would see. This is a
        real, distinct convention (Sphinx-generated docs use it), not a
        hypothetical edge case."""
        _anchor_hrefs, all_hrefs, _ = cit.parse_page(
            '<head><link rel="author" title="About" href="../about.html"></head><body><p>Hi.</p></body>'
        )
        self.assertEqual(cit.find_missing_about_link(all_hrefs), [])

    def test_link_tags_are_not_counted_as_external_citations_for_cit02(self):
        """A <link> can point off-domain too (a stylesheet CDN, a preload),
        and none of that is a source citation. Only <a> tags may satisfy
        CIT-02 — folding <link> into the same collection used there would
        let a CDN stylesheet silently suppress a real 'no source
        attribution' finding."""
        body = " ".join(["word"] * (cit.MIN_SUBSTANTIAL_WORD_COUNT + 10))
        html = f'<head><link rel="stylesheet" href="https://cdn.example.net/style.css"></head><body><p>{body}</p></body>'
        anchor_hrefs, all_hrefs, text = cit.parse_page(html)
        self.assertIn("https://cdn.example.net/style.css", all_hrefs)
        self.assertNotIn("https://cdn.example.net/style.css", anchor_hrefs)
        findings = cit.find_missing_source_attribution(anchor_hrefs, text, "example.com")
        self.assertEqual([f.id for f in findings], ["CIT-02-no-source-attribution"])


class SourceAttributionTests(unittest.TestCase):
    def _long_html(self, extra_links: str = "") -> str:
        body = " ".join(["word"] * (cit.MIN_SUBSTANTIAL_WORD_COUNT + 10))
        return f"<p>{body}</p>{extra_links}"

    def test_a_short_page_is_never_flagged(self):
        html = "<p>Short page, no links.</p>"
        hrefs, _all_hrefs, text = cit.parse_page(html)
        self.assertEqual(cit.find_missing_source_attribution(hrefs, text, "example.com"), [])

    def test_a_long_page_with_zero_links_fires(self):
        hrefs, _all_hrefs, text = cit.parse_page(self._long_html())
        findings = cit.find_missing_source_attribution(hrefs, text, "example.com")
        self.assertEqual([f.id for f in findings], ["CIT-02-no-source-attribution"])

    def test_a_long_page_with_only_internal_links_still_fires(self):
        html = self._long_html('<a href="/pricing">Pricing</a>')
        hrefs, _all_hrefs, text = cit.parse_page(html)
        findings = cit.find_missing_source_attribution(hrefs, text, "example.com")
        self.assertEqual([f.id for f in findings], ["CIT-02-no-source-attribution"])

    def test_a_long_page_with_one_external_link_does_not_fire(self):
        html = self._long_html('<a href="https://other.example/report">Report</a>')
        hrefs, _all_hrefs, text = cit.parse_page(html)
        self.assertEqual(cit.find_missing_source_attribution(hrefs, text, "example.com"), [])

    def test_a_www_prefixed_link_to_the_same_site_still_counts_as_no_external_source(self):
        """www.example.com is the same site as example.com, not a third
        party — a link to it is not a citation, so this must still fire."""
        html = self._long_html('<a href="https://www.example.com/report">Our own report</a>')
        hrefs, _all_hrefs, text = cit.parse_page(html)
        findings = cit.find_missing_source_attribution(hrefs, text, "example.com")
        self.assertEqual([f.id for f in findings], ["CIT-02-no-source-attribution"])

    def test_a_link_to_a_genuinely_different_www_prefixed_domain_counts_as_external(self):
        html = self._long_html('<a href="https://www.other-example.org/report">Report</a>')
        hrefs, _all_hrefs, text = cit.parse_page(html)
        self.assertEqual(cit.find_missing_source_attribution(hrefs, text, "example.com"), [])


class UnverifiableSuperlativeTests(unittest.TestCase):
    def test_a_superlative_with_a_number_in_the_same_sentence_is_clean(self):
        text = "The fastest plan processes 940 requests per second."
        self.assertEqual(cit.find_unverifiable_superlatives(text), [])

    def test_a_bare_superlative_fires(self):
        text = "Our platform is the fastest on the market for growing teams."
        findings = cit.find_unverifiable_superlatives(text)
        self.assertEqual([f.id for f in findings], ["CIT-06-unverifiable-superlatives"])

    def test_a_short_fragment_like_a_nav_label_does_not_fire(self):
        text = "Best Sellers"
        self.assertEqual(cit.find_unverifiable_superlatives(text), [])

    def test_multiple_superlatives_are_aggregated_into_one_finding(self):
        text = "We are the industry-leading choice. Our platform is unmatched in reliability."
        findings = cit.find_unverifiable_superlatives(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0].structured_evidence["matches"]), 2)

    def test_a_quoted_single_sentence_testimonial_does_not_fire(self):
        text = 'Read what our customers say. “The BEST bacon I have ever had.”'
        self.assertEqual(cit.find_unverifiable_superlatives(text), [])

    def test_a_middle_sentence_of_a_longer_quoted_testimonial_does_not_fire(self):
        text = (
            '“I have employed several law firms over the years for my case. '
            'Many are considered to be the best of their kind. '
            'Among all of these, this firm stands out for its insight and attention.”'
        )
        self.assertEqual(cit.find_unverifiable_superlatives(text), [])

    def test_a_straight_quoted_testimonial_does_not_fire(self):
        text = 'Customer feedback. "They make the best cinnamon rolls in the county."'
        self.assertEqual(cit.find_unverifiable_superlatives(text), [])

    def test_a_brand_authored_superlative_still_fires_alongside_a_quoted_testimonial(self):
        text = (
            'We strategically pursue the best outcome given your circumstances. '
            '“The BEST bacon I have ever had.”'
        )
        findings = cit.find_unverifiable_superlatives(text)
        self.assertEqual([f.id for f in findings], ["CIT-06-unverifiable-superlatives"])
        self.assertEqual(len(findings[0].structured_evidence["matches"]), 1)
        self.assertIn("pursue the best outcome", findings[0].structured_evidence["matches"][0]["sentence"])


class LateCitationTests(unittest.TestCase):
    """CIT-07: reuses CIT-02's own external-link definition — the new
    signal is where in the page a citation falls, not whether one exists
    (CIT-02's job, and a precondition for this one)."""

    def _page(self, words_before: int, href: str, words_after: int) -> str:
        before = " ".join(["word"] * words_before)
        after = " ".join(["word"] * words_after)
        return f'<p>{before}</p><p><a href="{href}">source</a></p><p>{after}</p>'

    def _positions_and_text(self, html: str):
        positions, total_length = cit.parse_page_with_anchor_positions(html)
        _anchor_hrefs, _all_hrefs, text = cit.parse_page(html)
        return positions, total_length, text

    def test_a_citation_buried_in_the_last_stretch_of_a_long_page_fires(self):
        html = self._page(900, "https://other.example/study", 10)
        positions, total_length, text = self._positions_and_text(html)
        findings = cit.find_late_citations(positions, total_length, text, "example.com")
        self.assertEqual([f.id for f in findings], ["CIT-07-late-citation"])

    def test_a_citation_reachable_early_does_not_fire(self):
        html = self._page(10, "https://other.example/study", 900)
        positions, total_length, text = self._positions_and_text(html)
        self.assertEqual(cit.find_late_citations(positions, total_length, text, "example.com"), [])

    def test_no_external_citations_at_all_is_cit02s_job_not_this_ones(self):
        html = self._page(900, "/internal-page", 10)
        positions, total_length, text = self._positions_and_text(html)
        self.assertEqual(cit.find_late_citations(positions, total_length, text, "example.com"), [])

    def test_a_short_page_is_never_flagged_regardless_of_position(self):
        html = self._page(2, "https://other.example/study", 1)
        positions, total_length, text = self._positions_and_text(html)
        self.assertEqual(cit.find_late_citations(positions, total_length, text, "example.com"), [])

    def test_a_www_prefixed_link_to_the_same_site_is_not_a_citation(self):
        html = self._page(900, "https://www.example.com/report", 10)
        positions, total_length, text = self._positions_and_text(html)
        self.assertEqual(cit.find_late_citations(positions, total_length, text, "example.com"), [])

    def test_one_early_and_one_late_external_citation_does_not_fire(self):
        before = " ".join(["word"] * 400)
        middle = " ".join(["word"] * 400)
        after = " ".join(["word"] * 10)
        html = (
            f'<p><a href="https://other.example/early">early source</a></p><p>{before}</p>'
            f'<p>{middle}</p><p><a href="https://other.example/late">late source</a></p><p>{after}</p>'
        )
        positions, total_length, text = self._positions_and_text(html)
        self.assertEqual(cit.find_late_citations(positions, total_length, text, "example.com"), [])


class CitationRecallExtractionTests(unittest.TestCase):
    """CIT-04 has no script verdict; only extraction is tested."""

    def test_a_sourced_numeric_claim_is_not_a_candidate(self):
        html = '<p>Our servers handle <a href="https://stats.example.com">10 million requests</a> per second.</p>'
        candidates = cit.find_citation_recall_candidates(html)
        self.assertEqual(candidates, [])

    def test_an_unsourced_numeric_claim_is_a_candidate(self):
        html = "<p>Our servers handle 10 million requests per second with no downtime.</p>"
        candidates = cit.find_citation_recall_candidates(html)
        self.assertEqual(len(candidates), 1)
        self.assertIn("10 million requests", candidates[0])

    def test_a_sentence_with_no_number_is_never_a_candidate(self):
        html = "<p>We help teams ship faster and communicate better.</p>"
        self.assertEqual(cit.find_citation_recall_candidates(html), [])

    def test_candidates_are_capped(self):
        sentences = " ".join(f"We shipped {i} updates this quarter." for i in range(30))
        html = f"<p>{sentences}</p>"
        candidates = cit.find_citation_recall_candidates(html)
        self.assertLessEqual(len(candidates), 15)

    def test_agent_judgement_request_names_cit04_and_carries_the_rubric_path(self):
        requests = cit.build_agent_judgement_requests("<p>Hi.</p>", "Hi.")
        self.assertEqual(requests[0]["capability_id"], "CIT-04")
        self.assertIn("references/citability-judgement-rubric.md", requests[0]["instructions"])


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        html = (
            '<a href="/pricing">Pricing</a>'
            "<h1>The best platform</h1>"
            "<p>We are unmatched in the industry.</p>"
        )
        out = cit.audit_html("example.com", html, page_url="https://example.com/page")
        self.assertGreaterEqual(len(out["findings"]), 2)  # CIT-01 + CIT-06
        for finding_dict in out["findings"]:
            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "citability-audit")
            self.assertEqual(restored.gate, 3)
            self.assertEqual(restored.category, "discoverability")

    def test_agent_judgement_required_is_present_and_names_cit04(self):
        out = cit.audit_html("example.com", "<h1>Hi</h1>")
        ids = {r["capability_id"] for r in out["agent_judgement_required"]}
        self.assertEqual(ids, {"CIT-04"})

    def test_evaluation_is_deterministic(self):
        html = '<a href="/pricing">Pricing</a><p>The best platform, unmatched.</p>'
        first = cit.audit_html("example.com", html)
        second = cit.audit_html("example.com", html)
        self.assertEqual(first, second)


class SignificantNumberTests(unittest.TestCase):
    def test_the_longest_numeric_token_is_chosen(self):
        self.assertEqual(cit._significant_number("We grew revenue by 47% in year 3."), "47%")

    def test_a_number_with_commas_is_captured_whole(self):
        self.assertEqual(cit._significant_number("Over 4,000,000 users trust us."), "4,000,000")

    def test_no_number_returns_none(self):
        self.assertIsNone(cit._significant_number("No numbers in this sentence at all."))


class OffsiteCorroborationCandidateTests(unittest.TestCase):
    _CLAIM_HTML = "<p>Our platform improved retention by 47% last year, per our internal survey.</p>"

    def test_an_uncorroborated_claim_becomes_a_candidate(self):
        pages = [{"url": "https://forum.example/t/1", "text": "Nothing about that number in this thread."}]
        candidates = cit.find_offsite_corroboration_candidates(self._CLAIM_HTML, pages)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["number"], "47%")

    def test_a_corroborated_claim_does_not_fire(self):
        pages = [{"url": "https://forum.example/t/1", "text": "I heard they hit 47% retention too."}]
        self.assertEqual(cit.find_offsite_corroboration_candidates(self._CLAIM_HTML, pages), [])

    def test_no_offsite_pages_produces_no_candidates(self):
        self.assertEqual(cit.find_offsite_corroboration_candidates(self._CLAIM_HTML, []), [])

    def test_a_claim_with_no_number_is_never_a_candidate(self):
        html = "<p>Our platform is the best choice for teams everywhere.</p>"
        pages = [{"url": "https://forum.example/t/1", "text": "Nothing relevant."}]
        self.assertEqual(cit.find_offsite_corroboration_candidates(html, pages), [])

    def test_a_number_present_only_as_a_substring_elsewhere_does_not_count_as_corroboration(self):
        # "47" must not match inside "1470" — word-boundary-guarded, same
        # discipline RET-01's _token_survives already applies.
        pages = [{"url": "https://forum.example/t/1", "text": "Order number 1470 was shipped yesterday."}]
        candidates = cit.find_offsite_corroboration_candidates(self._CLAIM_HTML, pages)
        self.assertEqual(len(candidates), 1)

    def test_candidates_are_capped(self):
        html = "".join(
            f"<p>Claim number {i} says we grew by {i}23% this quarter alone here.</p>" for i in range(10)
        )
        pages = [{"url": "https://forum.example/t/1", "text": "Nothing corroborated anywhere."}]
        candidates = cit.find_offsite_corroboration_candidates(html, pages)
        self.assertLessEqual(len(candidates), cit._CIT13_MAX_CANDIDATES)


class BuildAgentJudgementRequestsOffsiteTests(unittest.TestCase):
    _HTML = "<p>Our platform improved retention by 47% last year, per our internal survey.</p>"

    def test_cit13_is_omitted_when_offsite_pages_is_none(self):
        requests = cit.build_agent_judgement_requests(self._HTML, "some visible text", offsite_pages=None)
        ids = [r["capability_id"] for r in requests]
        self.assertNotIn("CIT-13", ids)

    def test_cit13_is_included_when_offsite_pages_is_an_empty_list(self):
        requests = cit.build_agent_judgement_requests(self._HTML, "some visible text", offsite_pages=[])
        ids = [r["capability_id"] for r in requests]
        self.assertIn("CIT-13", ids)

    def test_cit13_points_at_the_rubric(self):
        requests = cit.build_agent_judgement_requests(self._HTML, "some visible text", offsite_pages=[])
        cit13 = next(r for r in requests if r["capability_id"] == "CIT-13")
        self.assertIn("references/citability-judgement-rubric.md", cit13["instructions"])


class AuditHtmlOffsiteTests(unittest.TestCase):
    def test_no_offsite_urls_omits_cit13_and_leaves_unknown_checks_empty(self):
        out = cit.audit_html("example.com", "<p>Some ordinary text with 47% in it.</p>")
        ids = [r["capability_id"] for r in out["agent_judgement_required"]]
        self.assertNotIn("CIT-13", ids)
        self.assertEqual(out["unknown_checks"], [])

    def test_an_unreachable_offsite_url_becomes_an_unknown_check(self):
        html = "<p>Some ordinary text with 47% in it.</p>"
        out = cit.audit_html(
            "example.com", html, offsite_urls=["https://this-host-does-not-exist.invalid/page"]
        )
        self.assertEqual(len(out["unknown_checks"]), 1)
        self.assertEqual(out["unknown_checks"][0]["capability_id"], "CIT-13")
        ids = [r["capability_id"] for r in out["agent_judgement_required"]]
        self.assertIn("CIT-13", ids)


class RobotsAllowsOffsiteFetchTests(unittest.TestCase):
    def test_an_unreachable_robots_txt_defaults_to_allowed(self):
        self.assertTrue(cit.robots_allows_offsite_fetch("https://this-host-does-not-exist.invalid/page"))


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(cit.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(cit.is_public_host("10.0.0.5"))


def _hub_and_spoke_graph(num_spokes=6):
    """A hub page ("/") linked from and to every spoke; a separate
    "factdense" page links out to the hub but receives no inbound link at
    all. The hub soaks up nearly all PageRank from the reciprocal spokes,
    leaving the unlinked-to fact-dense page starved — exactly the shape
    CIT-08 exists to catch."""
    node_ids = (
        ["https://acme.com/"]
        + [f"https://acme.com/spoke{i}" for i in range(num_spokes)]
        + ["https://acme.com/factdense"]
    )
    edges = [("https://acme.com/factdense", "https://acme.com/")]
    for spoke in node_ids[1:-1]:
        edges.append(("https://acme.com/", spoke))
        edges.append((spoke, "https://acme.com/"))
    return node_ids, edges


class FindLinkAuthorityStarvedPagesTests(unittest.TestCase):
    def test_a_fact_dense_page_starved_by_a_thin_hub_is_flagged(self):
        node_ids, edges = _hub_and_spoke_graph()
        word_counts = {"https://acme.com/factdense": 800}
        findings = cit.find_link_authority_starved_pages(node_ids, edges, word_counts)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "CIT-08")
        self.assertEqual(findings[0].severity, "medium")

    def test_below_minimum_sample_size_never_fires(self):
        """Dominant false positive: PageRank over a tiny graph is too noisy
        to support even a sample-scoped claim."""
        node_ids, edges = _hub_and_spoke_graph(num_spokes=1)
        word_counts = {"https://acme.com/factdense": 800}
        self.assertEqual(cit.find_link_authority_starved_pages(node_ids, edges, word_counts), [])

    def test_no_fact_dense_page_in_the_sample_never_fires(self):
        node_ids, edges = _hub_and_spoke_graph()
        self.assertEqual(cit.find_link_authority_starved_pages(node_ids, edges, {}), [])

    def test_the_hub_itself_being_fact_dense_never_fires(self):
        """Dominant false positive: when the sample's top-authority page IS
        itself content-dense, hub and authority coincide — no separation
        problem exists to report."""
        node_ids, edges = _hub_and_spoke_graph()
        word_counts = {"https://acme.com/": 900, "https://acme.com/factdense": 800}
        self.assertEqual(cit.find_link_authority_starved_pages(node_ids, edges, word_counts), [])

    def test_a_uniformly_linked_graph_with_no_starvation_never_fires(self):
        """No dominant hub soaking up equity — every page links to every
        other page, so PageRank is roughly uniform and nothing is starved."""
        node_ids = [f"https://acme.com/p{i}" for i in range(6)]
        edges = [(a, b) for a in node_ids for b in node_ids if a != b]
        word_counts = {"https://acme.com/p0": 800}
        self.assertEqual(cit.find_link_authority_starved_pages(node_ids, edges, word_counts), [])

    def test_evidence_states_its_own_sample_size_never_site_wide_scope(self):
        node_ids, edges = _hub_and_spoke_graph()
        word_counts = {"https://acme.com/factdense": 800}
        finding = cit.find_link_authority_starved_pages(node_ids, edges, word_counts)[0]
        self.assertIn(f"{len(node_ids)} pages sampled", finding.evidence)
        self.assertIn("does not prove site-wide link starvation", finding.evidence)

    def test_finding_validates_against_the_shared_contract(self):
        node_ids, edges = _hub_and_spoke_graph()
        word_counts = {"https://acme.com/factdense": 800}
        finding = cit.find_link_authority_starved_pages(node_ids, edges, word_counts)[0]
        self.assertEqual(finding.validate(), [])


class AuditLinkGraphTests(unittest.TestCase):
    def test_an_unreachable_page_becomes_one_unknown_check(self):
        out = cit.audit_link_graph("acme.com", ["https://this-host-does-not-exist.invalid/page"])
        self.assertEqual(out["findings"], [])
        self.assertEqual(len(out["unknown_checks"]), 1)
        self.assertIn("this-host-does-not-exist.invalid", out["unknown_checks"][0]["reason"])

    def test_no_page_urls_produces_an_empty_clean_report_not_a_crash(self):
        out = cit.audit_link_graph("acme.com", [])
        self.assertEqual(out["findings"], [])
        self.assertEqual(out["unknown_checks"], [])

    def test_output_always_carries_the_capability_ids(self):
        out = cit.audit_link_graph("acme.com", [])
        self.assertEqual(out["capability_ids"], cit.CAPABILITY_IDS)
        self.assertIn("CIT-08", out["capability_ids"])
        self.assertIn("CIT-09", out["capability_ids"])

    def test_coverage_manifest_is_always_attached_and_not_expired_by_default(self):
        out = cit.audit_link_graph("acme.com", [])
        self.assertEqual(len(out["coverage"]["stages"]), 1)
        self.assertFalse(out["coverage"]["stages"][0]["expired"])

    def test_pages_beyond_the_fetch_budget_get_an_unknown_check_not_a_hang(self):
        calls = {"n": 0}

        def fake_clock():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 1000.0

        page_urls = ["https://this-host-does-not-exist.invalid/a", "https://this-host-does-not-exist.invalid/b"]
        out = cit.audit_link_graph("acme.com", page_urls, clock=fake_clock)
        self.assertEqual(len(out["unknown_checks"]), 2)
        for unknown in out["unknown_checks"]:
            self.assertEqual(unknown["capability_id"], "CIT-08")
            self.assertIn("budget", unknown["reason"])
        self.assertTrue(out["coverage"]["stages"][0]["expired"])


class ExtractTitleTests(unittest.TestCase):
    def test_a_title_tag_is_extracted(self):
        self.assertEqual(cit._extract_title("<html><head><title>Acme Widgets</title></head></html>"), "Acme Widgets")

    def test_whitespace_in_the_title_is_collapsed(self):
        html = "<title>Acme\n   Widgets  Co</title>"
        self.assertEqual(cit._extract_title(html), "Acme Widgets Co")

    def test_no_title_tag_returns_empty_string(self):
        self.assertEqual(cit._extract_title("<html><body>Hi</body></html>"), "")


class LooksLikeComparisonPageTests(unittest.TestCase):
    def test_a_vs_slug_is_recognised(self):
        self.assertTrue(cit._looks_like_comparison_page("https://acme.com/acme-vs-widgetco", ""))

    def test_an_alternatives_to_slug_is_recognised(self):
        self.assertTrue(cit._looks_like_comparison_page("https://acme.com/alternatives-to-widgetco", ""))

    def test_a_versus_title_is_recognised(self):
        self.assertTrue(cit._looks_like_comparison_page("https://acme.com/compare", "Acme Versus WidgetCo"))

    def test_a_compared_to_title_is_recognised(self):
        self.assertTrue(cit._looks_like_comparison_page("https://acme.com/page", "Acme compared to WidgetCo"))

    def test_an_ordinary_page_is_not_recognised(self):
        self.assertFalse(cit._looks_like_comparison_page("https://acme.com/pricing", "Pricing - Acme"))


class FindComparisonContentGapTests(unittest.TestCase):
    def test_no_comparison_page_anywhere_in_a_large_enough_sample_is_flagged(self):
        page_titles = {f"https://acme.com/p{i}": f"Page {i}" for i in range(5)}
        findings = cit.find_comparison_content_gap(page_titles)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].capability_id, "CIT-09")
        self.assertEqual(findings[0].track, "proactive")
        self.assertEqual(findings[0].severity, "low")

    def test_a_single_comparison_page_anywhere_suppresses_the_finding(self):
        page_titles = {f"https://acme.com/p{i}": f"Page {i}" for i in range(4)}
        page_titles["https://acme.com/acme-vs-widgetco"] = "Acme vs WidgetCo"
        self.assertEqual(cit.find_comparison_content_gap(page_titles), [])

    def test_below_minimum_sample_size_never_fires(self):
        page_titles = {f"https://acme.com/p{i}": f"Page {i}" for i in range(3)}
        self.assertEqual(cit.find_comparison_content_gap(page_titles), [])

    def test_finding_validates_against_the_shared_contract(self):
        page_titles = {f"https://acme.com/p{i}": f"Page {i}" for i in range(5)}
        finding = cit.find_comparison_content_gap(page_titles)[0]
        self.assertEqual(finding.validate(), [])


if __name__ == "__main__":
    unittest.main()
