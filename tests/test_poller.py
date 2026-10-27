import os
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import poller


def job(source, company, title, url, location="NYC"):
    return {"id": url, "company": company, "title": title, "location": location,
            "url": url, "source": source}


class RoleKey(unittest.TestCase):
    def test_cosmetic_title_and_company_differences_collide(self):
        a = job("a", "Anduril Industries", "2027 Early Career Flight Software Engineer", "u1")
        b = job("b", "Anduril", "Flight Software Engineer 🇺🇸", "u2")
        c = job("c", "anduril, inc.", "New Grad 2027: Software Engineer, Flight", "u3")
        self.assertEqual(poller.role_key(a), poller.role_key(b))
        self.assertEqual(poller.role_key(a), poller.role_key(c))

    def test_different_roles_differ(self):
        self.assertNotEqual(poller.role_key(job("a", "SpaceX", "Software Engineer (Starship)", "u1")),
                            poller.role_key(job("a", "SpaceX", "Software Engineer (Starlink)", "u2")))


class Poll(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for name in ("SEEN_PATH", "NOTIFIED_PATH", "HEADS_PATH"):
            patcher = mock.patch.object(poller, name, os.path.join(self.dir.name, name.lower() + ".json"))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sent = []
        patcher = mock.patch.object(poller.notify, "send", side_effect=self.sent.append)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.rows = {"a": [], "b": []}
        self.downloads = []

    def run_poll(self):
        # A repo's head SHA is its current rows, so it "moves" whenever they change.
        sources = {name: types.SimpleNamespace(REPO=name, BRANCH="main", PATH="README.md",
                                               parse=lambda name, n=name: list(self.rows[n]))
                   for name in self.rows}

        def latest_sha(repo, branch, etag=None):
            sha = repr([j["id"] for j in self.rows[repo]])
            return (None, etag) if sha == etag else (sha, sha)

        def get_file(repo, ref, path):
            self.downloads.append(repo)
            return repo

        with mock.patch.object(poller, "SOURCES", sources), \
                mock.patch.object(poller, "latest_sha", latest_sha), \
                mock.patch.object(poller, "get_file", get_file):
            poller.main()

    def test_first_poll_seeds_without_notifying(self):
        self.rows["a"] = [job("a", "Acme", "SWE", "u1")]
        self.rows["b"] = [job("b", "Beta", "SWE", "u2")]
        self.run_poll()
        self.assertEqual(self.sent, [])

    def test_same_role_across_repos_notifies_once(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "Acme", "Software Engineer", "u1")]
        self.run_poll()
        self.rows["b"] = [job("b", "Acme Inc.", "New Grad Software Engineer", "u2")]
        self.run_poll()
        self.assertEqual(len(self.sent), 1)

    def test_same_poll_duplicates_are_one_notification(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "Acme", "SWE", "u1", "NYC"), job("a", "Acme", "SWE", "u2", "SF")]
        self.rows["b"] = [job("b", "Acme", "SWE", "u3")]
        self.run_poll()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["location"], "NYC; SF")
        self.assertEqual(self.sent[0]["sources"], "a, b")

    def test_same_url_with_differently_worded_title_is_suppressed(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "RTX", "Software Engineer I", "https://rtx/1")]
        self.run_poll()
        self.rows["b"] = [job("b", "Raytheon", "Software Engineer I - Tucson, AZ", "https://rtx/1")]
        self.run_poll()
        self.assertEqual(len(self.sent), 1)

    def test_role_notifies_again_after_cooldown(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "Acme", "SWE", "u1")]
        self.run_poll()
        later = datetime.now(timezone.utc) + timedelta(days=poller.COOLDOWN_DAYS + 1)
        self.rows["b"] = [job("b", "Acme", "SWE", "u2")]
        with mock.patch.object(poller, "datetime", wraps=datetime) as fake:
            fake.now.return_value = later
            self.run_poll()
        self.assertEqual(len(self.sent), 2)

    def test_failed_send_is_retried_next_poll(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "Acme", "SWE", "u1")]
        with mock.patch.object(poller.notify, "send", side_effect=RuntimeError):
            with self.assertRaises(SystemExit):
                self.run_poll()
        self.run_poll()
        self.assertEqual(len(self.sent), 1)

    def test_unchanged_repos_are_not_downloaded(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", "Acme", "SWE", "u1")]
        self.downloads.clear()
        self.run_poll()
        self.assertEqual(self.downloads, ["a"])
        self.assertEqual(len(self.sent), 1)

    def test_mass_change_reseeds_instead_of_flooding(self):
        self.rows["a"] = self.rows["b"] = [job("x", "Old", "SWE", "u0")]
        self.run_poll()
        self.rows["a"] = [job("a", f"Co{i}", "SWE", f"u{i}") for i in range(1, poller.MAX_NEW_PER_SOURCE + 2)]
        self.run_poll()
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
