"""
Commits and pushes updated state files after a poller run, used by all
three poll_*.yml workflows in place of raw git commands.

state/notified.json is shared across all three workflows and gets
written on every run, so a long-running job (JobSpy's full scan can take
20+ minutes) can easily have the remote move underneath it before it
pushes. A plain `git pull --rebase` handles a clean fast-forward fine,
but a REAL content conflict on that file (two workflows both touched it
during the window) makes rebase fail outright — this happened in
practice: a 22-minute JobSpy run lost a push race against two much
faster commits and the whole job errored out.

The fix: don't rely on git's textual/line-based merge for
state/notified.json, and don't merge the whole local file either — the
working tree can be stale relative to what's on the remote by the time a
long job finishes (someone could have deliberately removed an entry on
the remote in the meantime; a whole-file union would silently resurrect
it, since it can only ever add keys, never honor a removal). Instead:
merge just THIS run's own delta of newly-added keys
(state/.notified_delta.json, written by dedup.py) onto a freshly-fetched
copy of the remote file. That's always correct regardless of how stale
the rest of the working tree's copy is, and commits fresh on top of the
latest remote each retry (no rebase needed).

Usage:
    python3 sync_state.py "<commit message>" state/seen.json state/notified.json
"""
import json
import random
import subprocess
import sys
import time

MAX_ATTEMPTS = 6
NOTIFIED_PATH = "state/notified.json"
NOTIFIED_DELTA_PATH = "state/.notified_delta.json"


def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True)


def sync_notified_with_remote_head():
    """Assumes HEAD has just been reset to origin/main. Rewrites
    state/notified.json as (HEAD's version) union (this run's own delta
    of newly-added keys) — never the stale working-tree copy beyond
    that delta, so a long-running job can't resurrect a remotely-removed
    entry just because its own checkout predates the removal."""
    remote = run("git", "show", f"HEAD:{NOTIFIED_PATH}", check=False)
    remote_data = {}
    if remote.returncode == 0:
        try:
            remote_data = json.loads(remote.stdout)
        except json.JSONDecodeError:
            remote_data = {}

    try:
        with open(NOTIFIED_DELTA_PATH) as f:
            delta = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        delta = {}

    merged = {**remote_data, **delta}
    with open(NOTIFIED_PATH, "w") as f:
        json.dump(merged, f, indent=2, sort_keys=True)


def main():
    message = sys.argv[1]
    files = sys.argv[2:]
    if not files:
        print("no files given, nothing to do")
        return

    run("git", "config", "user.name", "posting-notifier-bot")
    run("git", "config", "user.email", "actions@users.noreply.github.com")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        run("git", "fetch", "origin", "main", check=False)
        # moves HEAD to the latest remote without touching the working
        # tree/index, so our freshly-written state files on disk survive
        run("git", "reset", "--soft", "origin/main", check=False)

        if NOTIFIED_PATH in files:
            sync_notified_with_remote_head()

        run("git", "add", *files)
        diff = run("git", "diff", "--cached", "--quiet", check=False)
        if diff.returncode == 0:
            print("nothing to commit")
            return

        run("git", "commit", "-m", message)
        push = run("git", "push", check=False)
        if push.returncode == 0:
            print(f"pushed successfully (attempt {attempt})")
            return

        print(f"[attempt {attempt}] push rejected, retrying: {push.stderr.strip()}")
        time.sleep(random.uniform(1, 5))

    print(f"failed to push after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
