"""
Tests the two backup-repo parsers against synthetic README text shaped
exactly like the real repos (HTML table for SimplifyJobs, markdown pipe
table for speedyapply), with requests.get mocked so these run offline.

Same "nothing slips through" shape as test_connectors.py: one genuine
match plus decoys (intern, senior, non-US, stale, non-SWE) bundled into
one fixture, asserting the parse -> filter pipeline keeps exactly the
genuine one.
"""
import unittest
from unittest.mock import patch, MagicMock

import filters
from sources import simplify, speedyapply_backup
from tests.fixtures import age_str_days_ago, RECENT_DAYS, STALE_DAYS


def _mock_response(text):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = text
    resp.raise_for_status = MagicMock()
    return resp


SIMPLIFY_README = """\
# 2026 New Grad Positions

---

## 💻 Software Engineering New Grad Roles

[Back to top](#top)

<table>
<thead><tr><th>Company</th><th>Role</th><th>Location</th><th>Application</th><th>Age</th></tr></thead>
<tbody>
<tr>
<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>
<td>Software Engineer, New Grad</td>
<td>New York, NY</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/1?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
<tr>
<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>
<td>Software Engineer Intern</td>
<td>New York, NY</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/2?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
<tr>
<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>
<td>Senior Software Engineer, New Grad</td>
<td>New York, NY</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/3?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
<tr>
<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>
<td>Software Engineer, New Grad</td>
<td>London, UK</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/4?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
<tr>
<td><strong><a href="https://simplify.jobs/c/Acme">Acme</a></strong></td>
<td>Software Engineer, New Grad</td>
<td>New York, NY</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/5?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{stale_age}</td>
</tr>
<tr>
<td>↳</td>
<td>Software Engineer, New Grad</td>
<td>Denver, CO</td>
<td><div align="center"><a href="https://job-boards.greenhouse.io/acme/jobs/6?utm_source=Simplify&ref=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
</tbody>
</table>

## 📱 Product Management New Grad Roles

<table><tbody>
<tr>
<td><strong><a href="https://simplify.jobs/c/Other">Other</a></strong></td>
<td>Product Manager, New Grad</td>
<td>New York, NY</td>
<td><div align="center"><a href="https://example.com/pm?utm_source=Simplify"><img alt="Apply"></a></div></td>
<td>{recent_age}</td>
</tr>
</tbody></table>
""".format(recent_age=age_str_days_ago(RECENT_DAYS), stale_age=age_str_days_ago(STALE_DAYS))


class TestSimplifyParser(unittest.TestCase):
    @patch("sources.simplify.requests.get")
    def test_parses_only_swe_section(self, mock_get):
        mock_get.return_value = _mock_response(SIMPLIFY_README)
        jobs = simplify.fetch()
        # 6 rows in the SWE section; the PM-section row must NOT appear.
        self.assertEqual(len(jobs), 6)
        self.assertTrue(all("Other" != j["company"] for j in jobs))

    @patch("sources.simplify.requests.get")
    def test_carry_forward_company_symbol(self, mock_get):
        mock_get.return_value = _mock_response(SIMPLIFY_README)
        jobs = simplify.fetch()
        denver = [j for j in jobs if j["location"] == "Denver, CO"]
        self.assertEqual(len(denver), 1)
        self.assertEqual(denver[0]["company"], "Acme")

    @patch("sources.simplify.requests.get")
    def test_end_to_end_filter_survivors(self, mock_get):
        mock_get.return_value = _mock_response(SIMPLIFY_README)
        jobs = simplify.fetch()
        survivors = [
            j for j in jobs
            if not filters.EXCLUDE_RE.search(j["title"])
            and filters.is_us_location(j["location"])
            and filters.is_recent(age_days=j.get("age_days"))
        ]
        # Acme's 2 genuinely open US new-grad postings (NY + Denver, both
        # "Software Engineer, New Grad") should survive; intern, senior,
        # non-US, and stale should not. Backup-tier filtering intentionally
        # doesn't require SWE_RE/NEW_GRAD_RE wording (see backup_poller.py),
        # so the PM row isn't in this fixture's SWE-section slice at all.
        self.assertEqual(len(survivors), 2)
        self.assertEqual({j["location"] for j in survivors}, {"New York, NY", "Denver, CO"})


SPEEDYAPPLY_README = """\
## 2027 USA SWE New Graduate Positions

### FAANG+

<!-- TABLE_FAANG_START -->
| Company | Position | Location | Salary | Posting | Age |
|---|---|---|---|---|---|
| <a href="https://acme.com"><strong>Acme</strong></a> | Software Engineer, New Grad | New York, CA | $180k/yr | <a href="https://acme.com/jobs?gh_jid=11"><img alt="Apply"/></a> | {recent_age} |
| <a href="https://acme.com"><strong>Acme</strong></a> | Software Engineer Intern | New York, CA | $60/hr | <a href="https://acme.com/jobs?gh_jid=12"><img alt="Apply"/></a> | {recent_age} |
| <a href="https://acme.com"><strong>Acme</strong></a> | Senior Software Engineer, New Grad | New York, CA | $220k/yr | <a href="https://acme.com/jobs?gh_jid=13"><img alt="Apply"/></a> | {recent_age} |
| <a href="https://acme.com"><strong>Acme</strong></a> | Software Engineer, New Grad | London, UK | £90k/yr | <a href="https://acme.com/jobs?gh_jid=14"><img alt="Apply"/></a> | {recent_age} |
| <a href="https://acme.com"><strong>Acme</strong></a> | Software Engineer, New Grad | New York, CA | $180k/yr | <a href="https://acme.com/jobs?gh_jid=15"><img alt="Apply"/></a> | {stale_age} |
<!-- TABLE_FAANG_END -->

### Other

<!-- TABLE_START -->
| Company | Position | Location | Posting | Age |
|---|---|---|---|---|
| <a href="https://startup.com"><strong>Startup</strong></a> | Software Engineer - Business Systems | Austin, TX | <a href="https://jobs.ashbyhq.com/startup/xyz"><img alt="Apply"/></a> | {recent_age} |
<!-- TABLE_END -->
""".format(recent_age=age_str_days_ago(RECENT_DAYS), stale_age=age_str_days_ago(STALE_DAYS))


class TestSpeedyApplyBackupParser(unittest.TestCase):
    @patch("sources.speedyapply_backup.requests.get")
    def test_parses_faang_and_other_sections(self, mock_get):
        mock_get.return_value = _mock_response(SPEEDYAPPLY_README)
        jobs = speedyapply_backup.fetch()
        self.assertEqual(len(jobs), 6)  # 5 FAANG+ rows + 1 Other row

    @patch("sources.speedyapply_backup.requests.get")
    def test_location_is_third_cell_regardless_of_salary_column(self, mock_get):
        mock_get.return_value = _mock_response(SPEEDYAPPLY_README)
        jobs = speedyapply_backup.fetch()
        startup_job = next(j for j in jobs if j["company"] == "Startup")
        self.assertEqual(startup_job["location"], "Austin, TX")

    @patch("sources.speedyapply_backup.requests.get")
    def test_gh_jid_url_is_cleaned_but_intact(self, mock_get):
        mock_get.return_value = _mock_response(SPEEDYAPPLY_README)
        jobs = speedyapply_backup.fetch()
        acme_recent = next(j for j in jobs if "gh_jid=11" in j["url"])
        self.assertIn("gh_jid=11", acme_recent["url"])

    @patch("sources.speedyapply_backup.requests.get")
    def test_end_to_end_filter_survivors(self, mock_get):
        mock_get.return_value = _mock_response(SPEEDYAPPLY_README)
        jobs = speedyapply_backup.fetch()
        survivors = [
            j for j in jobs
            if not filters.EXCLUDE_RE.search(j["title"])
            and filters.is_us_location(j["location"])
            and filters.is_recent(age_days=j.get("age_days"))
        ]
        self.assertEqual(len(survivors), 2)  # Acme's NY row + Startup's Austin row
        self.assertEqual({j["company"] for j in survivors}, {"Acme", "Startup"})


if __name__ == "__main__":
    unittest.main()
