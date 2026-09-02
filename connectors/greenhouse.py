import requests

TIMEOUT = 15


def fetch(slug: str) -> list[dict]:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    out = []
    for j in jobs:
        out.append({
            "id": str(j["id"]),
            "company": j.get("company_name", slug),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "posted_at": j.get("first_published"),
        })
    return out
