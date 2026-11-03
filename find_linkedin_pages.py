#!/usr/bin/env python3
"""Fill the `linkedin` column of data/companies.csv for organisations that don't have one.

Looks for a linkedin.com/company/... link on the organisation's website (most sites
link it in the header or footer), then checks the page title on LinkedIn names the
organisation. Rows that already have a LinkedIn URL are left alone, so you can fix a
wrong match by hand and re-run safely.

  python3 find_linkedin_pages.py            # fill blanks, print what it found
  python3 find_linkedin_pages.py --dry-run  # print only
"""
import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from monitor import COMPANIES, EXA_URL, aliases, http_get, linkedin_fetch

LINK_RE = re.compile(r'linkedin\.com/(?:company|school|showcase)/([A-Za-z0-9_%.\-]+)', re.I)
SKIP = {"linkedin", "company", "school", "showcase"}


def words(s):
    return set(re.findall(r"[a-z0-9]{3,}", s.lower())) - {"the", "and", "foundation", "india", "trust", "for"}


def candidates_from_site(site):
    if not site:
        return []
    try:
        page = http_get(site, tries=1)
    except Exception:
        return []
    found = []
    for slug in LINK_RE.findall(page):
        slug = slug.strip(".").lower()
        if slug not in SKIP and slug not in found:
            found.append(slug)
    return found


def page_title(slug):
    """'Khushi Baby' for a live public page, else None."""
    try:
        page = linkedin_fetch(f"https://www.linkedin.com/company/{slug}/")
    except Exception:
        return None
    m = re.search(r"<title>([^<|]+)\|\s*LinkedIn", page)
    return m.group(1).strip() if m else None


def guessed_slugs(c):
    out = []
    for a in aliases(c) + [c["name"]]:
        base = re.sub(r"\(.*?\)", "", a).lower().replace("&", "and")
        parts = re.findall(r"[a-z0-9]+", base)
        if parts:
            out += ["-".join(parts), "".join(parts)]
    return list(dict.fromkeys(out))[:4]


def slugs_from_exa(c):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "web_search_exa",
        "arguments": {"query": f"category:company {aliases(c)[0]} India LinkedIn company page", "numResults": 8}}}).encode()
    try:
        raw = http_get(EXA_URL, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}, tries=1)
    except Exception:
        return []
    return list(dict.fromkeys(s.lower() for s in LINK_RE.findall(raw)))[:4]


def matches(c, title):
    # The page must share a distinctive word with one of the org's names; sites also link
    # funders' and website builders' pages, and guessed slugs can belong to someone else
    return any(words(title) & words(a) for a in aliases(c) + [c["name"]])


def resolve(c):
    tried = set()
    for source in (lambda: candidates_from_site(c["website"]), lambda: guessed_slugs(c), lambda: slugs_from_exa(c)):
        for slug in source():
            if slug in tried or slug in SKIP:
                continue
            tried.add(slug)
            title = page_title(slug)
            if title and matches(c, title):
                return f"https://www.linkedin.com/company/{slug}/", title
    return "", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    todo = [r for r in rows if not r["linkedin"]]
    print(f"{len(todo)} organisations without a LinkedIn page; checking their websites…", file=sys.stderr)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(resolve, todo))
    found = 0
    for r, (url, title) in zip(todo, results):
        if url:
            found += 1
            r["linkedin"] = url
            print(f"  {r['name']:<45} → {url}  ({title})")
        else:
            print(f"  {r['name']:<45} → not found (add it by hand)")
    print(f"Found {found} of {len(todo)}.", file=sys.stderr)
    if not args.dry_run:
        with open(COMPANIES, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
