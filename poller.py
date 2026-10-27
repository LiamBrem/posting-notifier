"""
Polls four community new-grad job repos and notifies on rows that were
added since the last poll:

- SimplifyJobs/New-Grad-Positions (SWE section)
- speedyapply/2027-SWE-College-Jobs (NEW_GRAD_USA.md)
- vanshb03/New-Grad-2027
- ApplyGuy/2027-New-Grad-Jobs

The repos overlap heavily, so the same role usually shows up in all of
them within a day or two. A notification for a company + title starts a
cooldown (COOLDOWN_DAYS, default 3) during which that role is not sent
again, whichever repo it reappears in. A row whose apply URL was already
notified is also covered, for when repos word the same title differently.

Each poll first asks GitHub for every repo's head commit (an ETag'd call
that's nearly free when nothing changed) and only downloads and parses
the repos that moved, so it's cheap to run every minute (runner.py).
Set GITHUB_TOKEN to lift the API's 60-calls/hour unauthenticated limit.

Run manually:
    NTFY_TOPIC=your-secret-topic python3 poller.py
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import notify
from sources import SOURCES
from sources.common import get_file, latest_sha
from state_io import load, save

SEEN_PATH = "state/seen.json"          # {source: [job_id, ...]}
NOTIFIED_PATH = "state/notified.json"  # {role_key: {notified_at, ...}}
HEADS_PATH = "state/heads.json"        # {source: {sha, etag}}
COOLDOWN_DAYS = float(os.environ.get("COOLDOWN_DAYS", 3))
# Records are kept past the cooldown only for reference; prune eventually.
RETENTION_DAYS = 30
# More new rows than this from one repo in a single poll means the repo
# was reformatted/re-linked, not that it posted that many jobs: reseed it.
MAX_NEW_PER_SOURCE = 40
MAX_LOCATIONS_SHOWN = 5

COMPANY_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "the",
                    "industries", "technologies", "technology", "systems", "group", "holdings"}
# Decoration the repos add to titles inconsistently ("New Grad 2027: ...",
# "2027 Early Career ...", "... I (Onsite)") that doesn't identify the role.
TITLE_NOISE = {"new", "grad", "graduate", "grads", "early", "career", "careers", "entry", "level",
               "university", "college", "i", "1", "onsite", "remote", "hybrid", "full", "time"}
YEAR_RE = re.compile(r"^20\d\d$")


def _tokens(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def role_key(job):
    """Company + title, normalized so cosmetic differences between repos
    (emoji markers, punctuation, word order, "Inc.") still collide."""
    company = "".join(t for t in _tokens(job["company"]) if t not in COMPANY_SUFFIXES)
    title = " ".join(sorted({t for t in _tokens(job["title"])
                             if t not in TITLE_NOISE and not YEAR_RE.match(t)}))
    return f"{company}::{title}"


def in_cooldown(record, now):
    notified_at = datetime.fromisoformat(record["notified_at"])
    return now - notified_at < timedelta(days=COOLDOWN_DAYS)


def fetch_if_changed(source, head):
    """Rows at the repo's new head commit, or None if it hasn't moved."""
    try:
        sha, etag = latest_sha(source.REPO, source.BRANCH, head.get("etag"))
    except Exception as e:
        # API down or rate-limited: fall back to the (CDN-cached) branch file.
        print(f"[warn] {source.REPO} head check failed ({type(e).__name__}); fetching branch", file=sys.stderr)
        return source.parse(get_file(source.REPO, source.BRANCH, source.PATH))
    if sha is None or sha == head.get("sha"):
        return None
    jobs = source.parse(get_file(source.REPO, sha, source.PATH))
    head.update(sha=sha, etag=etag)
    return jobs


def find_new_jobs(seen, heads):
    """Fetch every changed source; return (new_jobs, current_ids_by_source,
    error_count). A source that fails keeps its previous state untouched."""
    new_jobs, current, errors = [], {}, 0
    for name, source in SOURCES.items():
        head = dict(heads.get(name, {})) if name in seen else {}
        try:
            jobs = fetch_if_changed(source, head)
        except Exception as e:
            print(f"[error] {name}: {e}", file=sys.stderr)
            errors += 1
            continue
        if jobs is None:
            continue
        if not jobs:
            print(f"[error] {name}: no parseable rows; format may have changed", file=sys.stderr)
            errors += 1
            continue
        ids = {j["id"] for j in jobs}
        current[name] = ids
        heads[name] = head
        if name not in seen:
            print(f"[seed] {name}: {len(ids)} rows recorded without notifying")
            continue
        fresh = [j for j in jobs if j["id"] not in set(seen[name])]
        if len(fresh) > MAX_NEW_PER_SOURCE:
            print(f"[reseed] {name}: {len(fresh)} new rows at once, assuming a reformat; not notifying")
            continue
        print(f"[source] {name}: {len(jobs)} rows, {len(fresh)} new")
        new_jobs.extend(fresh)
    return new_jobs, current, errors


def group_by_role(jobs):
    groups = {}
    for job in jobs:
        groups.setdefault(role_key(job), []).append(job)
    return groups


def format_group(jobs):
    first = jobs[0]
    locations = list(dict.fromkeys(j["location"] for j in jobs if j["location"]))
    location = "; ".join(locations[:MAX_LOCATIONS_SHOWN])
    if len(locations) > MAX_LOCATIONS_SHOWN:
        location += f" (+{len(locations) - MAX_LOCATIONS_SHOWN} more)"
    sources = ", ".join(dict.fromkeys(j["source"] for j in jobs))
    return {"company": first["company"], "title": first["title"],
            "location": location, "url": first["url"], "sources": sources}


def main():
    now = datetime.now(timezone.utc)
    seen = load(SEEN_PATH, {})
    heads = load(HEADS_PATH, {})
    notified = {k: v for k, v in load(NOTIFIED_PATH, {}).items()
                if now - datetime.fromisoformat(v["notified_at"]) < timedelta(days=RETENTION_DAYS)}

    new_jobs, current, errors = find_new_jobs(seen, heads)
    url_index = {url: key for key, record in notified.items() for url in record["urls"]}
    failed_ids = set()
    sent = suppressed = 0
    for key, jobs in group_by_role(new_jobs).items():
        candidates = [key] + [url_index[j["url"]] for j in jobs if j["url"] in url_index]
        record = next((notified[k] for k in candidates if k in notified and in_cooldown(notified[k], now)), None)
        if record:
            suppressed += 1
            record["sources"] = sorted(set(record["sources"]) | {j["source"] for j in jobs})
            record["urls"] = sorted(set(record["urls"]) | {j["url"] for j in jobs})
            continue
        message = format_group(jobs)
        try:
            notify.send(message)
        except Exception as e:
            # Leave these rows unseen so the next poll retries them.
            # Only the type: exception text can contain the secret topic URL.
            print(f"[error] notify failed for {message['company']}: {type(e).__name__}", file=sys.stderr)
            failed_ids.update(j["id"] for j in jobs)
            continue
        sent += 1
        print(f"[notify] {message['company']}: {message['title']} via {message['sources']}")
        notified[key] = {"notified_at": now.isoformat(), "company": message["company"],
                         "title": message["title"], "url": message["url"],
                         "sources": sorted({j["source"] for j in jobs}),
                         "urls": sorted({j["url"] for j in jobs})}
        url_index.update((j["url"], key) for j in jobs)

    for name, ids in current.items():
        seen[name] = sorted(ids - failed_ids)
    save(SEEN_PATH, seen)
    # After a failed send, forget the new heads so the next poll re-reads
    # those repos even if they haven't moved, and retries the unseen rows.
    if not failed_ids:
        save(HEADS_PATH, heads)
    save(NOTIFIED_PATH, notified)
    print(f"Done. {len(new_jobs)} new row(s), {sent} sent, {suppressed} suppressed by cooldown.")
    if failed_ids or errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
