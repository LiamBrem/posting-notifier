# posting-notifier

Polls target companies' ATS APIs directly (Greenhouse, Lever, Ashby,
SmartRecruiters) every 30 minutes for new-grad US SWE postings and pushes
an [ntfy.sh](https://ntfy.sh) notification the moment a new one appears —
no daily-batch delay from aggregator repos/sites in the loop.

## How it's structured

- `companies.json` — the target company list.
- `classify.py` — auto-probes each company against all 4 ATS platforms to
  find its slug. Run this once, and again any time `companies.json` changes
  or you want to re-check the companies that came back unmatched (a company
  with zero open reqs at classify-time looks identical to a nonexistent
  slug on SmartRecruiters, so it's worth re-running periodically).
- `companies_classified.json` — output of the above: `{ats, slug, company}`
  per matched company. **This is what the poller actually reads.**
- `connectors/` — one fetch+normalize function per ATS.
- `filters.py` — new-grad + SWE + US-location matching logic. Tune the
  regexes here if you want to loosen/tighten what counts as a match.
- `poller.py` — the main loop: fetch → filter → diff against
  `state/seen.json` → notify on anything new.
- `notify.py` — sends the ntfy.sh push.
- `.github/workflows/poll.yml` — runs `poller.py` on a 30-minute cron via
  GitHub Actions and commits the updated `state/seen.json` back.
- `sources/` — parsers for the two backup GitHub repos (see below).
- `backup_poller.py` — the backup-tier loop: fetch both repos → filter →
  skip anything Tier 1 already caught → diff against
  `state/seen_backup.json` → notify.
- `.github/workflows/poll_backup.yml` — runs `backup_poller.py` hourly.
- `jobspy_poller.py` — Tier 3: scans [JobSpy](https://github.com/speedyapply/JobSpy)
  (Indeed + LinkedIn) for the companies Tier 1 can't reach directly,
  filters, diffs against `state/seen_jobspy.json`, hands matches to
  `dedup.py`.
- `.github/workflows/poll_jobspy.yml` — runs `jobspy_poller.py` every 2 hours.
- `company_match.py` — shared company-name matching (with an `ALIASES`
  table for name mismatches like ByteDance/TikTok), used by both
  `jobspy_poller.py` and `backup_poller.py` to keep notifications scoped
  to companies actually in `companies.json`.
- `dedup.py` — the cross-tier notification gate all three pollers funnel
  their matches through (see below).
- `bootstrap_dedup.py` — one-time seeding script for `state/notified.json`.
- `sync_state.py` — commits and pushes each workflow's updated state files;
  every `poll_*.yml` workflow calls this instead of raw git commands (see
  Cross-tier deduplication below for why).
- `tests/` — offline unit tests for every tier (see Testing below).

## Backup tier (GitHub repos)

Tier 1 (above) only covers 75 of the 141 target companies directly. As a
safety net, `backup_poller.py` polls two community-maintained repos that
track new-grad SWE postings broadly:

- [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)
  — parses the "Software Engineering New Grad Roles" table out of its
  README (`sources/simplify.py`).
- [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs)
  — parses `NEW_GRAD_USA.md` (`sources/speedyapply_backup.py`).

Both repos update themselves roughly daily, so this tier runs hourly —
polling faster wouldn't surface anything sooner.

**Company filter.** SimplifyJobs and speedyapply both track hundreds of
companies, way beyond `companies.json` — every row is checked against
your target list via `company_match.py` before anything else, so a
company only notifies here if it's actually one you're tracking. (This
was missing in an earlier version and caused a real incident: a single
run notified on ~38 postings, most from companies never on the list —
Booz Allen, Raytheon, Northrop Grumman, PepsiCo, and others. Fixed, with
regression tests in `tests/test_backup_poller.py` and
`tests/test_company_match.py`.)

**Backup, not a duplicate feed.** Before notifying on a row from either
repo, `backup_poller.py` also checks whether it's something Tier 1
already knows about: most rows' apply links point straight at a
Greenhouse/Lever/Ashby/SmartRecruiters URL (or a custom domain that
embeds one via `?gh_jid=`), and if that job's id is already in Tier 1's
`state/seen.json`, it's skipped — Tier 1 already caught (or will catch,
same cycle) that one directly and faster. What's left after both checks
is genuinely new information: either a company on your list outside the
75 Tier 1 covers directly (Amazon, Google, etc., for the companies that
also happen to show up in these repos), or — less commonly — a posting on
one of the 75 that slipped through Tier 1's filter wording or an API
hiccup.

Rows from these repos skip the `NEW_GRAD_RE`/`SWE_RE` keyword filters in
`filters.py` (raw ATS titles like "Software Engineer 1" often don't
literally say "new grad," and the repos have already made that call by
which file/section a row lives in) — only the US-location and
exclude-seniority filters still apply.

Run it the same way as the main poller:
```
NTFY_TOPIC=your-topic-here python3 backup_poller.py
```

## Tier 3: JobSpy (Tier-1-uncovered companies only)

`jobspy_poller.py` runs [JobSpy](https://github.com/speedyapply/JobSpy)
(the same scraping library speedyapply's own bots are built on) against
Indeed and LinkedIn, scoped to just the companies Tier 1 can't reach
directly — `uncovered_companies()` computes this fresh each run as
`companies.json` minus whatever `companies_classified.json` covers, so it
stays in sync automatically if `classify.py` ever picks up more coverage.

This used to run across all 141 companies for redundancy, but a full scan
took ~20 minutes (close to GitHub Actions' patience) for a benefit Tier 2
already provides on the covered companies without a second scraping pass.
Runs every 2 hours now rather than hourly, since it's a coverage gap-filler
rather than a speed play — for these companies, Tier 2's backup repos are
the faster path anyway. Notifications are tagged with which tier/site
caught them (e.g. `Anduril [jobspy/indeed]`) so you can tell.

This is the least precise tier: unlike Tier 1 (the company's full,
exhaustive listing) or the backup repos (pre-curated as new-grad), JobSpy
returns whatever Indeed/LinkedIn's own search ranks as relevant for
`"{company} software engineer"` — so it needs the full `filters.matches()`
check (new-grad + SWE + US-location) plus a company-name match to drop
stray results that leak in from unrelated employers (e.g. searching
"Palantir software engineer" surfaces a lot of consulting-firm listings
that just *mention* Palantir as a platform/skill — `company_matches()`
in `jobspy_poller.py` filters those out by checking the actual employer
field, not the title).

Known limitations, worth knowing before relying on this tier:
- **Google jobs was unreliable in testing** (silently returned 0 results)
  and isn't used — only Indeed + LinkedIn.
- **Recall isn't complete.** For companies whose name doubles as a common
  platform/skill reference (Palantir, Snowflake, Databricks, Elastic,
  Splunk, Workday, Oracle, Salesforce, ServiceNow, Tableau, MongoDB), a
  genuine posting can get buried under a wall of staffing-firm listings
  that just mention the name. Bump `RESULTS_PER_COMPANY` in
  `jobspy_poller.py` if this tier keeps missing a specific company.
- **Scraper-blocking risk.** Indeed and LinkedIn both actively work
  against scraping, and GitHub Actions runner IPs are shared/known —
  if this tier starts erroring out consistently, that's usually why. A
  self-hosted runner or a VPS with a residential-ish IP is the fix.
- **Name mismatches.** `ALIASES` in `jobspy_poller.py` covers known cases
  (ByteDance → TikTok, etc.) — add to it as you spot others.

Run it the same way as the other pollers:
```
NTFY_TOPIC=your-topic-here python3 jobspy_poller.py
```

## Cross-tier deduplication

Tier 2 and Tier 3 both cover the 66 Tier-1-uncovered companies, so there's
still real overlap between tiers even after scoping JobSpy down — plus a
role posted at multiple locations would otherwise ping once per location.
`dedup.py` is what keeps either from turning into repeat notifications:

- Each poller does its own fetch → per-source "is this id new" check →
  content/US/recency filtering, exactly as before, and ends up with a
  list of jobs that source considers new and relevant.
- Instead of notifying directly, that list goes to
  `dedup.group_and_notify()`, which groups jobs by a fuzzy `(company,
  title)` key — punctuation- and word-order-insensitive, so "Software
  Engineer, New Grad" and "New Grad Software Engineer" collapse together
  even when two different tiers report the same job with different
  wording — and consolidates every location into one notification.
- Each group is checked against `state/notified.json`, a registry shared
  by all three pollers. If any tier has ever notified for that
  `(company, title)`, every other tier stays silent on it.

Net effect: a role posted at 3 locations is 1 notification, not 3. A role
Tier 1 catches at 10:05 that JobSpy's hourly scan would also surface at
11:15 only pings once, at 10:05.

**One-time setup / after a reset:** because each tier's own `state/seen*.json`
may already have data (from before `dedup.py` existed, or from initial
testing), the very first run after adding this would otherwise treat all
of that pre-existing inventory as "new to the registry" and fire a
notification storm. Run `python3 bootstrap_dedup.py` once to seed
`state/notified.json` with everything currently matching, across all three
tiers, without sending anything — from then on, normal poller runs only
notify on genuinely new postings.

**Committing `state/notified.json` safely.** All three workflows write to
this one shared file on independent schedules, so two runs can genuinely
race — and JobSpy's run can take 15-20+ minutes, giving a wide window for
the other two (which take under a minute) to push in the meantime. A
plain `git pull --rebase` handles a clean fast-forward fine but can hit a
real textual conflict on this frequently-reformatted JSON file (this
happened in practice and broke a run). `sync_state.py` avoids it
entirely: `dedup.py` writes a `state/.notified_delta.json` alongside the
full file, listing only *this run's* newly-added entries, and
`sync_state.py` merges just that delta onto a freshly-fetched copy of the
remote file before committing — never the possibly-stale rest of the
working tree. That also means a long-running job can't accidentally
resurrect an entry someone deliberately removed on the remote while it
was mid-flight (a plain whole-file union would have).

## Coverage

Of the 141 target companies, **75 were auto-matched** to a standard ATS
(Greenhouse/Lever/Ashby/SmartRecruiters) for Tier 1 — see
`companies_classified.json`. The other 66 (Google, Meta, Amazon, Apple,
Microsoft, Netflix, Citadel, Two Sigma, D.E. Shaw, Renaissance
Technologies, Salesforce, IBM, etc.) run custom, JS-rendered career sites
that don't expose a guessable public API, so Tier 1 can't reach them
directly — Tiers 2 (backup repos) and 3 (JobSpy) are what cover this gap.
One option not yet built: manually find the Workday tenant/site slug for
the handful that use Workday
(`{tenant}.wdX.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` — a real
JSON API once you have the tenant, just not guessable from the company
name the way Greenhouse/Lever slugs are) and add a fourth direct-polling
connector for it.

## Setup

1. **Pick an ntfy topic.** Topics are public-by-obscurity on ntfy.sh — pick
   something long and random (not a real name/word combo anyone could
   guess). Subscribe to it in the [ntfy app](https://ntfy.sh/app)
   (iOS/Android/web) so it can push to your phone — on iOS, also enable
   **Instant Delivery** in the app's own Settings, or pushes will only
   sync when you open the app instead of arriving as real background
   notifications.

2. **Run locally first** to confirm it works and to seed `state/seen.json`
   (the first run bootstraps silently — it won't notify for postings that
   are already open, only ones that appear after):

   ```
   pip install -r requirements.txt
   python3 classify.py          # only needed once, or to refresh coverage
   NTFY_TOPIC=your-topic-here python3 poller.py
   NTFY_TOPIC=your-topic-here python3 backup_poller.py
   NTFY_TOPIC=your-topic-here python3 jobspy_poller.py   # scans ~66 Tier-1-uncovered companies
   ```

3. **Push to GitHub** and add the topic as a repo secret so Actions can use
   it without hardcoding it in the workflow file:

   ```
   gh repo create posting-notifier --private --source=. --push
   gh secret set NTFY_TOPIC --body "your-topic-here"
   ```

   Since the repo will contain your target company list, keep it private —
   Actions minutes aren't unlimited on a private repo, but at a 30-minute
   cadence this is well within the free tier.

4. Confirm all three workflows ran (Actions tab) and that `state/seen.json`,
   `state/seen_backup.json`, and `state/seen_jobspy.json` get committed
   back after each run.

## Tuning

- **Cadence:** edit the cron in `.github/workflows/poll.yml`. GitHub
  Actions' `schedule:` trigger is genuinely unreliable in practice, not
  just "occasionally a few minutes late" — in testing, a `*/10 * * * *`
  cron fired once in 3.5 hours. Tighter intervals seem to make it worse
  (plausibly GitHub coalescing/dropping a firing if the prior one hasn't
  finished), which is why Tier 1 runs every 30 min rather than 10. If
  even that proves unreliable, the real fix is bypassing `schedule:`
  entirely: have a free external cron service (e.g. cron-job.org) POST to
  GitHub's `repository_dispatch` API on schedule instead — API-triggered
  events don't get deprioritized the way `schedule:` evaluation does.
  That needs a `repository_dispatch:` trigger added to each workflow and
  a GitHub token (Actions-only permission, scoped to this repo) stored on
  the external service — not currently set up.
- **Filter too loose/tight:** edit `NEW_GRAD_RE`, `SWE_RE`, `EXCLUDE_RE` in
  `filters.py`. Run the scan-only check below to see what currently
  matches without touching `state/seen.json`:

  ```
  python3 -c "
  import json
  from connectors import FETCHERS
  import filters
  classified = json.load(open('companies_classified.json'))
  for key, e in classified.items():
      for j in FETCHERS[e['ats']](e['slug']):
          if filters.matches(j):
              print(e['company'], '-', j['title'], '-', j['location'])
  "
  ```
- **JobSpy tier missing a company:** bump `RESULTS_PER_COMPANY` in
  `jobspy_poller.py` (more results per search = better odds a buried
  posting shows up), or add an entry to `ALIASES` if the employer name on
  Indeed/LinkedIn differs from `companies.json`.
- **JobSpy tier erroring out / 0 results across the board:** likely
  Indeed/LinkedIn temporarily blocking the runner's IP. Re-run later, or
  move that workflow to a self-hosted runner / VPS.
- **Notification volume:** edit `MAX_AGE_DAYS` in `filters.py` (default 5).

## Age filter

All three tiers skip notifying on a posting older than `MAX_AGE_DAYS`
(default 5) — this is what keeps an evergreen req that's been open for
months, or a first-time-seen posting from a company we just started
tracking, from generating a notification. Each source's "posted" date
means something slightly different:

| Tier | Source of the date | Caveat |
|---|---|---|
| 1 (direct ATS) | Greenhouse `first_published`, Lever `createdAt`, Ashby `publishedAt`, SmartRecruiters `releasedDate` | SmartRecruiters' date is when the req was *first created*, not renewed — a genuinely still-open evergreen posting can look "old" and get skipped. |
| 2 (backup repos) | The repo's own "Age" column (`0d`, `12d`, `1mo`, ...) | The repos already compute this themselves; we just parse it. |
| 3 (JobSpy) | Indeed/LinkedIn's `date_posted` | This is when the *board* indexed it, not necessarily when the employer posted it — can lag the real posting by a bit. |

**The check fails open**: if a posting's date can't be determined at all
(missing field, unparseable format), it's treated as recent rather than
silently dropped — the goal is cutting spam from postings we can *confirm*
are stale, not risking a false negative on one we're unsure about.

Note this is a separate, later check from the seen-state diffing every
tier already does — a posting has to be both *new to us* (not in
`state/seen*.json`) and *recently posted* (per the table above) to
trigger a notification.

## Testing

```
python3 -m unittest discover -s tests -v
```

Runs offline and deterministically (no live network calls, `requests.get`/
`scrape_jobs` are mocked with synthetic fixtures shaped like real API
responses) — `.github/workflows/test.yml` runs this on every push. Two
design choices make this actually catch real bugs rather than just
exercising code paths:

- **Relative dates.** `tests/fixtures.py` computes every date relative to
  `datetime.now()` at test-run time ("2 days ago", "30 days ago") instead
  of hardcoding a date — a hardcoded fixture would silently drift out of
  (or into) the 5-day recency window as real time passes, which is exactly
  the flakiness risk with testing anything age-filter-related against a
  fixed date.
- **Fixtures bundle a full decoy set.** Every connector/source test fires
  one genuine US new-grad SWE posting alongside an intern, a senior role,
  a non-US location, and a stale (>5d) posting *of the same genuine role*,
  then asserts the filtered result is exactly the one genuine posting —
  not just "the parser doesn't crash." This is what "nothing slips
  through" actually gets tested against: a parsing bug (wrong field name)
  and a filtering bug (regex gap) both fail the same assertion. This
  suite already caught one real gap this way — `NEW_GRAD_RE` didn't match
  "New College Graduate" phrasing (a real Nvidia listing uses exactly
  that), fixed in `filters.py`.

What's covered: all 4 Tier-1 connectors, both backup-repo parsers
(including section-scoping and the `↳`-carries-company-forward quirk),
`jobspy_poller.py`'s company-name matching and NaN/NaT date handling,
`sources/common.py`'s URL cross-referencing (including the `gh_jid`
custom-domain case), and `dedup.py`'s grouping/registry behavior
end-to-end (multi-location collapsing, cross-tier same-role suppression,
bootstrap mode). What's *not* covered: the live APIs/pages themselves —
these tests verify "given a response shaped like the real one, does the
pipeline behave correctly," not "is the real API still shaped that way
today." If a source changes its response shape, these tests won't catch
it — only a live run (or `classify.py` re-run) will.
