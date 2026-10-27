"""Shared parsing helpers for the GitHub-repo job lists."""
import html as html_module
import os
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

TIMEOUT = 20
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "source"}


def latest_sha(repo: str, branch: str, etag: str | None = None) -> tuple[str | None, str | None]:
    """Head commit of repo@branch as (sha, etag); sha is None when unchanged
    since etag. A 304 doesn't count against GitHub's rate limit when the
    request is authenticated, so with GITHUB_TOKEN set this is cheap to
    call every minute (unauthenticated is limited to 60 calls/hour)."""
    headers = {"Accept": "application/vnd.github.sha"}
    if etag:
        headers["If-None-Match"] = etag
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(f"https://api.github.com/repos/{repo}/commits/{branch}", headers=headers, timeout=TIMEOUT)
    if r.status_code == 304:
        return None, etag
    r.raise_for_status()
    return r.text.strip(), r.headers.get("ETag")


def get_file(repo: str, ref: str, path: str) -> str:
    # Pinning to a commit SHA sidesteps raw.githubusercontent.com's
    # 5-minute cache of branch URLs.
    r = requests.get(f"https://raw.githubusercontent.com/{repo}/{ref}/{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def clean_url(url: str) -> str:
    """Strip tracking query params so the same job doesn't get a new URL
    (and therefore a new id) every time a source re-links it."""
    parsed = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS]
    return urlunparse(parsed._replace(query=urlencode(q)))


def strip_tags(html_fragment: str) -> str:
    html_fragment = re.sub(r"</?br\s*/?>", "; ", html_fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html_fragment)
    # markdown bold/links: **X**, [X](url)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text).replace("**", "")
    return html_module.unescape(text).strip()


def first_href(html_fragment: str) -> str:
    m = re.search(r'href="([^"]+)"', html_fragment)
    return m.group(1) if m else ""


def pipe_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def job(source: str, company: str, title: str, location: str, raw_url: str) -> dict:
    url = clean_url(raw_url)
    return {"id": url, "company": company, "title": title,
            "location": location, "url": url, "source": source}
