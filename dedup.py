"""
Shared cross-tier notification gate. Without this, the same real-world
posting can ping you more than once: once per location it's listed at
(Tier 1/JobSpy report each location as a separate job id), and once per
tier that independently discovers it (Tier 1, the backup repos, and
JobSpy are all watching overlapping ground on purpose, for redundancy —
see README).

This sits *after* each tier's own per-source "is this id new" check and
*before* the actual notify.send() call: every tier funnels its
already-filtered, already-new matches through group_and_notify() at the
end of its run, which:
  1. groups them by a fuzzy (company, title) key, so 3 locations of the
     same req become one notification listing all 3 instead of 3 pings;
  2. checks that key against state/notified.json, a registry shared by
     all three pollers — if any tier already notified for this role
     (ever), every other tier skips it silently;
  3. sends one notification per genuinely new group and records it.
"""
import json
import re
from datetime import datetime, timezone

import notify

NOTIFIED_PATH = "state/notified.json"
# Keys this run added to the registry, written alongside the full file so
# sync_state.py can merge just the delta against a freshly-fetched remote
# copy instead of the whole (possibly stale) local file — see sync_state.py
# for why that distinction matters.
NOTIFIED_DELTA_PATH = "state/.notified_delta.json"
MAX_LOCATIONS_SHOWN = 5


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, sort words — so "Software Engineer,
    New Grad" / "New Grad Software Engineer" / "software engineer - new
    grad" (title wording that legitimately differs across an ATS, a
    curated repo, and Indeed/LinkedIn's own listing for the very same
    job) all collapse to the same key."""
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return " ".join(sorted(words))


def canonical_key(company: str, title: str) -> str:
    return f"{_normalize(company)}::{_normalize(title)}"


def load_notified() -> dict:
    try:
        with open(NOTIFIED_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_notified(data: dict):
    with open(NOTIFIED_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def group_and_notify(jobs: list[dict], bootstrap: bool = False) -> int:
    """jobs: normalized dicts with company/title/location/url, already
    filtered down to "new + relevant + recent" by the calling tier.
    Returns how many notifications were actually sent.

    bootstrap=True records every group as notified without sending
    anything — used the very first time a tier runs, same idea as each
    tier's own per-source bootstrap, so standing up a new tier (or
    resetting state) doesn't replay history as a notification storm."""
    if not jobs:
        return 0

    groups = {}
    for j in jobs:
        # key is computed from the plain company/title only — a tier tag
        # must never leak in here, or the same role reported by two tiers
        # would get two different keys and defeat cross-tier dedup.
        key = canonical_key(j["company"], j["title"])
        g = groups.setdefault(key, {
            "company": j["company"],
            "title": j["title"],
            "locations": [],
            "urls": [],
            "sources": [],
        })
        loc = (j.get("location") or "").strip()
        if loc and loc not in g["locations"]:
            g["locations"].append(loc)
        url = j.get("url")
        if url and url not in g["urls"]:
            g["urls"].append(url)
        source = j.get("source", "tier1")
        if source not in g["sources"]:
            g["sources"].append(source)

    notified = load_notified()
    now = datetime.now(timezone.utc).isoformat()
    sent = 0
    added = {}  # this run's additions only — see NOTIFIED_DELTA_PATH

    for key, g in groups.items():
        if key in notified:
            continue
        if bootstrap:
            notified[key] = now
            added[key] = now
            continue

        locations = g["locations"]
        shown = locations[:MAX_LOCATIONS_SHOWN]
        location_str = "; ".join(shown) if shown else "location not specified"
        if len(locations) > MAX_LOCATIONS_SHOWN:
            location_str += f" +{len(locations) - MAX_LOCATIONS_SHOWN} more"

        display_company = g["company"]
        if g["sources"] != ["tier1"]:
            display_company = f"{g['company']} [{'+'.join(g['sources'])}]"

        notify.send({
            "company": display_company,
            "title": g["title"],
            "location": location_str,
            "url": g["urls"][0] if g["urls"] else "",
        })
        notified[key] = now
        added[key] = now
        sent += 1

    save_notified(notified)
    with open(NOTIFIED_DELTA_PATH, "w") as f:
        json.dump(added, f, indent=2, sort_keys=True)
    return sent
