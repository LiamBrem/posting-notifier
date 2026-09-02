"""Per-ATS fetch + normalize functions.

Every connector exposes fetch(slug) -> list[dict], where each dict is
normalized to:
    {
        "id": str,          # stable, unique within this company
        "company": str,
        "title": str,
        "location": str,    # human-readable, may list multiple locations
        "url": str,
    }
"""
from . import greenhouse, lever, ashby, smartrecruiters

FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}
