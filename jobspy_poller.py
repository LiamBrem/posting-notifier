"""
Tier 3: broad market scan via JobSpy (Indeed + LinkedIn), run across ALL
141 target companies for redundancy — not just the 66 Tier 1 can't reach
directly. Tier 1 (direct ATS polling) and the backup tier (curated GitHub
repos) are both scoped to a company's actual job board, so if either has a
bug, an API change, or simply hasn't run yet, this tier is an independent
third path to the same posting via Indeed/LinkedIn's own search.

This is the least precise tier: JobSpy returns whatever the job board's own
search ranks as relevant for "{company} software engineer", so — unlike
Tier 1's exhaustive per-company listing or the backup tier's pre-curated
new-grad lists — it needs the full new-grad + SWE + US-location filter
from filters.py to avoid spam, and a company-name match to drop stray
results that leak in from unrelated companies.

It's redundant with the other two tiers by design, but unlike the earlier
version of this script, that no longer means duplicate pings: matches are
handed to dedup.py, which groups by role and checks the shared cross-tier
notified registry before sending — so if Tier 1 already notified for a
role, JobSpy finding "the same" role again here stays silent.

Run manually:
    NTFY_TOPIC=your-secret-topic python3 jobspy_poller.py
"""
import json
import os
import random
import sys
import time

import pandas as pd
from jobspy import scrape_jobs

import dedup
import filters
from company_match import ALIASES, company_matches

COMPANIES_PATH = "companies.json"
SEEN_PATH = "state/seen_jobspy.json"

# Google jobs was unreliable/blocked in testing (silent 0 results); Indeed
# and LinkedIn both returned real, relevant data.
SITES = ["indeed", "linkedin"]
RESULTS_PER_COMPANY = 15
HOURS_OLD = 168  # 1 week — state-based dedup handles genuine "new", this
                 # just bounds how much each call returns
SLEEP_BETWEEN_CALLS = (1.5, 3.5)  # seconds of jitter between scrape calls


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def clean_str(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def clean_date(value):
    """date_posted comes back as a datetime.date, NaN/NaT, or missing —
    normalize the "missing" cases to None so filters.is_recent() fails open
    on them instead of choking on a pandas NaT."""
    return None if pd.isna(value) else value


def search_terms_for(company: str) -> list[str]:
    return [f"{alias} software engineer" for alias in ALIASES.get(company, [company])]


def collect_matches() -> list[dict]:
    companies = load_json(COMPANIES_PATH, [])
    print(f"Scanning {len(companies)} companies via JobSpy (Indeed + LinkedIn)...")

    bootstrap = not os.path.exists(SEEN_PATH)
    seen = load_json(SEEN_PATH, {})
    if bootstrap:
        print("[bootstrap] state/seen_jobspy.json not found — seeding without notifying.")

    matches = []
    for company in companies:
        seen_ids = set(seen.get(company, []))
        current_ids = set(seen_ids)

        for term in search_terms_for(company):
            try:
                df = scrape_jobs(
                    site_name=SITES,
                    search_term=term,
                    location="United States",
                    results_wanted=RESULTS_PER_COMPANY,
                    hours_old=HOURS_OLD,
                    country_indeed="usa",
                )
            except Exception as e:
                print(f"[error] {company} ({term!r}): {e}", file=sys.stderr)
                time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS))
                continue

            for _, row in df.iterrows():
                if not company_matches(row.get("company"), company):
                    continue
                job_url = row.get("job_url")
                if not job_url:
                    continue
                current_ids.add(job_url)
                if job_url in seen_ids or bootstrap:
                    continue

                site = row.get("site") or "jobspy"
                job = {
                    "company": company,
                    "title": clean_str(row.get("title")),
                    "location": clean_str(row.get("location")),
                    "url": job_url,
                    "posted_at": clean_date(row.get("date_posted")),
                    "source": f"jobspy/{site}",
                }
                if not filters.matches(job):
                    continue
                if not filters.is_recent(job["posted_at"]):
                    continue

                print(f"[jobspy match] {company}: {job['title']} ({job['location']}) via {site}")
                matches.append(job)

            time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS))

        seen[company] = sorted(current_ids)

    save_json(SEEN_PATH, seen)
    return matches


def main():
    matches = collect_matches()
    sent = dedup.group_and_notify(matches)
    print(f"Done. {len(matches)} matching posting(s) found, {sent} notification(s) sent.")


if __name__ == "__main__":
    main()
