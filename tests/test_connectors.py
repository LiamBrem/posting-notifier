"""
Tests each Tier-1 ATS connector against a synthetic API response shaped
exactly like the real one (verified against live Greenhouse/Lever/Ashby/
SmartRecruiters responses during development), with requests.get mocked
out so these run offline and deterministically.

Each fixture response bundles one genuine match plus every kind of decoy
that should NOT survive filters.matches() + filters.is_recent(): an
intern posting, a senior posting, a non-US posting, and a stale (>5d old)
posting that is otherwise a perfect match. The "nothing slips through"
guarantee this suite gives you: fetch -> normalize -> filter end-to-end,
for real response shapes, catches both a parsing bug (wrong field name)
and a filtering bug (regex gap) in one run.
"""
import unittest
from unittest.mock import patch, MagicMock

import filters
from connectors import greenhouse, lever, ashby, smartrecruiters
from tests.fixtures import iso_days_ago, epoch_ms_days_ago, RECENT_DAYS, STALE_DAYS


def _mock_response(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _assert_end_to_end(testcase, jobs):
    """Given the connector's normalized job list, assert exactly the
    genuine/recent/US/SWE/new-grad posting survives filters."""
    survivors = [j for j in jobs if filters.matches(j) and filters.is_recent(j.get("posted_at"))]
    testcase.assertEqual(
        len(survivors), 1,
        f"expected exactly 1 survivor, got {len(survivors)}: {[s['title'] for s in survivors]}",
    )
    testcase.assertEqual(survivors[0]["title"], "Software Engineer, New Grad")
    testcase.assertEqual(survivors[0]["location"], "New York, NY")


class TestGreenhouseConnector(unittest.TestCase):
    @patch("connectors.greenhouse.requests.get")
    def test_fetch_and_filter_end_to_end(self, mock_get):
        mock_get.return_value = _mock_response({
            "jobs": [
                {
                    "id": 1, "title": "Software Engineer, New Grad",
                    "location": {"name": "New York, NY"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                    "first_published": iso_days_ago(RECENT_DAYS),
                    "company_name": "Acme",
                },
                {
                    "id": 2, "title": "Software Engineer Intern",
                    "location": {"name": "New York, NY"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/2",
                    "first_published": iso_days_ago(RECENT_DAYS),
                    "company_name": "Acme",
                },
                {
                    "id": 3, "title": "Senior Software Engineer, New Grad",
                    "location": {"name": "New York, NY"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/3",
                    "first_published": iso_days_ago(RECENT_DAYS),
                    "company_name": "Acme",
                },
                {
                    "id": 4, "title": "Software Engineer, New Grad",
                    "location": {"name": "London, UK"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/4",
                    "first_published": iso_days_ago(RECENT_DAYS),
                    "company_name": "Acme",
                },
                {
                    "id": 5, "title": "Software Engineer, New Grad",
                    "location": {"name": "New York, NY"},
                    "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/5",
                    "first_published": iso_days_ago(STALE_DAYS),
                    "company_name": "Acme",
                },
            ]
        })
        jobs = greenhouse.fetch("acme")
        self.assertEqual(len(jobs), 5)
        _assert_end_to_end(self, jobs)


class TestLeverConnector(unittest.TestCase):
    @patch("connectors.lever.requests.get")
    def test_fetch_and_filter_end_to_end(self, mock_get):
        def posting(id_, title, location, days_ago):
            return {
                "id": id_, "text": title,
                "categories": {"location": location, "allLocations": [location]},
                "hostedUrl": f"https://jobs.lever.co/acme/{id_}",
                "createdAt": epoch_ms_days_ago(days_ago),
            }

        mock_get.return_value = _mock_response([
            posting("a1", "Software Engineer, New Grad", "New York, NY", RECENT_DAYS),
            posting("a2", "Software Engineer Intern", "New York, NY", RECENT_DAYS),
            posting("a3", "Senior Software Engineer, New Grad", "New York, NY", RECENT_DAYS),
            posting("a4", "Software Engineer, New Grad", "London, UK", RECENT_DAYS),
            posting("a5", "Software Engineer, New Grad", "New York, NY", STALE_DAYS),
        ])
        jobs = lever.fetch("acme")
        self.assertEqual(len(jobs), 5)
        _assert_end_to_end(self, jobs)


class TestAshbyConnector(unittest.TestCase):
    @patch("connectors.ashby.requests.get")
    def test_fetch_and_filter_end_to_end(self, mock_get):
        def posting(id_, title, location, days_ago):
            return {
                "id": id_, "title": title, "location": location,
                "secondaryLocations": [],
                "jobUrl": f"https://jobs.ashbyhq.com/acme/{id_}",
                "publishedAt": iso_days_ago(days_ago),
            }

        mock_get.return_value = _mock_response({"jobs": [
            posting("b1", "Software Engineer, New Grad", "New York, NY", RECENT_DAYS),
            posting("b2", "Software Engineer Intern", "New York, NY", RECENT_DAYS),
            posting("b3", "Senior Software Engineer, New Grad", "New York, NY", RECENT_DAYS),
            posting("b4", "Software Engineer, New Grad", "London, UK", RECENT_DAYS),
            posting("b5", "Software Engineer, New Grad", "New York, NY", STALE_DAYS),
        ]})
        jobs = ashby.fetch("acme")
        self.assertEqual(len(jobs), 5)
        _assert_end_to_end(self, jobs)


class TestSmartRecruitersConnector(unittest.TestCase):
    @patch("connectors.smartrecruiters.requests.get")
    def test_fetch_and_filter_end_to_end(self, mock_get):
        def posting(id_, title, city, region, country, days_ago):
            return {
                "id": id_, "name": title,
                "company": {"identifier": "Acme"},
                "location": {"city": city, "region": region, "country": country,
                             "fullLocation": f"{city}, {region}, {country}"},
                "releasedDate": iso_days_ago(days_ago),
            }

        page = {
            "totalFound": 5,
            "content": [
                posting("c1", "Software Engineer, New Grad", "New York", "NY", "us", RECENT_DAYS),
                posting("c2", "Software Engineer Intern", "New York", "NY", "us", RECENT_DAYS),
                posting("c3", "Senior Software Engineer, New Grad", "New York", "NY", "us", RECENT_DAYS),
                posting("c4", "Software Engineer, New Grad", "London", "", "uk", RECENT_DAYS),
                posting("c5", "Software Engineer, New Grad", "New York", "NY", "us", STALE_DAYS),
            ],
        }
        mock_get.return_value = _mock_response(page)
        jobs = smartrecruiters.fetch("acme")
        self.assertEqual(len(jobs), 5)
        # SmartRecruiters builds location from fullLocation, e.g.
        # "New York, NY, us" — is_us_location must still catch that.
        survivors = [j for j in jobs if filters.matches(j) and filters.is_recent(j.get("posted_at"))]
        self.assertEqual(len(survivors), 1)
        self.assertEqual(survivors[0]["title"], "Software Engineer, New Grad")


if __name__ == "__main__":
    unittest.main()
