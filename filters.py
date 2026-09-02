"""New-grad / SWE / US-location filtering for normalized job postings."""
import re
from datetime import date, datetime, timezone

MAX_AGE_DAYS = 5

NEW_GRAD_RE = re.compile(
    r"new\s*grad|university\s*grad|college\s*grad|early\s*career|"
    r"entry[\s-]?level|recent\s*graduate|class\s*of\s*20(2[4-9])|"
    r"20(2[4-9])\s*grad(uate)?",
    re.I,
)

EXCLUDE_RE = re.compile(
    r"\bintern(ship)?\b|\bsr\.?\b|\bsenior\b|\bstaff\b|\bprincipal\b|\blead\b|"
    r"\bmanager\b|\bdirector\b|\bvp\b|\bhead\s+of\b|\bmba\b",
    re.I,
)

SWE_RE = re.compile(
    r"software\s*engineer|\bswe\b|backend|back-end|frontend|front-end|"
    r"full[\s-]?stack|infrastructure\s*engineer|platform\s*engineer|"
    r"systems?\s*engineer|site\s*reliability|\bsre\b|devops|"
    r"machine\s*learning\s*engineer|\bml\s*engineer\b|data\s*engineer|"
    r"security\s*engineer",
    re.I,
)

US_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}

NON_US_MARKERS = re.compile(
    r"canada|india|london|uk\b|united\s*kingdom|germany|france|ireland|"
    r"singapore|australia|japan|china|hong\s*kong|netherlands|poland|"
    r"switzerland|israel|brazil|mexico|spain|italy|sweden|toronto|"
    r"vancouver|bangalore|berlin|dublin|amsterdam|paris|tokyo|remote\s*-\s*emea",
    re.I,
)

US_MARKERS = re.compile(r"united\s*states|\bu\.?s\.?a?\.?\b", re.I)


def is_new_grad_swe(title: str) -> bool:
    if EXCLUDE_RE.search(title):
        return False
    return bool(NEW_GRAD_RE.search(title)) and bool(SWE_RE.search(title))


def is_us_location(location: str) -> bool:
    if not location:
        return False
    if NON_US_MARKERS.search(location):
        return False
    if US_MARKERS.search(location):
        return True
    # look for ", XX" state-abbreviation pattern common in ATS location strings
    for token in re.findall(r"\b[A-Z]{2}\b", location):
        if token in US_STATE_ABBR:
            return True
    return False


def matches(job: dict) -> bool:
    """job: normalized dict with 'title' and 'location' keys."""
    return is_new_grad_swe(job.get("title", "")) and is_us_location(job.get("location", ""))


def _posted_at_to_age_days(posted_at) -> float | None:
    """posted_at: an ISO8601 string, epoch milliseconds (Lever), or a
    date/datetime object (JobSpy's date_posted column). Returns days since
    posted, or None if posted_at is missing/unparseable."""
    if posted_at is None or posted_at == "":
        return None
    dt = None
    if isinstance(posted_at, datetime):
        dt = posted_at
    elif isinstance(posted_at, date):
        dt = datetime(posted_at.year, posted_at.month, posted_at.day)
    elif isinstance(posted_at, (int, float)):
        try:
            dt = datetime.fromtimestamp(posted_at / 1000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    elif isinstance(posted_at, str):
        try:
            dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def is_recent(posted_at=None, age_days=None, max_days=MAX_AGE_DAYS) -> bool:
    """True if the posting is within max_days old. Accepts either a raw
    posted_at (ISO8601 string or epoch-ms int) or an already-computed
    age_days (e.g. from the backup repos' "Age" column).

    Fails open: if age can't be determined from what's given, treat it as
    recent — the goal is cutting spam from stale postings, not silently
    dropping a genuinely fresh one just because a source omitted a date."""
    if age_days is None and posted_at is not None:
        age_days = _posted_at_to_age_days(posted_at)
    if age_days is None:
        return True
    return age_days <= max_days
