"""Always-on scheduler: runs poller.py every 60 seconds.

Run from this repository with NTFY_TOPIC set and a durable state/ directory.
"""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from state_io import load, save

TIERS = {"repos": ("poller.py", 60, 120)}


def worker(name, stop):
    script, interval, timeout = TIERS[name]
    path = f"state/runner_{name}.json"
    health = load(path, {})
    while not stop.is_set():
        started = time.monotonic()
        health["started_at"] = datetime.now(timezone.utc).isoformat()
        save(path, health)
        try:
            result = subprocess.run([sys.executable, "-u", script], timeout=timeout)
            health["exit_code"] = result.returncode
        except subprocess.TimeoutExpired:
            health["exit_code"] = 124
        health["finished_at"] = datetime.now(timezone.utc).isoformat()
        if health["exit_code"] == 0:
            health["last_success"] = health["finished_at"]
        save(path, health)
        # No overlapping scans of the same tier, and no busy retry loop.
        stop.wait(max(5, interval - (time.monotonic() - started)))


def healthy():
    now = datetime.now(timezone.utc)
    for name in TIERS:
        value = load(f"state/runner_{name}.json", {}).get("last_success")
        if not value:
            return False
        if (now - datetime.fromisoformat(value)).total_seconds() > max(180, TIERS[name][1] * 3):
            return False
    return True


def main():
    os.chdir(Path(__file__).resolve().parent)
    if "--healthcheck" in sys.argv:
        raise SystemExit(0 if healthy() else 1)
    if not os.environ.get("NTFY_TOPIC"):
        raise SystemExit("Set NTFY_TOPIC before starting the runner")
    Path("state").mkdir(exist_ok=True)
    with open("state/runner.lock", "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another runner is already using this state directory")
        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        threads = [threading.Thread(target=worker, args=(name, stop), daemon=True) for name in TIERS]
        for thread in threads:
            thread.start()
        while not stop.wait(1):
            if any(not thread.is_alive() for thread in threads):
                raise SystemExit("A polling worker stopped unexpectedly; restart required")
        for thread in threads:
            thread.join()


if __name__ == "__main__":
    main()
