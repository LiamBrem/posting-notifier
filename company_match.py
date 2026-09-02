"""
Shared company-name matching, used by every tier that has to check "is
this job actually from one of our target companies" against a company
name string that didn't come from our own company_slug lookup (JobSpy's
search results, the backup repos' free-text company column).

Without this check, JobSpy's own search noise (a staffing firm's listing
that happens to mention a target company) or a backup repo's much broader
company universe (SimplifyJobs/speedyapply track hundreds of companies,
not just ours) leaks into notifications for companies never asked for.
"""
import json
import re

COMPANIES_PATH = "companies.json"

# Company names Indeed/LinkedIn/the backup repos actually use, when they
# differ from companies.json. Add to this as false-negatives turn up.
ALIASES = {
    "ByteDance": ["TikTok", "ByteDance"],
    "X": ["X", "Twitter"],
    "Meta": ["Meta", "Facebook"],
    "D.E. Shaw": ["D.E. Shaw", "DE Shaw"],
    "Hudson River Trading": ["Hudson River Trading", "HRT"],
    "JPMC": ["JPMorgan Chase", "JPMorganChase", "JPMC"],
    "IMC Trading": ["IMC Trading", "IMC"],
}


def _load_target_companies() -> list[str]:
    try:
        with open(COMPANIES_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def _contains_sublist(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(
        haystack[i:i + len(needle)] == needle
        for i in range(len(haystack) - len(needle) + 1)
    )


def company_matches(company_field, target: str) -> bool:
    """company_field: whatever free-text company name a source returned.
    target: one specific company from companies.json to check it against.

    Matches on whole word-tokens, not raw substrings — a raw substring
    check would make short company names like "X", "Box", "IBM" false-
    positive match against unrelated names that merely contain those
    letters (e.g. target "Box" would substring-match "Roblox" or "Xbox";
    target "X" would match "Nutanix"). Tokenizing first and requiring a
    contiguous whole-token match avoids that while still letting a
    multi-word alias match as part of a longer field and vice versa."""
    if not isinstance(company_field, str) or not company_field.strip():
        return False
    field_tokens = _tokens(company_field)
    for alias in ALIASES.get(target, [target]):
        alias_tokens = _tokens(alias)
        if _contains_sublist(field_tokens, alias_tokens) or _contains_sublist(alias_tokens, field_tokens):
            return True
    return False


def matches_any_target(company_field, targets: list[str] | None = None) -> str | None:
    """Checks company_field against every company in companies.json (or an
    explicit `targets` list, mainly for tests). Returns the matched target
    company's canonical name from companies.json, or None if it isn't one
    of ours — this is what keeps a backup-repo row for e.g. "Booz Allen"
    or "Raytheon" from notifying when they're not on the target list."""
    if targets is None:
        targets = _load_target_companies()
    for target in targets:
        if company_matches(company_field, target):
            return target
    return None
