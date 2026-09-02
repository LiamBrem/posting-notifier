"""
Tests sources/common.py's URL parsing helpers — extract_ats_ref is what
lets the backup tier recognize "this repo row is actually the same
Greenhouse/Lever/Ashby/SmartRecruiters job Tier 1 already has," including
the gh_jid-on-a-custom-domain case (Stripe, Optiver, Roblox, ...) found
during development.
"""
import unittest

from sources.common import extract_ats_ref, clean_url, parse_age_days


class TestExtractAtsRef(unittest.TestCase):
    def test_greenhouse_direct_url(self):
        self.assertEqual(
            extract_ats_ref("https://job-boards.greenhouse.io/acme/jobs/12345"),
            ("greenhouse", "12345"),
        )

    def test_greenhouse_legacy_boards_subdomain(self):
        self.assertEqual(
            extract_ats_ref("https://boards.greenhouse.io/acme/jobs/12345"),
            ("greenhouse", "12345"),
        )

    def test_greenhouse_gh_jid_on_custom_domain(self):
        # e.g. Stripe: https://stripe.com/jobs/search?gh_jid=8128744
        self.assertEqual(
            extract_ats_ref("https://stripe.com/jobs/search?gh_jid=8128744"),
            ("greenhouse", "8128744"),
        )

    def test_lever_url(self):
        self.assertEqual(
            extract_ats_ref("https://jobs.lever.co/acme/2193db3f-77c5-43b8-b030-8f92c9882bf1"),
            ("lever", "2193db3f-77c5-43b8-b030-8f92c9882bf1"),
        )

    def test_ashby_url(self):
        self.assertEqual(
            extract_ats_ref("https://jobs.ashbyhq.com/acme/1fc309c8-da20-4ff2-84c7-8b863ece2b0a"),
            ("ashby", "1fc309c8-da20-4ff2-84c7-8b863ece2b0a"),
        )

    def test_smartrecruiters_url(self):
        self.assertEqual(
            extract_ats_ref("https://jobs.smartrecruiters.com/Acme/743999708013815"),
            ("smartrecruiters", "743999708013815"),
        )

    def test_unrecognized_url_returns_none(self):
        self.assertIsNone(extract_ats_ref("https://www.linkedin.com/jobs/view/4431835005"))

    def test_unrecognized_custom_site_returns_none(self):
        self.assertIsNone(extract_ats_ref("https://acme.applytojob.com/apply/xyz"))


class TestCleanUrl(unittest.TestCase):
    def test_strips_tracking_params(self):
        cleaned = clean_url("https://job-boards.greenhouse.io/acme/jobs/1?utm_source=Simplify&ref=Simplify")
        self.assertNotIn("utm_source", cleaned)
        self.assertNotIn("ref=", cleaned)

    def test_preserves_meaningful_params(self):
        cleaned = clean_url("https://stripe.com/jobs/search?gh_jid=8128744&utm_source=Simplify")
        self.assertIn("gh_jid=8128744", cleaned)
        self.assertNotIn("utm_source", cleaned)


class TestParseAgeDays(unittest.TestCase):
    def test_days(self):
        self.assertEqual(parse_age_days("0d"), 0)
        self.assertEqual(parse_age_days("12d"), 12)

    def test_months(self):
        self.assertEqual(parse_age_days("1mo"), 30)
        self.assertEqual(parse_age_days("2mo"), 60)

    def test_years(self):
        self.assertEqual(parse_age_days("1y"), 365)

    def test_unparseable_returns_none(self):
        self.assertIsNone(parse_age_days(""))
        self.assertIsNone(parse_age_days(None))
        self.assertIsNone(parse_age_days("garbage"))


if __name__ == "__main__":
    unittest.main()
