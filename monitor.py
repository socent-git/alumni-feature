#!/usr/bin/env python3
"""Watch ~130 organisations for news, awards/recognition, LinkedIn posts and
website updates, and post anything new to Slack.

Free sources only, no logins, no API keys:
  - Google News RSS   (news articles naming the org; award news naming its founders)
  - Bing News RSS     (second news source / fallback)
  - LinkedIn page     (the org's public company page, read logged out: latest posts)
  - Exa public MCP    (public LinkedIn posts by or about the org)
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
import threading
import time
import unicodedata
import urllib.error
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

# Strong signals only, checked against the headline / opening of a post: words like
# "fellowship", "cohort" or "honoured to partner" appear in everyday posts too.
AWARD_RE = re.compile(
    r"\b(awards?|awarded|awardees?|(win|wins|won) (the|an?|first|second|gold|silver|bronze)|winners?|finalists?|shortlisted|felicitated|prizes?|"
    r"recogni[sz]ed|recognition|special mention|honou?red (with|by|to receive)|accolades?|troph(y|ies)|"
    r"\d+ under \d+|named (among|in|to|as)|conferred|"
    r"(raises|raised|secures|secured) [^.]{0,40}(funding|seed|round|grant|crore|lakh|million|[$₹]))\b",
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


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
LINKEDIN_GAP = 4.0  # seconds between LinkedIn requests, across all threads
_li_lock, _li_last = threading.Lock(), [0.0]
_li_blocked = threading.Event()  # set once LinkedIn rate-limits us; stop asking for the rest of the run


def linkedin_fetch(url):
    """Logged-out GET of a public LinkedIn page, one at a time and politely spaced."""
    if _li_blocked.is_set():
        raise RuntimeError("LinkedIn rate-limited this run (HTTP 999); skipped")
    with _li_lock:
        wait = _li_last[0] + LINKEDIN_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            return http_get(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en"}, tries=1)
        except urllib.error.HTTPError as e:
            if e.code in (429, 999):
                _li_blocked.set()
            raise
        finally:
            _li_last[0] = time.time()


def clean(text):
    # NFKC turns LinkedIn's 𝐛𝐨𝐥𝐝 unicode letters back into plain text so keywords match
    text = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>", " ", html.unescape(text or "")))
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
    return not ctx or any(re.search(r"(?<![a-z0-9])" + re.escape(w.lower()), ct) for w in ctx)


def founders(c):
    return [f.strip() for f in c.get("founders", "").split("|") if f.strip()]


def or_query(c):
    return " OR ".join(f'"{a}"' for a in aliases(c))


AWARD_QUERY = ('(award OR awarded OR prize OR wins OR won OR honoured OR honored OR felicitated OR '
               'recognised OR recognized OR finalist OR fellowship OR "special mention" OR conferred)')


# ---------- sources ----------

def google_news(c, days):
    q = f"({or_query(c)}) when:{days}d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    return [dict(i, via="Google News") for i in parse_feed(http_get(url))]


def google_news_founders(c, days):
    """Awards and recognition naming a founder; articles often lead with the person, not the org."""
    names = founders(c)
    if not names:
        return []
    q = f"({' OR '.join(f'{chr(34)}{n}{chr(34)}' for n in names)}) {AWARD_QUERY} when:{days}d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    return [dict(i, via="Google News (founder)") for i in parse_feed(http_get(url))]


def bing_news(c, days):
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": or_query(c), "format": "rss", "qft": 'interval="8"'})  # interval 8 = past week
    items = parse_feed(http_get(url))
    for i in items:
        real = urllib.parse.parse_qs(urllib.parse.urlparse(i["url"]).query).get("url")
        if real:
            i["url"] = real[0]
    return [dict(i, via="Bing News") for i in items]


def linkedin_page(c, days):
    """Latest posts on the org's public LinkedIn page (no login; LinkedIn shows ~10 to guests)."""
    if not c.get("linkedin"):
        return []
    page = linkedin_fetch(c["linkedin"].split("?")[0])
    if "main-feed-activity-card" not in page:
        if "authwall" in page or "/uas/login" in page[:5000]:
            raise RuntimeError("LinkedIn asked for a login (guest view blocked from this network)")
        return []  # page exists but has no public posts
    items = []
    for aid, body in re.findall(r'<article[^>]*data-activity-urn="urn:li:activity:(\d+)"(.*?)</article>', page, re.S):
        m = re.search(r'data-test-id="main-feed-activity-card__commentary"[^>]*>(.*?)</p>', body, re.S)
        reshare = re.search(r'data-test-id="feed-reshare-content__commentary"[^>]*>(.*?)</p>', body, re.S)
        text = clean(m.group(1)) if m else ""
        if not text and reshare:
            text = clean(reshare.group(1))
        if not text:
            continue
        link = re.search(r'href="(https://[a-z]+\.linkedin\.com/posts/[^"?]+)', body)
        # Guests see the org's reposts of people's posts with the person as the author
        actor = re.search(r'aria-label="View (organization page|profile) for ([^"]+)"', body)
        if actor and actor.group(1) == "profile":
            prefix = f"Reposted from {clean(actor.group(2))}: "
        elif reshare and not m:
            prefix = "Reposted: "
        else:
            prefix = ""
        items.append({
            "title": prefix + (text[:160] + ("…" if len(text) > 160 else "")),
            "url": link.group(1) if link else f"https://www.linkedin.com/feed/update/urn:li:activity:{aid}/",
            # LinkedIn activity IDs carry their creation time in the top 41 bits (ms since epoch)
            "published": datetime.fromtimestamp((int(aid) >> 22) / 1000, timezone.utc),
            "summary": text[:600],
            "source": "LinkedIn",
            "via": "LinkedIn page",
        })
    return items


def exa_linkedin(c, days):
    name = aliases(c)[0]
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "web_search_exa", "arguments": {
            "query": f"Recent LinkedIn post by {name} (Indian non-profit / social enterprise)"
                     + (f" or its founder {', '.join(founders(c))}" if founders(c) else "")
                     + " sharing news, an award or recognition",
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
            "title": clean(title.group(1)) if title else "LinkedIn post",
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


SOURCES = [("Google News", google_news), ("Google News (founder)", google_news_founders), ("Bing News", bing_news),
           ("LinkedIn page", linkedin_page), ("LinkedIn (Exa)", exa_linkedin), ("Own website", website_feed)]


# ---------- pipeline ----------

def collect(c, days, skip=()):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    found, failed = [], []
    for label, fn in SOURCES:
        if label in skip:
            continue
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
                headline = f"{i['title']} {i['url'].replace('-', ' ')}"
                # Bing ignores quotes and matches loose words, so its headline must name the org.
                # Google results go through the three-layer check, which reads the whole article.
                if label == "Bing News" and not mentions(c, headline, f"{headline} {i['summary']}"):
                    continue
                if any(a.lower() in i["source"].lower() for a in aliases(c)):
                    continue  # the org's own articles; those come from its website feed
            elif label == "LinkedIn (Exa)" and not mentions(c, f"{i['title']} {i['summary']} {i['url'].replace('-', ' ')}"):
                continue
            text = i["title"] + (" " + i["summary"][:250] if i["via"].startswith("LinkedIn") else "")
            i["category"] = "Awards, recognition & funding" if AWARD_RE.search(text) else "Update"
            i["company"] = c["name"]
            found.append(i)
    return found, failed


def text_key(i):
    """Same post text under different IDs (an original and its reshare)."""
    t = re.sub(r"^reposted( from [^:]+)?: ", "", i["title"].lower())
    return f"{i['company']}|t:" + re.sub(r"[^a-z0-9]+", " ", t).strip()[:80]


def key_for(i):
    post = re.search(r"activity[:-](\d{19})", i["url"])
    if post:  # same LinkedIn post found via the page and via Exa
        return f"{i['company']}|li:{post.group(1)}"
    title = re.sub(r"\s+[-|–]\s+[^-|–]+$", "", i["title"].lower())
    title = re.sub(r"[^a-z0-9]+", " ", title).strip()[:90]
    return f"{i['company']}|{title}"


# ---------- three-layer check ----------
#   1. Org + founder:   the org's name (full or short) AND one of its founders' names are in the article
#   2. Org identity:    the org is named in the headline, or its website / LinkedIn page is in the article
#   3. Founder link:    a founder's full name is in the headline, or sits right next to the org's name
#                       ("Prashant Chaudhary, founder of CodeYogi")
# An item reaches Slack only when at least 2 of the 3 pass. Posts from the org's own LinkedIn page or
# website are the org speaking for itself, so they count as verified (3/3).

OWN_CHANNELS = ("LinkedIn page", "Own website")


def real_url(url):
    """Google News hides the article behind its own link; ask Google for the real one."""
    if "news.google.com/" not in url:
        return url
    aid = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    page = http_get(f"https://news.google.com/rss/articles/{aid}", tries=1)
    sg = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not sg or not ts:
        return url
    inner = (f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
             f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts.group(1)},"{sg.group(1)}"]')
    body = urllib.parse.urlencode({"f.req": json.dumps([[["Fbv4je", inner, None, "generic"]]])}).encode()
    raw = http_get("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                   headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}, tries=1)
    m = re.search(r'\\"garturlres\\",\\"(.*?)\\"', raw)
    return m.group(1) if m else url


def article_text(url):
    """(visible text, raw html) of an article, without menus, sidebars and footers."""
    page = http_get(url, headers={"User-Agent": BROWSER_UA}, tries=1)
    body = re.sub(r"(?is)<(script|style|nav|aside|footer|header|form|noscript)\b.*?</\1>", " ", page)
    return clean(body).lower(), page.lower()


def near(text, a, b, window=300):
    pa = [m.start() for m in re.finditer(re.escape(a), text)]
    pb = [m.start() for m in re.finditer(re.escape(b), text)]
    return any(abs(x - y) <= window for x in pa for y in pb)


def three_checks(c, i):
    """Returns the list of checks passed, e.g. ["org+founder", "org identity"]."""
    slug = re.search(r"linkedin\.com/company/([^/?#]+)", c.get("linkedin", ""))
    if i["via"] in OWN_CHANNELS or (slug and f"/posts/{slug.group(1).lower()}_" in i["url"].lower()):
        return ["own channel"] * 3
    text, page = f"{i['title']} {i['summary']}".lower(), ""
    if i["via"].startswith(("Google News", "Bing News")):
        try:
            i["url"] = real_url(i["url"])
            text, page = article_text(i["url"])
            text = f"{i['title'].lower()} {text}"
        except Exception:
            pass  # judge on the headline alone; it will usually score low and be held
    names = [a.lower() for a in aliases(c)]
    org_in_text = mentions(c, text)
    founders_in = [f for f in founders(c) if re.search(r"(?<![a-z])" + re.escape(f.lower()) + r"(?![a-z])", text)]
    site = re.sub(r"^https?://(www\.)?", "", c.get("website", "")).split("/")[0].lower()
    passed = []
    if org_in_text and founders_in:
        passed.append("org+founder")
    if mentions(c, i["title"], text) or (site and site in page + text) or (slug and slug.group(1).lower() in page):
        passed.append("org identity")
    if any(f.lower() in i["title"].lower() for f in founders(c)) or any(
            near(text, f.lower(), n) for f in founders_in for n in names):
        passed.append("founder link")
    return passed


def slack_post(webhook, text):
    data = json.dumps({"text": text, "unfurl_links": False, "unfurl_media": False}).encode()
    http_get(webhook, data=data, headers={"Content-Type": "application/json"}, tries=2)


def render(new, failed_sources, n_companies, days, held=0):
    awards = [i for i in new if i["category"] != "Update"]
    lines = [f"*Organisation updates* — {len(new)} new item(s) across {len({i['company'] for i in new})} "
             f"organisation(s) in the last {days} days ({len(awards)} awards, recognition or funding)."]
    def link(i):
        t = i["title"].replace("<", "‹").replace(">", "›").replace("|", "¦")
        score = "✓✓✓" if len(i.get("checks", [])) >= 3 else "✓✓"
        return f"<{i['url']}|{t}> — _{i['via']}, {i['published']:%d %b}_ {score}"

    if awards:
        lines.append("\n:trophy: *Awards, recognition & funding*")
        for company in sorted({i["company"] for i in awards}):
            lines.append(f"*{company}*")
            group = sorted((x for x in awards if x["company"] == company), key=lambda x: x["published"], reverse=True)
            for i in group[:3]:  # one award often gets a dozen articles; show the newest few
                lines.append(f"  • {link(i)}")
            if len(group) > 3:
                lines.append(f"  _+{len(group) - 3} more articles/posts (see data/updates.csv)_")
    updates = [i for i in new if i["category"] == "Update"]
    if updates:
        lines.append("\n:newspaper: *Other updates* (latest per organisation; all of them are in data/updates.csv)")
        for company in sorted({i["company"] for i in updates}):
            group = sorted((x for x in updates if x["company"] == company), key=lambda x: x["published"], reverse=True)
            more = f" _(+{len(group) - 1} more)_" if len(group) > 1 else ""
            lines.append(f"• *{company}*: {link(group[0])}{more}")
    if not new:
        lines.append(f"Nothing new this cycle (checked {n_companies} organisations).")
    if held:
        lines.append(f"\n_{held} lower-confidence item(s) passed fewer than 2 of 3 checks and were held "
                     f"for review (data/updates.csv, status \"held\")._")
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
    ap.add_argument("--news-only", action="store_true",
                    help="skip LinkedIn company pages (for the extra runs during the day)")
    ap.add_argument("--quiet", action="store_true", help="don't post to Slack when nothing is new")
    args = ap.parse_args()

    companies = list(csv.DictReader(open(COMPANIES, encoding="utf-8")))
    if args.only:
        companies = [c for c in companies if args.only.lower() in c["name"].lower()]
    seen = json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    by_name = {c["name"]: c for c in companies}

    print(f"Checking {len(companies)} organisations, last {args.days} days…", file=sys.stderr)
    with ThreadPoolExecutor(args.workers) as pool:
        skip = ("LinkedIn page",) if args.news_only else ()
        results = list(pool.map(lambda c: collect(c, args.days, skip), companies))

    failed_sources, new, taken, today = {}, [], set(), datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for items, failed in results:
        for f in failed:
            if f == "Own website":
                continue  # one site being down isn't worth a Slack note; see the run log
            failed_sources[f] = failed_sources.get(f, 0) + 1
        for i in items:
            keys = {key_for(i), text_key(i)}
            if keys & seen.keys() or keys & taken:
                continue
            taken |= keys
            new.append(i)

    # Three-layer check (reads each new article in full); only 2-of-3 or better reach Slack
    with ThreadPoolExecutor(args.workers * 2) as pool:
        for i, passed in zip(new, pool.map(lambda i: three_checks(by_name[i["company"]], i), new)):
            i["checks"] = passed
    held = [i for i in new if len(i["checks"]) < 2]
    posted = [i for i in new if len(i["checks"]) >= 2]
    print(f"Three-layer check: {len(posted)} passed, {len(held)} held for review", file=sys.stderr)

    report = render(posted, failed_sources, len(companies), args.days, len(held))
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(report.replace("*", "**") + "\n")
    if args.dry_run:
        return

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook and not (args.quiet and not posted):
        for part in chunks(report):
            slack_post(webhook, part)
    else:
        print("SLACK_WEBHOOK_URL not set; skipped Slack.", file=sys.stderr)

    for i in new:
        seen[key_for(i)] = seen[text_key(i)] = today
    cutoff = (datetime.now(timezone.utc) - timedelta(days=180)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    with open(SEEN, "w") as f:
        json.dump(seen, f, indent=0, sort_keys=True)
    write_header = not os.path.exists(UPDATES)
    with open(UPDATES, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["found_on", "organisation", "category", "source", "published", "status", "checks_passed",
                        "title", "url"])
        for i in new:
            w.writerow([today, i["company"], i["category"], i["via"], i["published"].strftime("%Y-%m-%d"),
                        "posted" if i in posted else "held", "; ".join(i["checks"]), i["title"], i["url"]])


if __name__ == "__main__":
    main()
