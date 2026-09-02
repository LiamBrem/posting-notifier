"""
End-to-end test for backup_poller.collect_matches(), specifically the
company-list filter — this is the regression test for the actual incident
that motivated it: a live run notified on ~38 postings, most from
companies never in companies.json (Booz Allen, Raytheon, Northrop
Grumman, PepsiCo, ...), because the backup sources track a much broader
company universe than our target list and nothing filtered it down.
"""
import unittest
from unittest.mock import patch
import tempfile
import os
import json

import backup_poller as bp
from tests.fixtures import iso_days_ago, RECENT_DAYS


def _job(company, title, url, id_suffix):
    return {
        "id": f"https://example.com/{id_suffix}",
        "company": company,
        "title": title,
        "location": "New York, NY",
        "url": f"https://example.com/{id_suffix}",
        "age_days": RECENT_DAYS,
        "source": "TestSource",
    }


class TestBackupPollerCompanyFilter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.companies_path = os.path.join(self.tmpdir, "companies.json")
        self.tier1_seen_path = os.path.join(self.tmpdir, "seen.json")
        self.backup_seen_path = os.path.join(self.tmpdir, "seen_backup.json")

        with open(self.companies_path, "w") as f:
            json.dump(["Acme", "ByteDance"], f)
        with open(self.tier1_seen_path, "w") as f:
            json.dump({}, f)
        # seed as already-run so this isn't treated as a bootstrap
        with open(self.backup_seen_path, "w") as f:
            json.dump({"fake_source": []}, f)

        self._orig = (bp.COMPANIES_PATH, bp.TIER1_SEEN_PATH, bp.BACKUP_SEEN_PATH)
        bp.COMPANIES_PATH = self.companies_path
        bp.TIER1_SEEN_PATH = self.tier1_seen_path
        bp.BACKUP_SEEN_PATH = self.backup_seen_path

    def tearDown(self):
        bp.COMPANIES_PATH, bp.TIER1_SEEN_PATH, bp.BACKUP_SEEN_PATH = self._orig

    @patch("backup_poller.BACKUP_SOURCES", new_callable=dict)
    def test_off_list_company_is_dropped(self, mock_sources):
        mock_sources["fake_source"] = lambda: [
            _job("Acme", "Software Engineer, New Grad", "u", "1"),
            _job("Raytheon", "Software Engineer, New Grad", "u", "2"),
            _job("Booz Allen Hamilton", "Software Engineer, New Grad", "u", "3"),
            _job("Northrop Grumman", "Software Engineer, New Grad", "u", "4"),
        ]
        matches = bp.collect_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["company"], "Acme")

    @patch("backup_poller.BACKUP_SOURCES", new_callable=dict)
    def test_aliased_company_is_kept_and_normalized(self, mock_sources):
        # source lists it as "TikTok"; companies.json has "ByteDance"
        mock_sources["fake_source"] = lambda: [
            _job("TikTok", "Software Engineer, New Grad", "u", "1"),
        ]
        matches = bp.collect_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["company"], "ByteDance")  # normalized, not "TikTok"

    @patch("backup_poller.BACKUP_SOURCES", new_callable=dict)
    def test_short_name_target_does_not_leak(self, mock_sources):
        with open(self.companies_path, "w") as f:
            json.dump(["Box"], f)
        mock_sources["fake_source"] = lambda: [
            _job("Roblox", "Software Engineer, New Grad", "u", "1"),  # must NOT match "Box"
            _job("Box", "Software Engineer, New Grad", "u", "2"),
        ]
        matches = bp.collect_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["company"], "Box")


if __name__ == "__main__":
    unittest.main()
