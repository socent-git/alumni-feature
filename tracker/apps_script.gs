/**
 * Organisation achievements tracker (Google Sheets + Apps Script). Free; runs on Google's servers.
 *
 * What it does:
 *  1. Receives each new achievement from the monitor (doPost) and adds a row to the "Alerts" tab.
 *  2. Every hour, asks GitHub to run the monitor (mode=auto: it only checks when something is due).
 *     GitHub's own schedule has proved unreliable, so this is the main alarm clock.
 *  3. Every morning, emails a reminder listing achievements not reposted after 2+ days, tagging owners.
 *  4. Watchdog: if no check has reported in for 8 hours, emails a warning.
 *
 * Setup: see tracker/README.md. Settings live in Project Settings → Script properties:
 *   SHARED_SECRET    any long random text; the same value goes in GitHub secret TRACKER_SECRET
 *   GITHUB_TOKEN     fine-grained GitHub token with "Actions: Read and write" on the repo
 *   GITHUB_REPO      socent-git/alumni-feature
 *   ALERT_EMAILS     who gets reminders and watchdog warnings, comma-separated
 */

const SHEET = 'Alerts';
const HEADERS = ['Found on', 'Organisation', 'Type', 'What happened', 'Link', 'Source', 'Published',
                 'Repost status', 'Owner (email)', 'Reposted on', 'Notes', 'ID'];
const STATUS = ['Not reposted', 'Reposted', 'Not needed'];
const REMIND_AFTER_DAYS = 2;
const WATCHDOG_HOURS = 8;

function props_() { return PropertiesService.getScriptProperties(); }

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#eef2f7');
    sh.setColumnWidth(4, 420);
    // Repost status dropdown, and a red row once something sits un-reposted past the deadline
    const rule = SpreadsheetApp.newDataValidation().requireValueInList(STATUS, true).build();
    sh.getRange('H2:H').setDataValidation(rule);
    const overdue = SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied(`=AND($H2="Not reposted", $A2<>"", TODAY()-$A2>=${REMIND_AFTER_DAYS})`)
      .setBackground('#f8d7da').setRanges([sh.getRange('A2:L')]).build();
    const done = SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=$H2="Reposted"').setBackground('#d4edda').setRanges([sh.getRange('A2:L')]).build();
    sh.setConditionalFormatRules([overdue, done]);
  }
  return sh;
}

/** 1. The monitor posts {secret, check, items:[...]} here after every check. */
function doPost(e) {
  const data = JSON.parse(e.postData.contents || '{}');
  if (!data.secret || data.secret !== props_().getProperty('SHARED_SECRET')) {
    return ContentService.createTextOutput('forbidden');
  }
  props_().setProperty('LAST_HEARTBEAT', new Date().toISOString());
  props_().deleteProperty('WATCHDOG_SENT');
  const sh = sheet_();
  const known = new Set(sh.getRange(2, 12, Math.max(sh.getLastRow() - 1, 1), 1).getValues().flat());
  (data.items || []).forEach(i => {
    if (known.has(i.id)) return;
    sh.appendRow([new Date(), i.organisation, i.type, i.summary, i.url, i.source, i.published,
                  'Not reposted', '', '', '', i.id]);
    known.add(i.id);
  });
  return ContentService.createTextOutput('ok');
}

/** 2. Hourly: ask GitHub to run the monitor; it decides itself whether a check is due. */
function triggerMonitor() {
  const repo = props_().getProperty('GITHUB_REPO');
  const res = UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/actions/workflows/monitor.yml/dispatches`, {
    method: 'post', muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + props_().getProperty('GITHUB_TOKEN'),
               Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main', inputs: { mode: 'auto' } }),
  });
  if (res.getResponseCode() !== 204) {
    console.error('GitHub refused the trigger: ' + res.getResponseCode() + ' ' + res.getContentText());
  }
}

/** 3. Daily: remind about achievements not reposted after REMIND_AFTER_DAYS days. */
function remindUnreposted() {
  const sh = sheet_();
  const rows = sh.getLastRow() > 1 ? sh.getRange(2, 1, sh.getLastRow() - 1, HEADERS.length).getValues() : [];
  const cutoff = Date.now() - REMIND_AFTER_DAYS * 864e5;
  const overdue = rows.filter(r => r[7] === 'Not reposted' && r[0] instanceof Date && r[0].getTime() <= cutoff);
  if (!overdue.length) return;
  const owners = new Set(overdue.map(r => String(r[8]).trim()).filter(o => o.includes('@')));
  const to = (props_().getProperty('ALERT_EMAILS') || '').split(',').map(s => s.trim()).filter(Boolean);
  const lines = overdue.map(r => {
    const days = Math.floor((Date.now() - r[0].getTime()) / 864e5);
    return `<li><b>${r[1]}</b> — ${r[2]}: <a href="${r[4]}">${r[3]}</a> ` +
           `<i>(${days} days, owner: ${r[8] || 'unassigned'})</i></li>`;
  });
  MailApp.sendEmail({
    to: to.concat([...owners]).join(','),
    subject: `⏰ ${overdue.length} achievement(s) not reposted for ${REMIND_AFTER_DAYS}+ days`,
    htmlBody: `<p>These achievements haven't been reposted yet. Repost them, or set "Repost status" to ` +
              `"Not needed" in the <a href="${SpreadsheetApp.getActiveSpreadsheet().getUrl()}">tracker</a>.</p>` +
              `<ul>${lines.join('')}</ul>`,
  });
}

/** 4. Hourly: warn if the monitor has gone quiet. One warning until it reports in again. */
function watchdog() {
  const last = props_().getProperty('LAST_HEARTBEAT');
  if (!last || props_().getProperty('WATCHDOG_SENT')) return;
  const hours = (Date.now() - new Date(last).getTime()) / 36e5;
  if (hours < WATCHDOG_HOURS) return;
  const to = props_().getProperty('ALERT_EMAILS');
  MailApp.sendEmail(to, `⚠️ Organisation monitor silent for ${Math.round(hours)} hours`,
    `No check has reported in since ${last}. Look at the runs on GitHub: ` +
    `https://github.com/${props_().getProperty('GITHUB_REPO')}/actions`);
  props_().setProperty('WATCHDOG_SENT', '1');
}

/** Run once from the editor (▶ Run → setup) to create the tab and the timed triggers. */
function setup() {
  sheet_();
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('triggerMonitor').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('watchdog').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('remindUnreposted').timeBased().atHour(10).everyDays(1)
    .inTimezone('Asia/Kolkata').create();
  triggerMonitor();  // first check right away
}
