#!/usr/bin/env python3
"""Fill the `founders` column of data/companies.csv with each organisation's founders/leaders.

Uses Exa's public people search (no LinkedIn login). A person is only accepted when
their current role is founder / co-founder / CEO / executive director AND it is tied
to this organisation: their profile links the org's LinkedIn page, or their headline
names the org. Rows that already have founders are left alone, so you can correct a
row by hand and re-run safely.

  python3 find_founders.py            # fill blanks, print what it found
  python3 find_founders.py --dry-run  # print only
"""
import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from monitor import COMPANIES, EXA_URL, aliases, http_get

ROLE_RE = re.compile(r"\b(co-?\s?founder|founder|ceo|chief executive|executive director|managing trustee)\b", re.I)


def slug_of(c):
    m = re.search(r"linkedin\.com/company/([^/?#]+)", c.get("linkedin", ""))
    return m.group(1).lower() if m else None


def people(c):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "web_search_exa",
        "arguments": {"query": f"category:people founder of {aliases(c)[0]} India", "numResults": 10}}}).encode()
    raw = http_get(EXA_URL, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}, tries=2)
    msg = json.loads(next((l[5:] for l in raw.splitlines() if l.startswith("data:")), raw))
    text = "\n".join(p.get("text", "") for p in msg.get("result", {}).get("content", []))
    return re.split(r"\n(?=Title: )", text)


def founders_of(c):
    slug, names = slug_of(c), [a.lower() for a in aliases(c)]
    found = []
    for block in people(c):
        name = re.search(r"^Title: (.+)", block, re.M)
        url = re.search(r"^URL: (\S+linkedin\.com/in/\S+)", block, re.M)
        if not name or not url:
            continue
        name = re.sub(r"\s*[-|–].*$", "", name.group(1)).strip()
        lines = [l.strip() for l in block.split("Highlights:", 1)[-1].splitlines() if l.strip()]
        headline = lines[1] if len(lines) > 1 else ""
        # A current founder-type role at this org: in the headline, or in an experience entry
        # that links the org's LinkedIn page or names it
        tied = ROLE_RE.search(headline) and any(n in headline.lower() for n in names)
        for i, l in enumerate(lines):
            if tied:
                break
            if "(Current)" in l and ROLE_RE.search(l) and (
                    (slug and f"/company/{slug}" in l.lower()) or any(n in l.lower() for n in names)):
                tied = True
        if tied and name.lower() not in (f.lower() for f in found) and len(name.split()) >= 2:
            found.append(name)
    return found[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    fields = list(rows[0].keys())
    if "founders" not in fields:
        fields.insert(fields.index("aliases") + 1, "founders")
        for r in rows:
            r["founders"] = ""
    todo = [r for r in rows if not r["founders"]]
    print(f"Looking up founders for {len(todo)} organisations…", file=sys.stderr)

    def safe(c):
        try:
            return founders_of(c)
        except Exception as e:
            print(f"  ! {c['name']}: {e}", file=sys.stderr)
            return []

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(safe, todo))
    hits = 0
    for r, names in zip(todo, results):
        r["founders"] = "|".join(names)
        hits += bool(names)
        print(f"  {r['name']:<45} → {', '.join(names) or 'none found (add by hand)'}")
    print(f"Found founders for {hits} of {len(todo)}.", file=sys.stderr)
    if not args.dry_run:
        with open(COMPANIES, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
