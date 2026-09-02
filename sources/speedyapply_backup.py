"""
Parses the markdown pipe-tables in speedyapply/2027-SWE-College-Jobs'
NEW_GRAD_USA.md (FAANG+, Quant, and Other sections all follow the same
row shape: Company | Position | Location | [Salary] | Posting | Age —
location is always the 3rd cell regardless of whether Salary is present).
"""
import re

import requests

from .common import strip_tags, first_href, clean_url, parse_age_days

RAW_URL = "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md"
TIMEOUT = 20

# Real data rows start with a company link; header/separator rows don't.
ROW_RE = re.compile(r'^\|\s*<a href="[^"]*"><strong>.*\|\s*$', re.M)


def fetch() -> list[dict]:
    r = requests.get(RAW_URL, timeout=TIMEOUT)
    r.raise_for_status()
    text = r.text

    out = []
    for line in ROW_RE.findall(text):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        company = strip_tags(cells[0])
        title = strip_tags(cells[1])
        location = strip_tags(cells[2])
        age_days = parse_age_days(strip_tags(cells[-1]))
        apply_cell = next((c for c in cells if 'alt="Apply"' in c), "")
        raw_url = first_href(apply_cell)
        if not company or not title or not raw_url:
            continue
        url = clean_url(raw_url)

        out.append({
            "id": url,
            "company": company,
            "title": title,
            "location": location,
            "url": url,
            "age_days": age_days,
            "source": "speedyapply/2027-SWE-College-Jobs",
        })
    return out
