#!/usr/bin/env python3
"""Decide what this hourly wake-up should do, so a skipped GitHub schedule is caught up.

GitHub's cron is best effort: runs can start hours late or not at all. The workflow
wakes every hour and asks this script:
  full  - it's 08:00 IST or later and today's full check (with LinkedIn pages) hasn't run
  news  - 6+ hours since the last check of any kind
  skip  - nothing due

  python3 schedule_gate.py decide        # prints full | news | skip
  python3 schedule_gate.py record full   # after a successful run
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "run_state.json")
IST = timezone(timedelta(hours=5, minutes=30))
FULL_AT_HOUR = 8       # IST
NEWS_EVERY_HOURS = 6


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def decide(now=None):
    now = now or datetime.now(timezone.utc)
    state = load()
    today = now.astimezone(IST).strftime("%Y-%m-%d")
    if now.astimezone(IST).hour >= FULL_AT_HOUR and state.get("last_full_date") != today:
        return "full"
    if now.astimezone(IST).hour == FULL_AT_HOUR - 1 and state.get("last_full_date") != today:
        return "skip"  # the full check is under an hour away and covers the news too
    last = state.get("last_run_utc")
    if not last or now - datetime.fromisoformat(last) >= timedelta(hours=NEWS_EVERY_HOURS) - timedelta(minutes=10):
        return "news"
    return "skip"


def record(kind, now=None):
    now = now or datetime.now(timezone.utc)
    state = load()
    state["last_run_utc"] = now.isoformat(timespec="seconds")
    if kind == "full":
        state["last_full_date"] = now.astimezone(IST).strftime("%Y-%m-%d")
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["decide"]:
        print(decide())
    elif sys.argv[1:2] == ["record"] and len(sys.argv) == 3:
        record(sys.argv[2])
    else:
        sys.exit(__doc__)
