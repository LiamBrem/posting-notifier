"""
Probes each company in companies.json against the public read APIs of the
common ATS platforms (Greenhouse, Lever, Ashby, SmartRecruiters) and records
which platform + slug actually returns job data for it.

Run once (and re-run whenever companies.json changes):
    python3 classify.py

Writes companies_classified.json:
    {
      "andurilindustries": {"company": "Anduril", "ats": "greenhouse", "slug": "andurilindustries"},
      ...
    }
and prints a list of companies nothing matched for, which need either a
manual slug override (see OVERRIDES below) or fall in the "custom site"
bucket (mega-caps like Google/Meta/Amazon almost always do).
"""
import json
import re
import sys
import concurrent.futures as cf

import requests

TIMEOUT = 6
WORKERS = 24

# Manual slug hints for companies where the obvious slug guess is wrong.
# Add to this as classify.py's "UNMATCHED" report turns up false negatives.
OVERRIDES = {
    "Anduril": {"greenhouse": ["andurilindustries"]},
    "D.E. Shaw": {"greenhouse": ["deshaw"]},
    "Hudson River Trading": {"greenhouse": ["hudsonrivertrading", "hrt"]},
    "Jane Street": {"greenhouse": ["janestreet"]},
    "Scale AI": {"greenhouse": ["scaleai"]},
    "Hugging Face": {"greenhouse": ["huggingface"]},
    "JPMC": {"greenhouse": ["jpmorganchase", "jpmorgan"]},
    "Blackrock": {"greenhouse": ["blackrock"]},
    "IMC Trading": {"greenhouse": ["imc", "imctrading"]},
    "Five Rings": {"greenhouse": ["fiveringstrading", "fiverings"]},
    "Radix Trading": {"greenhouse": ["radixtrading", "radix"]},
    "Akuna Capital": {"greenhouse": ["akunacapital", "akuna"]},
    "Voleon": {"greenhouse": ["thevoleongroup", "voleon"]},
    "Flow Traders": {"greenhouse": ["flowtraders"]},
    "Renaissance Technologies": {"greenhouse": ["rentec", "renaissancetechnologies"]},
}


def slug_variants(name: str) -> list[str]:
    base = name.lower()
    cleaned = re.sub(r"[.,'’]", "", base)
    no_space = re.sub(r"\s+", "", cleaned.strip())
    hyphen = re.sub(r"\s+", "-", cleaned.strip())
    variants = {no_space, hyphen}
    # also try dropping generic suffixes
    for suffix in (" trading", " capital", " technologies", " industries", " inc"):
        if cleaned.strip().endswith(suffix.strip()):
            trimmed = cleaned.strip()[: -len(suffix)].strip()
            variants.add(re.sub(r"\s+", "", trimmed))
            variants.add(re.sub(r"\s+", "-", trimmed))
    return [v for v in variants if v]


def probe_greenhouse(slug: str) -> bool:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        timeout=TIMEOUT,
    )
    return r.status_code == 200 and isinstance(r.json().get("jobs"), list)


def probe_lever(slug: str) -> bool:
    r = requests.get(
        f"https://api.lever.co/v0/postings/{slug}?mode=json",
        timeout=TIMEOUT,
    )
    return r.status_code == 200 and isinstance(r.json(), list)


def probe_ashby(slug: str) -> bool:
    r = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        return False
    try:
        return isinstance(r.json().get("jobs"), list)
    except ValueError:
        return False


def probe_smartrecruiters(slug: str) -> bool:
    # NB: this endpoint returns HTTP 200 with totalFound:0 for ANY slug,
    # real or fake, so a 200 status alone is not proof the company exists.
    # Require at least one open posting as evidence the slug is real.
    r = requests.get(
        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        return False
    try:
        return r.json().get("totalFound", 0) > 0
    except ValueError:
        return False


PROBES = {
    "greenhouse": probe_greenhouse,
    "lever": probe_lever,
    "ashby": probe_ashby,
    "smartrecruiters": probe_smartrecruiters,
}


def classify_company(name: str):
    candidates = slug_variants(name)
    overrides = OVERRIDES.get(name, {})
    # merge override slugs in front so they're tried first
    ordered_ats = list(PROBES.keys())
    for ats, slugs in overrides.items():
        candidates = slugs + candidates

    for ats in ordered_ats:
        probe = PROBES[ats]
        tried = overrides.get(ats, []) + candidates
        seen = set()
        for slug in tried:
            if slug in seen:
                continue
            seen.add(slug)
            try:
                if probe(slug):
                    return {"company": name, "ats": ats, "slug": slug}
            except requests.RequestException:
                continue
    return None


def main():
    companies = json.load(open("companies.json"))
    results = {}
    unmatched = []

    with cf.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(classify_company, name): name for name in companies}
        for i, fut in enumerate(cf.as_completed(futures), 1):
            name = futures[fut]
            match = fut.result()
            if match:
                key = f"{match['ats']}:{match['slug']}"
                results[key] = match
                print(f"[{i}/{len(companies)}] {name:30s} -> {match['ats']:16s} {match['slug']}")
            else:
                unmatched.append(name)
                print(f"[{i}/{len(companies)}] {name:30s} -> NO MATCH")

    with open("companies_classified.json", "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    print(f"\nMatched {len(results)}/{len(companies)} companies.")
    print(f"Wrote companies_classified.json")
    if unmatched:
        print(f"\n{len(unmatched)} unmatched (likely custom career sites, or need a slug override):")
        for name in unmatched:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
