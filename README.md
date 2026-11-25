# alumni-feature

Watches ~130 organisations for news, awards and recognition, LinkedIn posts and
their own website/blog posts, then posts anything new to a Slack channel.
Free: no paid APIs, no keys, no LinkedIn login.

**When it runs** (GitHub Actions):

| Time (IST) | What | Alerts |
|---|---|---|
| About 08:05 daily | Everything, including LinkedIn company pages | Always sent |
| 14:00, 20:00, 02:00 | News, founders, websites (no LinkedIn pages) | Always sent ("✓ No new updates" when there's nothing) |

Every check sends a message, so silence means something is wrong; a crashed check sends a
"⚠️ check FAILED" alert. Each message opens with a summary of achievements.

GitHub's scheduler often delays or drops runs (on this repo, most of them), so the workflow wakes
every 10 minutes (the optional Google Sheet tracker can trigger it too), and
`schedule_gate.py` decides what is due (state in `data/run_state.json`). A skipped slot is
caught up at the next wake-up that gets through; wake-ups with nothing due stop within seconds.
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
message notes which source was unavailable. Each item is only ever reported once, and every
message is sorted into three parts (rules in `classify.py`):

- **🏆 Achievements:** awards, recognition, grants, funding
- **⭐ Notable updates:** partnerships, government launches, milestones, announcements, media and news coverage
- **Routine posts:** hiring, calls for applications, events, greetings, staff reposts (one line per type)

Each message opens with **📣 Highlights to evangelise**: up to 5 stories worth promoting (achievements
first, then government, partnership, news, milestone and media items), each tagged with how to amplify it:
**LinkedIn reshare** (the organisation posted it on LinkedIn), **LinkedIn post** (only a news article
covers it, so we write our own) and **Newsletter addition** (grant or funding secured, award or
recognition, government launch).

News that names an organisation but has no founder and no link to its website or LinkedIn is not
counted as confirmed; it appears at the bottom of each message under **❔ Unconfirmed mentions** (up to
10, newest first) so it can be checked by eye. In `data/updates.csv` these rows have status `unconfirmed`.

If something important lands under Routine, add its phrase to the matching rule in `classify.py`.
Test the rules without sending anything: `python3 monitor.py --dry-run --ignore-seen --days 7`.

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
| `TRACKER_WEBHOOK_URL`, `TRACKER_SECRET` | Tracker (optional) | Google Sheet achievements tracker; see [tracker/README.md](tracker/README.md) |

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
| `exclude` | Phrases that mean a story is about a namesake, `\|`-separated; such stories are dropped (e.g. SAMAVESH: `e-Anudaan\|Ministry of Social Justice`, the government portal) |

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
