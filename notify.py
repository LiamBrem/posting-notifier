import os

import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"


def send(job: dict):
    if not NTFY_TOPIC:
        print(f"[notify] NTFY_TOPIC not set, skipping push for: {job['company']} - {job['title']}")
        return
    # Keep headers pure ASCII (ntfy requires RFC 2047 encoding otherwise) —
    # put the actual company/title/location details in the body instead.
    body = f"{job['company']}: {job['title']}\n{job['location']}\n{job['url']}"
    requests.post(
        NTFY_URL,
        data=body.encode("utf-8"),
        headers={
            "Title": "New grad SWE posting",
            "Priority": "high",
            "Tags": "briefcase",
            "Click": job["url"],
        },
        timeout=10,
    )
