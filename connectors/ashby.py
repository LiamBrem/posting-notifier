import requests

TIMEOUT = 15


def fetch(slug: str) -> list[dict]:
    r = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    out = []
    for j in jobs:
        locations = [j.get("location", "")] + [
            sl.get("location", "") for sl in j.get("secondaryLocations", [])
        ]
        location = ", ".join(l for l in locations if l)
        out.append({
            "id": str(j["id"]),
            "company": slug,
            "title": j.get("title", ""),
            "location": location,
            "url": j.get("jobUrl", ""),
            "posted_at": j.get("publishedAt"),
        })
    return out
