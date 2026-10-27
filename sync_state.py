"""
Commits and pushes the poller's updated state files from CI.

The workflow's concurrency group means this job is the only writer of
state/, so on a push race (someone pushed code meanwhile) it's enough to
move HEAD onto the latest remote and commit our state files on top — no
rebase, and no content merge of state needed.

Usage:
    python3 sync_state.py "<commit message>" state/seen.json state/notified.json
"""
import random
import subprocess
import sys
import time

MAX_ATTEMPTS = 6


def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True)


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
