/**
 * SCRIPT 2 — Execute the reorganisation
 * -------------------------------------
 * Reads the "Mapping" sheet (filled from Claude's analysis, then reviewed
 * by the team) and applies it. It runs as a DRY RUN by default: nothing in
 * Drive changes, and every row gets a "Result" showing what would happen.
 *
 * Mapping columns (row 1 = header, written by Script 1):
 *   A Source Folder ID   folder to act on (blank for CREATE)
 *   B Current Path       for humans only, not used
 *   C Action             MOVE | MERGE | RENAME | SHORTCUT | CREATE | SKIP
 *   D Target Path        under the new root, e.g. "05 ORGANISATIONS/Acme Foundation"
 *   E New Name           RENAME / MOVE: new folder name (optional for MOVE)
 *   F Reason             for humans only
 *   G Status             set by the script: DONE / WOULD DO / ERROR. Rows marked DONE are skipped.
 *   H Result             set by the script
 *
 * Actions
 *   MOVE      Move the folder (with everything inside) into Target Path.
 *             If New Name is set, it is also renamed.
 *   MERGE     Move the *contents* of the source folder into Target Path
 *             (target is created if missing). The empty source is renamed
 *             "zz_MERGED_<name>" so it can be checked and deleted by hand.
 *   RENAME    Rename in place to New Name.
 *   SHORTCUT  Leave the original where it is, add a shortcut in Target Path
 *             (used for "02 RESEARCH & IMPACT/Data rooms").
 *   CREATE    Create Target Path (all missing levels).
 *   SKIP      Do nothing (e.g. "#not move files" folders).
 *
 * Safety
 *   - DRY_RUN = true by default. Review the Result column, then set false.
 *   - Nothing is ever deleted or trashed.
 *   - The script stops after ~5 min and can be re-run. It picks up at the first row not marked DONE.
 *   - Moving folders inside a shared drive needs Manager or Content manager.
 *
 * SETUP: same project as Script 1 (Drive API v3 service enabled).
 *   1. Set SPREADSHEET_ID (the schema sheet Script 1 produced) and NEW_ROOT_ID.
 *   2. Run buildSkeleton() once (dry run first), then runReorganisation().
 */

const REORG = {
  SPREADSHEET_ID: '',            // the "Drive schema - ..." sheet
  MAPPING_SHEET: 'Mapping',
  NEW_ROOT_ID: '0AGUWPWZlmPBEUk9PVA', // where the 00-07 structure lives (shared drive or folder ID)
  DRY_RUN: true,
  TIME_BUDGET_MS: 5 * 60 * 1000,
};

/**
 * Target skeleton, from SocEnt_Folder_Structure_1.xlsx (preliminary, open to
 * change). Org folders are not pre-created. Use ORG_SUBFOLDERS via
 * createOrgFolder('Org name') or let MOVE/MERGE rows create them.
 */
const SKELETON = {
  '00 START HERE': ['Readme', 'Register', 'Naming rules'],
  '01 STRATEGY & OPERATIONS': [
    'Decks', 'Decks/CURRENT', 'Decks/_superseded',
    'Strategy, reviews & deepdives', 'Process & templates', 'Team operations',
    'Thought leadership', 'Product', 'Network & ecosystem', 'AIC N-Core',
  ],
  '02 RESEARCH & IMPACT': ['Landscape & studies', 'Impact data', 'Data rooms'],
  '03 LEGAL & COMPLIANCE': [
    '01 Agreements & MoUs', '02 Utilisation certificates',
    '03 Registrations & statutory', '04 Templates',
  ],
  '04 BRAND & MEDIA': ['Logos', 'Collaterals & campaigns', 'Events', 'Films & photo library'],
  '05 ORGANISATIONS': ['_Programme docs', '_Programme resources'],
  '06 FUNDING PROPOSALS': ['CSR & volunteering', 'Reporting to funders', '_FR resources'],
  '07 TO BE SORTED': [],
};

const ORG_SUBFOLDERS = [
  '01 Profile & pitch deck', '02 Readiness & assessments', '03 Budgets & utilisation',
  '04 Photos, videos & logos', '05 Recommendations & nominations', '06 Partner-supplied',
];

const FOLDER = 'application/vnd.google-apps.folder';
const _folderCache = {};
let _dryCreated = 0;

/** Creates the 00-07 top level and fixed subfolders. Safe to re-run. */
function buildSkeleton() {
  Object.keys(SKELETON).forEach((top) => {
    ensurePath_(top);
    SKELETON[top].forEach((sub) => ensurePath_(top + '/' + sub));
  });
  Logger.log('%s skeleton done%s', REORG.DRY_RUN ? '[DRY RUN]' : '',
    REORG.DRY_RUN ? ' (' + _dryCreated + ' folders would be created)' : '');
}

/** Creates 05 ORGANISATIONS/<name> with the six standard subfolders. */
function createOrgFolder(name) {
  ORG_SUBFOLDERS.forEach((s) => ensurePath_('05 ORGANISATIONS/' + name + '/' + s));
}

/** Applies every Mapping row not yet DONE. */
function runReorganisation() {
  const started = Date.now();
  const sh = SpreadsheetApp.openById(REORG.SPREADSHEET_ID).getSheetByName(REORG.MAPPING_SHEET);
  const data = sh.getDataRange().getValues();
  let done = 0, errors = 0;

  for (let r = 1; r < data.length; r++) {
    if (Date.now() - started > REORG.TIME_BUDGET_MS) {
      Logger.log('Time budget reached at row %s. Run again to continue.', r + 1);
      break;
    }
    const [srcId, , actionRaw, targetPath, newName, , status] = data[r];
    const action = String(actionRaw || '').trim().toUpperCase();
    if (!action || status === 'DONE') continue;

    let result;
    try {
      result = applyRow_(String(srcId).trim(), action, String(targetPath || '').trim(),
        String(newName || '').trim());
      sh.getRange(r + 1, 7, 1, 2).setValues([[REORG.DRY_RUN ? 'WOULD DO' : 'DONE', result]]);
      done++;
    } catch (e) {
      sh.getRange(r + 1, 7, 1, 2).setValues([['ERROR', String(e.message || e)]]);
      errors++;
    }
  }
  Logger.log('%s rows processed: %s, errors: %s', REORG.DRY_RUN ? '[DRY RUN]' : '', done, errors);
}

function applyRow_(srcId, action, targetPath, newName) {
  const tag = REORG.DRY_RUN ? 'would ' : '';
  switch (action) {
    case 'SKIP':
      return 'skipped';

    case 'CREATE':
      requireVal_(targetPath, 'Target Path');
      ensurePath_(targetPath);
      return tag + 'create ' + targetPath;

    case 'RENAME': {
      requireVal_(srcId, 'Source Folder ID'); requireVal_(newName, 'New Name');
      const f = getFile_(srcId);
      if (!REORG.DRY_RUN) Drive.Files.update({ name: newName }, srcId, null, { supportsAllDrives: true });
      return tag + 'rename "' + f.name + '" -> "' + newName + '"';
    }

    case 'MOVE': {
      requireVal_(srcId, 'Source Folder ID'); requireVal_(targetPath, 'Target Path');
      const f = getFile_(srcId);
      const dest = ensurePath_(targetPath);
      const finalName = newName || f.name.trim();
      const clash = findChild_(dest, finalName);
      if (clash && clash !== srcId) {
        throw new Error('"' + finalName + '" already exists in ' + targetPath + ' - use MERGE instead');
      }
      if (!REORG.DRY_RUN) {
        Drive.Files.update(finalName !== f.name ? { name: finalName } : {}, srcId, null, {
          addParents: dest, removeParents: (f.parents || []).join(','), supportsAllDrives: true,
        });
      }
      return tag + 'move "' + f.name + '" -> ' + targetPath + '/' + finalName;
    }

    case 'MERGE': {
      requireVal_(srcId, 'Source Folder ID'); requireVal_(targetPath, 'Target Path');
      const f = getFile_(srcId);
      const dest = ensurePath_(targetPath);
      if (dest === srcId) throw new Error('source and target are the same folder');
      const kids = listChildren_(srcId);
      const clashes = [];
      kids.forEach((k) => {
        // Same-named subfolder already in target: leave it in the source and report it
        // so it can get its own MERGE row. Same-named files are moved anyway
        // (Drive allows duplicates, and the analysis flags them).
        if (k.mimeType === FOLDER && findChild_(dest, k.name)) { clashes.push(k.name); return; }
        if (!REORG.DRY_RUN) {
          Drive.Files.update({}, k.id, null, { addParents: dest, removeParents: srcId, supportsAllDrives: true });
        }
      });
      if (!REORG.DRY_RUN && !clashes.length) {
        Drive.Files.update({ name: 'zz_MERGED_' + f.name.trim() }, srcId, null, { supportsAllDrives: true });
      }
      return tag + 'merge ' + (kids.length - clashes.length) + ' items from "' + f.name + '" into ' +
        targetPath + (clashes.length ? ' | subfolder clash, left in place: ' + clashes.join('; ') : '');
    }

    case 'SHORTCUT': {
      requireVal_(srcId, 'Source Folder ID'); requireVal_(targetPath, 'Target Path');
      const f = getFile_(srcId);
      const dest = ensurePath_(targetPath);
      if (!REORG.DRY_RUN) {
        Drive.Files.create({
          name: newName || f.name.trim(), mimeType: 'application/vnd.google-apps.shortcut',
          parents: [dest], shortcutDetails: { targetId: srcId },
        }, null, { supportsAllDrives: true });
      }
      return tag + 'add shortcut to "' + f.name + '" in ' + targetPath;
    }

    default:
      throw new Error('unknown action "' + action + '"');
  }
}

/** Returns the folder ID for "A/B/C" under NEW_ROOT_ID, creating missing levels. */
function ensurePath_(path) {
  let parent = REORG.NEW_ROOT_ID;
  let soFar = '';
  path.split('/').map((p) => p.trim()).filter(String).forEach((part) => {
    soFar += '/' + part;
    if (_folderCache[soFar]) { parent = _folderCache[soFar]; return; }
    let id = parent.startsWith('DRY:') ? null : findChild_(parent, part, true);
    if (!id) {
      if (REORG.DRY_RUN) {
        id = 'DRY:' + soFar;
        _dryCreated++;
      } else {
        id = Drive.Files.create({ name: part, mimeType: FOLDER, parents: [parent] }, null,
          { supportsAllDrives: true }).id;
      }
    }
    _folderCache[soFar] = id;
    parent = id;
  });
  return parent;
}

/** ID of a child with this exact (trimmed) name, or null. */
function findChild_(parentId, name, foldersOnly) {
  if (String(parentId).startsWith('DRY:')) return null;
  const want = name.trim();
  const hit = listChildren_(parentId).filter((c) =>
    c.name.trim() === want && (!foldersOnly || c.mimeType === FOLDER))[0];
  return hit ? hit.id : null;
}

function listChildren_(parentId) {
  if (String(parentId).startsWith('DRY:')) return [];
  const out = [];
  let pageToken;
  do {
    const res = Drive.Files.list({
      q: "'" + parentId + "' in parents and trashed = false",
      pageSize: 1000, pageToken: pageToken,
      includeItemsFromAllDrives: true, supportsAllDrives: true, corpora: 'allDrives',
      fields: 'nextPageToken, files(id, name, mimeType)',
    });
    (res.files || []).forEach((f) => out.push(f));
    pageToken = res.nextPageToken;
  } while (pageToken);
  return out;
}

function getFile_(id) {
  return Drive.Files.get(id, { supportsAllDrives: true, fields: 'id, name, parents, mimeType' });
}

function requireVal_(v, label) {
  if (!v) throw new Error(label + ' is required for this action');
}
