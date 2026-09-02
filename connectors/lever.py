import requests

TIMEOUT = 15


def fetch(slug: str) -> list[dict]:
    r = requests.get(
        f"https://api.lever.co/v0/postings/{slug}?mode=json",
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    jobs = r.json()
    out = []
    for j in jobs:
        categories = j.get("categories", {}) or {}
        all_locations = categories.get("allLocations") or []
        location = ", ".join(all_locations) if all_locations else categories.get("location", "")
        out.append({
            "id": str(j["id"]),
            "company": slug,
            "title": j.get("text", ""),
            "location": location,
            "url": j.get("hostedUrl", ""),
            "posted_at": j.get("createdAt"),  # epoch ms
        })
    return out
