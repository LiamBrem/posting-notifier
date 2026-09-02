"""
Tests dedup.py — the shared cross-tier gate that (a) collapses one role
posted at multiple locations into a single notification, and (b) makes
sure a role only ever notifies once even if more than one tier discovers
it. This is the piece that directly addresses "don't get pinged for ones
I've already gotten."
"""
import unittest
from unittest.mock import patch
import tempfile
import os

import dedup


class TestCanonicalKey(unittest.TestCase):
    def test_identical_title_same_key(self):
        self.assertEqual(
            dedup.canonical_key("Acme", "Software Engineer, New Grad"),
            dedup.canonical_key("Acme", "Software Engineer, New Grad"),
        )

    def test_punctuation_insensitive(self):
        self.assertEqual(
            dedup.canonical_key("Acme", "Software Engineer, New Grad"),
            dedup.canonical_key("Acme", "Software Engineer - New Grad"),
        )

    def test_word_order_insensitive(self):
        # Different tiers can report the same real job with reordered
        # wording (Tier 1's exact ATS title vs. Indeed's own listing title)
        self.assertEqual(
            dedup.canonical_key("Acme", "Software Engineer, New Grad"),
            dedup.canonical_key("Acme", "New Grad Software Engineer"),
        )

    def test_case_insensitive(self):
        self.assertEqual(
            dedup.canonical_key("Acme", "Software Engineer"),
            dedup.canonical_key("ACME", "SOFTWARE ENGINEER"),
        )

    def test_different_titles_different_keys(self):
        self.assertNotEqual(
            dedup.canonical_key("Acme", "Backend Software Engineer, New Grad"),
            dedup.canonical_key("Acme", "Frontend Software Engineer, New Grad"),
        )

    def test_different_companies_different_keys(self):
        self.assertNotEqual(
            dedup.canonical_key("Acme", "Software Engineer, New Grad"),
            dedup.canonical_key("Globex", "Software Engineer, New Grad"),
        )


class TestGroupAndNotify(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.notified_path = os.path.join(self.tmpdir, "notified.json")
        self._orig_path = dedup.NOTIFIED_PATH
        dedup.NOTIFIED_PATH = self.notified_path
        self.send_patcher = patch("dedup.notify.send")
        self.mock_send = self.send_patcher.start()

    def tearDown(self):
        dedup.NOTIFIED_PATH = self._orig_path
        self.send_patcher.stop()

    def test_multiple_locations_collapse_to_one_notification(self):
        jobs = [
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "New York, NY", "url": "https://acme.com/1"},
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "Denver, CO", "url": "https://acme.com/2"},
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": "Palo Alto, CA", "url": "https://acme.com/3"},
        ]
        sent = dedup.group_and_notify(jobs)
        self.assertEqual(sent, 1)
        self.mock_send.assert_called_once()
        (payload,), _ = self.mock_send.call_args
        self.assertIn("New York, NY", payload["location"])
        self.assertIn("Denver, CO", payload["location"])
        self.assertIn("Palo Alto, CA", payload["location"])

    def test_second_call_same_role_does_not_renotify(self):
        job = [{"company": "Acme", "title": "Software Engineer, New Grad",
                "location": "New York, NY", "url": "https://acme.com/1"}]
        sent_first = dedup.group_and_notify(job)
        sent_second = dedup.group_and_notify(job)
        self.assertEqual(sent_first, 1)
        self.assertEqual(sent_second, 0)
        self.mock_send.assert_called_once()

    def test_cross_tier_same_role_different_wording_only_notifies_once(self):
        # Simulates Tier 1 catching it first, then a later run handing in
        # the "same" role as reported by a different tier/source with
        # slightly different title wording and a different URL.
        tier1_job = [{"company": "Acme", "title": "Software Engineer, New Grad",
                      "location": "New York, NY", "url": "https://job-boards.greenhouse.io/acme/jobs/1",
                      "source": "tier1"}]
        jobspy_job = [{"company": "Acme", "title": "New Grad Software Engineer",
                       "location": "New York, NY", "url": "https://indeed.com/view/999",
                       "source": "jobspy/indeed"}]
        sent1 = dedup.group_and_notify(tier1_job)
        sent2 = dedup.group_and_notify(jobspy_job)
        self.assertEqual(sent1, 1)
        self.assertEqual(sent2, 0)
        self.mock_send.assert_called_once()

    def test_different_roles_both_notify(self):
        jobs = [
            {"company": "Acme", "title": "Backend Software Engineer, New Grad",
             "location": "New York, NY", "url": "https://acme.com/1"},
            {"company": "Acme", "title": "Frontend Software Engineer, New Grad",
             "location": "New York, NY", "url": "https://acme.com/2"},
        ]
        sent = dedup.group_and_notify(jobs)
        self.assertEqual(sent, 2)
        self.assertEqual(self.mock_send.call_count, 2)

    def test_bootstrap_mode_records_without_sending(self):
        jobs = [{"company": "Acme", "title": "Software Engineer, New Grad",
                 "location": "New York, NY", "url": "https://acme.com/1"}]
        sent = dedup.group_and_notify(jobs, bootstrap=True)
        self.assertEqual(sent, 0)
        self.mock_send.assert_not_called()
        # but it's now in the registry, so a real (non-bootstrap) run
        # afterward correctly stays silent on it too
        sent_after = dedup.group_and_notify(jobs)
        self.assertEqual(sent_after, 0)
        self.mock_send.assert_not_called()

    def test_empty_input_sends_nothing(self):
        self.assertEqual(dedup.group_and_notify([]), 0)
        self.mock_send.assert_not_called()

    def test_many_locations_truncated_in_display(self):
        jobs = [
            {"company": "Acme", "title": "Software Engineer, New Grad",
             "location": f"City{i}, ST", "url": f"https://acme.com/{i}"}
            for i in range(8)
        ]
        dedup.group_and_notify(jobs)
        (payload,), _ = self.mock_send.call_args
        self.assertIn("+3 more", payload["location"])


if __name__ == "__main__":
    unittest.main()
