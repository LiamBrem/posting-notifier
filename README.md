# posting-notifier

Watches four community-maintained new-grad job repos and sends an
[ntfy.sh](https://ntfy.sh) push for each row added since the last poll:

- [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions)
  (Software Engineering section only)
- [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md)
  (`NEW_GRAD_USA.md`)
- [vanshb03/New-Grad-2027](https://github.com/vanshb03/New-Grad-2027)
- [ApplyGuy/2027-New-Grad-Jobs](https://github.com/ApplyGuy/2027-New-Grad-Jobs)

There's no company list or title filtering: whatever the repos add, you
hear about it.

## Cross-repo cooldown

The repos overlap heavily, so the same role usually lands in several of
them over a day or two. Once a role is notified, it won't be notified
again for `COOLDOWN_DAYS` (default 3), whichever repo it shows up in.
A role is identified by:

- **company + title**, normalized so cosmetic differences collide:
  case, punctuation, emoji markers, word order, company suffixes
  ("Inc.", "Industries", ...), and title decoration ("New Grad 2027:",
  "Early Career", "I", "(Onsite)", years); or
- **the same apply URL** as something already notified, which catches
  repos that word the same title differently.

Rows that turn up in several repos within one poll become a single
notification listing every repo it came from.

## Layout

- `sources/` — one parser per repo; each returns
  `{id, company, title, location, url, source}` rows. Closed (🔒) rows are
  skipped.
- `poller.py` — fetches every source, diffs against `state/seen.json`,
  applies the cooldown against `state/notified.json`, sends.
- `notify.py` — sends the ntfy push.
- `.github/workflows/poll.yml` — runs `poller.py` and commits state back
  via `sync_state.py`. Triggered every 5 minutes by an external cron (below).
- `runner.py` + `Dockerfile` — always-on alternative to Actions (polls
  every 60s; mount a volume at `/app/state`). Don't run both at once:
  they'd keep separate state and double-notify.

Each poll first checks every repo's head commit (an ETag'd GitHub API
call that's ~free when nothing changed) and only downloads and parses the
repos that moved, fetching the file at that exact commit to dodge
raw.githubusercontent.com's 5-minute cache. A no-change poll takes ~1s.

## Triggering every 5 minutes

GitHub's `schedule:` trigger is best-effort and in practice fired only
every 3–6 hours for this repo, so a free external cron (e.g.
[cron-job.org](https://cron-job.org)) calls the dispatch API instead:

1. Create a fine-grained GitHub token scoped to only this repository with
   **Actions: Read and write**.
2. Add a cron job, every 5 minutes:
   - `POST https://api.github.com/repos/LiamBrem/posting-notifier/actions/workflows/poll.yml/dispatches`
   - Headers: `Authorization: Bearer <token>`,
     `Accept: application/vnd.github+json`
   - Body: `{"ref": "main"}` — a `204` response means it queued.

The `schedule:` trigger stays as a fallback in case the external cron
stops. The repo is private, so every run bills at least 1 Actions minute:
5-minute polling is ~8,600 minutes/month, over the free plan's 2,000.

## Safety valves

- **First poll of a repo** records its current rows without notifying.
  Delete `state/seen.json` (or one repo's key in it) to reseed.
- **More than 40 new rows from one repo in one poll** is treated as the
  repo being reformatted or re-linked, not as 40 new jobs: those rows are
  recorded silently.
- **A failed send** leaves its rows unseen, so the next poll retries them.
- **A repo that fails to fetch or parses to zero rows** keeps its previous
  state; the run exits non-zero so the workflow shows red.
- **GitHub API unavailable or rate-limited**: falls back to downloading
  the branch file directly. Set `GITHUB_TOKEN` when running outside
  Actions; unauthenticated API calls are capped at 60/hour.

## Running

```
pip install -r requirements.txt
NTFY_TOPIC=your-secret-topic python3 poller.py
python3 -m unittest discover -s tests
```

`NTFY_TOPIC` is a GitHub Actions secret for the workflow.
