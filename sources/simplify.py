"""
Parses the HTML job table in SimplifyJobs/New-Grad-Positions' README.md,
scoped to the "Software Engineering New Grad Roles" section (the repo
also lists PM, Data Science, Quant, and Hardware roles).
"""
import re

from .common import strip_tags, first_href, job

NAME = REPO = "SimplifyJobs/New-Grad-Positions"
BRANCH = "dev"
PATH = "README.md"

SECTION_START = re.compile(r"## .*Software Engineering New Grad Roles")
NEXT_SECTION = re.compile(r"\n## ")
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def parse(text: str) -> list[dict]:
    start_m = SECTION_START.search(text)
    if not start_m:
        raise ValueError("Simplify SWE section missing; source format may have changed")
    next_m = NEXT_SECTION.search(text, start_m.end())
    section = text[start_m.end(): next_m.start() if next_m else len(text)]

    out = []
    last_company = None
    for row_m in ROW_RE.finditer(section):
        cells = CELL_RE.findall(row_m.group(1))
        if len(cells) < 4:
            continue
        company = strip_tags(cells[0])
        # "↳" rows are additional roles at the company in the row above
        if company in ("↳", ""):
            company = last_company
        if not company:
            continue
        last_company = company
        title = strip_tags(cells[1])
        raw_url = first_href(cells[3])  # closed rows have 🔒 instead of a link
        if title and raw_url:
            out.append(job(NAME, company, title, strip_tags(cells[2]), raw_url))
    return out

