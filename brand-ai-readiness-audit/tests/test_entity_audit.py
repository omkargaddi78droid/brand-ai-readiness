"""Unit tests for entity-audit (ENT-01/02/03/04/09).

Each detector is tested as a positive/negative pair, per project convention.
The empty-canonical regression test documents a bug caught during
development: a naive `attr_dict.get("href")` truthiness check silently
folded `href=""` into "no canonical tag" instead of the more specific
"canonical tag present but empty" — found by sweeping the fixture corpus
against the code before writing any formal test, same discipline as the
previous two cycles.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "shared"))

from finding_contract import Finding  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "check_entity", REPO_ROOT / "skills/entity-audit/scripts/check_entity.py"
)
ent = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ent)


def ld(obj_json: str) -> str:
    return f'<script type="application/ld+json">{obj_json}</script>'


class ParsePageTests(unittest.TestCase):
    def test_json_ld_block_is_parsed(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme"}'))
        self.assertEqual(errors, [])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Acme")

    def test_invalid_json_is_reported_as_an_error_not_a_crash(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Organization",,,}'))
        self.assertEqual(nodes, [])
        self.assertEqual(len(errors), 1)

    def test_at_graph_array_is_flattened(self):
        html = ld('{"@graph":[{"@type":"Organization","name":"A"},{"@type":"WebSite","name":"A"}]}')
        nodes, errors, _, _ = ent.parse_page(html)
        self.assertEqual(errors, [])
        self.assertEqual({n["@type"] for n in nodes}, {"Organization", "WebSite"})

    def test_top_level_array_of_objects_is_flattened(self):
        html = ld('[{"@type":"Organization","name":"A"},{"@type":"Product","name":"P"}]')
        nodes, _, _, _ = ent.parse_page(html)
        self.assertEqual(len(nodes), 2)

    def test_script_and_style_do_not_pollute_visible_text(self):
        html = "<style>.x{color:red}</style><script>var x=1;</script><p>Hello.</p>"
        _, _, _, text = ent.parse_page(html)
        self.assertEqual(text, "Hello.")

    def test_canonical_href_is_extracted(self):
        _, _, hrefs, _ = ent.parse_page('<link rel="canonical" href="https://example.com/">')
        self.assertEqual(hrefs, ["https://example.com/"])

    def test_canonical_among_multiple_rel_values_is_still_found(self):
        _, _, hrefs, _ = ent.parse_page('<link rel="alternate canonical" href="https://example.com/">')
        self.assertEqual(hrefs, ["https://example.com/"])

    def test_self_closed_canonical_link_is_still_found(self):
        """Regression, found live against apple.com: HTMLParser routes a
        self-closed tag (`<link ... />`) through handle_startendtag, not
        handle_starttag. Overriding handle_startendtag without delegating to
        handle_starttag silently dropped canonical-link extraction for every
        self-closed <link> — reported as 'no canonical' on a page that had
        one."""
        _, _, hrefs, _ = ent.parse_page('<link rel="canonical" href="https://example.com/page" />')
        self.assertEqual(hrefs, ["https://example.com/page"])

    def test_self_closed_json_ld_script_does_not_corrupt_later_parsing(self):
        """A self-closed <script/> is invalid HTML and never emitted by real
        pages, but the parser must not get stuck mid-skip if one appears."""
        html = '<script type="application/ld+json" />' + ld('{"@type":"Organization","name":"Acme"}')
        nodes, errors, _, text = ent.parse_page(html)
        self.assertEqual(errors, [])
        self.assertTrue(any(n.get("name") == "Acme" for n in nodes))

    def test_empty_canonical_href_is_captured_not_dropped(self):
        """Regression: a naive truthiness check on href silently dropped an
        empty-href canonical tag entirely, making it indistinguishable from
        no canonical tag at all."""
        _, _, hrefs, _ = ent.parse_page('<link rel="canonical" href="">')
        self.assertEqual(hrefs, [""])


class SchemaValidityTests(unittest.TestCase):
    def test_no_json_ld_at_all_fires_missing_finding(self):
        nodes, errors, _, _ = ent.parse_page("<p>Hello.</p>")
        findings, unknowns = ent.find_schema_issues(nodes, errors)
        self.assertEqual([f.id for f in findings], ["ENT-01-no-structured-data"])
        self.assertEqual(unknowns, [])

    def test_malformed_json_ld_fires_and_does_not_also_claim_no_data(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Organization",,,}'))
        findings, _ = ent.find_schema_issues(nodes, errors)
        self.assertEqual([f.id for f in findings], ["ENT-01-malformed-json-ld"])

    def test_organization_with_name_and_url_is_clean(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme","url":"https://acme.com"}'))
        findings, _ = ent.find_schema_issues(nodes, errors)
        self.assertEqual(findings, [])

    def test_organization_missing_url_is_flagged(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme"}'))
        findings, _ = ent.find_schema_issues(nodes, errors)
        ids = [f.id for f in findings]
        self.assertIn("ENT-01-organization-missing-fields", ids)

    def test_only_product_type_present_flags_no_identity_type(self):
        nodes, errors, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget"}'))
        findings, _ = ent.find_schema_issues(nodes, errors)
        self.assertIn("ENT-01-no-identity-type", [f.id for f in findings])

    def test_organization_present_suppresses_no_identity_type(self):
        nodes, errors, _, _ = ent.parse_page(
            ld('{"@type":"Organization","name":"Acme","url":"https://acme.com"}')
        )
        findings, _ = ent.find_schema_issues(nodes, errors)
        self.assertNotIn("ENT-01-no-identity-type", [f.id for f in findings])


class KnowledgeGraphTests(unittest.TestCase):
    def test_no_organization_node_means_ent02_stays_silent(self):
        """If there is no Organization at all, ENT-01 already reports the
        absence; a second 'no sameAs either' finding would be redundant
        noise for the same root cause."""
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget"}'))
        self.assertEqual(ent.find_knowledge_graph_gaps(nodes), [])

    def test_organization_with_no_sameas_is_flagged(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme","url":"https://acme.com"}'))
        findings = ent.find_knowledge_graph_gaps(nodes)
        self.assertEqual([f.id for f in findings], ["ENT-02-no-knowledge-graph-link"])

    def test_sameas_to_an_authority_domain_suppresses_the_finding(self):
        html = ld(
            '{"@type":"Organization","name":"Acme","sameAs":["https://www.wikidata.org/wiki/Q1"]}'
        )
        nodes, _, _, _ = ent.parse_page(html)
        self.assertEqual(ent.find_knowledge_graph_gaps(nodes), [])

    def test_sameas_to_an_unrecognised_domain_still_fires(self):
        html = ld('{"@type":"Organization","name":"Acme","sameAs":["https://example-blog.example.net/about"]}')
        nodes, _, _, _ = ent.parse_page(html)
        self.assertEqual(len(ent.find_knowledge_graph_gaps(nodes)), 1)

    def test_sameas_as_a_single_string_not_a_list_is_handled(self):
        html = ld('{"@type":"Organization","name":"Acme","sameAs":"https://www.linkedin.com/company/acme"}')
        nodes, _, _, _ = ent.parse_page(html)
        self.assertEqual(ent.find_knowledge_graph_gaps(nodes), [])


class MarkupTextAgreementTests(unittest.TestCase):
    def test_no_aggregate_rating_in_markup_stays_silent(self):
        _, _, _, text = ent.parse_page("<p>Rated 3.2 out of 5.</p>")
        self.assertEqual(ent.find_markup_text_disagreement([], text), [])

    def test_matching_rating_is_clean(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.8"}}') + "<p>Rated 4.8 out of 5.</p>"
        nodes, _, _, text = ent.parse_page(html)
        self.assertEqual(ent.find_markup_text_disagreement(nodes, text), [])

    def test_disagreeing_rating_fires(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.8"}}') + "<p>Rated 3.2 out of 5.</p>"
        nodes, _, _, text = ent.parse_page(html)
        findings = ent.find_markup_text_disagreement(nodes, text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].structured_evidence["markup_value"], 4.8)

    def test_no_rating_claim_in_visible_text_stays_silent(self):
        """The markup has a rating; the page never states one in prose.
        Nothing to disagree with, so this must not guess."""
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.8"}}') + "<p>Buy now.</p>"
        nodes, _, _, text = ent.parse_page(html)
        self.assertEqual(ent.find_markup_text_disagreement(nodes, text), [])

    def test_within_tolerance_rounding_does_not_fire(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.8"}}') + "<p>Rated 4.9 out of 5.</p>"
        nodes, _, _, text = ent.parse_page(html)
        self.assertEqual(ent.find_markup_text_disagreement(nodes, text), [])

    def test_rated_n_phrasing_is_also_recognised(self):
        html = ld('{"@type":"Product","aggregateRating":{"ratingValue":"4.8"}}') + "<p>Customers rated 3.0.</p>"
        nodes, _, _, text = ent.parse_page(html)
        self.assertEqual(len(ent.find_markup_text_disagreement(nodes, text)), 1)


class CanonicalTests(unittest.TestCase):
    def test_no_canonical_at_all_is_flagged(self):
        findings = ent.find_canonical_issues([], "https://example.com/")
        self.assertEqual([f.id for f in findings], ["ENT-04-canonical-missing"])

    def test_a_single_self_referencing_canonical_is_clean(self):
        findings = ent.find_canonical_issues(["https://example.com/page"], "https://example.com/page")
        self.assertEqual(findings, [])

    def test_two_different_canonicals_is_a_conflict(self):
        findings = ent.find_canonical_issues(["https://example.com/a", "https://example.com/b"], "https://example.com/a")
        self.assertEqual([f.id for f in findings], ["ENT-04-canonical-conflicting"])

    def test_the_same_canonical_repeated_is_not_a_conflict(self):
        findings = ent.find_canonical_issues(["https://example.com/a", "https://example.com/a"], "https://example.com/a")
        self.assertEqual(findings, [])

    def test_empty_href_is_a_distinct_finding_from_missing(self):
        findings = ent.find_canonical_issues([""], "https://example.com/")
        self.assertEqual([f.id for f in findings], ["ENT-04-canonical-empty"])

    def test_off_domain_canonical_is_flagged(self):
        findings = ent.find_canonical_issues(["https://other.example/page"], "https://example.com/page")
        self.assertEqual([f.id for f in findings], ["ENT-04-canonical-off-domain"])
        self.assertEqual(findings[0].confidence, "medium")

    def test_relative_canonical_resolved_against_page_url_is_not_off_domain(self):
        findings = ent.find_canonical_issues(["/page"], "https://example.com/other")
        self.assertEqual(findings, [])

    def test_www_prefix_alone_is_not_off_domain(self):
        findings = ent.find_canonical_issues(["https://www.example.com/page"], "https://example.com/page")
        self.assertEqual(findings, [])

    def test_bare_domain_canonical_from_www_page_is_not_off_domain(self):
        findings = ent.find_canonical_issues(["https://example.com/page"], "https://www.example.com/page")
        self.assertEqual(findings, [])

    def test_no_page_url_skips_the_off_domain_check_without_crashing(self):
        findings = ent.find_canonical_issues(["https://other.example/page"], None)
        self.assertEqual(findings, [])


class SitemapUrlForkTests(unittest.TestCase):
    """ENT-04's crawl-wide half, sitemap-scoped rather than a full crawl:
    a slug-variant/trailing-slash fork is detectable from the sitemap's own
    declared URL list alone — two distinct listed URLs that are the same
    resource once trailing-slash/www/scheme differences are normalised."""

    def test_a_trailing_slash_fork_is_flagged(self):
        urls = ["https://example.com/blog/post", "https://example.com/blog/post/"]
        findings = ent.find_sitemap_url_forks(urls)
        self.assertEqual([f.id for f in findings], ["ENT-04-sitemap-url-fork"])

    def test_a_www_prefix_fork_is_flagged(self):
        urls = ["https://example.com/pricing", "https://www.example.com/pricing"]
        findings = ent.find_sitemap_url_forks(urls)
        self.assertEqual([f.id for f in findings], ["ENT-04-sitemap-url-fork"])

    def test_an_http_https_fork_is_flagged(self):
        urls = ["http://example.com/about", "https://example.com/about"]
        findings = ent.find_sitemap_url_forks(urls)
        self.assertEqual([f.id for f in findings], ["ENT-04-sitemap-url-fork"])

    def test_two_genuinely_distinct_pages_are_not_a_fork(self):
        urls = ["https://example.com/blog/post-1", "https://example.com/blog/post-2"]
        self.assertEqual(ent.find_sitemap_url_forks(urls), [])

    def test_the_same_url_listed_twice_verbatim_is_not_a_fork(self):
        urls = ["https://example.com/pricing", "https://example.com/pricing"]
        self.assertEqual(ent.find_sitemap_url_forks(urls), [])

    def test_an_empty_url_list_produces_nothing(self):
        self.assertEqual(ent.find_sitemap_url_forks([]), [])

    def test_multiple_fork_groups_are_named_in_one_finding(self):
        urls = [
            "https://example.com/blog/post-1",
            "https://example.com/blog/post-1/",
            "https://example.com/about",
            "https://www.example.com/about",
        ]
        findings = ent.find_sitemap_url_forks(urls)
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0].structured_evidence["fork_groups"]), 2)


class PageAttributionTests(unittest.TestCase):
    def test_page_url_is_stamped_into_evidence_and_structured_evidence(self):
        out = ent.audit_html("example.com", "<p>Hi.</p>", page_url="https://example.com/about")
        finding = out["findings"][0]
        self.assertTrue(finding["evidence"].startswith("On https://example.com/about:"))
        self.assertEqual(finding["structured_evidence"]["page_url"], "https://example.com/about")


class ContractComplianceTests(unittest.TestCase):
    def test_every_emitted_finding_satisfies_the_contract(self):
        html = (
            ld('{"@type":"Product","name":"Widget","aggregateRating":{"ratingValue":"4.8"}}')
            + '<link rel="canonical" href="https://other.example/page">'
            + "<p>Rated 3.2 out of 5.</p>"
        )
        out = ent.audit_html("example.com", html, page_url="https://example.com/page")
        self.assertGreaterEqual(len(out["findings"]), 3)
        for finding_dict in out["findings"]:
            restored = Finding.from_dict(finding_dict)
            self.assertEqual(restored.validate(), [])
            self.assertEqual(restored.owner_skill, "entity-audit")
            self.assertEqual(restored.gate, 3)
            self.assertEqual(restored.category, "discoverability")

    def test_evaluation_is_deterministic(self):
        html = ld('{"@type":"Organization","name":"Acme"}')
        first = ent.audit_html("example.com", html)
        second = ent.audit_html("example.com", html)
        self.assertEqual(first, second)


class CategoryLabelExtractionTests(unittest.TestCase):
    def test_product_category_string_is_extracted(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget","category":"Laptops"}'))
        labels = ent.extract_category_labels(nodes)
        self.assertEqual(labels, [("Laptops", "product_category")])

    def test_article_section_is_extracted(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Article","articleSection":"Politics"}'))
        labels = ent.extract_category_labels(nodes)
        self.assertEqual(labels, [("Politics", "article_section")])

    def test_breadcrumb_list_uses_the_deepest_item(self):
        breadcrumb = (
            '{"@type":"BreadcrumbList","itemListElement":['
            '{"@type":"ListItem","position":1,"name":"Home","item":"https://example.com/"},'
            '{"@type":"ListItem","position":2,"name":"Electronics","item":"https://example.com/e"},'
            '{"@type":"ListItem","position":3,"name":"Laptops","item":"https://example.com/e/l"}'
            "]}"
        )
        nodes, _, _, _ = ent.parse_page(ld(breadcrumb))
        labels = ent.extract_category_labels(nodes)
        self.assertEqual(labels, [("Laptops", "breadcrumb")])

    def test_breadcrumb_item_as_nested_object_is_handled(self):
        breadcrumb = (
            '{"@type":"BreadcrumbList","itemListElement":['
            '{"@type":"ListItem","position":1,"item":{"name":"Home"}},'
            '{"@type":"ListItem","position":2,"item":{"name":"Laptops"}}'
            "]}"
        )
        nodes, _, _, _ = ent.parse_page(ld(breadcrumb))
        labels = ent.extract_category_labels(nodes)
        self.assertEqual(labels, [("Laptops", "breadcrumb")])

    def test_duplicate_labels_across_sources_are_deduplicated(self):
        html = (
            ld('{"@type":"Product","name":"Widget","category":"Laptops"}')
            + ld(
                '{"@type":"BreadcrumbList","itemListElement":['
                '{"@type":"ListItem","position":1,"name":"Laptops"}]}'
            )
        )
        nodes, _, _, _ = ent.parse_page(html)
        labels = ent.extract_category_labels(nodes)
        self.assertEqual(len(labels), 1)

    def test_no_category_signal_at_all_returns_nothing(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme"}'))
        self.assertEqual(ent.extract_category_labels(nodes), [])


class TaxonomyJudgementCandidateTests(unittest.TestCase):
    """ENT-09. Extraction only — no script verdict, same pattern as
    content-quality-audit's CQ-02/04/09/12."""

    _PLENTY_OF_TEXT = " ".join(["ordinary product description text here"] * 15)

    def test_zero_keyword_overlap_is_a_candidate(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget","category":"Bicycles"}'))
        candidates = ent.find_taxonomy_judgement_candidates(nodes, self._PLENTY_OF_TEXT)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["category_label"], "Bicycles")
        self.assertEqual(candidates[0]["source"], "product_category")

    def test_any_shared_keyword_suppresses_the_candidate(self):
        nodes, _, _, _ = ent.parse_page(
            ld('{"@type":"Product","name":"Widget","category":"Laptops"}')
        )
        text = "This laptop has a fast processor and a bright screen. " * 5
        self.assertEqual(ent.find_taxonomy_judgement_candidates(nodes, text), [])

    def test_a_generic_category_label_is_not_a_candidate(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Article","articleSection":"General"}'))
        self.assertEqual(ent.find_taxonomy_judgement_candidates(nodes, self._PLENTY_OF_TEXT), [])

    def test_too_little_visible_text_is_not_evaluated(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget","category":"Bicycles"}'))
        self.assertEqual(ent.find_taxonomy_judgement_candidates(nodes, "Short page."), [])

    def test_no_category_signal_produces_no_candidates(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Organization","name":"Acme"}'))
        self.assertEqual(ent.find_taxonomy_judgement_candidates(nodes, self._PLENTY_OF_TEXT), [])

    def test_candidate_carries_a_text_excerpt_for_the_agent_to_read(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget","category":"Bicycles"}'))
        candidates = ent.find_taxonomy_judgement_candidates(nodes, self._PLENTY_OF_TEXT)
        self.assertIn("visible_text_excerpt", candidates[0])
        self.assertTrue(candidates[0]["visible_text_excerpt"])


class AgentJudgementRequestTests(unittest.TestCase):
    def test_ent09_is_requested(self):
        nodes, _, _, _ = ent.parse_page(ld('{"@type":"Product","name":"Widget","category":"Bicycles"}'))
        requests = ent.build_agent_judgement_requests(nodes, TaxonomyJudgementCandidateTests._PLENTY_OF_TEXT)
        ids = {r["capability_id"] for r in requests}
        self.assertEqual(ids, {"ENT-09"})

    def test_the_request_points_at_the_rubric(self):
        requests = ent.build_agent_judgement_requests([], "some text")
        self.assertIn("references/entity-judgement-rubric.md", requests[0]["instructions"])

    def test_audit_html_carries_agent_judgement_required(self):
        html = ld('{"@type":"Product","name":"Widget","category":"Bicycles"}') + f"<p>{TaxonomyJudgementCandidateTests._PLENTY_OF_TEXT}</p>"
        out = ent.audit_html("example.com", html)
        self.assertIn("agent_judgement_required", out)
        self.assertEqual(len(out["agent_judgement_required"]), 1)
        self.assertEqual(len(out["agent_judgement_required"][0]["observations"]["candidates"]), 1)


class BrandCollisionCandidateTests(unittest.TestCase):
    def test_a_brand_mention_produces_a_candidate(self):
        pages = [{"url": "https://forum.example/t/1", "text": "I bought an Acme Widget last week and love it."}]
        candidates = ent.find_brand_collision_candidates("Acme Widget", pages)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["url"], "https://forum.example/t/1")
        self.assertIn("Acme Widget", candidates[0]["snippet"])

    def test_no_mention_produces_no_candidate(self):
        pages = [{"url": "https://forum.example/t/1", "text": "Nothing relevant here at all."}]
        self.assertEqual(ent.find_brand_collision_candidates("Acme Widget", pages), [])

    def test_case_insensitive_match_still_counts(self):
        pages = [{"url": "https://forum.example/t/1", "text": "acme widget owners unite."}]
        self.assertEqual(len(ent.find_brand_collision_candidates("Acme Widget", pages)), 1)

    def test_substring_of_a_longer_word_does_not_count(self):
        pages = [{"url": "https://forum.example/t/1", "text": "AcmeWidgetPro is a different product entirely."}]
        self.assertEqual(ent.find_brand_collision_candidates("Acme Widget", pages), [])

    def test_no_pages_produces_no_candidates(self):
        self.assertEqual(ent.find_brand_collision_candidates("Acme Widget", []), [])

    def test_candidates_are_capped(self):
        pages = [{"url": f"https://forum.example/t/{i}", "text": "Acme Widget mentioned here."} for i in range(15)]
        self.assertEqual(len(ent.find_brand_collision_candidates("Acme Widget", pages)), 10)


class LookalikeDomainCandidateTests(unittest.TestCase):
    def test_a_similar_domain_fires(self):
        pages = [{"url": "https://acme-w1dgets.com/", "text": "Official Acme Widgets store, buy now."}]
        candidates = ent.find_lookalike_domain_candidates("acmewidgets.com", pages)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["domain"], "acme-w1dgets.com")

    def test_the_audited_sites_own_domain_is_excluded(self):
        pages = [{"url": "https://acmewidgets.com/reviews", "text": "Our own review page."}]
        self.assertEqual(ent.find_lookalike_domain_candidates("acmewidgets.com", pages), [])

    def test_the_audited_sites_own_subdomain_is_excluded(self):
        # Live-found: meta.discourse.org scored 0.839 similarity against
        # discourse.org and would otherwise have flagged the project's own
        # official community subdomain as a lookalike-domain candidate.
        pages = [{"url": "https://meta.discourse.org/t/1", "text": "Official Discourse community."}]
        self.assertEqual(ent.find_lookalike_domain_candidates("discourse.org", pages), [])

    def test_a_www_prefix_is_not_treated_as_a_lookalike(self):
        pages = [{"url": "https://www.acmewidgets.com/", "text": "Same site, www prefix."}]
        self.assertEqual(ent.find_lookalike_domain_candidates("acmewidgets.com", pages), [])

    def test_an_unrelated_domain_does_not_fire(self):
        pages = [{"url": "https://totally-unrelated-site.com/", "text": "Nothing to do with acme."}]
        self.assertEqual(ent.find_lookalike_domain_candidates("acmewidgets.com", pages), [])

    def test_no_pages_produces_no_candidates(self):
        self.assertEqual(ent.find_lookalike_domain_candidates("acmewidgets.com", []), [])


class OffsiteJudgementRequestTests(unittest.TestCase):
    def test_returns_one_entry_per_capability(self):
        requests = ent.build_offsite_judgement_requests("acmewidgets.com", "Acme Widgets", [])
        ids = [r["capability_id"] for r in requests]
        self.assertEqual(ids, ["ENT-05", "ENT-06"])

    def test_every_entry_points_at_the_rubric(self):
        requests = ent.build_offsite_judgement_requests("acmewidgets.com", "Acme Widgets", [])
        for request in requests:
            self.assertIn("references/entity-judgement-rubric.md", request["instructions"])


class AuditOffsiteTests(unittest.TestCase):
    def test_disallowed_or_unreachable_urls_become_unknown_checks(self):
        # this-host-does-not-exist.invalid never resolves, so is_public_host
        # (and therefore fetch_page_html) refuses it before any network call —
        # the same SSRF/reachability path every other fetch in this file uses.
        out = ent.audit_offsite(
            "acmewidgets.com", "Acme Widgets", ["https://this-host-does-not-exist.invalid/page"]
        )
        self.assertEqual(out["findings"], [])
        self.assertEqual(len(out["unknown_checks"]), 1)
        self.assertIn("this-host-does-not-exist.invalid", out["unknown_checks"][0]["reason"])

    def test_output_always_carries_both_capability_ids(self):
        out = ent.audit_offsite("acmewidgets.com", "Acme Widgets", [])
        self.assertEqual(out["capability_ids"], ent.CAPABILITY_IDS)
        ids = [r["capability_id"] for r in out["agent_judgement_required"]]
        self.assertEqual(ids, ["ENT-05", "ENT-06"])

    def test_no_urls_produces_empty_candidates_not_a_crash(self):
        out = ent.audit_offsite("acmewidgets.com", "Acme Widgets", [])
        for request in out["agent_judgement_required"]:
            self.assertEqual(request["observations"]["candidates"], [])


class RobotsAllowsOffsiteFetchTests(unittest.TestCase):
    def test_an_unreachable_robots_txt_defaults_to_allowed(self):
        # RFC 9309 convention: no reachable robots.txt means unrestricted
        # access. The URL itself may still fail later at the actual fetch
        # step (fetch_page_html's own SSRF/reachability guard) — this check
        # only decides whether robots.txt permits the attempt.
        self.assertTrue(ent.robots_allows_offsite_fetch("https://this-host-does-not-exist.invalid/page"))


class SsrfGuardTests(unittest.TestCase):
    def test_a_loopback_address_is_refused(self):
        self.assertFalse(ent.is_public_host("127.0.0.1"))

    def test_a_private_range_address_is_refused(self):
        self.assertFalse(ent.is_public_host("10.0.0.5"))


if __name__ == "__main__":
    unittest.main()
