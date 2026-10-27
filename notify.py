import os

import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def send(job: dict):
    if not NTFY_TOPIC:
        raise RuntimeError("NTFY_TOPIC is required")
    # Keep headers pure ASCII (ntfy requires RFC 2047 encoding otherwise) —
    # put the actual company/title/location details in the body instead.
    body = f"{job['company']}: {job['title']}\n{job['location']}\n{job['url']}\nvia {job['sources']}"
    response = requests.post(
        NTFY_URL,
        data=body.encode("utf-8"),
        headers={
            "Title": "New grad posting",
            "Priority": "high",
            "Tags": "briefcase",
            "Click": job["url"],
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
