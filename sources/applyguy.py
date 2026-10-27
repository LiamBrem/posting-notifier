"""
Parses the markdown table in ApplyGuy/2027-New-Grad-Jobs' README.md:
| Company | Role | Location | Posted | Actions |
Actions holds an applyguy.ai redirect and a "View original listing" link;
the original listing is preferred since it's the employer's own URL.
"""
import re

from .common import strip_tags, pipe_cells, job

NAME = REPO = "ApplyGuy/2027-New-Grad-Jobs"
BRANCH = "main"
PATH = "README.md"

ORIGINAL_RE = re.compile(r"\[!\[View original listing\][^\]]*\]\((https?://[^)\s]+)\)")
ANY_LINK_RE = re.compile(r"\]\((https?://[^)\s]+)\)")


def parse(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if not line.startswith("| ") or "](http" not in line:
            continue
        cells = pipe_cells(line)
        if len(cells) < 5:
            continue
        actions = cells[-1]
        m = ORIGINAL_RE.search(actions) or ANY_LINK_RE.search(actions)
        company, title = strip_tags(cells[0]), strip_tags(cells[1])
        if company and title and m:
            out.append(job(NAME, company, title, strip_tags(cells[2]), m.group(1)))
    return out

