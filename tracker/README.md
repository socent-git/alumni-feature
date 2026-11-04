# Achievements tracker (Google Sheet)

A free Google Sheet that:
- **logs every achievement** the monitor finds: organisation, type, what happened, link, repost status, owner
- **reminds** (daily, 10:00 IST) about anything still "Not reposted" after 2 days, emailing the owner too
- **triggers the monitor every hour**, because GitHub's own schedule is unreliable
- **warns** if no check has reported in for 8 hours

It works like Excel: File → Download → Microsoft Excel (.xlsx) whenever you want a copy.

## Setup (about 15 minutes, once)

### 1. GitHub token (lets the sheet start the monitor)
1. Open https://github.com/settings/personal-access-tokens/new (fine-grained token).
2. Name: `Org monitor trigger`. Expiration: 1 year (set a reminder to renew).
3. Resource owner: `socent-git`. Repository access: **Only select repositories** → `alumni-feature`.
4. Permissions → Repository permissions → **Actions: Read and write**. Nothing else.
5. Generate, and copy the token (starts with `github_pat_`).

### 2. The sheet and script
1. Create a new Google Sheet (https://sheets.new) and name it `Organisation achievements tracker`.
2. **Extensions → Apps Script.** Delete what's in the editor, paste all of `tracker/apps_script.gs`, and save (💾).
3. **Project Settings (⚙️) → Script properties → Add script property**, four times:

   | Property | Value |
   |---|---|
   | `SHARED_SECRET` | any long random text, e.g. 30 random letters and numbers |
   | `GITHUB_TOKEN` | the token from step 1 |
   | `GITHUB_REPO` | `socent-git/alumni-feature` |
   | `ALERT_EMAILS` | who gets reminders and warnings, comma-separated |

4. Back in the editor, pick **setup** in the function dropdown and click **▶ Run**. Google asks for permission:
   Review permissions → choose your account → Advanced → Go to project → Allow.
   This creates the "Alerts" tab and the hourly / daily timers, and starts a first check.
5. **Deploy → New deployment** → type **Web app**. Execute as: **Me**. Who has access: **Anyone**.
   Deploy, and copy the **Web app URL** (ends in `/exec`). The shared secret keeps strangers out.

### 3. Connect GitHub to the sheet
At https://github.com/socent-git/alumni-feature/settings/secrets/actions add:

| Secret | Value |
|---|---|
| `TRACKER_WEBHOOK_URL` | the Web app URL from step 2.5 |
| `TRACKER_SECRET` | the same text as `SHARED_SECRET` |

Done. New achievements appear as rows after the next check.

## Using it
- **Repost status:** dropdown with Not reposted / Reposted / Not needed. Rows turn green when reposted and red when overdue.
- **Owner (email):** put a person's email to have reminders go to them as well.
- **Reposted on / Notes:** free text for your own records.

If you edit the script later, use **Deploy → Manage deployments → Edit → New version** so the web app picks up the change.
