# alumni-feature

Watches ~130 organisations for news, awards and recognition, LinkedIn posts and
their own website/blog posts, then posts anything new to a Slack channel.
Runs on GitHub Actions every 3 days. Free: no paid APIs, no keys, no LinkedIn login.

## Sources

| Source | What it finds |
|---|---|
| Google News RSS | News articles naming the organisation |
| Bing News RSS | Second news source (catches regional / non-English coverage) |
| Exa (public search) | Public LinkedIn posts by or about the organisation |
| Organisation's website RSS feed | Blog / news posts it publishes itself |

Each source runs independently, so if one is down the others still report; the
Slack message notes which source was unavailable. Items are tagged
**Awards, recognition & funding** (award, wins, prize, fellowship, 40 under 40,
raises, grant…) or **Update**, and each item is only ever reported once.

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
| `linkedin` | LinkedIn page (reference only) |
| `aliases` | Names to search for, separated by `\|` (e.g. `Simplyblood\|Change With One Foundation`) |
| `context` | For generic names (e.g. "Karya", "STEP"): a result must also contain one of these words, `\|`-separated |
| `skip` | `website` to ignore the org's own feed (e.g. IDR, which publishes daily) |

If an organisation gets irrelevant results, add more specific `aliases` or `context`
words. If it gets none, check its `aliases`.

## Running locally

```bash
python3 monitor.py --dry-run                       # print, don't post or save
python3 monitor.py --dry-run --only "Mitti Cafe" --days 30
```

Results are logged in `data/updates.csv`; `data/seen.json` remembers what's
already been reported.
