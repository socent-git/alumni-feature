# alumni-feature

Watches ~130 organisations for news, awards and recognition, LinkedIn posts and
their own website/blog posts, then posts anything new to a Slack channel.
Free: no paid APIs, no keys, no LinkedIn login.

**When it runs** (GitHub Actions):

| Time (IST) | What | Alerts |
|---|---|---|
| About 08:05 daily | Everything, including LinkedIn company pages | Always sent (says "nothing new" if so) |
| Every ~6 hours after that | News, founders, websites (no LinkedIn pages) | Sent only when something is new |

GitHub's scheduler sometimes delays or skips runs, so the workflow wakes every hour and
`schedule_gate.py` decides what is due (state in `data/run_state.json`). A skipped slot is
caught up at the next hourly wake-up; wake-ups with nothing due stop within seconds.
News is usually reported within about 6 hours of Google News picking it up.

## Sources

| Source | What it finds |
|---|---|
| LinkedIn company page (public, logged out) | The organisation's latest posts (LinkedIn shows guests ~10), with exact dates |
| Google News RSS | News articles naming the organisation (Times of India, ET, The Hindu, Indian Express… all flow through Google News) |
| Google News RSS, founders | Award / recognition stories naming one of the org's founders, even when the headline doesn't name the org |
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

Alerts go to Slack, Gmail, or both: whichever secrets are set. Add secrets in GitHub under
**Settings → Secrets and variables → Actions → New repository secret**.

| Secret | For | Value |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Slack | An [incoming webhook](https://api.slack.com/messaging/webhooks) URL for the channel |
| `GMAIL_ADDRESS` | Email | The Gmail address that sends the alerts |
| `GMAIL_APP_PASSWORD` | Email | A Gmail [app password](https://myaccount.google.com/apppasswords) (needs 2-Step Verification), not the normal password |
| `ALERT_EMAIL_TO` | Email (optional) | Who receives it, comma-separated; defaults to `GMAIL_ADDRESS` |

Then **Actions → Organisation updates → Run workflow** to test it now.

After that it runs by itself every 3 days.

## Editing the list — `data/companies.csv`

| Column | Meaning |
|---|---|
| `name` | Display name |
| `website` | Site URL; its RSS feed is found automatically |
| `linkedin` | LinkedIn company page URL; its public posts are read each run |
| `aliases` | Names to search for, separated by `\|` (e.g. `Simplyblood\|Change With One Foundation`). Include the short name people actually write ("CodeYogi", not only "CodeYogi Foundation") |
| `founders` | Founders / leaders, separated by `\|`; their names are searched in award news |
| `context` | For generic names (e.g. "Karya", "STEP"): a result must also contain one of these words, `\|`-separated |
| `skip` | `website` to ignore the org's own feed (e.g. IDR, which publishes daily) |

When you add organisations, leave `linkedin` and `founders` blank and run
`python3 find_founders.py` (people search; accepts only a current founder/CEO role at
that org) and `python3 find_linkedin_pages.py`: it finds the page from the organisation's website,
likely page names or a search, and only accepts a page whose title matches. Check what it
prints; fix any wrong match by editing the CSV.

If an organisation gets irrelevant results, add more specific `aliases` or `context`
words. If it gets none, check its `aliases`.

## Running locally

```bash
python3 monitor.py --dry-run                       # print, don't post or save
python3 monitor.py --dry-run --only "Mitti Cafe" --days 30
python3 monitor.py --dry-run --news-only --days 2         # what a daytime run sees
```

Results are logged in `data/updates.csv`; `data/seen.json` remembers what's
already been reported.
