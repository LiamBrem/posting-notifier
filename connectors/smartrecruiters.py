import requests

TIMEOUT = 15
PAGE_SIZE = 100


def fetch(slug: str) -> list[dict]:
    out = []
    offset = 0
    while True:
        r = requests.get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
            params={"limit": PAGE_SIZE, "offset": offset},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        content = data.get("content", [])
        for j in content:
            loc = j.get("location", {}) or {}
            location = loc.get("fullLocation") or ", ".join(
                p for p in [loc.get("city"), loc.get("region"), loc.get("country")] if p
            )
            company_identifier = (j.get("company") or {}).get("identifier", slug)
            out.append({
                "id": str(j["id"]),
                "company": company_identifier,
                "title": j.get("name", ""),
                "location": location,
                "url": f"https://jobs.smartrecruiters.com/{company_identifier}/{j['id']}",
                # NB: releasedDate is when the req was first created, not
                # last renewed — for an evergreen posting still open years
                # later, this can make it look "old" and get skipped by
                # filters.is_recent() even though it's a live listing.
                "posted_at": j.get("releasedDate"),
            })
        offset += PAGE_SIZE
        if offset >= data.get("totalFound", 0):
            break
    return out
