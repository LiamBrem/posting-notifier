"""Shared helpers for the GitHub-repo "backup" sources."""
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref"}


def clean_url(url: str) -> str:
    """Strip tracking query params so the same job doesn't get a new URL
    (and therefore a duplicate id) every time a source re-links it."""
    parsed = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS]
    return urlunparse(parsed._replace(query=urlencode(q)))


# Matches the public job-posting URL formats these repos link to, in the
# same 4 platforms Tier 1 polls directly. The captured id is the same id
# Tier 1's connectors store in state/seen.json, which is what makes
# cross-referencing against Tier-1 state possible.
ATS_URL_PATTERNS = [
    ("greenhouse", re.compile(r"(?:job-boards|boards)\.greenhouse\.io/([a-zA-Z0-9_-]+)/jobs/(\d+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)/([0-9a-fA-F-]{36})")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)/([0-9a-fA-F-]{36})")),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9_-]+)/(\d+)")),
]


GH_JID_RE = re.compile(r"[?&]gh_jid=(\d+)")


def extract_ats_ref(url: str):
    """Return (ats, job_id) if url matches a known ATS's public posting URL
    format, else None. slug is intentionally not returned/matched here —
    the (ats, job_id) pair alone is enough to check state/seen.json,
    since Tier 1 stores ids per ats:slug key but ids are unique per ats."""
    for ats, pattern in ATS_URL_PATTERNS:
        m = pattern.search(url)
        if m:
            return ats, m.group(2)
    # Companies on custom domains often embed a Greenhouse posting via a
    # ?gh_jid=<id> query param on their own careers page (Stripe, Optiver,
    # Roblox, Databricks, Samsara, ...) rather than linking straight to
    # greenhouse.io — that id is still the same Greenhouse job id Tier 1's
    # greenhouse connector stores, so it's just as good a cross-reference.
    m = GH_JID_RE.search(url)
    if m:
        return "greenhouse", m.group(1)
    return None


def strip_tags(html_fragment: str) -> str:
    import html as html_module
    text = re.sub(r"<[^>]+>", "", html_fragment)
    return html_module.unescape(text).strip()


def first_href(html_fragment: str) -> str:
    m = re.search(r'href="([^"]+)"', html_fragment)
    return m.group(1) if m else ""


AGE_RE = re.compile(r"(\d+)\s*(d|mo|y)\b", re.I)
_UNIT_DAYS = {"d": 1, "mo": 30, "y": 365}


def parse_age_days(text: str):
    """Parses the repos' "Age" column ("0d", "12d", "1mo", ...) into a day
    count. Returns None if it doesn't match a known format (fail-open —
    callers should treat unknown age as recent, not stale)."""
    if not text:
        return None
    m = AGE_RE.search(text.strip())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return n * _UNIT_DAYS[unit]
