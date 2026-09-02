"""
Parses the HTML job table embedded in SimplifyJobs/New-Grad-Positions'
README.md, scoped to just the "Software Engineering New Grad Roles"
section (the repo also lists PM, Data Science, Quant, and Hardware roles,
which we don't want).
"""
import re

import requests

from .common import strip_tags, first_href, clean_url, parse_age_days

RAW_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
TIMEOUT = 20

SECTION_START = re.compile(r"## .*Software Engineering New Grad Roles")
NEXT_SECTION = re.compile(r"\n## ")
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def fetch() -> list[dict]:
    r = requests.get(RAW_URL, timeout=TIMEOUT)
    r.raise_for_status()
    text = r.text

    start_m = SECTION_START.search(text)
    if not start_m:
        return []
    section_start = start_m.end()
    next_m = NEXT_SECTION.search(text, section_start)
    section = text[section_start: next_m.start() if next_m else len(text)]

    out = []
    last_company = None
    for row_m in ROW_RE.finditer(section):
        cells = CELL_RE.findall(row_m.group(1))
        if len(cells) < 4:
            continue
        company_cell, title_cell, location_cell, apply_cell = cells[0], cells[1], cells[2], cells[3]
        age_days = parse_age_days(strip_tags(cells[4])) if len(cells) > 4 else None

        company_text = strip_tags(company_cell)
        if company_text in ("↳", "") :
            company = last_company
        else:
            company = company_text
        if not company:
            continue
        last_company = company

        title = strip_tags(title_cell)
        location = strip_tags(location_cell)
        raw_url = first_href(apply_cell)
        if not raw_url or not title:
            continue
        url = clean_url(raw_url)

        out.append({
            "id": url,
            "company": company,
            "title": title,
            "location": location,
            "url": url,
            "age_days": age_days,
            "source": "SimplifyJobs/New-Grad-Positions",
        })
    return out
