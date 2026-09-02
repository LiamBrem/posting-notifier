"""
One-time (or one-off, after a reset) seeding step for the cross-tier
notified registry (state/notified.json).

Why this exists: each tier's own per-source seen state (state/seen.json,
seen_backup.json, seen_jobspy.json) already existed before dedup.py was
introduced, already populated with whatever's currently open. Without this
script, the first real run of each poller after adding dedup.py would
treat all of that pre-existing, currently-open matching inventory as
"new" (since it's new to state/notified.json specifically) and fire a
notification storm — exactly the spam this feature exists to prevent.

Run this once when first adding dedup.py to an already-running setup (or
any time you intentionally reset state/notified.json) to mark everything
currently matching as already-notified, with nothing actually sent. Every
run after this only notifies on genuinely new postings going forward.

    python3 bootstrap_dedup.py
"""
import dedup
import poller
import backup_poller
import jobspy_poller


def main():
    print("Collecting current matches from all three tiers (no notifications will be sent)...")
    matches = []
    matches += poller.collect_matches()
    matches += backup_poller.collect_matches()
    matches += jobspy_poller.collect_matches()

    sent = dedup.group_and_notify(matches, bootstrap=True)
    assert sent == 0, "bootstrap mode should never send"

    notified = dedup.load_notified()
    print(f"Seeded state/notified.json with {len(notified)} role(s) across all tiers.")
    print("From here on, only genuinely new postings will trigger a notification.")


if __name__ == "__main__":
    main()
