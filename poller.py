"""
Tier 1: polls every company in companies_classified.json directly against
its own ATS API, filters for new-grad US SWE postings, diffs against
state/seen.json, and hands genuinely new matches to dedup.py, which
groups them by role (collapsing multiple locations into one notification)
and checks them against the cross-tier notified registry before sending.

Run manually:
    NTFY_TOPIC=your-secret-topic python3 poller.py

Run on a schedule via .github/workflows/poll.yml (every 10 min).
"""
import json
import os
import sys

from connectors import FETCHERS
import dedup
import filters

CLASSIFIED_PATH = "companies_classified.json"
SEEN_PATH = "state/seen.json"


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def collect_matches() -> list[dict]:
    """Fetches every classified company, updates state/seen.json, and
    returns the jobs that are new-to-this-source, filter-relevant, and
    recent. Does NOT notify — that's dedup.group_and_notify()'s job, so a
    role Tier 1 and another tier both discover only pings once."""
    classified = load_json(CLASSIFIED_PATH, {})
    # First-ever run: seed seen.json with every currently-open job without
    # treating any of it as a "match" to hand off, so standing this up
    # doesn't dump the entire current job market on you.
    bootstrap = not os.path.exists(SEEN_PATH)
    seen = load_json(SEEN_PATH, {})  # {slug_key: [job_id, ...]}
    if bootstrap:
        print("[bootstrap] state/seen.json not found — seeding without notifying.")

    matches = []
    for key, entry in classified.items():
        ats, slug, company = entry["ats"], entry["slug"], entry["company"]
        fetch = FETCHERS[ats]
        try:
            jobs = fetch(slug)
        except Exception as e:
            print(f"[error] {company} ({ats}:{slug}): {e}", file=sys.stderr)
            continue

        seen_ids = set(seen.get(key, []))
        current_ids = set()

        for job in jobs:
            current_ids.add(job["id"])
            if job["id"] in seen_ids or bootstrap:
                continue
            if filters.matches(job) and filters.is_recent(job.get("posted_at")):
                print(f"[match] {company}: {job['title']} ({job['location']})")
                matches.append(job)

        # only track ids currently live, so a job that's removed and later
        # reposted under the same id (rare, but happens) still fires
        seen[key] = sorted(current_ids)

    save_json(SEEN_PATH, seen)
    return matches


def main():
    matches = collect_matches()
    sent = dedup.group_and_notify(matches)
    print(f"Done. {len(matches)} matching posting(s) found, {sent} notification(s) sent.")


if __name__ == "__main__":
    main()
