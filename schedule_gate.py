#!/usr/bin/env python3
"""Decide what this wake-up should do, so a skipped GitHub schedule is caught up.

GitHub's cron is best effort: runs can start hours late or not at all. The workflow wakes
often (and an outside alarm such as cron-job.org can trigger it with mode=auto) and asks:
  full  - it's 08:00 IST or later and today's full check (with LinkedIn pages) hasn't run
  news  - the latest of the fixed check times (02:00, 14:00, 20:00 IST) has passed since the last check
  skip  - nothing due
Checks stay on the fixed times even when one runs late: a late 08:00 check doesn't push 14:00 back.

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
CHECK_HOURS = (2, 8, 14, 20)  # IST; 08:00 is the full check, the others news checks


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
    # The most recent fixed check time at or before now (it may be yesterday's 20:00)
    local = now.astimezone(IST)
    slot = max(local.replace(hour=h, minute=0, second=0, microsecond=0) - timedelta(days=d)
               for h in CHECK_HOURS for d in (0, 1)
               if local.replace(hour=h, minute=0, second=0, microsecond=0) - timedelta(days=d) <= local)
    last = state.get("last_run_utc")
    if not last or datetime.fromisoformat(last) < slot:
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
