import unittest

from sources import applyguy, simplify, speedyapply, vansh

SIMPLIFY = """
## 💻 Software Engineering New Grad Roles
<table><tbody>
<tr><td><strong><a href="x">Acme</a></strong></td><td>Software Engineer</td><td>NYC</td>
<td><a href="https://jobs.acme.com/1?utm_source=Simplify"><img alt="Apply"></a></td><td>0d</td></tr>
<tr><td>↳</td><td>Backend Engineer</td><td>SF</br>Remote</td>
<td><a href="https://jobs.acme.com/2"><img alt="Apply"></a></td><td>1d</td></tr>
<tr><td>Closed Co</td><td>SWE</td><td>LA</td><td>🔒</td><td>3d</td></tr>
</tbody></table>
## 📱 Product Management New Grad Roles
<tr><td>PM Co</td><td>PM</td><td>NYC</td><td><a href="https://pm.co/1">a</a></td><td>0d</td></tr>
"""

SPEEDY = """
| Company | Position | Location | Salary | Posting | Age |
|---|---|---|---|---|---|
| <a href="https://roblox.com"><strong>Roblox</strong></a> | Software Engineer | San Mateo, CA | $150k | <a href="https://careers.roblox.com/jobs/1"><img alt="Apply"></a> | 0d |
"""

VANSH = """
| Company | Role | Location | Application/Link | Date Posted |
| --- | --- | --- | :---: | :---: |
| **SpaceX** | AI Software Engineer 🇺🇸 | Hawthorne, CA | <a href="https://go.vansh.nyc/BJ?s=A"><img src="x" alt="Apply"></a> | Oct 26 |
| **Boeing** | Software Engineer | Hazelwood, MO | 🔒 | Oct 23 |
"""

APPLYGUY = """
| Company | Role | Location | Posted | Actions |
|---|---|---|---:|---|
| Etsy | Software Engineer I | Brooklyn, NY | Today | [![Apply with Apply Guy](a.svg)](https://applyguy.ai/jobs?job=1&utm_source=github) [![View original listing](v.svg)](https://etsy.wd5.myworkdayjobs.com/job/SE-I_JR1) |
| Amazon | SDE I | Seattle, WA | Today | [![View original listing](v.svg)](https://www.amazon.jobs/en/jobs/1) |
"""


class SourceParsing(unittest.TestCase):
    def test_simplify_scoped_to_swe_with_continuations_and_closed_rows(self):
        jobs = simplify.parse(SIMPLIFY)
        self.assertEqual([(j["company"], j["title"]) for j in jobs],
                         [("Acme", "Software Engineer"), ("Acme", "Backend Engineer")])
        self.assertEqual(jobs[0]["url"], "https://jobs.acme.com/1")
        self.assertEqual(jobs[1]["location"], "SF; Remote")

    def test_speedyapply(self):
        [job] = speedyapply.parse(SPEEDY)
        self.assertEqual((job["company"], job["location"], job["url"]),
                         ("Roblox", "San Mateo, CA", "https://careers.roblox.com/jobs/1"))

    def test_vansh_skips_closed(self):
        [job] = vansh.parse(VANSH)
        self.assertEqual((job["company"], job["url"]), ("SpaceX", "https://go.vansh.nyc/BJ?s=A"))

    def test_applyguy_prefers_original_listing(self):
        jobs = applyguy.parse(APPLYGUY)
        self.assertEqual([j["url"] for j in jobs],
                         ["https://etsy.wd5.myworkdayjobs.com/job/SE-I_JR1", "https://www.amazon.jobs/en/jobs/1"])


if __name__ == "__main__":
    unittest.main()
