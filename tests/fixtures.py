"""
Date helpers for building test fixtures relative to "now" instead of a
hardcoded date. Real live postings drift in and out of the 5-day recency
window as time passes, which would make hardcoded-date fixtures flaky —
computing every fixture date relative to datetime.now() at test-run time
keeps "genuinely recent" and "genuinely stale" fixtures correct forever.
"""
from datetime import date, datetime, timedelta, timezone

RECENT_DAYS = 2   # well inside MAX_AGE_DAYS (5) — should always match
STALE_DAYS = 30   # well outside it — should always be filtered out


def iso_days_ago(n: int) -> str:
    """ISO8601 with timezone offset, the format Greenhouse/Ashby/
    SmartRecruiters use for their posted-date fields."""
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return dt.isoformat()


def epoch_ms_days_ago(n: int) -> int:
    """Epoch milliseconds, the format Lever's createdAt uses."""
    dt = datetime.now(timezone.utc) - timedelta(days=n)
    return int(dt.timestamp() * 1000)


def date_days_ago(n: int) -> date:
    """A bare date, the type JobSpy's date_posted column returns."""
    return (datetime.now(timezone.utc) - timedelta(days=n)).date()


def age_str_days_ago(n: int) -> str:
    """The backup repos' own "Age" column text (e.g. "2d")."""
    return f"{n}d"
