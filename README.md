# alumni-feature

Watches ~130 organisations for news, awards and recognition, LinkedIn posts and
their own website/blog posts, then posts anything new to a Slack channel.
Runs on GitHub Actions every 3 days. Free: no paid APIs, no keys, no LinkedIn login.

## Sources

| Source | What it finds |
|---|---|
| LinkedIn company page (public, logged out) | The organisation's latest posts (LinkedIn shows guests ~10), with exact dates |
| Google News RSS | News articles naming the organisation |
| Bing News RSS | Second news source (catches regional / non-English coverage) |
| Exa (public search) | Public LinkedIn posts by or about the organisation; backup when LinkedIn blocks a run |
| Organisation's website RSS feed | Blog / news posts it publishes itself |

Each source runs independently, so if one is down the others still report; the
Slack message notes which source was unavailable. Items are tagged
**Awards, recognition & funding** (award, won, finalist, prize, felicitated,
recognised, special mention, 40 under 40, raised funding…) or **Update**, and each
item is only ever reported once. Slack shows awards in full and other updates as one
line per organisation; every item is logged in `data/updates.csv`.

**About LinkedIn:** no account is used, so no account can be restricted. The tool reads
the same public company page anyone sees without signing in, one page every 4 seconds
(~10 minutes for 125 pages). If LinkedIn rate-limits a run (HTTP 999), the tool stops
asking LinkedIn for that run and relies on Exa; the next run tries again. LinkedIn's
terms discourage automated access even to public pages, so keep the frequency modest.

## Setup (one time)

1. In Slack, create an [incoming webhook](https://api.slack.com/messaging/webhooks)
   for the channel and copy its URL.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**,
   name `SLACK_WEBHOOK_URL`, paste the URL.
3. **Actions → Organisation updates → Run workflow** to test it now.

After that it runs by itself every 3 days.

## Editing the list — `data/companies.csv`

| Column | Meaning |
|---|---|
| `name` | Display name |
| `website` | Site URL; its RSS feed is found automatically |
| `linkedin` | LinkedIn company page URL; its public posts are read each run |
| `aliases` | Names to search for, separated by `\|` (e.g. `Simplyblood\|Change With One Foundation`) |
| `context` | For generic names (e.g. "Karya", "STEP"): a result must also contain one of these words, `\|`-separated |
| `skip` | `website` to ignore the org's own feed (e.g. IDR, which publishes daily) |

When you add organisations, leave `linkedin` blank and run
`python3 find_linkedin_pages.py`: it finds the page from the organisation's website,
likely page names or a search, and only accepts a page whose title matches. Check what it
prints; fix any wrong match by editing the CSV.

If an organisation gets irrelevant results, add more specific `aliases` or `context`
words. If it gets none, check its `aliases`.

## Running locally

```bash
python3 monitor.py --dry-run                       # print, don't post or save
python3 monitor.py --dry-run --only "Mitti Cafe" --days 30
```

Results are logged in `data/updates.csv`; `data/seen.json` remembers what's
already been reported.
