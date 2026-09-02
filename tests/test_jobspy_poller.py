"""
Tests jobspy_poller.py against a synthetic pandas DataFrame shaped like
scrape_jobs()'s real return value (verified against a live call during
development: columns include company/title/location/job_url/date_posted/
site), with jobspy.scrape_jobs mocked so these run offline.

Covers the two things that are unique to this tier and don't exist in the
ATS connectors: company-name matching (rejecting results that just
mention the target company, e.g. a staffing firm's listing) and NaN/NaT
handling in the date_posted column.
"""
import unittest
from unittest.mock import patch
import tempfile
import os

import pandas as pd

import jobspy_poller as jp
from tests.fixtures import date_days_ago, RECENT_DAYS, STALE_DAYS


def _df(rows):
    return pd.DataFrame(rows)


class TestCompanyMatches(unittest.TestCase):
    def test_exact_and_substring_matches(self):
        self.assertTrue(jp.company_matches("Acme", "Acme"))
        self.assertTrue(jp.company_matches("Acme Corporation", "Acme"))
        self.assertTrue(jp.company_matches("Acme", "Acme Corporation"))

    def test_unrelated_company_rejected(self):
        self.assertFalse(jp.company_matches("Some Staffing Firm", "Acme"))

    def test_nan_company_field_rejected_not_crashed(self):
        self.assertFalse(jp.company_matches(float("nan"), "Acme"))

    def test_none_company_field_rejected(self):
        self.assertFalse(jp.company_matches(None, "Acme"))

    def test_alias_matches(self):
        self.assertTrue(jp.company_matches("TikTok", "ByteDance"))
        self.assertTrue(jp.company_matches("TikTok Inc.", "ByteDance"))
        self.assertFalse(jp.company_matches("Meta", "ByteDance"))


class TestCleanDate(unittest.TestCase):
    def test_real_date_passes_through(self):
        d = date_days_ago(RECENT_DAYS)
        self.assertEqual(jp.clean_date(d), d)

    def test_nan_becomes_none(self):
        self.assertIsNone(jp.clean_date(float("nan")))

    def test_nat_becomes_none(self):
        self.assertIsNone(jp.clean_date(pd.NaT))

    def test_none_stays_none(self):
        self.assertIsNone(jp.clean_date(None))


class TestCollectMatchesEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.seen_path = os.path.join(self.tmpdir, "seen_jobspy.json")
        self.companies_path = os.path.join(self.tmpdir, "companies.json")
        with open(self.companies_path, "w") as f:
            f.write('["Acme"]')

        self._orig_seen_path = jp.SEEN_PATH
        self._orig_companies_path = jp.COMPANIES_PATH
        jp.SEEN_PATH = self.seen_path
        jp.COMPANIES_PATH = self.companies_path

        self._sleep_patcher = patch("jobspy_poller.time.sleep")
        self._sleep_patcher.start()

    def tearDown(self):
        jp.SEEN_PATH = self._orig_seen_path
        jp.COMPANIES_PATH = self._orig_companies_path
        self._sleep_patcher.stop()

    @patch("jobspy_poller.scrape_jobs")
    def test_bootstrap_run_finds_nothing_to_notify(self, mock_scrape):
        mock_scrape.return_value = _df([
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "New York, NY", "job_url": "https://indeed.com/1",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},
        ])
        matches = jp.collect_matches()
        self.assertEqual(matches, [])  # first run bootstraps silently
        self.assertTrue(os.path.exists(self.seen_path))

    @patch("jobspy_poller.scrape_jobs")
    def test_second_run_catches_genuinely_new_relevant_posting(self, mock_scrape):
        # seed as if a prior run already saw job 1
        import json
        with open(self.seen_path, "w") as f:
            json.dump({"Acme": ["https://indeed.com/1"]}, f)

        mock_scrape.return_value = _df([
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "New York, NY", "job_url": "https://indeed.com/1",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},  # already seen
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "New York, NY", "job_url": "https://indeed.com/2",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},  # new + matches
            {"company": "Acme", "title": "Software Engineer Intern",
             "location": "New York, NY", "job_url": "https://indeed.com/3",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},  # new but intern
            {"company": "Some Staffing Firm", "title": "Software Engineer, New Grad (Acme client)",
             "location": "New York, NY", "job_url": "https://indeed.com/4",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},  # wrong company
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "New York, NY", "job_url": "https://indeed.com/5",
             "date_posted": date_days_ago(STALE_DAYS), "site": "indeed"},  # new but stale
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "London, UK", "job_url": "https://indeed.com/6",
             "date_posted": date_days_ago(RECENT_DAYS), "site": "indeed"},  # new but non-US
        ])
        matches = jp.collect_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["url"], "https://indeed.com/2")
        self.assertEqual(matches[0]["source"], "jobspy/indeed")


if __name__ == "__main__":
    unittest.main()
