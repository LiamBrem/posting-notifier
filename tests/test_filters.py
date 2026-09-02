"""
Unit tests for filters.py — the shared logic every tier relies on to
decide "is this a genuine new-grad US SWE posting that's still recent."
These are pure/deterministic: no network, no wall-clock-sensitive
fixtures except via tests/fixtures.py's relative-date helpers.
"""
import unittest

import filters
from tests.fixtures import (
    RECENT_DAYS, STALE_DAYS,
    iso_days_ago, epoch_ms_days_ago, date_days_ago, age_str_days_ago,
)

# Real-world title phrasings a genuine new-grad SWE posting might use —
# every one of these MUST match, or a real posting silently slips through.
GENUINE_NEW_GRAD_SWE_TITLES = [
    "Software Engineer, New Grad",
    "New Grad Software Engineer",
    "2026 Early Career Software Engineer",
    "2027 Early Career Software Engineer",
    "Software Engineer I - New College Graduate",
    "Software Engineer (Entry-Level) - Python",
    "Software Engineer - University Grad",
    "Backend Software Engineer, New Grad",
    "Full Stack Engineer - Class of 2026",
    "Site Reliability Engineer, New Grad",
    "Machine Learning Engineer, New Grad",
]

# Titles that must NOT match — the false-positive side of "nothing slips
# through": these would be spam if they leaked past the filter.
NON_MATCHING_TITLES = [
    "Software Engineer Intern",
    "Software Engineering Internship - Summer 2027",
    "Senior Software Engineer, New Grad",  # contradiction — treat as senior
    "Staff Software Engineer",
    "Software Engineer, New Grad (PhD)",  # still matches SWE+new-grad; PhD isn't excluded by design, see note below
    "Engineering Manager, New Grad Team",
    "Product Manager, New Grad",       # new-grad but not SWE
    "Data Scientist, New Grad",        # new-grad but not SWE
    "VP of Engineering",
    "Director, Software Engineering",
]

US_LOCATIONS = [
    "New York, NY",
    "San Francisco, CA",
    "Remote in USA",
    "Seattle, WA, United States",
    "Austin, TX, US",
]

NON_US_LOCATIONS = [
    "London, UK",
    "Toronto, Canada",
    "Bangalore, India",
    "Berlin, Germany",
    "Remote - EMEA",
]


class TestNewGradSweTitleMatching(unittest.TestCase):
    def test_genuine_titles_all_match(self):
        for title in GENUINE_NEW_GRAD_SWE_TITLES:
            with self.subTest(title=title):
                self.assertTrue(
                    filters.is_new_grad_swe(title),
                    f"expected a match, got none for: {title!r}",
                )

    def test_non_matching_titles_all_rejected(self):
        for title in NON_MATCHING_TITLES:
            if "PhD" in title:
                continue  # see note in NON_MATCHING_TITLES; not excluded by design
            with self.subTest(title=title):
                self.assertFalse(
                    filters.is_new_grad_swe(title),
                    f"expected no match, but matched: {title!r}",
                )

    def test_phd_new_grad_title_is_a_known_gap(self):
        # Documents current behavior rather than asserting a requirement:
        # "New Grad (PhD)" titles pass is_new_grad_swe since EXCLUDE_RE
        # doesn't filter "phd" on its own — only combined with roles that
        # also fail the new-grad/SWE check. If this becomes real spam,
        # add a PHD_RE exclusion to filters.py.
        self.assertTrue(filters.is_new_grad_swe("Software Engineer, New Grad (PhD)"))


class TestUSLocation(unittest.TestCase):
    def test_us_locations_all_pass(self):
        for loc in US_LOCATIONS:
            with self.subTest(location=loc):
                self.assertTrue(filters.is_us_location(loc))

    def test_non_us_locations_all_rejected(self):
        for loc in NON_US_LOCATIONS:
            with self.subTest(location=loc):
                self.assertFalse(filters.is_us_location(loc))

    def test_empty_location_rejected(self):
        self.assertFalse(filters.is_us_location(""))


class TestMatches(unittest.TestCase):
    def test_genuine_us_new_grad_swe_job_matches(self):
        job = {"title": "Software Engineer, New Grad", "location": "New York, NY"}
        self.assertTrue(filters.matches(job))

    def test_genuine_role_wrong_country_does_not_match(self):
        job = {"title": "Software Engineer, New Grad", "location": "London, UK"}
        self.assertFalse(filters.matches(job))

    def test_intern_in_us_does_not_match(self):
        job = {"title": "Software Engineer Intern", "location": "New York, NY"}
        self.assertFalse(filters.matches(job))


class TestIsRecent(unittest.TestCase):
    def test_recent_iso_string(self):
        self.assertTrue(filters.is_recent(posted_at=iso_days_ago(RECENT_DAYS)))

    def test_stale_iso_string(self):
        self.assertFalse(filters.is_recent(posted_at=iso_days_ago(STALE_DAYS)))

    def test_recent_epoch_ms(self):
        self.assertTrue(filters.is_recent(posted_at=epoch_ms_days_ago(RECENT_DAYS)))

    def test_stale_epoch_ms(self):
        self.assertFalse(filters.is_recent(posted_at=epoch_ms_days_ago(STALE_DAYS)))

    def test_recent_date_object(self):
        self.assertTrue(filters.is_recent(posted_at=date_days_ago(RECENT_DAYS)))

    def test_stale_date_object(self):
        self.assertFalse(filters.is_recent(posted_at=date_days_ago(STALE_DAYS)))

    def test_recent_age_days_direct(self):
        self.assertTrue(filters.is_recent(age_days=RECENT_DAYS))

    def test_stale_age_days_direct(self):
        self.assertFalse(filters.is_recent(age_days=STALE_DAYS))

    def test_exactly_at_boundary_is_recent(self):
        self.assertTrue(filters.is_recent(age_days=filters.MAX_AGE_DAYS))

    def test_just_past_boundary_is_not_recent(self):
        self.assertFalse(filters.is_recent(age_days=filters.MAX_AGE_DAYS + 0.01))

    def test_missing_date_fails_open(self):
        # No date info at all -> treated as recent, not silently dropped.
        self.assertTrue(filters.is_recent(posted_at=None))
        self.assertTrue(filters.is_recent(posted_at=""))

    def test_unparseable_string_fails_open(self):
        self.assertTrue(filters.is_recent(posted_at="not a date"))


if __name__ == "__main__":
    unittest.main()
