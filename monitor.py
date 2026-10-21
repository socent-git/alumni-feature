#!/usr/bin/env python3
"""Watch ~130 organisations for news, awards/recognition, LinkedIn posts and
website updates, and post anything new to Slack.

Free sources only, no logins, no API keys:
  - Google News RSS   (news articles)
  - Bing News RSS     (second news source / fallback)
  - Exa public MCP    (public LinkedIn posts)
  - Org website RSS   (blog/news posts the org publishes itself)

Usage:
  python monitor.py                 # normal run (posts to Slack if SLACK_WEBHOOK_URL is set)
  python monitor.py --dry-run       # print what would be posted, don't save state
  python monitor.py --only "Khushi Baby" --dry-run
"""
import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
COMPANIES = os.path.join(ROOT, "data", "companies.csv")
SEEN = os.path.join(ROOT, "data", "seen.json")
UPDATES = os.path.join(ROOT, "data", "updates.csv")
UA = "Mozilla/5.0 (compatible; org-update-monitor/1.0)"
EXA_URL = "https://mcp.exa.ai/mcp"
JUNK_TITLE = re.compile(r'^(tags?|category|categories|author|topics?|archives?)\s*:|^"?[a-z0-9-]+"?$', re.I)

AWARD_RE = re.compile(
    r"\b(award(s|ed|ee)?|wins?|won|winners?|recogni[sz](ed|es|tion)|honou?r(ed|s)?|felicitat\w*|"
    r"finalists?|shortlist\w*|fellow(s|ship)?|prizes?|grants?|selected|named (among|in|to|as)|"
    r"\d+ under \d+|special mention|top \d+|cohort|accelerator|ranked|medals?|troph(y|ies)|accolades?|laurels?|"
    r"funding|raises?|raised|backed by)\b",
    re.I,
)


# ---------- helpers ----------

def http_get(url, headers=None, data=None, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # network errors, 429s, 5xx
            last = e
            time.sleep(2 ** (i + 1))
    raise last


def clean(text):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_feed(xml_text):
    """RSS 2.0 or Atom -> list of {title, url, published, summary, source}."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError:
        return []
    items = []
    for it in root.iter("item"):
        items.append({
            "title": clean(it.findtext("title")),
            "url": (it.findtext("link") or "").strip(),
            "published": parse_date(it.findtext("pubDate")),
            "summary": clean(it.findtext("description")),
            "source": clean(it.findtext("source")),
        })
    atom = "{http://www.w3.org/2005/Atom}"
    for e in root.iter(atom + "entry"):
        link = e.find(atom + "link")
        items.append({
            "title": clean(e.findtext(atom + "title")),
            "url": link.get("href", "") if link is not None else "",
            "published": parse_date(e.findtext(atom + "published") or e.findtext(atom + "updated")),
            "summary": clean(e.findtext(atom + "summary") or e.findtext(atom + "content")),
            "source": "",
        })
    return items


def aliases(c):
    return [a.strip() for a in c["aliases"].split("|") if a.strip()]


def mentions(c, text, context_text=None):
    """True if text names the org and, for generic names, context_text has a context word."""
    t = text.lower()
    if not any(re.search(r"(?<![a-z0-9])" + re.escape(a.lower()) + r"(?![a-z0-9])", t) for a in aliases(c)):
        return False
    ctx = [w for w in c["context"].split("|") if w]
    ct = (context_text or text).lower()
    return not ctx or any(w.lower() in ct for w in ctx)


def or_query(c):
    return " OR ".join(f'"{a}"' for a in aliases(c))


# ---------- sources ----------

def google_news(c, days):
    q = f"({or_query(c)}) when:{days}d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    return [dict(i, via="Google News") for i in parse_feed(http_get(url))]


def bing_news(c, days):
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": or_query(c), "format": "rss", "qft": 'interval="8"'})  # interval 8 = past week
    items = parse_feed(http_get(url))
    for i in items:
        real = urllib.parse.parse_qs(urllib.parse.urlparse(i["url"]).query).get("url")
        if real:
            i["url"] = real[0]
    return [dict(i, via="Bing News") for i in items]


def exa_linkedin(c, days):
    name = aliases(c)[0]
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "web_search_exa", "arguments": {
            "query": f"Recent LinkedIn post by {name} (Indian non-profit / social enterprise) sharing news, an award or recognition",
            "objective": f"Rank LinkedIn posts published by or about the organisation '{name}' in the last {days} days first.",
            "numResults": 10,
        }},
    }).encode()
    raw = http_get(EXA_URL, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    payload = next((l[5:].strip() for l in raw.splitlines() if l.startswith("data:")), raw)
    msg = json.loads(payload)
    if "error" in msg:
        raise RuntimeError(msg["error"].get("message", "Exa error"))
    text = "\n".join(p.get("text", "") for p in msg["result"]["content"])
    items = []
    for block in re.split(r"\n(?=Title: )", text):
        url = re.search(r"^URL: (\S+)", block, re.M)
        if not url or not re.search(r"linkedin\.com/(posts|pulse|feed/update)/", url.group(1)):
            continue  # skip profile pages; keep posts and articles
        pub = re.search(r"^Published: (\S+)", block, re.M)
        title = re.search(r"^Title: (.*)", block, re.M)
        body_text = clean(block.split("Highlights:", 1)[-1])
        items.append({
            "title": title.group(1).strip() if title else "LinkedIn post",
            "url": url.group(1),
            "published": parse_date(pub.group(1)) if pub else None,
            "summary": body_text[:400],
            "source": "LinkedIn",
            "via": "LinkedIn (Exa)",
        })
    return items


def website_feed(c, days):
    site = c["website"]
    if not site or "website" in c.get("skip", ""):
        return []
    page = http_get(site)
    m = re.search(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*>', page, re.I)
    href = re.search(r'href="([^"]+)"', m.group(0)) if m else None
    candidates = [urllib.parse.urljoin(site, href.group(1))] if href else []
    candidates.append(urllib.parse.urljoin(site.rstrip("/") + "/", "feed/"))
    for feed in candidates:
        try:
            items = parse_feed(http_get(feed, tries=1))
        except Exception:
            continue
        if items:
            # Skip comment feeds; they're noise
            items = [i for i in items if "/comments/" not in feed]
            return [dict(i, via="Own website", source=urllib.parse.urlparse(site).netloc) for i in items]
    return []


SOURCES = [("Google News", google_news), ("Bing News", bing_news),
           ("LinkedIn (Exa)", exa_linkedin), ("Own website", website_feed)]


# ---------- pipeline ----------

def collect(c, days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    found, failed = [], []
    for label, fn in SOURCES:
        try:
            items = fn(c, days)
        except Exception as e:
            failed.append(label)
            print(f"  ! {c['name']}: {label} failed: {e}", file=sys.stderr)
            continue
        for i in items:
            if not i["url"] or not i["title"]:
                continue
            if i["published"] is None or i["published"] < cutoff:
                continue  # unknown or too old
            if JUNK_TITLE.search(i["title"]):
                continue  # tag/category index pages
            if label in ("Google News", "Bing News"):
                # Headline or link must name the org; Bing ignores quotes and matches loose words
                headline = f"{i['title']} {i['url'].replace('-', ' ')}"
                if not mentions(c, headline, f"{headline} {i['summary']}"):
                    continue
                if any(a.lower() in i["source"].lower() for a in aliases(c)):
                    continue  # the org's own articles; those come from its website feed
            elif label == "LinkedIn (Exa)" and not mentions(c, f"{i['title']} {i['summary']} {i['url'].replace('-', ' ')}"):
                continue
            text = i["title"] + (" " + i["summary"][:200] if i["via"] == "LinkedIn (Exa)" else "")
            i["category"] = "Awards, recognition & funding" if AWARD_RE.search(text) else "Update"
            i["company"] = c["name"]
            found.append(i)
    return found, failed


def key_for(i):
    title = re.sub(r"\s+[-|–]\s+[^-|–]+$", "", i["title"].lower())
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()[:90]
    return f"{i['company']}|{title}"


def slack_post(webhook, text):
    data = json.dumps({"text": text, "unfurl_links": False, "unfurl_media": False}).encode()
    http_get(webhook, data=data, headers={"Content-Type": "application/json"}, tries=2)


def render(new, failed_sources, n_companies, days):
    awards = [i for i in new if i["category"] != "Update"]
    lines = [f"*Organisation updates* — {len(new)} new item(s) across {len({i['company'] for i in new})} "
             f"organisation(s) in the last {days} days ({len(awards)} awards, recognition or funding)."]
    for cat, emoji in (("Awards, recognition & funding", ":trophy:"), ("Update", ":newspaper:")):
        group = [i for i in new if i["category"] == cat]
        if not group:
            continue
        lines.append(f"\n{emoji} *{cat}*")
        for company in sorted({i["company"] for i in group}):
            lines.append(f"*{company}*")
            for i in sorted((x for x in group if x["company"] == company), key=lambda x: x["published"], reverse=True):
                t = i["title"].replace("<", "‹").replace(">", "›").replace("|", "¦")
                lines.append(f"  • <{i['url']}|{t}> — _{i['via']}, {i['published']:%d %b}_")
    if not new:
        lines.append(f"Nothing new this cycle (checked {n_companies} organisations).")
    if failed_sources:
        lines.append("\n_Unavailable this run (will retry next cycle): "
                     + ", ".join(f"{k} ×{v}" for k, v in sorted(failed_sources.items())) + "_")
    return "\n".join(lines)


def chunks(text, size=3500):
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > size:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    return out + [cur] if cur.strip() else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="look-back window (default 7)")
    ap.add_argument("--only", help="check a single organisation by name")
    ap.add_argument("--dry-run", action="store_true", help="print only; don't post or save")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    companies = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    if args.only:
        companies = [c for c in companies if args.only.lower() in c["name"].lower()]
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}

    print(f"Checking {len(companies)} organisations, last {args.days} days…", file=sys.stderr)
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda c: collect(c, args.days), companies))

    failed_sources, new, today = {}, [], datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for items, failed in results:
        for f in failed:
            if f == "Own website":
                continue  # one site being down isn't worth a Slack note; see the run log
            failed_sources[f] = failed_sources.get(f, 0) + 1
        for i in items:
            k = key_for(i)
            if k in seen or k in {key_for(n) for n in new}:
                continue
            new.append(i)

    report = render(new, failed_sources, len(companies), args.days)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report.replace("*", "**") + "\n")
    if args.dry_run:
        return

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        for part in chunks(report):
            slack_post(webhook, part)
    else:
        print("SLACK_WEBHOOK_URL not set; skipped Slack.", file=sys.stderr)

    for i in new:
        seen[key_for(i)] = today
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN, "w") as f:
        json.dump(seen, f, indent=0, sort_keys=True)
    write_header = not os.path.exists(UPDATES)
    with open(UPDATES, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["found_on", "organisation", "category", "source", "published", "title", "url"])
        for i in new:
            w.writerow([today, i["company"], i["category"], i["via"],
                        i["published"].strftime("%Y-%m-%d"), i["title"], i["url"]])


if __name__ == "__main__":
    main()
