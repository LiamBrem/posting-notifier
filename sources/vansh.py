"""
Parses the markdown table in vanshb03/New-Grad-2027's README.md:
| **Company** | Role | Location | <a href=...>Apply</a> | Date Posted |
Closed rows have 🔒 in place of the apply link.
"""
from .common import strip_tags, first_href, pipe_cells, job

NAME = REPO = "vanshb03/New-Grad-2027"
BRANCH = "dev"
PATH = "README.md"


def parse(text: str) -> list[dict]:
    out = []
    last_company = None
    for line in text.splitlines():
        if not line.startswith("| ") or 'alt="Apply"' not in line:
            continue
        cells = pipe_cells(line)
        if len(cells) < 4:
            continue
        company = strip_tags(cells[0])
        if company in ("↳", ""):
            company = last_company
        if not company:
            continue
        last_company = company
        title = strip_tags(cells[1])
        raw_url = first_href(cells[3])
        if title and raw_url:
            out.append(job(NAME, company, title, strip_tags(cells[2]), raw_url))
    return out

