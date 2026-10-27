"""
Parses the markdown pipe-tables in speedyapply/2027-SWE-College-Jobs'
NEW_GRAD_USA.md (FAANG+, Quant, and Other sections all share the shape
Company | Position | Location | [Salary] | Posting | Age).
"""
import re

from .common import strip_tags, first_href, pipe_cells, job

NAME = REPO = "speedyapply/2027-SWE-College-Jobs"
BRANCH = "main"
PATH = "NEW_GRAD_USA.md"

# Real data rows start with a company link; header/separator rows don't.
ROW_RE = re.compile(r'^\|\s*<a href="[^"]*"><strong>.*\|\s*$', re.M)


def parse(text: str) -> list[dict]:
    out = []
    for line in ROW_RE.findall(text):
        cells = pipe_cells(line)
        if len(cells) < 4:
            continue
        company, title = strip_tags(cells[0]), strip_tags(cells[1])
        apply_cell = next((c for c in cells if 'alt="Apply"' in c), "")
        raw_url = first_href(apply_cell)
        if company and title and raw_url:
            out.append(job(NAME, company, title, strip_tags(cells[2]), raw_url))
    return out

