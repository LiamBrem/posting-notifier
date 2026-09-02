"""
Tier 2 (backup): polls SimplifyJobs/New-Grad-Positions and
speedyapply/2027-SWE-College-Jobs for new-grad SWE postings and hands
anything Tier 1 (direct ATS polling, poller.py) hasn't already caught to
dedup.py, which groups by role and checks the cross-tier notified
registry before sending.

Cross-referencing against Tier 1: if a row's apply link points to a
Greenhouse/Lever/Ashby/SmartRecruiters URL whose job id is already in
state/seen.json (written by poller.py), it's something Tier 1 already
knows about — skip it here to avoid a duplicate ping. This also means: if
this repo has a job Tier 1 doesn't cover (a company outside our 75, or one
Tier 1 hasn't polled yet), it fires here as a genuine catch. (This is on
top of, not instead of, dedup.py's own company+title cross-tier check —
this one is precise/id-based when the URL is recognizable, dedup.py's is
the fuzzy fallback that also catches JobSpy overlap.)

Meant to run on a slower cadence than Tier 1 (hourly is plenty — both
source repos update themselves roughly daily anyway, so polling faster
than that buys nothing).

Run manually:
    NTFY_TOPIC=your-secret-topic python3 backup_poller.py
"""
import json
import os
import sys

import dedup
import filters
from sources import BACKUP_SOURCES
from sources.common import extract_ats_ref

TIER1_SEEN_PATH = "state/seen.json"
BACKUP_SEEN_PATH = "state/seen_backup.json"


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def build_tier1_id_index(tier1_seen: dict) -> dict:
    """{ats: set(job_id, ...)} across all companies, so a backup row can be
    checked without needing to know which Tier-1 slug it belongs to."""
    index = {}
    for key, ids in tier1_seen.items():
        ats = key.split(":", 1)[0]
        index.setdefault(ats, set()).update(ids)
    return index


def already_caught_by_tier1(job: dict, tier1_index: dict) -> bool:
    ref = extract_ats_ref(job["url"])
    if not ref:
        return False
    ats, job_id = ref
    return job_id in tier1_index.get(ats, set())


def collect_matches() -> list[dict]:
    tier1_seen = load_json(TIER1_SEEN_PATH, {})
    tier1_index = build_tier1_id_index(tier1_seen)

    bootstrap = not os.path.exists(BACKUP_SEEN_PATH)
    backup_seen = load_json(BACKUP_SEEN_PATH, {})  # {source_name: [job_id, ...]}
    if bootstrap:
        print("[bootstrap] state/seen_backup.json not found — seeding without notifying.")

    matches = []
    for source_name, fetch in BACKUP_SOURCES.items():
        try:
            jobs = fetch()
        except Exception as e:
            print(f"[error] source {source_name}: {e}", file=sys.stderr)
            continue

        seen_ids = set(backup_seen.get(source_name, []))
        current_ids = set()

        for job in jobs:
            current_ids.add(job["id"])
            if job["id"] in seen_ids or bootstrap:
                continue
            # backup sources are already scoped to new-grad SWE roles by the
            # repo itself, so we only re-apply the US-location + exclude
            # filters here, not the new-grad/SWE keyword regexes (raw ATS
            # titles like "Software Engineer 1" often don't literally say
            # "new grad", and the source has already made that call).
            if filters.EXCLUDE_RE.search(job["title"]):
                continue
            if not filters.is_us_location(job["location"]):
                continue
            if not filters.is_recent(age_days=job.get("age_days")):
                continue
            if already_caught_by_tier1(job, tier1_index):
                continue

            print(f"[backup match] {job['company']}: {job['title']} ({job['location']}) via {source_name}")
            matches.append(job)

        backup_seen[source_name] = sorted(current_ids)

    save_json(BACKUP_SEEN_PATH, backup_seen)
    return matches


def main():
    matches = collect_matches()
    sent = dedup.group_and_notify(matches)
    print(f"Done. {len(matches)} matching posting(s) found, {sent} notification(s) sent.")


if __name__ == "__main__":
    main()
